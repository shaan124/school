# fixed_app.py

from flask import Flask, render_template, request, redirect, session, send_file
import os
from datetime import datetime
import json
from functools import wraps
import pandas as pd
from io import BytesIO
from xhtml2pdf import pisa
import sqlite3
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Local SQLite database file
DATABASE = 'school_management.db'

# ---- DATABASE UTILITIES ----
@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        # Students table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                dob TEXT NOT NULL,
                class TEXT NOT NULL,
                division TEXT NOT NULL
            )
        ''')
        
        # Teachers table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                teacher_id TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                name TEXT NOT NULL
            )
        ''')
        
        # Results table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                marks INTEGER NOT NULL,
                max_marks INTEGER NOT NULL,
                teacher_id TEXT NOT NULL,
                date TEXT NOT NULL,
                test_name TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (teacher_id) REFERENCES teachers (teacher_id)
            )
        ''')
        
        # Tests table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tests (
                test_id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                name TEXT NOT NULL,
                max_marks INTEGER NOT NULL,
                date TEXT NOT NULL,
                class TEXT NOT NULL,
                division TEXT NOT NULL
            )
        ''')
        
        # Admin credentials table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS admin_credentials (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL
            )
        ''')
        
        # Insert default admin if not exists
        conn.execute('''
            INSERT OR IGNORE INTO admin_credentials (username, password)
            VALUES ('admin', 'admin')
        ''')
        
        conn.commit()

# Initialize database
init_db()

# ---- DATABASE OPERATIONS ----
def get_student(student_id):
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        return cursor.fetchone()

def get_all_students():
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM students')
        return cursor.fetchall()

def get_students_by_class(class_name, division):
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM students WHERE class = ? AND division = ?', 
                             (class_name, division))
        return cursor.fetchall()

def add_student(student_id, password, name, dob, class_name, division):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO students (student_id, password, name, dob, class, division)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, password, name, dob, class_name, division))
        conn.commit()

def get_teacher(teacher_id):
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM teachers WHERE teacher_id = ?', (teacher_id,))
        return cursor.fetchone()

def get_all_teachers():
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM teachers')
        return cursor.fetchall()

def add_teacher(teacher_id, password, name):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO teachers (teacher_id, password, name)
            VALUES (?, ?, ?)
        ''', (teacher_id, password, name))
        conn.commit()

def verify_admin(username, password):
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM admin_credentials WHERE username = ? AND password = ?', 
                             (username, password))
        return cursor.fetchone() is not None

def add_test(test_id, subject, name, max_marks, date, class_name, division):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO tests (test_id, subject, name, max_marks, date, class, division)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (test_id, subject, name, max_marks, date, class_name, division))
        conn.commit()

def get_all_tests():
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM tests')
        return cursor.fetchall()

def add_result(student_id, subject, marks, max_marks, teacher_id, date, test_name):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO results (student_id, subject, marks, max_marks, teacher_id, date, test_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, subject, marks, max_marks, teacher_id, date, test_name))
        conn.commit()

def get_student_results(student_id):
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT r.*, s.name as student_name, t.name as teacher_name
            FROM results r
            JOIN students s ON r.student_id = s.student_id
            JOIN teachers t ON r.teacher_id = t.teacher_id
            WHERE r.student_id = ?
            ORDER BY r.date
        ''', (student_id,))
        return cursor.fetchall()

def get_student_total_performance(student_id):
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT 
                SUM(marks) as total_marks,
                SUM(max_marks) as total_max_marks,
                (SUM(marks) * 100.0 / SUM(max_marks)) as percentage
            FROM results 
            WHERE student_id = ?
        ''', (student_id,))
        return cursor.fetchone()

# ---- LOGIN CHECK DECORATOR ----
def student_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'student' or not session.get('student_id'):
            return redirect('/student_login')
        return f(*args, **kwargs)
    return wrapper

def teacher_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'teacher' or not session.get('teacher_id'):
            return redirect('/teacher_login')
        return f(*args, **kwargs)
    return wrapper

def admin_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect('/admin_login')
        return f(*args, **kwargs)
    return wrapper

# ---- ROUTES ----
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        if verify_admin(username, password):
            session['role'] = 'admin'
            session['username'] = username
            return redirect('/admin_dashboard')
        return 'Invalid admin credentials.'
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
@admin_login_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/manage_students')
@admin_login_required
def manage_students():
    class_filter = request.args.get('class')
    division_filter = request.args.get('division')

    if class_filter and division_filter:
        students = get_students_by_class(class_filter, division_filter)
    else:
        students = get_all_students()

    filtered = []
    for student in students:
        try:
            age = (datetime.now() - datetime.strptime(student['dob'], "%Y-%m-%d")).days // 365
        except:
            age = "N/A"
        filtered.append({
            'id': student['student_id'],
            'name': student['name'],
            'dob': student['dob'],
            'class': student['class'],
            'division': student['division'],
            'age': age
        })
    return render_template('manage_students.html', students=filtered)

@app.route('/manage_teachers')
@admin_login_required
def manage_teachers():
    teachers = get_all_teachers()
    return render_template('manage_teachers.html', teachers=teachers)

@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        sid = request.form['student_id']
        password = request.form['password']
        name = request.form['name']
        dob = request.form['dob']
        class_name = request.form['class_name']
        division = request.form['division']

        if get_student(sid):
            return 'Student ID already registered.'

        add_student(sid, password, name, dob, class_name, division)
        return redirect('/student_login')
    return render_template('student_register.html')

@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        sid = request.form['student_id']
        password = request.form['password']
        student = get_student(sid)
        if student and student['password'] == password:
            session['role'] = 'student'
            session['username'] = student['name']
            session['student_id'] = sid
            return redirect('/result_view')
        return 'Invalid credentials.'
    return render_template('student_login.html')

@app.route('/result_view')
@student_login_required
def student_results():
    sid = session['student_id']
    student = get_student(sid)
    if not student:
        return "Student not found."

    results = get_student_results(sid)
    total_performance = get_student_total_performance(sid)
    
    trend_data = []
    total_max = 0
    total_obtained = 0

    dob = datetime.strptime(student['dob'], "%Y-%m-%d")
    age = (datetime.now() - dob).days // 365

    formatted_results = []
    for result in results:
        marks = result['marks']
        max_marks = result['max_marks']
        percentage = float(str(marks * 100 / max_marks).replace('%', '').replace('%%', ''))
        grade = "A+" if percentage >= 90 else "A" if percentage >= 75 else "B" if percentage >= 60 else "C" if percentage >= 50 else "D"
        color = "green" if percentage >= 90 else "blue" if percentage >= 75 else "orange" if percentage >= 60 else "darkorange" if percentage >= 50 else "red"

        formatted_results.append({
            'subject': result['subject'],
            'marks': marks,
            'max_marks': max_marks,
            'teacher_name': result['teacher_name'],
            'date': result['date'],
            'test_name': result['test_name'],
            'grade': grade,
            'color': color
        })

        total_obtained += marks
        total_max += max_marks

    overall = round(total_obtained / total_max * 100, 2) if total_max > 0 else 0
    overall_grade = "A+" if overall >= 90 else "A" if overall >= 75 else "B" if overall >= 60 else "C" if overall >= 50 else "D"

    return render_template('result_view.html',
                           student_name=student['name'],
                           student_id=sid,
                           student_dob=student['dob'],
                           student_age=age,
                           results=formatted_results,
                           performance_data=json.dumps({
                               'subjects': [r['subject'] for r in formatted_results],
                               'marks': [r['marks'] for r in formatted_results],
                               'max_marks': [r['max_marks'] for r in formatted_results]
                           }),
                           trend_data=json.dumps(trend_data),
                           overall_performance=overall,
                           grade=overall_grade)

@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        tid = request.form.get('teacher_id')
        pw = request.form.get('password')
        teacher = get_teacher(tid)
        if teacher and teacher['password'] == pw:
            session['role'] = 'teacher'
            session['username'] = teacher['name']
            session['teacher_id'] = tid
            return redirect('/teacher_dashboard')
        return 'Invalid credentials.'
    return render_template('teacher_login.html')

@app.route('/teacher_register', methods=['GET', 'POST'])
def teacher_register():
    if request.method == 'POST':
        tid = request.form.get('teacher_id')
        pw = request.form.get('password')
        name = request.form.get('name', tid)
        if not tid or not pw:
            return "Missing fields"
        if get_teacher(tid):
            return "Teacher ID exists"
        add_teacher(tid, pw, name)
        return redirect('/teacher_login')
    return render_template('teacher_register.html')

@app.route('/teacher_dashboard')
@teacher_login_required
def teacher_dashboard():
    return render_template('teacher_dashboard.html')

@app.route('/upload_result', methods=['GET', 'POST'])
@teacher_login_required
def upload_result():
    test_options = get_all_tests()
    students = get_all_students()

    if request.method == 'POST':
        test_id = request.form['test_id']
        sid = request.form['student_id']
        marks = int(request.form['marks'])

        # Get test data
        with get_db() as conn:
            cursor = conn.execute('SELECT * FROM tests WHERE test_id = ?', (test_id,))
            selected_test = cursor.fetchone()

        if not selected_test:
            return "Invalid test selected."

        maxm = int(selected_test['max_marks'])
        
        # Add result to database
        add_result(sid, selected_test['subject'], marks, maxm, 
                  session['teacher_id'], selected_test['date'], selected_test['name'])

        return redirect('/upload_result')

    return render_template('upload_result.html', tests=test_options, students=students)

@app.route('/create_test', methods=['GET', 'POST'])
@teacher_login_required
def create_test():
    if request.method == 'POST':
        test_id = request.form['test_id']
        subject = request.form['subject']
        name = request.form['name']
        max_marks = int(request.form['max_marks'])
        date = request.form['date']
        class_name = request.form['class_name']
        division = request.form['division']

        add_test(test_id, subject, name, max_marks, date, class_name, division)
        return redirect('/upload_result')
    
    return render_template('create_test.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    # Create database directory if it doesn't exist
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    app.run(host='0.0.0.0', port=8080, debug=True)

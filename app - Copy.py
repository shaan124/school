# fixed_app.py

from flask import Flask, render_template, request, redirect, session, send_file
import os
from datetime import datetime
import json
from functools import wraps
import pandas as pd
from io import BytesIO
from xhtml2pdf import pisa

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Global data
students_db = {}
teachers_db = {}
admin_credentials = {'admin': 'admin'}

students_file = 'students.txt'
teachers_file = 'teachers.txt'


# ---- LOAD DATA ----
def load_students():
    if os.path.exists(students_file):
        with open(students_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 6:
                    student_id, password, name, dob, class_name, division = parts
                    students_db[student_id] = {
                        'password': password,
                        'name': name,
                        'dob': dob,
                        'class': class_name,
                        'division': division
                    }

def load_teachers():
    if os.path.exists(teachers_file):
        with open(teachers_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                if len(parts) == 2:
                    teacher_id, password = parts
                    teachers_db[teacher_id] = {'password': password, 'name': teacher_id}

def save_students():
    with open(students_file, 'w') as f:
        for sid, data in students_db.items():
            f.write(f"{sid},{data['password']},{data['name']},{data['dob']},{data['class']},{data['division']}\n")

def save_teachers():
    with open(teachers_file, 'w') as f:
        for tid, data in teachers_db.items():
            f.write(f"{tid},{data['password']}\n")

# Load initial data
load_students()
load_teachers()

# ---- LOGIN CHECK DECORATOR ----
def student_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'student' or not session.get('student_id'):
            return redirect('/student_login')
        return f(*args, **kwargs)
    return wrapper

# ---- ROUTES ----
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/boom')
def boom():
    1 / 0  # Force a crash

@app.route('/app')
def app_page():
    return render_template('app.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        if admin_credentials.get(username) == password:
            session['role'] = 'admin'
            session['username'] = username
            return redirect('/admin_dashboard')
        return 'Invalid admin credentials.'
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect('/')
    return render_template('admin_dashboard.html')

@app.route('/manage_students')
def manage_students():
    if session.get('role') != 'admin':
        return redirect('/admin_login')

    class_filter = request.args.get('class')
    division_filter = request.args.get('division')

    filtered = []
    for sid, data in students_db.items():
        if class_filter and data.get('class') != class_filter:
            continue
        if division_filter and data.get('division') != division_filter:
            continue
        try:
            age = (datetime.now() - datetime.strptime(data['dob'], "%Y-%m-%d")).days // 365
        except:
            age = "N/A"
        filtered.append({
            'id': sid,
            'name': data['name'],
            'dob': data['dob'],
            'class': data['class'],
            'division': data['division'],
            'age': age
        })
    return render_template('manage_students.html', students=filtered)

@app.route('/manage_teachers')
def manage_teachers():
    if session.get('role') != 'admin':
        return redirect('/admin_login')
    return render_template('manage_teachers.html', teachers=teachers_db)

@app.route('/manage_results')
def manage_results():
    if session.get('role') != 'admin':
        return redirect('/admin_login')
    results = []
    if os.path.exists(results_file):
        with open(results_file, 'r') as f:
            for line in f:
                results.append(line.strip().split(','))
    return render_template('manage_results.html', results=results)

@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        sid = request.form['student_id']
        password = request.form['password']
        name = request.form['name']
        dob = request.form['dob']
        class_name = request.form['class_name']
        division = request.form['division']

        if sid in students_db:
            return 'Student ID already registered.'

        students_db[sid] = {
            'password': password,
            'name': name,
            'dob': dob,
            'class': class_name,
            'division': division
        }
        save_students()
        return redirect('/student_login')
    return render_template('student_register.html')

@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        sid = request.form['student_id']
        password = request.form['password']
        student = students_db.get(sid)
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
    student = students_db.get(sid)
    if not student:
        return "Student not found."

    results = []
    trend_data = []
    total_max = 0
    total_obtained = 0

    year = str(datetime.now().year)
    class_name = student['class']
    division = student['division']
    file_path = f"results_data/{year}/Class_{class_name}_{division}.xlsx"

    if not os.path.exists(file_path):
        return "No result data available yet."

    dob = datetime.strptime(student['dob'], "%Y-%m-%d")
    age = (datetime.now() - dob).days // 365

    df = pd.read_excel(file_path)
    df['Student ID'] = df['Student ID'].astype(str)  # 🔥 THIS FIXES THE MATCHING
    student_rows = df[df['Student ID'] == sid]

    for _, row in student_rows.iterrows():
        subject = row['Subject']
        if isinstance(subject, str) and subject.startswith("→ Total"):
            trend_data.append({
                'date': row.get('Date', ''),
                'percent': float(str(row['%']).replace('%', ''))
            })
        elif pd.notna(subject) and "Total" not in str(subject):
            marks = row['Marks']
            max_marks = row['Max Marks']
            percentage = float(str(row['%']).replace('%', '').replace('%%', ''))
            grade = row['Grade']
            teacher = row['Teacher']
            date = row['Date']

            color = "green" if percentage >= 90 else "blue" if percentage >= 75 else "orange" if percentage >= 60 else "darkorange" if percentage >= 50 else "red"

            results.append({
                'subject': subject,
                'marks': marks,
                'max_marks': max_marks,
                'teacher_name': teacher,
                'date': date,
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
                           results=results,
                           performance_data=json.dumps({
                               'subjects': [r['subject'] for r in results],
                               'marks': [r['marks'] for r in results],
                               'max_marks': [r['max_marks'] for r in results]
                           }),
                           trend_data=json.dumps(trend_data),
                           overall_performance=overall,
                           grade=overall_grade)





@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        tid = request.form.get('teacher_id')
        pw = request.form.get('password')
        t = teachers_db.get(tid)
        if t and t['password'] == pw:
            session['role'] = 'teacher'
            session['username'] = t['name']
            session['teacher_id'] = tid
            return redirect('/upload_result')
        return 'Invalid credentials.'
    return render_template('teacher_login.html')

@app.route('/teacher_register', methods=['GET', 'POST'])
def teacher_register():
    if request.method == 'POST':
        tid = request.form.get('teacher_id')
        pw = request.form.get('password')
        if not tid or not pw:
            return "Missing fields"
        if tid in teachers_db:
            return "Teacher ID exists"
        teachers_db[tid] = {'password': pw, 'name': tid}
        save_teachers()
        return redirect('/teacher_login')
    return render_template('teacher_register.html')



@app.route('/upload_result', methods=['GET', 'POST'])
def upload_result():
    if session.get('role') != 'teacher':
        return redirect('/teacher_login')

    test_list_file = 'test_list.txt'
    test_options = []

    # Load test list
    if os.path.exists(test_list_file):
        with open(test_list_file, 'r') as f:
            for line in f:
                tid, subject, name, maxm, date, cls, div = line.strip().split(',')
                test_options.append({
                    'id': tid,
                    'subject': subject,
                    'name': name,
                    'max_marks': maxm,
                    'date': date,
                    'class': cls,
                    'division': div
                })

    if request.method == 'POST':
        test_id = request.form['test_id']
        sid = request.form['student_id']
        marks = int(request.form['marks'])

        # Get test data
        selected_test = None
        for test in test_options:
            if test['id'] == test_id:
                selected_test = test
                break

        if not selected_test:
            return "Invalid test selected."

        file_path = f"results_data/{datetime.now().year}/Class_{selected_test['class']}_{selected_test['division']}.xlsx"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        maxm = int(selected_test['max_marks'])
        percent = round((marks / maxm) * 100, 2)
        grade = 'A+' if percent >= 90 else 'A' if percent >= 75 else 'B' if percent >= 60 else 'C' if percent >= 50 else 'D'

        new_row = {
            'Student ID': sid,
            'Name': students_db[sid]['name'],
            'Class': selected_test['class'],
            'Subject': f"{selected_test['subject']} ({selected_test['name']})",
            'Marks': marks,
            'Max Marks': maxm,
            '%': f"{percent}%",
            'Grade': grade,
            'Teacher': session['username'],
            'Date': selected_test['date']
        }

        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            df['Student ID'] = df['Student ID'].astype(str)

            # Remove old total row
            df = df[~((df['Student ID'] == sid) & (df['Subject'] == "→ Total"))]

            # Add new row
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

            student_rows = df[df['Student ID'] == sid]
            relevant = student_rows[~student_rows['Subject'].astype(str).str.startswith("→ Total")]
            total_marks = relevant['Marks'].sum()
            total_max = relevant['Max Marks'].sum()
            total_percent = round((total_marks / total_max) * 100, 2) if total_max > 0 else 0
            total_grade = 'A+' if total_percent >= 90 else 'A' if total_percent >= 75 else 'B' if total_percent >= 60 else 'C' if total_percent >= 50 else 'D'

            total_row = {
                'Student ID': sid,
                'Name': students_db[sid]['name'],
                'Class': selected_test['class'],
                'Subject': "→ Total",
                'Marks': total_marks,
                'Max Marks': total_max,
                '%': f"{total_percent}%",
                'Grade': total_grade,
                'Teacher': '',
                'Date': selected_test['date']
            }

            df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
            df.to_excel(file_path, index=False)
        else:
            total_row = {
                'Student ID': sid,
                'Name': students_db[sid]['name'],
                'Class': selected_test['class'],
                'Subject': "→ Total",
                'Marks': marks,
                'Max Marks': maxm,
                '%': f"{percent}%",
                'Grade': grade,
                'Teacher': '',
                'Date': selected_test['date']
            }
            df = pd.DataFrame([new_row, total_row])
            df.to_excel(file_path, index=False)

        return redirect('/upload_result')

    return render_template('upload_result.html', tests=test_options, students=students_db)




@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/download_excel')
def download_excel():
    if not os.path.exists(results_file):
        return "No results found."

    data = []
    with open(results_file, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) == 6:
                sid, subject, marks, max_marks, teacher, date = parts
                marks = int(marks)
                max_marks = int(max_marks)
                percent = marks / max_marks * 100
                grade = "A+" if percent >= 90 else "A" if percent >= 75 else "B" if percent >= 60 else "C" if percent >= 50 else "D"
                data.append({
                    "Student ID": sid,
                    "Subject": subject,
                    "Marks Obtained": marks,
                    "Max Marks": max_marks,
                    "Grade": grade,
                    "Teacher": teacher,
                    "Date": date
                })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Results')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='student_results.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/download_pdf')
def download_pdf():
    results = []
    if not os.path.exists(results_file):
        return "No result data found."

    with open(results_file, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) == 6:
                results.append(parts)

    rendered = render_template("pdf_template.html", results=results)
    pdf = BytesIO()
    pisa_status = pisa.CreatePDF(rendered, dest=pdf)
    if pisa_status.err:
        return "Error generating PDF"
    pdf.seek(0)
    return send_file(pdf, as_attachment=True, download_name="student_results.pdf", mimetype='application/pdf')





if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)


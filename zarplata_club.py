from flask import Flask, render_template_string, request, redirect, url_for, session
import sqlite3
from datetime import date, datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'zarplata_club_secret_2024'
app.permanent_session_lifetime = timedelta(days=30)

# === БАЗА ДАННЫХ ===
def get_db():
    db_path = os.path.join(os.path.dirname(__file__), 'zarplata_club.db')
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    
    cur.execute('''CREATE TABLE IF NOT EXISTS employees 
                   (id INTEGER PRIMARY KEY, name TEXT UNIQUE, password TEXT, is_admin INTEGER DEFAULT 0)''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS hours_log 
                   (id INTEGER PRIMARY KEY, employee_id INTEGER, work_date TEXT, 
                    hours REAL, rate REAL DEFAULT 400, konserzhka INTEGER DEFAULT 0,
                    FOREIGN KEY(employee_id) REFERENCES employees(id))''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS fixed_payments 
                   (id INTEGER PRIMARY KEY, employee_id INTEGER, payment_date TEXT,
                    amount REAL, description TEXT,
                    FOREIGN KEY(employee_id) REFERENCES employees(id))''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS events 
                   (id INTEGER PRIMARY KEY, event_date TEXT, title TEXT, description TEXT)''')
    
    conn.commit()
    return conn

# === СОЗДАЁМ БАЗУ ПРИ ЗАПУСКЕ ===
with app.app_context():
    get_db()

def format_date_ru(date_str):
    months_gen = {
        '01': 'января', '02': 'февраля', '03': 'марта',
        '04': 'апреля', '05': 'мая', '06': 'июня',
        '07': 'июля', '08': 'августа', '09': 'сентября',
        '10': 'октября', '11': 'ноября', '12': 'декабря'
    }
    try:
        year, month, day = date_str.split('-')
        return f"{int(day)} {months_gen.get(month, month)}"
    except:
        return date_str

# === HTML ШАБЛОНЫ ===
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏢 ЗАРПЛАТА КЛУБ</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #0a0a1a; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: #fff; border-radius: 30px; padding: 30px; }
        h1 { text-align: center; color: #9d4edd; }
        .card { background: #f8f6ff; border-radius: 16px; padding: 20px; margin-bottom: 20px; border-left: 4px solid #9d4edd; }
        .card h3 { margin-bottom: 12px; }
        .form-group { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
        input, select { padding: 10px; border: 2px solid #e0ddf0; border-radius: 10px; flex: 1; min-width: 120px; }
        .btn { padding: 10px 20px; border: none; border-radius: 10px; background: #9d4edd; color: white; cursor: pointer; font-weight: bold; }
        .btn:hover { opacity: 0.8; }
        .btn-green { background: #6bcb77; }
        .btn-red { background: #ff6b6b; }
        .btn-gold { background: #ffd93d; color: #333; }
        table { width: 100%; border-collapse: collapse; }
        th { background: #9d4edd; color: white; padding: 10px; text-align: left; }
        td { padding: 10px; border-bottom: 1px solid #eee; }
        .badge { background: #e8d5f5; color: #6c3483; padding: 3px 12px; border-radius: 20px; font-size: 12px; }
        .badge-gold { background: #fff3cd; color: #856404; }
        .alert { padding: 15px; border-radius: 10px; margin: 10px 0; background: #d4edda; color: #155724; border-left: 5px solid #28a745; }
        .hidden { display: none; }
        .tab { display: inline-block; padding: 10px 20px; background: #f0edff; border-radius: 20px; cursor: pointer; margin-right: 5px; font-weight: bold; }
        .tab.active { background: #9d4edd; color: white; }
        .logout { float: right; background: #ff6b6b; padding: 8px 16px; border-radius: 12px; color: white; text-decoration: none; font-weight: bold; }
        @media (max-width: 700px) { .container { padding: 15px; } input, select { width: 100%; } }
    </style>
</head>
<body>
<div class="container">
    <h1>🏢 ЗАРПЛАТА КЛУБ</h1>
    <p style="text-align:center;color:#888;">Ставка 400 или 350 ₽/ч · Консержка +1500 ₽</p>

    {% if session.get('user_id') is none %}
    <div class="card">
        <h3>🔐 Вход</h3>
        <form method="POST" action="/login" class="form-group">
            <input type="text" name="name" placeholder="Имя" required>
            <input type="password" name="password" placeholder="Пароль" required>
            <button type="submit" class="btn">🚪 Войти</button>
        </form>
        {% if msg %}<div class="alert">{{ msg }}</div>{% endif %}
    </div>
    {% else %}

    <div style="overflow:hidden;margin-bottom:15px;">
        <span style="font-weight:bold;">👋 {{ session.user_name }} 
        {% if session.is_admin %}👑 Админ{% endif %}</span>
        <a href="/logout" class="logout">Выйти</a>
    </div>

    {% if session.is_admin %}
    <!-- АДМИН: КРАТКИЙ ИНТЕРФЕЙС -->
    <div class="card">
        <h3>👤 Новый сотрудник</h3>
        <form method="POST" action="/add_employee" class="form-group">
            <input type="text" name="name" placeholder="Имя" required>
            <input type="password" name="password" placeholder="Пароль" required>
            <button type="submit" class="btn btn-green">➕ Добавить</button>
        </form>
    </div>

    <div class="card">
        <h3>👥 Сотрудники</h3>
        {% if employees %}
        <table>
            <tr><th>Имя</th><th>Часов</th><th>Консержек</th><th>Сумма</th><th>Действия</th></tr>
            {% for emp in employees %}
            <tr>
                <td><span class="badge">{{ emp.name }}</span></td>
                <td>{{ emp.month_hours|round(1) }}</td>
                <td>{{ emp.month_konserzhka }}</td>
                <td>{{ emp.month_total|round(0) }} ₽</td>
                <td>
                    <form method="POST" action="/delete_employee" style="display:inline;" onsubmit="return confirm('Удалить?')">
                        <input type="hidden" name="emp_id" value="{{ emp.id }}">
                        <button type="submit" class="btn btn-red" style="padding:5px 10px;font-size:12px;">🗑️</button>
                    </form>
                    <form method="POST" action="/make_admin" style="display:inline;">
                        <input type="hidden" name="emp_id" value="{{ emp.id }}">
                        <button type="submit" class="btn btn-gold" style="padding:5px 10px;font-size:12px;">👑</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <p>Нет сотрудников</p>
        {% endif %}
    </div>

    <div class="card">
        <h3>⏱ Добавить часы</h3>
        <form method="POST" action="/add_hours" class="form-group">
            <select name="emp_id" required>
                <option value="">Выберите сотрудника</option>
                {% for emp in employees %}
                <option value="{{ emp.id }}">{{ emp.name }}</option>
                {% endfor %}
            </select>
            <input type="number" name="hours" placeholder="Часы" step="0.5" required>
            <input type="date" name="work_date" value="{{ today }}">
            <select name="rate">
                <option value="400">400 ₽/ч</option>
                <option value="350">350 ₽/ч</option>
            </select>
            <label><input type="checkbox" name="konserzhka" value="1"> 🥫 Консержка</label>
            <button type="submit" class="btn">⏱ Добавить</button>
        </form>
    </div>

    <div class="card">
        <h3>🎁 Премия</h3>
        <form method="POST" action="/add_bonus" class="form-group">
            <select name="emp_id" required>
                <option value="">Выберите сотрудника</option>
                {% for emp in employees %}
                <option value="{{ emp.id }}">{{ emp.name }}</option>
                {% endfor %}
            </select>
            <input type="number" name="amount" placeholder="Сумма ₽" step="0.1" required>
            <input type="text" name="description" placeholder="Описание">
            <input type="date" name="payment_date" value="{{ today }}">
            <button type="submit" class="btn btn-gold">🎁 Добавить</button>
        </form>
    </div>

    <div class="card">
        <h3>📅 Мероприятия</h3>
        <form method="POST" action="/add_event" class="form-group">
            <input type="date" name="event_date" value="{{ today }}" required>
            <input type="text" name="title" placeholder="Название" required>
            <input type="text" name="description" placeholder="Описание">
            <button type="submit" class="btn btn-green">➕ Добавить</button>
        </form>
        {% if events %}
        <ul>
            {% for event in events %}
            <li><strong>{{ event.date_ru }}</strong> — {{ event.title }} 
                <form method="POST" action="/delete_event" style="display:inline;">
                    <input type="hidden" name="event_id" value="{{ event.id }}">
                    <button type="submit" class="btn btn-red" style="padding:2px 8px;font-size:12px;">🗑️</button>
                </form>
            </li>
            {% endfor %}
        </ul>
        {% endif %}
    </div>

    {% else %}
    <!-- СОТРУДНИК -->
    <div class="card">
        <h3>📊 Моя статистика</h3>
        <p>⏱ Часов: {{ stats.total_hours|round(1) if stats else 0 }}</p>
        <p>💰 Зарплата: {{ stats.total_salary|round(0) if stats else 0 }} ₽</p>
        <p>🥫 Консержек: {{ stats.total_konserzhka if stats else 0 }}</p>
        <p>💎 ИТОГО: {{ stats.grand_total|round(0) if stats else 0 }} ₽</p>
    </div>
    <div class="card">
        <h3>📅 Мои часы</h3>
        {% if my_logs %}
        <table>
            <tr><th>Дата</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
            {% for log in my_logs %}
            <tr>
                <td>{{ log.date_ru }}</td>
                <td>{{ log.hours }}</td>
                <td>{{ log.rate }} ₽/ч</td>
                <td>{% if log.konserzhka %}🥫{% else %}—{% endif %}</td>
                <td>{{ log.total }} ₽</td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <p>Нет записей</p>
        {% endif %}
    </div>
    {% endif %}

    {% if msg %}<div class="alert">{{ msg }}</div>{% endif %}
    {% endif %}
</div>

<script>
function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
    document.getElementById('tab-' + tab).classList.remove('hidden');
    document.querySelector(`.tab[onclick*="${tab}"]`).classList.add('active');
}
</script>
</body>
</html>
'''

EMPLOYEE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ employee.name }} — Зарплата Клуб</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #0a0a1a; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: #fff; border-radius: 30px; padding: 30px; }
        h1 { color: #9d4edd; }
        .card { background: #f8f6ff; border-radius: 16px; padding: 20px; margin-bottom: 20px; border-left: 4px solid #9d4edd; }
        .back { color: #9d4edd; text-decoration: none; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; }
        th { background: #9d4edd; color: white; padding: 10px; text-align: left; }
        td { padding: 10px; border-bottom: 1px solid #eee; }
        .badge { background: #e8d5f5; color: #6c3483; padding: 3px 12px; border-radius: 20px; }
    </style>
</head>
<body>
<div class="container">
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <h1>👤 {{ employee.name }}</h1>
        <a href="/" class="back">← Назад</a>
    </div>

    <div class="card">
        <p>⏱ Часов: {{ total_hours|round(1) }}</p>
        <p>💰 Зарплата: {{ total_salary|round(0) }} ₽</p>
        <p>🥫 Консержек: {{ total_konserzhka }}</p>
        <p>🎁 Премии: {{ total_bonus|round(0) }} ₽</p>
        <p>💎 ИТОГО: {{ grand_total|round(0) }} ₽</p>
    </div>

    <div class="card">
        <h3>📅 Детали по дням</h3>
        {% if logs %}
        <table>
            <tr><th>Дата</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
            {% for log in logs %}
            <tr>
                <td>{{ log.date_ru }}</td>
                <td>{{ log.hours }}</td>
                <td>{{ log.rate }} ₽/ч</td>
                <td>{% if log.konserzhka %}🥫{% else %}—{% endif %}</td>
                <td>{{ log.total }} ₽</td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <p>Нет записей</p>
        {% endif %}
    </div>
</div>
</body>
</html>
'''

# === МАРШРУТЫ ===
@app.route('/')
def index():
    if session.get('user_id') is None:
        return render_template_string(HTML, session={}, employees=[], all_logs=[], all_bonuses=[], my_logs=[], stats={}, payments={'first': [], 'second': [], 'first_total': 0, 'second_total': 0}, events=[], today=date.today().strftime('%Y-%m-%d'), selected_month=date.today().strftime('%Y-%m'), msg=request.args.get('msg'))
    
    conn = get_db()
    today = date.today()
    month = request.args.get('month', today.strftime('%Y-%m'))
    today_str = today.strftime('%Y-%m-%d')
    
    employees = []
    all_logs = []
    all_bonuses = []
    my_logs = []
    stats = {}
    payments = {'first': [], 'second': [], 'first_total': 0, 'second_total': 0}
    
    events_raw = conn.execute("SELECT id, event_date, title, description FROM events ORDER BY event_date DESC").fetchall()
    events = []
    for ev in events_raw:
        events.append({
            'id': ev[0],
            'date': ev[1],
            'date_ru': format_date_ru(ev[1]),
            'title': ev[2],
            'description': ev[3]
        })
    
    if session.get('is_admin'):
        employees_raw = conn.execute("SELECT id, name FROM employees").fetchall()
        for emp in employees_raw:
            rows_month = conn.execute("SELECT hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ?", (emp[0], month + "%")).fetchall()
            month_hours = sum(r[0] for r in rows_month)
            month_salary = sum(r[0] * r[1] for r in rows_month)
            month_konserzhka = sum(1500 for r in rows_month if r[2] == 1)
            bonus_month = conn.execute("SELECT amount FROM fixed_payments WHERE employee_id=? AND payment_date LIKE ?", (emp[0], month + "%")).fetchall()
            month_bonus = sum(b[0] for b in bonus_month)
            employees.append({
                'id': emp[0],
                'name': emp[1],
                'month_hours': month_hours,
                'month_salary': month_salary,
                'month_konserzhka': month_konserzhka,
                'month_bonus': month_bonus,
                'month_total': month_salary + month_konserzhka + month_bonus
            })
        
        logs = conn.execute("SELECT h.work_date, e.name, h.hours, h.rate, h.konserzhka FROM hours_log h JOIN employees e ON h.employee_id=e.id WHERE h.work_date LIKE ? ORDER BY h.work_date DESC", (month + "%",)).fetchall()
        for log in logs:
            total = log[2] * log[3] + (1500 if log[4] == 1 else 0)
            all_logs.append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'employee': log[1], 'hours': log[2], 'rate': log[3], 'konserzhka': log[4], 'total': total})
            day = log[0].split('-')[2]
            period = 'first' if int(day) <= 15 else 'second'
            payments[period].append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'employee': log[1], 'hours': log[2], 'rate': log[3], 'konserzhka': log[4], 'total': total})
            payments[period + '_total'] = payments.get(period + '_total', 0) + total
        
        bonuses = conn.execute("SELECT f.payment_date, e.name, f.amount, f.description FROM fixed_payments f JOIN employees e ON f.employee_id=e.id ORDER BY f.payment_date DESC").fetchall()
        for bonus in bonuses:
            all_bonuses.append({'date': bonus[0], 'date_ru': format_date_ru(bonus[0]), 'employee': bonus[1], 'amount': bonus[2], 'description': bonus[3]})
        stats = {}
    else:
        emp_id = session['user_id']
        logs = conn.execute("SELECT work_date, hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date DESC", (emp_id, month + "%")).fetchall()
        total_salary = 0
        total_konserzhka = 0
        for log in logs:
            total = log[1] * log[2] + (1500 if log[3] == 1 else 0)
            total_salary += log[1] * log[2]
            total_konserzhka += 1500 if log[3] == 1 else 0
            my_logs.append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'hours': log[1], 'rate': log[2], 'konserzhka': log[3], 'total': total})
        bonuses = conn.execute("SELECT amount FROM fixed_payments WHERE employee_id=? AND payment_date LIKE ?", (emp_id, month + "%")).fetchall()
        total_bonus = sum(b[0] for b in bonuses)
        stats = {
            'total_hours': sum(l['hours'] for l in my_logs),
            'total_salary': total_salary,
            'total_konserzhka': total_konserzhka,
            'grand_total': total_salary + total_konserzhka + total_bonus
        }
    
    conn.close()
    return render_template_string(HTML, session=session, employees=employees, all_logs=all_logs[:200], all_bonuses=all_bonuses[:200], my_logs=my_logs, stats=stats, payments=payments, events=events, today=today_str, selected_month=month, msg=request.args.get('msg'))

@app.route('/employee/<int:emp_id>')
def employee_detail(emp_id):
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='Войдите в систему!'))
    conn = get_db()
    if not session.get('is_admin') and session['user_id'] != emp_id:
        conn.close()
        return redirect(url_for('index', msg='Нет доступа!'))
    employee = conn.execute("SELECT id, name FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not employee:
        conn.close()
        return redirect(url_for('index', msg='Сотрудник не найден!'))
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    logs_raw = conn.execute("SELECT work_date, hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date DESC", (emp_id, month + "%")).fetchall()
    logs = []
    total_salary = 0
    total_konserzhka = 0
    for log in logs_raw:
        total = log[1] * log[2] + (1500 if log[3] == 1 else 0)
        total_salary += log[1] * log[2]
        total_konserzhka += 1500 if log[3] == 1 else 0
        logs.append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'hours': log[1], 'rate': log[2], 'konserzhka': log[3], 'total': total})
    bonuses_raw = conn.execute("SELECT payment_date, amount, description FROM fixed_payments WHERE employee_id=? ORDER BY payment_date DESC", (emp_id,)).fetchall()
    bonuses = []
    total_bonus = 0
    for bonus in bonuses_raw:
        total_bonus += bonus[1]
        bonuses.append({'date': bonus[0], 'date_ru': format_date_ru(bonus[0]), 'amount': bonus[1], 'description': bonus[2]})
    month_hours = sum(l['hours'] for l in logs)
    month_total = total_salary + total_konserzhka + total_bonus
    all_logs = conn.execute("SELECT hours, rate, konserzhka FROM hours_log WHERE employee_id=?", (emp_id,)).fetchall()
    total_hours = sum(l[0] for l in all_logs)
    total_salary_all = sum(l[0] * l[1] for l in all_logs)
    total_konserzhka_all = sum(1500 for l in all_logs if l[2] == 1)
    all_bonuses = conn.execute("SELECT amount FROM fixed_payments WHERE employee_id=?", (emp_id,)).fetchall()
    total_bonus_all = sum(b[0] for b in all_bonuses)
    grand_total = total_salary_all + total_konserzhka_all + total_bonus_all
    conn.close()
    return render_template_string(EMPLOYEE_HTML, employee={'id': employee[0], 'name': employee[1]}, logs=logs, bonuses=bonuses, total_hours=total_hours, total_salary=total_salary_all, total_konserzhka=total_konserzhka_all, total_bonus=total_bonus_all, grand_total=grand_total, month_hours=month_hours, month_konserzhka=total_konserzhka, month_total=month_total, selected_month=month, msg=request.args.get('msg'))

@app.route('/login', methods=['POST'])
def login():
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '').strip()
    if not name or not password:
        return redirect(url_for('index', msg='Введите имя и пароль!'))
    if name == 'admin' and password == 'admin123':
        session.permanent = True
        session['user_id'] = 0
        session['user_name'] = 'Admin'
        session['is_admin'] = True
        return redirect(url_for('index', msg='Добро пожаловать, Админ!'))
    conn = get_db()
    employee = conn.execute("SELECT id, name, password, is_admin FROM employees WHERE name=?", (name,)).fetchone()
    conn.close()
    if not employee:
        return redirect(url_for('index', msg='Сотрудник не найден!'))
    if employee[2] != password:
        return redirect(url_for('index', msg='Неверный пароль!'))
    session.permanent = True
    session['user_id'] = employee[0]
    session['user_name'] = employee[1]
    session['is_admin'] = bool(employee[3])
    return redirect(url_for('index', msg=f'Добро пожаловать, {employee[1]}!'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index', msg='Вы вышли из системы'))

@app.route('/add_employee', methods=['POST'])
def add_employee():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='Только админ может добавлять сотрудников!'))
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '').strip()
    if not name or not password:
        return redirect(url_for('index', msg='Введите имя и пароль!'))
    conn = get_db()
    try:
        conn.execute("INSERT INTO employees (name, password, is_admin) VALUES (?, ?, 0)", (name, password))
        conn.commit()
        msg = f"Сотрудник {name} добавлен!"
    except sqlite3.IntegrityError:
        msg = f"Сотрудник '{name}' уже существует!"
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('index', msg=msg))

@app.route('/make_admin', methods=['POST'])
def make_admin():
    if not session.get('is_admin') or session['user_id'] != 0:
        return redirect(url_for('index', msg='Только главный админ может давать права!'))
    emp_id = int(request.form['emp_id'])
    conn = get_db()
    try:
        conn.execute("UPDATE employees SET is_admin = 1 WHERE id=?", (emp_id,))
        conn.commit()
        name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
        msg = f"{name} теперь админ!"
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('index', msg=msg))

@app.route('/delete_employee', methods=['POST'])
def delete_employee():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='Только админ может удалять сотрудников!'))
    emp_id = int(request.form['emp_id'])
    conn = get_db()
    try:
        conn.execute("DELETE FROM hours_log WHERE employee_id=?", (emp_id,))
        conn.execute("DELETE FROM fixed_payments WHERE employee_id=?", (emp_id,))
        conn.execute("DELETE FROM employees WHERE id=?", (emp_id,))
        conn.commit()
        msg = "Сотрудник удалён!"
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('index', msg=msg))

@app.route('/add_event', methods=['POST'])
def add_event():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='Только админ может добавлять мероприятия!'))
    event_date = request.form.get('event_date', '')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    if not event_date or not title:
        return redirect(url_for('index', msg='Введите дату и название!'))
    conn = get_db()
    try:
        conn.execute("INSERT INTO events (event_date, title, description) VALUES (?, ?, ?)", (event_date, title, description))
        conn.commit()
        msg = f"Мероприятие '{title}' добавлено!"
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('index', msg=msg))

@app.route('/delete_event', methods=['POST'])
def delete_event():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='Только админ может удалять мероприятия!'))
    event_id = int(request.form['event_id'])
    conn = get_db()
    try:
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        conn.commit()
        msg = "Мероприятие удалено!"
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('index', msg=msg))

@app.route('/add_hours', methods=['POST'])
def add_hours():
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='Войдите в систему!'))
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='Только администратор может добавлять часы!'))
    try:
        emp_id = int(request.form['emp_id'])
        hours_str = request.form.get('hours', '').strip()
        work_date = request.form.get('work_date', '')
        rate = float(request.form.get('rate', 400))
        konserzhka = 1 if request.form.get('konserzhka') == '1' else 0
        if not hours_str:
            return redirect(url_for('index', msg='Введите часы!'))
        hours = float(hours_str)
        if hours <= 0:
            return redirect(url_for('index', msg='Часы должны быть больше 0!'))
        if not work_date:
            work_date = str(date.today())
        conn = get_db()
        conn.execute("INSERT INTO hours_log (employee_id, work_date, hours, rate, konserzhka) VALUES (?, ?, ?, ?, ?)", (emp_id, work_date, hours, rate, konserzhka))
        conn.commit()
        name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
        conn.close()
        total = hours * rate + (1500 if konserzhka else 0)
        msg = f"{name} ({format_date_ru(work_date)}): {hours}ч × {rate}₽ = {hours*rate}₽" + (" (+1500 консержка)" if konserzhka else "")
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    return redirect(url_for('index', msg=msg))

@app.route('/add_bonus', methods=['POST'])
def add_bonus():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='Только админ может добавлять премии!'))
    try:
        emp_id = int(request.form['emp_id'])
        amount_str = request.form.get('amount', '').strip()
        description = request.form.get('description', '').strip()
        payment_date = request.form.get('payment_date', '')
        if not amount_str:
            return redirect(url_for('index', msg='Введите сумму!'))
        amount = float(amount_str)
        if amount <= 0:
            return redirect(url_for('index', msg='Сумма должна быть больше 0!'))
        if not payment_date:
            payment_date = str(date.today())
        conn = get_db()
        conn.execute("INSERT INTO fixed_payments (employee_id, payment_date, amount, description) VALUES (?, ?, ?, ?)", (emp_id, payment_date, amount, description))
        conn.commit()
        name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
        conn.close()
        msg = f"{name}: премия {amount}₽ ({description or 'без описания'})"
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    return redirect(url_for('index', msg=msg))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

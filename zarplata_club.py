from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
import sqlite3
from datetime import date, datetime, timedelta
import os
import io
import csv
import base64

app = Flask(__name__)
app.secret_key = 'zarplata_club_secret_2024'
app.permanent_session_lifetime = timedelta(days=30)

# === БАЗА ДАННЫХ ===
def get_db():
    db_path = '/tmp/zarplata_club.db'
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    
    # Сотрудники (добавлено поле avatar)
    cur.execute('''CREATE TABLE IF NOT EXISTS employees 
                   (id INTEGER PRIMARY KEY, name TEXT UNIQUE, password TEXT, is_admin INTEGER DEFAULT 0, avatar TEXT DEFAULT '')''')
    
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
    
    # === ТАБЛИЦА АУДИТА ===
    cur.execute('''CREATE TABLE IF NOT EXISTS audit_log 
                   (id INTEGER PRIMARY KEY, admin_id INTEGER, admin_name TEXT,
                    action_type TEXT, action_details TEXT, action_date TEXT,
                    FOREIGN KEY(admin_id) REFERENCES employees(id))''')
    
    conn.commit()
    return conn

# === ФУНКЦИЯ ДЛЯ ЗАПИСИ В АУДИТ ===
def log_audit(admin_id, admin_name, action_type, action_details):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit_log (admin_id, admin_name, action_type, action_details, action_date) VALUES (?, ?, ?, ?, ?)",
        (admin_id, admin_name, action_type, action_details, str(date.today()))
    )
    conn.commit()
    conn.close()

# === ФУНКЦИЯ ДЛЯ ПРЕОБРАЗОВАНИЯ ДАТ ===
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

def get_month_days(year, month):
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    return [date(year, month, d) for d in range(1, last_day.day + 1)]

# === ГЛАВНАЯ СТРАНИЦА ===
HTML = '''
<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎵 Зарплата Клуб</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-body);
            min-height: 100vh;
            padding: 20px;
            position: relative;
            overflow-x: hidden;
            transition: background 0.3s ease, color 0.3s ease;
        }
        :root {
            --bg-body: #0b0b1a;
            --bg-container: rgba(255, 255, 255, 0.07);
            --border-color: rgba(255, 255, 255, 0.06);
            --text-primary: #fff;
            --text-secondary: rgba(255,255,255,0.6);
            --card-bg: rgba(255, 255, 255, 0.04);
            --input-bg: rgba(255, 255, 255, 0.05);
            --shadow-color: rgba(0,0,0,0.6);
            --glass-border: rgba(255,255,255,0.08);
        }
        [data-theme="light"] {
            --bg-body: #f0f2f5;
            --bg-container: rgba(255, 255, 255, 0.7);
            --border-color: rgba(0, 0, 0, 0.06);
            --text-primary: #1a1a2e;
            --text-secondary: rgba(0,0,0,0.5);
            --card-bg: rgba(255, 255, 255, 0.6);
            --input-bg: rgba(255, 255, 255, 0.8);
            --shadow-color: rgba(0,0,0,0.1);
            --glass-border: rgba(0,0,0,0.05);
        }
        #particles-js {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            pointer-events: none;
        }
        .star {
            position: fixed;
            width: 3px;
            height: 3px;
            background: white;
            border-radius: 50%;
            opacity: 0.5;
            animation: twinkle var(--duration) ease-in-out infinite alternate;
            z-index: 0;
            pointer-events: none;
        }
        @keyframes twinkle {
            0% { opacity: 0.1; transform: scale(0.8); }
            100% { opacity: 0.8; transform: scale(1.2); }
        }
        .container {
            max-width: 1300px;
            margin: 0 auto;
            background: var(--bg-container);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 40px;
            padding: 35px;
            box-shadow: 0 30px 60px var(--shadow-color);
            animation: slideIn 0.6s ease;
            position: relative;
            z-index: 1;
            border: 1px solid var(--glass-border);
            transition: background 0.3s ease;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(-40px) scale(0.96); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .header {
            text-align: center;
            margin-bottom: 25px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            position: relative;
        }
        .header .logo { font-size: 60px; display: block; animation: floatIcon 4s ease-in-out infinite; }
        @keyframes floatIcon {
            0%, 100% { transform: translateY(0) rotate(0deg); }
            50% { transform: translateY(-12px) rotate(4deg); }
        }
        h1 {
            font-size: 3em;
            font-weight: 900;
            background: linear-gradient(135deg, #c084fc 0%, #f472b6 40%, #fcd34d 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
            letter-spacing: 5px;
            text-transform: uppercase;
        }
        .subtitle {
            color: var(--text-secondary);
            font-size: 1.1em;
            font-weight: 300;
            transition: color 0.3s ease;
        }
        .subtitle span { color: #c084fc; font-weight: 600; }
        .theme-toggle {
            position: absolute;
            top: 0;
            left: 0;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 50%;
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-secondary);
            font-size: 18px;
            cursor: pointer;
            transition: 0.3s;
        }
        .theme-toggle:hover {
            border-color: #c084fc;
            color: #c084fc;
            transform: scale(1.05);
        }
        .logout-icon {
            position: absolute;
            top: 0;
            right: 0;
            font-size: 18px;
            color: var(--text-secondary);
            text-decoration: none;
            padding: 8px 12px;
            border-radius: 50%;
            transition: 0.3s;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .logout-icon:hover {
            background: rgba(255,107,107,0.15);
            color: #ff6b6b;
            border-color: rgba(255,107,107,0.3);
            transform: rotate(90deg);
        }
        .main-menu {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 18px;
            margin: 35px 0;
        }
        .menu-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 28px 16px;
            border-radius: 24px;
            text-align: center;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            text-decoration: none;
            color: var(--text-primary);
            display: block;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        }
        .menu-card:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 40px rgba(157, 78, 221, 0.15);
            border-color: rgba(157, 78, 221, 0.2);
            background: var(--card-bg);
        }
        .menu-card .icon { font-size: 38px; display: block; margin-bottom: 12px; color: #c084fc; }
        .menu-card .title { font-size: 16px; font-weight: 700; }
        .menu-card .desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
        .menu-card.events .icon { color: #fcd34d; }
        .menu-card.add .icon { color: #6bcb77; }
        .menu-card.audit .icon { color: #60a5fa; }
        
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 24px;
            margin-bottom: 24px;
            transition: 0.3s;
        }
        .card:hover { border-color: var(--border-color); }
        .card h3 {
            color: var(--text-primary);
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 700;
            font-size: 1.2em;
        }
        .card h3 .icon { font-size: 22px; color: #c084fc; }
        .card.green { border-left: 3px solid #6bcb77; }
        .card.pink { border-left: 3px solid #f472b6; }
        .card.gold { border-left: 3px solid #fcd34d; }
        .card.blue { border-left: 3px solid #60a5fa; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
            gap: 12px;
            margin-bottom: 25px;
        }
        .stat-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 16px 10px;
            border-radius: 20px;
            text-align: center;
            transition: 0.3s;
        }
        .stat-card:hover {
            transform: translateY(-3px);
            border-color: rgba(157, 78, 221, 0.15);
        }
        .stat-card .number {
            font-size: 24px;
            font-weight: 800;
            background: linear-gradient(135deg, #c084fc 0%, #f472b6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-card .label {
            color: var(--text-secondary);
            font-size: 11px;
            font-weight: 600;
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-card .icon { font-size: 20px; display: block; margin-bottom: 4px; color: var(--text-secondary); }
        
        .form-group {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
        }
        input, select, textarea {
            padding: 12px 18px;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            color: var(--text-primary);
            transition: all 0.3s ease;
            flex: 1;
            min-width: 120px;
            outline: none;
        }
        input::placeholder, select { color: var(--text-secondary); }
        input:focus, select:focus {
            border-color: #c084fc;
            box-shadow: 0 0 0 4px rgba(192, 132, 252, 0.1);
            background: var(--input-bg);
        }
        input[type="date"] { min-width: 160px; cursor: pointer; color: var(--text-primary); }
        input[type="file"] { padding: 10px; color: var(--text-secondary); }
        input[type="checkbox"] {
            width: 22px;
            height: 22px;
            flex: 0 0 auto;
            min-width: unset;
            accent-color: #c084fc;
            cursor: pointer;
        }
        label { color: var(--text-secondary); font-size: 14px; display: flex; align-items: center; gap: 8px; cursor: pointer; }
        
        .search-box {
            display: flex;
            gap: 10px;
            align-items: center;
            margin-bottom: 15px;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 4px 16px;
            transition: 0.3s;
        }
        .search-box:focus-within {
            border-color: #c084fc;
            box-shadow: 0 0 0 4px rgba(192, 132, 252, 0.05);
        }
        .search-box input {
            border: none;
            background: transparent;
            padding: 12px 0;
            flex: 1;
            font-size: 14px;
            color: var(--text-primary);
            outline: none;
        }
        .search-box i {
            color: var(--text-secondary);
            font-size: 16px;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 14px;
            font-size: 14px;
            font-weight: 700;
            font-family: 'Inter', sans-serif;
            cursor: pointer;
            transition: all 0.3s ease;
            color: #fff;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            flex: 0 0 auto;
        }
        .btn:hover { transform: translateY(-3px) scale(1.02); box-shadow: 0 12px 30px rgba(0,0,0,0.2); }
        .btn-purple { background: linear-gradient(135deg, #9d4edd 0%, #6d28d9 100%); }
        .btn-green { background: linear-gradient(135deg, #6bcb77 0%, #2d8f47 100%); }
        .btn-gold { background: linear-gradient(135deg, #fcd34d 0%, #f59e0b 100%); color: #1a1a2e; }
        .btn-red { background: linear-gradient(135deg, #ff6b6b 0%, #dc2626 100%); }
        .btn-sm { padding: 8px 16px; font-size: 12px; border-radius: 10px; }
        .btn-avatar { background: rgba(192,132,252,0.15); color: #c084fc; border: 1px solid rgba(192,132,252,0.2); padding: 6px 12px; font-size: 12px; border-radius: 10px; cursor: pointer; transition: 0.3s; }
        .btn-avatar:hover { background: rgba(192,132,252,0.25); }
        
        .table-wrapper { overflow-x: auto; border-radius: 16px; border: 1px solid var(--border-color); }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            color: var(--text-primary);
        }
        table th {
            background: var(--card-bg);
            color: var(--text-secondary);
            padding: 12px 14px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border-color);
        }
        table td {
            padding: 11px 14px;
            border-bottom: 1px solid var(--border-color);
        }
        table tr:hover td { background: var(--card-bg); }
        
        .badge {
            display: inline-block;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            background: rgba(192, 132, 252, 0.15);
            color: #c084fc;
        }
        .badge-gold { background: rgba(252, 211, 77, 0.15); color: #fcd34d; }
        .badge-blue { background: rgba(96, 165, 250, 0.15); color: #60a5fa; }
        .rate-badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .rate-badge.r400 { background: rgba(107, 203, 119, 0.15); color: #6bcb77; }
        .rate-badge.r350 { background: rgba(252, 211, 77, 0.15); color: #fcd34d; }
        
        .alert {
            padding: 14px 20px;
            border-radius: 16px;
            margin: 12px 0;
            font-weight: 600;
            border-left: 3px solid;
            background: var(--card-bg);
        }
        .alert-success { color: #6bcb77; border-color: #6bcb77; }
        .alert-danger { color: #ff6b6b; border-color: #ff6b6b; }
        
        .back-link {
            display: inline-block;
            margin-bottom: 16px;
            color: var(--text-secondary);
            font-weight: 600;
            text-decoration: none;
            font-size: 14px;
            transition: 0.3s;
        }
        .back-link:hover { color: #c084fc; transform: translateX(-4px); }
        
        .employee-card {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 18px;
            background: var(--card-bg);
            border-radius: 16px;
            margin-bottom: 8px;
            border: 1px solid var(--border-color);
            transition: 0.3s;
            color: var(--text-primary);
        }
        .employee-card:hover {
            border-color: rgba(157, 78, 221, 0.2);
            background: var(--card-bg);
        }
        .employee-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
            margin-right: 12px;
            border: 2px solid rgba(192,132,252,0.2);
        }
        .employee-avatar-placeholder {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--border-color);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;
            color: var(--text-secondary);
            font-size: 16px;
        }
        .employee-info { display: flex; align-items: center; flex: 1; }
        .delete-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 16px;
            transition: 0.3s;
            padding: 0 5px;
        }
        .delete-btn:hover { color: #ff6b6b; transform: scale(1.2); }
        
        .month-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
        }
        .month-nav .month-title { font-size: 22px; font-weight: 700; color: var(--text-primary); }
        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 6px;
            margin: 15px 0;
        }
        .calendar-day {
            background: var(--card-bg);
            padding: 10px 4px;
            border-radius: 14px;
            text-align: center;
            min-height: 70px;
            border: 1px solid var(--border-color);
            transition: 0.3s;
        }
        .calendar-day:hover { border-color: rgba(192, 132, 252, 0.2); }
        .calendar-day .day-num { font-weight: 700; font-size: 16px; color: var(--text-primary); }
        .calendar-day .day-event {
            font-size: 10px;
            background: rgba(252, 211, 77, 0.15);
            color: #fcd34d;
            border-radius: 8px;
            padding: 2px 8px;
            margin-top: 4px;
            display: inline-block;
            font-weight: 600;
            cursor: pointer;
        }
        .calendar-day.weekend .day-num { color: rgba(255,107,107,0.5); }
        .calendar-day.today { border-color: #c084fc; background: rgba(192, 132, 252, 0.05); }
        .calendar-day .add-event-btn {
            font-size: 12px;
            color: var(--text-secondary);
            cursor: pointer;
            display: block;
            margin-top: 2px;
        }
        .calendar-day .add-event-btn:hover { color: #c084fc; }
        
        .chart-container {
            background: var(--card-bg);
            border-radius: 16px;
            padding: 18px;
            margin-top: 12px;
            border: 1px solid var(--border-color);
        }
        .chart-bar {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 10px;
        }
        .chart-bar .bar-label {
            min-width: 80px;
            font-weight: 600;
            font-size: 13px;
            color: var(--text-secondary);
        }
        .chart-bar .bar-track {
            flex: 1;
            height: 26px;
            background: var(--border-color);
            border-radius: 14px;
            overflow: hidden;
        }
        .chart-bar .bar-fill {
            height: 100%;
            border-radius: 14px;
            background: linear-gradient(90deg, #9d4edd, #f472b6);
            transition: width 1s ease;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 10px;
            color: #fff;
            font-weight: 700;
            font-size: 12px;
        }
        
        .period-group h4 {
            color: var(--text-secondary);
            margin-bottom: 10px;
            font-size: 14px;
            padding: 8px 14px;
            border-radius: 12px;
            background: var(--card-bg);
        }
        .period-group h4.first { border-left: 3px solid #6bcb77; }
        .period-group h4.second { border-left: 3px solid #fcd34d; }
        
        .total-row td { 
            border-top: 1px solid var(--border-color);
            color: var(--text-primary) !important;
            font-weight: 700;
        }
        
        .audit-item {
            padding: 10px 14px;
            background: var(--card-bg);
            border-radius: 12px;
            margin-bottom: 6px;
            border-left: 3px solid #60a5fa;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .audit-item .admin { color: #c084fc; font-weight: 600; }
        .audit-item .action { color: var(--text-primary); }
        .audit-item .date { color: var(--text-secondary); font-size: 12px; }
        
        @media (max-width: 700px) {
            .container { padding: 16px; border-radius: 24px; }
            h1 { font-size: 2em; }
            .main-menu { grid-template-columns: 1fr 1fr; gap: 12px; }
            .menu-card { padding: 20px 12px; }
            .menu-card .icon { font-size: 28px; }
            .form-group { flex-direction: column; }
            .btn { width: 100%; justify-content: center; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .calendar-grid { gap: 4px; font-size: 12px; }
            .calendar-day { min-height: 50px; padding: 4px; }
            .employee-card { flex-direction: column; align-items: stretch; gap: 6px; }
            .theme-toggle, .logout-icon { top: 4px; width: 36px; height: 36px; font-size: 14px; }
            .theme-toggle { left: 4px; }
            .logout-icon { right: 4px; }
            .header .logo { font-size: 40px; }
        }
    </style>
</head>
<body>
<div id="particles-js"></div>

<div class="container">
    <div class="header">
        <span class="logo">🏢</span>
        <h1>ЗАРПЛАТА КЛУБ</h1>
        <p class="subtitle">🎵 Учёт зарплаты · Ставка <span>400</span> или <span>350</span> ₽/ч · Консержка <span>+1500 ₽</span></p>
        
        {% if session.get('user_id') is not none %}
        <button class="theme-toggle" onclick="toggleTheme()" title="Сменить тему">
            <i class="fas fa-moon"></i>
        </button>
        <a href="/logout" class="logout-icon" title="Выйти">
            <i class="fas fa-sign-out-alt"></i>
        </a>
        {% endif %}
    </div>

    {% if session.get('user_id') is none %}
    <div class="card" style="border-left: 3px solid #60a5fa;">
        <h3><span class="icon"><i class="fas fa-lock"></i></span> Вход</h3>
        <form method="POST" action="/login" class="form-group">
            <input type="text" name="name" placeholder="Имя" required style="flex:1;">
            <input type="password" name="password" placeholder="Пароль" required style="flex:1;">
            <button type="submit" class="btn" style="background:linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);"><i class="fas fa-sign-in-alt"></i> Войти</button>
        </form>
        {% if msg %}
        <div class="alert alert-danger">{{ msg }}</div>
        {% endif %}
    </div>
    {% else %}
    
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:18px;">
        <div style="font-weight:600;font-size:18px;color:var(--text-secondary);">
            <i class="fas fa-user" style="color:#c084fc;"></i> 
            <span style="color:var(--text-primary);font-weight:700;">{{ session.user_name }}</span>
            {% if session.is_admin %}
            <span style="font-size:13px;color:var(--text-secondary);margin-left:10px;">
                <i class="fas fa-crown" style="color:#fcd34d;"></i> Админ
            </span>
            {% endif %}
        </div>
    </div>

    {% if not current_section or current_section == 'main' %}
    <div class="main-menu">
        <a href="/section/employees" class="menu-card">
            <span class="icon"><i class="fas fa-users"></i></span>
            <div class="title">Сотрудники</div>
            <div class="desc">Управление персоналом</div>
        </a>
        <a href="/section/events" class="menu-card events">
            <span class="icon"><i class="fas fa-calendar-alt"></i></span>
            <div class="title">Мероприятия</div>
            <div class="desc">Календарь и события</div>
        </a>
        <a href="/section/hours" class="menu-card">
            <span class="icon"><i class="fas fa-clock"></i></span>
            <div class="title">Часы</div>
            <div class="desc">Все записи по дням</div>
        </a>
        <a href="/section/payments" class="menu-card">
            <span class="icon"><i class="fas fa-money-bill-wave"></i></span>
            <div class="title">Выплаты</div>
            <div class="desc">Расчёт зарплаты</div>
        </a>
        <a href="/section/bonus" class="menu-card">
            <span class="icon"><i class="fas fa-gift"></i></span>
            <div class="title">Премии</div>
            <div class="desc">Управление премиями</div>
        </a>
        {% if session.is_admin %}
        <a href="/section/add" class="menu-card add">
            <span class="icon"><i class="fas fa-plus-circle"></i></span>
            <div class="title">Добавить</div>
            <div class="desc">Новый сотрудник / часы</div>
        </a>
        <a href="/section/audit" class="menu-card audit">
            <span class="icon"><i class="fas fa-history"></i></span>
            <div class="title">История</div>
            <div class="desc">Аудит действий</div>
        </a>
        {% endif %}
    </div>

    <div class="card">
        <h3><span class="icon"><i class="fas fa-chart-bar"></i></span> Статистика месяца</h3>
        <div class="stats-grid">
            <div class="stat-card"><span class="icon"><i class="fas fa-users"></i></span><div class="number">{{ stats.total_employees }}</div><div class="label">Сотрудников</div></div>
            <div class="stat-card"><span class="icon"><i class="fas fa-clock"></i></span><div class="number">{{ stats.total_hours|round(1) }}</div><div class="label">Часов</div></div>
            <div class="stat-card"><span class="icon"><i class="fas fa-ruble-sign"></i></span><div class="number">{{ stats.total_salary|round(0) }}</div><div class="label">Зарплата</div></div>
            <div class="stat-card"><span class="icon"><i class="fas fa-utensils"></i></span><div class="number">{{ stats.total_konserzhka }}</div><div class="label">Консержек</div></div>
            <div class="stat-card"><span class="icon"><i class="fas fa-gem"></i></span><div class="number">{{ stats.grand_total|round(0) }}</div><div class="label">ИТОГО</div></div>
        </div>
        
        {% if chart_data %}
        <div class="chart-container">
            <h4 style="margin-bottom:12px;color:var(--text-secondary);font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">
                <i class="fas fa-chart-simple" style="color:#c084fc;"></i> Часы по сотрудникам
            </h4>
            {% for item in chart_data %}
            <div class="chart-bar">
                <div class="bar-label">{{ item.name }}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width: {{ item.percent }}%;">
                        {{ item.hours|round(1) }}ч
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}
    </div>
    {% endif %}

    {% if current_section == 'employees' %}
    <div class="card">
        <h3><span class="icon"><i class="fas fa-users"></i></span> Все сотрудники</h3>
        <p style="color:var(--text-secondary);margin-bottom:14px;font-size:14px;">📌 Нажмите на сотрудника для просмотра деталей</p>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        
        <div class="search-box">
            <i class="fas fa-search"></i>
            <input type="text" id="employeeSearch" placeholder="Поиск по имени..." oninput="filterEmployees()">
        </div>
        
        <div id="employeeList">
        {% if employees %}
        {% for emp in employees %}
        <div class="employee-card" data-name="{{ emp.name|lower }}" onclick="window.location.href='/employee/{{ emp.id }}'" style="cursor:pointer;">
            <div class="employee-info">
                {% if emp.avatar %}
                <img src="data:image/jpeg;base64,{{ emp.avatar }}" class="employee-avatar" alt="{{ emp.name }}">
                {% else %}
                <div class="employee-avatar-placeholder"><i class="fas fa-user"></i></div>
                {% endif %}
                <div class="name">{{ emp.name }}</div>
            </div>
            <div class="stats" style="color:var(--text-secondary);font-size:14px;">
                <i class="fas fa-clock" style="color:#c084fc;"></i> <strong style="color:var(--text-primary);">{{ emp.month_hours|round(1) }}</strong> ч · 
                <i class="fas fa-utensils" style="color:#fcd34d;"></i> <strong style="color:var(--text-primary);">{{ emp.month_konserzhka }}</strong> · 
                <i class="fas fa-ruble-sign" style="color:#6bcb77;"></i> <strong style="color:var(--text-primary);">{{ emp.month_total|round(0) }}</strong> ₽
            </div>
            <div class="actions">
                {% if session.is_admin %}
                <form method="POST" action="/upload_avatar" enctype="multipart/form-data" style="display:inline;" onclick="event.stopPropagation();">
                    <input type="hidden" name="emp_id" value="{{ emp.id }}">
                    <input type="file" name="avatar" accept="image/*" style="display:none;" id="avatar-{{ emp.id }}" onchange="this.form.submit()">
                    <label for="avatar-{{ emp.id }}" class="btn-avatar" style="cursor:pointer;"><i class="fas fa-camera"></i></label>
                </form>
                <form method="POST" action="/delete_employee" onsubmit="return confirm('Удалить {{ emp.name }}? Все данные будут потеряны!')" onclick="event.stopPropagation();">
                    <input type="hidden" name="emp_id" value="{{ emp.id }}">
                    <button type="submit" class="delete-btn" title="Удалить сотрудника"><i class="fas fa-trash"></i></button>
                </form>
                {% endif %}
            </div>
        </div>
        {% endfor %}
        {% else %}
        <p style="text-align:center;color:var(--text-secondary);padding:30px;"><i class="fas fa-face-frown"></i> Нет сотрудников</p>
        {% endif %}
        </div>
    </div>
    {% endif %}

    {% if current_section == 'audit' and session.is_admin %}
    <div class="card blue">
        <h3><span class="icon"><i class="fas fa-history"></i></span> История изменений (Аудит)</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        {% if audit_logs %}
        <div style="max-height:500px;overflow-y:auto;">
            {% for log in audit_logs %}
            <div class="audit-item">
                <span>
                    <span class="admin">👤 {{ log.admin_name }}</span>
                    <span class="action">{{ log.action_type }}: {{ log.action_details }}</span>
                </span>
                <span class="date"><i class="far fa-calendar-alt"></i> {{ log.date_ru }}</span>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <p style="color:var(--text-secondary);"><i class="fas fa-inbox"></i> История пока пуста</p>
        {% endif %}
    </div>
    {% endif %}

    {% if current_section == 'events' %}
    <div class="card gold">
        <h3><span class="icon"><i class="fas fa-calendar-alt"></i></span> Календарь мероприятий</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div class="month-nav">
            <button class="btn btn-sm btn-purple" onclick="window.location.href='/section/events?month={{ prev_month }}'"><i class="fas fa-chevron-left"></i></button>
            <span class="month-title">{{ month_name }}</span>
            <button class="btn btn-sm btn-purple" onclick="window.location.href='/section/events?month={{ next_month }}'"><i class="fas fa-chevron-right"></i></button>
        </div>
        <div class="calendar-grid">
            <div style="font-weight:700;color:var(--text-secondary);text-align:center;font-size:11px;text-transform:uppercase;">Пн</div>
            <div style="font-weight:700;color:var(--text-secondary);text-align:center;font-size:11px;text-transform:uppercase;">Вт</div>
            <div style="font-weight:700;color:var(--text-secondary);text-align:center;font-size:11px;text-transform:uppercase;">Ср</div>
            <div style="font-weight:700;color:var(--text-secondary);text-align:center;font-size:11px;text-transform:uppercase;">Чт</div>
            <div style="font-weight:700;color:var(--text-secondary);text-align:center;font-size:11px;text-transform:uppercase;">Пт</div>
            <div style="font-weight:700;color:var(--text-secondary);text-align:center;font-size:11px;text-transform:uppercase;">Сб</div>
            <div style="font-weight:700;color:var(--text-secondary);text-align:center;font-size:11px;text-transform:uppercase;">Вс</div>
            {% for day in calendar_days %}
            <div class="calendar-day{% if day.is_weekend %} weekend{% endif %}{% if day.is_today %} today{% endif %}">
                <div class="day-num">{{ day.day }}</div>
                {% if day.event %}
                <div class="day-event" onclick="alert('{{ day.event.title }}: {{ day.event.description or '' }}')">
                    {{ day.event.title }}
                </div>
                {% endif %}
                {% if session.is_admin %}
                <div class="add-event-btn" onclick="addEvent('{{ day.date_str }}')"><i class="fas fa-plus-circle"></i></div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        {% if session.is_admin %}
        <div style="margin-top:18px;padding-top:18px;border-top:1px solid var(--border-color);">
            <h4 style="color:var(--text-secondary);margin-bottom:12px;"><i class="fas fa-plus-circle" style="color:#fcd34d;"></i> Добавить мероприятие</h4>
            <form method="POST" action="/add_event" class="form-group">
                <input type="date" name="event_date" value="{{ today }}" required>
                <input type="text" name="title" placeholder="Название" required>
                <input type="text" name="description" placeholder="Описание">
                <button type="submit" class="btn btn-gold"><i class="fas fa-plus"></i> Добавить</button>
            </form>
        </div>
        {% endif %}
        <div class="events-list">
            <h4 style="margin:18px 0 12px;color:var(--text-secondary);font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">
                <i class="fas fa-list" style="color:#fcd34d;"></i> Все события месяца
            </h4>
            {% if events %}
            {% for event in events %}
            <div class="event-item" style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:var(--card-bg);border-radius:12px;margin-bottom:6px;border-left:3px solid rgba(252,211,77,0.2);">
                <span style="font-weight:600;color:var(--text-secondary);font-size:13px;"><i class="far fa-calendar"></i> {{ event.date_ru }}</span>
                <span style="font-weight:600;flex:1;margin:0 10px;color:var(--text-primary);">{{ event.title }}</span>
                <span style="font-size:13px;color:var(--text-secondary);">{{ event.description or '' }}</span>
                {% if session.is_admin %}
                <form method="POST" action="/delete_event" style="display:inline;" onsubmit="return confirm('Удалить мероприятие?')">
                    <input type="hidden" name="event_id" value="{{ event.id }}">
                    <button type="submit" class="delete-btn" style="background:none;border:none;color:var(--text-secondary);cursor:pointer;transition:0.3s;padding:0 5px;" onmouseover="this.style.color='#ff6b6b'" onmouseout="this.style.color='var(--text-secondary)'"><i class="fas fa-trash"></i></button>
                </form>
                {% endif %}
            </div>
            {% endfor %}
            {% else %}
            <p style="color:var(--text-secondary);text-align:center;padding:16px;"><i class="far fa-calendar-alt"></i> Нет событий на этот месяц</p>
            {% endif %}
        </div>
    </div>
    {% endif %}

    {% if current_section == 'hours' %}
    <div class="card pink">
        <h3><span class="icon"><i class="fas fa-clock"></i></span> Все часы по дням</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div class="month-selector">
            <form method="GET" action="/section/hours" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
                <input type="month" name="month" value="{{ selected_month }}">
                <button type="submit" class="btn btn-sm btn-purple"><i class="fas fa-search"></i> Показать</button>
            </form>
        </div>
        <div class="search-box">
            <i class="fas fa-search"></i>
            <input type="text" id="hoursSearch" placeholder="Поиск по сотруднику или дате..." oninput="filterHours()">
        </div>
        <div id="hoursList">
        {% if all_logs %}
        <div class="table-wrapper">
            <table>
                <tr><th>Дата</th><th>Сотрудник</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
                {% for log in all_logs %}
                <tr class="hours-row" data-employee="{{ log.employee|lower }}" data-date="{{ log.date_ru|lower }}">
                    <td>{{ log.date_ru }}</td>
                    <td><span class="badge">{{ log.employee }}</span></td>
                    <td>{{ log.hours }}</td>
                    <td><span class="rate-badge r{{ log.rate|int }}">{{ log.rate }} ₽/ч</span></td>
                    <td>{% if log.konserzhka %}<i class="fas fa-utensils" style="color:#fcd34d;"></i> +1500 ₽{% else %}—{% endif %}</td>
                    <td><strong>{{ log.total }} ₽</strong></td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% if session.is_admin %}
        <div style="margin-top:14px;">
            <a href="/export?month={{ selected_month }}" class="btn btn-green"><i class="fas fa-file-excel"></i> Скачать Excel</a>
        </div>
        {% endif %}
        {% else %}
        <p style="text-align:center;color:var(--text-secondary);padding:30px;"><i class="fas fa-inbox"></i> Нет записей</p>
        {% endif %}
        </div>
    </div>
    {% endif %}

    {% if current_section == 'payments' %}
    <div class="card gold">
        <h3><span class="icon"><i class="fas fa-money-bill-wave"></i></span> Выплаты по периодам</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div class="month-selector">
            <form method="GET" action="/section/payments" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
                <input type="month" name="month" value="{{ selected_month }}">
                <button type="submit" class="btn btn-sm btn-purple"><i class="fas fa-search"></i> Показать</button>
            </form>
        </div>
        <div class="period-group">
            <h4 class="first"><i class="fas fa-hand-holding-usd"></i> 1–15 число (АВАНС)</h4>
            {% if payments.first %}
            <div class="table-wrapper">
                <table>
                    <tr><th>Дата</th><th>Сотрудник</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
                    {% for p in payments.first %}
                    <tr>
                        <td>{{ p.date_ru }}</td>
                        <td><span class="badge">{{ p.employee }}</span></td>
                        <td>{{ p.hours }}</td>
                        <td><span class="rate-badge r{{ p.rate|int }}">{{ p.rate }} ₽/ч</span></td>
                        <td>{% if p.konserzhka %}<i class="fas fa-utensils" style="color:#fcd34d;"></i> +1500{% else %}—{% endif %}</td>
                        <td><strong>{{ p.total }} ₽</strong></td>
                    </tr>
                    {% endfor %}
                    <tr class="total-row">
                        <td colspan="5"><strong>ИТОГО (АВАНС)</strong></td>
                        <td><strong>{{ payments.first_total|round(0) }} ₽</strong></td>
                    </tr>
                </table>
            </div>
            {% else %}
            <p style="color:var(--text-secondary);font-size:14px;padding:8px 0;">Нет записей за этот период</p>
            {% endif %}
        </div>
        <div class="period-group">
            <h4 class="second"><i class="fas fa-hand-holding-usd"></i> 16–конец месяца (ОКОНЧАТЕЛЬНЫЙ)</h4>
            {% if payments.second %}
            <div class="table-wrapper">
                <table>
                    <tr><th>Дата</th><th>Сотрудник</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
                    {% for p in payments.second %}
                    <tr>
                        <td>{{ p.date_ru }}</td>
                        <td><span class="badge">{{ p.employee }}</span></td>
                        <td>{{ p.hours }}</td>
                        <td><span class="rate-badge r{{ p.rate|int }}">{{ p.rate }} ₽/ч</span></td>
                        <td>{% if p.konserzhka %}<i class="fas fa-utensils" style="color:#fcd34d;"></i> +1500{% else %}—{% endif %}</td>
                        <td><strong>{{ p.total }} ₽</strong></td>
                    </tr>
                    {% endfor %}
                    <tr class="total-row">
                        <td colspan="5"><strong>ИТОГО (ОКОНЧАТЕЛЬНЫЙ)</strong></td>
                        <td><strong>{{ payments.second_total|round(0) }} ₽</strong></td>
                    </tr>
                </table>
            </div>
            {% else %}
            <p style="color:var(--text-secondary);font-size:14px;padding:8px 0;">Нет записей за этот период</p>
            {% endif %}
        </div>
    </div>
    {% endif %}

    {% if current_section == 'bonus' %}
    <div class="card" style="border-left: 3px solid #fcd34d;">
        <h3><span class="icon"><i class="fas fa-gift"></i></span> Премии</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        {% if session.is_admin %}
        <form method="POST" action="/add_bonus" class="form-group" style="margin-bottom:18px;">
            <select name="emp_id" required>
                <option value="">Выберите сотрудника</option>
                {% for emp in employees %}
                <option value="{{ emp.id }}">{{ emp.name }}</option>
                {% endfor %}
            </select>
            <input type="number" name="amount" placeholder="Сумма ₽" step="0.1" required>
            <input type="text" name="description" placeholder="Описание">
            <input type="date" name="payment_date" value="{{ today }}">
            <button type="submit" class="btn btn-gold"><i class="fas fa-plus"></i> Добавить</button>
        </form>
        {% endif %}
        {% if all_bonuses %}
        <div class="table-wrapper">
            <table>
                <tr><th>Дата</th><th>Сотрудник</th><th>Сумма</th><th>Описание</th></tr>
                {% for bonus in all_bonuses %}
                <tr>
                    <td>{{ bonus.date_ru }}</td>
                    <td><span class="badge badge-gold">{{ bonus.employee }}</span></td>
                    <td><strong>{{ bonus.amount }} ₽</strong></td>
                    <td>{{ bonus.description or '—' }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% else %}
        <p style="color:var(--text-secondary);"><i class="fas fa-gift"></i> Пока нет премий</p>
        {% endif %}
    </div>
    {% endif %}

    {% if current_section == 'add' and session.is_admin %}
    <div class="card green">
        <h3><span class="icon"><i class="fas fa-user-plus"></i></span> Новый сотрудник</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <form method="POST" action="/add_employee" class="form-group">
            <input type="text" name="name" placeholder="Имя" required>
            <input type="password" name="password" placeholder="Пароль" required>
            <button type="submit" class="btn btn-green"><i class="fas fa-plus"></i> Добавить</button>
        </form>
    </div>
    <div class="card" style="border-left: 3px solid #6bcb77;">
        <h3><span class="icon"><i class="fas fa-clock"></i></span> Добавить часы сотруднику</h3>
        <form method="POST" action="/add_hours" class="form-group">
            <select name="emp_id" required style="flex:1;">
                <option value="">Выберите сотрудника</option>
                {% for emp in employees %}
                <option value="{{ emp.id }}">{{ emp.name }}</option>
                {% endfor %}
            </select>
            <input type="number" name="hours" placeholder="Часы" step="0.5" required style="flex:1;">
            <input type="date" name="work_date" value="{{ today }}" style="flex:1;">
            <select name="rate" required style="flex:0 0 auto;min-width:100px;">
                <option value="400">400 ₽/ч</option>
                <option value="350">350 ₽/ч</option>
            </select>
            <label style="white-space:nowrap;">
                <input type="checkbox" name="konserzhka" value="1">
                <i class="fas fa-utensils" style="color:#fcd34d;"></i> Консержка (+1500)
            </label>
            <button type="submit" class="btn btn-green"><i class="fas fa-plus"></i> Добавить</button>
        </form>
    </div>
    {% endif %}

    {% if msg and session.get('user_id') is not none %}
    <div class="alert alert-success">{{ msg }}</div>
    {% endif %}
    {% endif %}
</div>

<script>
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    const btn = document.querySelector('.theme-toggle i');
    if (newTheme === 'dark') {
        btn.className = 'fas fa-moon';
    } else {
        btn.className = 'fas fa-sun';
    }
}
document.addEventListener('DOMContentLoaded', function() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        const btn = document.querySelector('.theme-toggle i');
        if (savedTheme === 'light') {
            btn.className = 'fas fa-sun';
        }
    }
});
function filterEmployees() {
    const input = document.getElementById('employeeSearch');
    const filter = input.value.toLowerCase();
    const cards = document.querySelectorAll('#employeeList .employee-card');
    cards.forEach(card => {
        const name = card.getAttribute('data-name');
        if (name && name.includes(filter)) {
            card.style.display = 'flex';
        } else {
            card.style.display = 'none';
        }
    });
}
function filterHours() {
    const input = document.getElementById('hoursSearch');
    const filter = input.value.toLowerCase();
    const rows = document.querySelectorAll('#hoursList .hours-row');
    rows.forEach(row => {
        const employee = row.getAttribute('data-employee');
        const date = row.getAttribute('data-date');
        if ((employee && employee.includes(filter)) || (date && date.includes(filter))) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}
function addEvent(date) {
    var title = prompt('Введите название мероприятия:');
    if (title) {
        var desc = prompt('Описание (необязательно):');
        var form = document.createElement('form');
        form.method = 'POST';
        form.action = '/add_event';
        var input1 = document.createElement('input');
        input1.type = 'hidden';
        input1.name = 'event_date';
        input1.value = date;
        var input2 = document.createElement('input');
        input2.type = 'hidden';
        input2.name = 'title';
        input2.value = title;
        var input3 = document.createElement('input');
        input3.type = 'hidden';
        input3.name = 'description';
        input3.value = desc || '';
        form.appendChild(input1);
        form.appendChild(input2);
        form.appendChild(input3);
        document.body.appendChild(form);
        form.submit();
    }
}
</script>
</body>
</html>
'''

EMPLOYEE_HTML = '''
<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ employee.name }} — Зарплата Клуб</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-body);
            min-height: 100vh;
            padding: 20px;
            position: relative;
            overflow-x: hidden;
            transition: background 0.3s, color 0.3s;
        }
        :root {
            --bg-body: #0b0b1a;
            --bg-container: rgba(255,255,255,0.06);
            --border-color: rgba(255,255,255,0.05);
            --text-primary: #fff;
            --text-secondary: rgba(255,255,255,0.4);
            --card-bg: rgba(255,255,255,0.04);
            --shadow: rgba(0,0,0,0.5);
        }
        [data-theme="light"] {
            --bg-body: #f0f2f5;
            --bg-container: rgba(255,255,255,0.6);
            --border-color: rgba(0,0,0,0.05);
            --text-primary: #1a1a2e;
            --text-secondary: rgba(0,0,0,0.5);
            --card-bg: rgba(255,255,255,0.4);
            --shadow: rgba(0,0,0,0.1);
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: var(--bg-container);
            backdrop-filter: blur(20px);
            border-radius: 40px;
            padding: 35px;
            box-shadow: 0 30px 60px var(--shadow);
            position: relative;
            z-index: 1;
            border: 1px solid var(--border-color);
            animation: slideIn 0.6s ease;
        }
        @keyframes slideIn { from { opacity: 0; transform: translateY(-40px); } to { opacity: 1; transform: translateY(0); } }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 25px;
        }
        .header h1 {
            font-size: 2.2em;
            font-weight: 900;
            background: linear-gradient(135deg, #c084fc 0%, #f472b6 50%, #fcd34d 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .back-link { color: var(--text-secondary); font-weight: 600; text-decoration: none; transition: 0.3s; }
        .back-link:hover { color: #c084fc; transform: translateX(-4px); }
        
        .profile-avatar {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            object-fit: cover;
            border: 3px solid rgba(192,132,252,0.2);
            margin-bottom: 10px;
        }
        .profile-avatar-placeholder {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: var(--card-bg);
            border: 3px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            color: var(--text-secondary);
            margin-bottom: 10px;
        }
        .avatar-upload {
            margin: 10px 0 20px 0;
        }
        .avatar-upload input[type="file"] { display: none; }
        .avatar-upload label {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 8px 16px;
            border-radius: 12px;
            cursor: pointer;
            font-size: 13px;
            color: var(--text-secondary);
            transition: 0.3s;
        }
        .avatar-upload label:hover { border-color: #c084fc; color: #c084fc; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
            margin-bottom: 25px;
        }
        .stat-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 16px;
            border-radius: 20px;
            text-align: center;
            transition: 0.3s;
        }
        .stat-card:hover { transform: translateY(-3px); }
        .stat-card .number {
            font-size: 24px;
            font-weight: 800;
            background: linear-gradient(135deg, #c084fc 0%, #f472b6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-card .label { color: var(--text-secondary); font-size: 11px; font-weight: 600; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
        .stat-card .icon { font-size: 20px; display: block; margin-bottom: 4px; color: var(--text-secondary); }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 24px;
            margin-bottom: 24px;
            transition: 0.3s;
        }
        .card h3 { color: var(--text-primary); margin-bottom: 14px; font-weight: 700; font-size: 1.1em; }
        .card h3 i { color: #c084fc; margin-right: 10px; }
        .month-selector {
            display: flex;
            gap: 12px;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 16px;
        }
        .month-selector input[type="month"] {
            padding: 10px 16px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            color: var(--text-primary);
            min-width: 180px;
            outline: none;
        }
        .month-selector input[type="month"]:focus { border-color: #c084fc; box-shadow: 0 0 0 4px rgba(192,132,252,0.1); }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 14px;
            font-size: 14px;
            font-weight: 700;
            font-family: 'Inter', sans-serif;
            cursor: pointer;
            transition: all 0.3s ease;
            color: #fff;
        }
        .btn:hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 12px 30px rgba(0,0,0,0.3); }
        .btn-purple { background: linear-gradient(135deg, #9d4edd 0%, #6d28d9 100%); }
        .table-wrapper { overflow-x: auto; border-radius: 16px; border: 1px solid var(--border-color); }
        table { width: 100%; border-collapse: collapse; font-size: 14px; color: var(--text-primary); }
        table th {
            background: var(--card-bg);
            color: var(--text-secondary);
            padding: 12px 14px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        table td {
            padding: 11px 14px;
            border-bottom: 1px solid var(--border-color);
        }
        table tr:hover td { background: var(--card-bg); }
        .badge-purple { background: rgba(192,132,252,0.15); color: #c084fc; padding: 4px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; display: inline-block; }
        .rate-badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .rate-badge.r400 { background: rgba(107,203,119,0.15); color: #6bcb77; }
        .rate-badge.r350 { background: rgba(252,211,77,0.15); color: #fcd34d; }
        .total-row td { border-top: 1px solid var(--border-color); color: var(--text-primary) !important; font-weight: 700; }
        .alert {
            padding: 14px 20px;
            border-radius: 16px;
            margin: 12px 0;
            font-weight: 600;
            border-left: 3px solid;
            background: var(--card-bg);
        }
        .alert-success { color: #6bcb77; border-color: #6bcb77; }
        @media (max-width: 700px) {
            .container { padding: 16px; border-radius: 24px; }
            .header h1 { font-size: 1.6em; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1><i class="fas fa-user" style="color:#c084fc;"></i> {{ employee.name }}</h1>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> Назад</a>
    </div>

    <div style="text-align:center;">
        {% if employee.avatar %}
        <img src="data:image/jpeg;base64,{{ employee.avatar }}" class="profile-avatar" alt="{{ employee.name }}">
        {% else %}
        <div class="profile-avatar-placeholder"><i class="fas fa-user"></i></div>
        {% endif %}
        {% if session.is_admin %}
        <div class="avatar-upload">
            <form method="POST" action="/upload_avatar" enctype="multipart/form-data" style="display:inline;">
                <input type="hidden" name="emp_id" value="{{ employee.id }}">
                <input type="file" name="avatar" accept="image/*" id="avatar-upload" onchange="this.form.submit()">
                <label for="avatar-upload"><i class="fas fa-camera"></i> Сменить аватар</label>
            </form>
        </div>
        {% endif %}
    </div>

    <div class="stats-grid">
        <div class="stat-card"><span class="icon"><i class="fas fa-clock"></i></span><div class="number">{{ total_hours|round(1) }}</div><div class="label">Часов</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-ruble-sign"></i></span><div class="number">{{ total_salary|round(0) }}</div><div class="label">Зарплата</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-utensils"></i></span><div class="number">{{ total_konserzhka }}</div><div class="label">Консержек</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-gift"></i></span><div class="number">{{ total_bonus|round(0) }}</div><div class="label">Премии</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-gem"></i></span><div class="number">{{ grand_total|round(0) }}</div><div class="label">ИТОГО</div></div>
    </div>

    <div class="card">
        <h3><i class="fas fa-calendar-day"></i> Детали по дням</h3>
        <div class="month-selector">
            <form method="GET" action="/employee/{{ employee.id }}" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
                <input type="month" name="month" value="{{ selected_month }}">
                <button type="submit" class="btn btn-purple"><i class="fas fa-search"></i> Показать</button>
            </form>
        </div>
        {% if logs %}
        <div class="table-wrapper">
            <table>
                <tr><th>Дата</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
                {% for log in logs %}
                <tr>
                    <td>{{ log.date_ru }}</td>
                    <td>{{ log.hours }}</td>
                    <td><span class="rate-badge r{{ log.rate|int }}">{{ log.rate }} ₽/ч</span></td>
                    <td>{% if log.konserzhka %}<i class="fas fa-utensils" style="color:#fcd34d;"></i> +1500 ₽{% else %}—{% endif %}</td>
                    <td><strong>{{ log.total }} ₽</strong></td>
                </tr>
                {% endfor %}
                <tr class="total-row">
                    <td><strong>ИТОГО за месяц</strong></td>
                    <td><strong>{{ month_hours|round(1) }}</strong></td>
                    <td></td>
                    <td><strong>{{ month_konserzhka }}</strong></td>
                    <td><strong>{{ month_total|round(0) }} ₽</strong></td>
                </tr>
            </table>
        </div>
        {% else %}
        <p style="color:var(--text-secondary);"><i class="fas fa-inbox"></i> Нет записей за этот месяц</p>
        {% endif %}
    </div>

    <div class="card" style="border-left: 3px solid #fcd34d;">
        <h3><i class="fas fa-gift" style="color:#fcd34d;"></i> Премии</h3>
        {% if bonuses %}
        <div class="table-wrapper">
            <table>
                <tr><th>Дата</th><th>Сумма</th><th>Описание</th></tr>
                {% for bonus in bonuses %}
                <tr>
                    <td>{{ bonus.date_ru }}</td>
                    <td><strong>{{ bonus.amount }} ₽</strong></td>
                    <td>{{ bonus.description or '—' }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% else %}
        <p style="color:var(--text-secondary);"><i class="fas fa-gift"></i> Нет премий</p>
        {% endif %}
    </div>

    {% if msg %}
    <div class="alert alert-success">{{ msg }}</div>
    {% endif %}
</div>
</body>
</html>
'''

# === МАРШРУТЫ ===
@app.route('/')
def index():
    if session.get('user_id') is None:
        return render_template_string(HTML, session={}, employees=[], all_logs=[], all_bonuses=[], my_logs=[], stats={}, payments={'first': [], 'second': [], 'first_total': 0, 'second_total': 0}, events=[], calendar_days=[], chart_data=[], audit_logs=[], today=date.today().strftime('%Y-%m-%d'), selected_month=date.today().strftime('%Y-%m'), current_section='main', month_name='', current_year=0, prev_month='', next_month='', msg=request.args.get('msg'))
    
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
    chart_data = []
    audit_logs = []
    
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
        employees_raw = conn.execute("SELECT id, name, avatar FROM employees").fetchall()
        max_hours = 0
        for emp in employees_raw:
            rows_month = conn.execute(
                "SELECT hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ?",
                (emp[0], month + "%")
            ).fetchall()
            month_hours = sum(r[0] for r in rows_month)
            month_salary = sum(r[0] * r[1] for r in rows_month)
            month_konserzhka = sum(1500 for r in rows_month if r[2] == 1)
            bonus_month = conn.execute(
                "SELECT amount FROM fixed_payments WHERE employee_id=? AND payment_date LIKE ?",
                (emp[0], month + "%")
            ).fetchall()
            month_bonus = sum(b[0] for b in bonus_month)
            emp_data = {
                'id': emp[0],
                'name': emp[1],
                'avatar': emp[2] or '',
                'month_hours': month_hours,
                'month_salary': month_salary,
                'month_konserzhka': month_konserzhka,
                'month_bonus': month_bonus,
                'month_total': month_salary + month_konserzhka + month_bonus
            }
            employees.append(emp_data)
            if month_hours > max_hours:
                max_hours = month_hours
        
        if max_hours > 0:
            for emp in employees:
                percent = (emp['month_hours'] / max_hours * 100) if max_hours > 0 else 0
                chart_data.append({
                    'name': emp['name'],
                    'hours': emp['month_hours'],
                    'percent': min(percent, 100)
                })
            chart_data.sort(key=lambda x: x['hours'], reverse=True)
        
        logs = conn.execute(
            "SELECT h.work_date, e.name, h.hours, h.rate, h.konserzhka FROM hours_log h JOIN employees e ON h.employee_id=e.id WHERE h.work_date LIKE ? ORDER BY h.work_date DESC",
            (month + "%",)
        ).fetchall()
        for log in logs:
            total = log[2] * log[3] + (1500 if log[4] == 1 else 0)
            all_logs.append({
                'date': log[0],
                'date_ru': format_date_ru(log[0]),
                'employee': log[1],
                'hours': log[2],
                'rate': log[3],
                'konserzhka': log[4],
                'total': total
            })
            
            day = log[0].split('-')[2]
            period = 'first' if int(day) <= 15 else 'second'
            payments[period].append({
                'date': log[0],
                'date_ru': format_date_ru(log[0]),
                'employee': log[1],
                'hours': log[2],
                'rate': log[3],
                'konserzhka': log[4],
                'total': total
            })
            payments[period + '_total'] = payments.get(period + '_total', 0) + total
        
        bonuses = conn.execute(
            "SELECT f.payment_date, e.name, f.amount, f.description FROM fixed_payments f JOIN employees e ON f.employee_id=e.id ORDER BY f.payment_date DESC"
        ).fetchall()
        for bonus in bonuses:
            all_bonuses.append({
                'date': bonus[0],
                'date_ru': format_date_ru(bonus[0]),
                'employee': bonus[1],
                'amount': bonus[2],
                'description': bonus[3]
            })
        
        # === АУДИТ ===
        audit_raw = conn.execute(
            "SELECT admin_name, action_type, action_details, action_date FROM audit_log ORDER BY id DESC LIMIT 100"
        ).fetchall()
        for a in audit_raw:
            audit_logs.append({
                'admin_name': a[0],
                'action_type': a[1],
                'action_details': a[2],
                'date_ru': format_date_ru(a[3])
            })
        
        stats = {
            'total_employees': len(employees_raw),
            'total_hours': sum(e['month_hours'] for e in employees),
            'total_salary': sum(e['month_salary'] for e in employees),
            'total_konserzhka': sum(e['month_konserzhka'] for e in employees),
            'grand_total': sum(e['month_total'] for e in employees)
        }
        
    else:
        emp_id = session['user_id']
        logs = conn.execute(
            "SELECT work_date, hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date DESC",
            (emp_id, month + "%")
        ).fetchall()
        
        total_salary = 0
        total_konserzhka = 0
        for log in logs:
            total = log[1] * log[2] + (1500 if log[3] == 1 else 0)
            total_salary += log[1] * log[2]
            total_konserzhka += 1500 if log[3] == 1 else 0
            my_logs.append({
                'date': log[0],
                'date_ru': format_date_ru(log[0]),
                'hours': log[1],
                'rate': log[2],
                'konserzhka': log[3],
                'total': total
            })
        
        bonuses = conn.execute(
            "SELECT amount FROM fixed_payments WHERE employee_id=? AND payment_date LIKE ?",
            (emp_id, month + "%")
        ).fetchall()
        total_bonus = sum(b[0] for b in bonuses)
        
        stats = {
            'total_employees': 1,
            'total_hours': sum(l['hours'] for l in my_logs),
            'total_salary': total_salary,
            'total_konserzhka': total_konserzhka,
            'grand_total': total_salary + total_konserzhka + total_bonus
        }
    
    # Календарь
    year, month_num = map(int, month.split('-'))
    days_in_month = get_month_days(year, month_num)
    calendar_days = []
    month_name_ru = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'][month_num - 1]
    
    events_by_date = {}
    for ev in events_raw:
        events_by_date[ev[1]] = ev
    
    first_weekday = days_in_month[0].weekday()
    start_offset = (first_weekday - 0) % 7
    
    for i in range(start_offset):
        calendar_days.append({'day': '', 'is_weekend': False, 'is_today': False, 'event': None, 'date_str': ''})
    
    for d in days_in_month:
        date_str = d.strftime('%Y-%m-%d')
        is_weekend = d.weekday() >= 5
        is_today = date_str == today_str
        event = events_by_date.get(date_str)
        calendar_days.append({
            'day': d.day,
            'is_weekend': is_weekend,
            'is_today': is_today,
            'event': {'title': event[2], 'description': event[3]} if event else None,
            'date_str': date_str
        })
    
    prev_month_date = date(year, month_num, 1) - timedelta(days=1)
    next_month_date = date(year, month_num, 1) + timedelta(days=32)
    prev_month = prev_month_date.strftime('%Y-%m')
    next_month = next_month_date.strftime('%Y-%m')
    
    conn.close()
    
    return render_template_string(
        HTML,
        session=session,
        employees=employees,
        all_logs=all_logs[:200],
        all_bonuses=all_bonuses[:200],
        my_logs=my_logs,
        stats=stats,
        payments=payments,
        events=events,
        calendar_days=calendar_days,
        chart_data=chart_data,
        audit_logs=audit_logs,
        today=today_str,
        selected_month=month,
        current_section='main',
        month_name=f'{month_name_ru} {year}',
        current_year=year,
        prev_month=prev_month,
        next_month=next_month,
        msg=request.args.get('msg')
    )

@app.route('/section/<section>')
def section(section):
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='Войдите в систему!'))
    
    conn = get_db()
    today = date.today()
    month = request.args.get('month', today.strftime('%Y-%m'))
    today_str = today.strftime('%Y-%m-%d')
    
    employees = []
    all_logs = []
    all_bonuses = []
    stats = {}
    payments = {'first': [], 'second': [], 'first_total': 0, 'second_total': 0}
    chart_data = []
    events = []
    audit_logs = []
    
    events_raw = conn.execute("SELECT id, event_date, title, description FROM events ORDER BY event_date DESC").fetchall()
    for ev in events_raw:
        events.append({
            'id': ev[0],
            'date': ev[1],
            'date_ru': format_date_ru(ev[1]),
            'title': ev[2],
            'description': ev[3]
        })
    
    if session.get('is_admin'):
        employees_raw = conn.execute("SELECT id, name, avatar FROM employees").fetchall()
        max_hours = 0
        for emp in employees_raw:
            rows_month = conn.execute(
                "SELECT hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ?",
                (emp[0], month + "%")
            ).fetchall()
            month_hours = sum(r[0] for r in rows_month)
            month_salary = sum(r[0] * r[1] for r in rows_month)
            month_konserzhka = sum(1500 for r in rows_month if r[2] == 1)
            bonus_month = conn.execute(
                "SELECT amount FROM fixed_payments WHERE employee_id=? AND payment_date LIKE ?",
                (emp[0], month + "%")
            ).fetchall()
            month_bonus = sum(b[0] for b in bonus_month)
            emp_data = {
                'id': emp[0],
                'name': emp[1],
                'avatar': emp[2] or '',
                'month_hours': month_hours,
                'month_salary': month_salary,
                'month_konserzhka': month_konserzhka,
                'month_bonus': month_bonus,
                'month_total': month_salary + month_konserzhka + month_bonus
            }
            employees.append(emp_data)
            if month_hours > max_hours:
                max_hours = month_hours
        
        if max_hours > 0:
            for emp in employees:
                percent = (emp['month_hours'] / max_hours * 100) if max_hours > 0 else 0
                chart_data.append({
                    'name': emp['name'],
                    'hours': emp['month_hours'],
                    'percent': min(percent, 100)
                })
            chart_data.sort(key=lambda x: x['hours'], reverse=True)
        
        logs = conn.execute(
            "SELECT h.work_date, e.name, h.hours, h.rate, h.konserzhka FROM hours_log h JOIN employees e ON h.employee_id=e.id WHERE h.work_date LIKE ? ORDER BY h.work_date DESC",
            (month + "%",)
        ).fetchall()
        for log in logs:
            total = log[2] * log[3] + (1500 if log[4] == 1 else 0)
            all_logs.append({
                'date': log[0],
                'date_ru': format_date_ru(log[0]),
                'employee': log[1],
                'hours': log[2],
                'rate': log[3],
                'konserzhka': log[4],
                'total': total
            })
            
            day = log[0].split('-')[2]
            period = 'first' if int(day) <= 15 else 'second'
            payments[period].append({
                'date': log[0],
                'date_ru': format_date_ru(log[0]),
                'employee': log[1],
                'hours': log[2],
                'rate': log[3],
                'konserzhka': log[4],
                'total': total
            })
            payments[period + '_total'] = payments.get(period + '_total', 0) + total
        
        bonuses = conn.execute(
            "SELECT f.payment_date, e.name, f.amount, f.description FROM fixed_payments f JOIN employees e ON f.employee_id=e.id ORDER BY f.payment_date DESC"
        ).fetchall()
        for bonus in bonuses:
            all_bonuses.append({
                'date': bonus[0],
                'date_ru': format_date_ru(bonus[0]),
                'employee': bonus[1],
                'amount': bonus[2],
                'description': bonus[3]
            })
        
        # === АУДИТ ===
        audit_raw = conn.execute(
            "SELECT admin_name, action_type, action_details, action_date FROM audit_log ORDER BY id DESC LIMIT 100"
        ).fetchall()
        for a in audit_raw:
            audit_logs.append({
                'admin_name': a[0],
                'action_type': a[1],
                'action_details': a[2],
                'date_ru': format_date_ru(a[3])
            })
        
        stats = {
            'total_employees': len(employees_raw),
            'total_hours': sum(e['month_hours'] for e in employees),
            'total_salary': sum(e['month_salary'] for e in employees),
            'total_konserzhka': sum(e['month_konserzhka'] for e in employees),
            'grand_total': sum(e['month_total'] for e in employees)
        }
    else:
        emp_id = session['user_id']
        logs = conn.execute(
            "SELECT work_date, hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date DESC",
            (emp_id, month + "%")
        ).fetchall()
        for log in logs:
            total = log[1] * log[2] + (1500 if log[3] == 1 else 0)
            all_logs.append({
                'date': log[0],
                'date_ru': format_date_ru(log[0]),
                'employee': session['user_name'],
                'hours': log[1],
                'rate': log[2],
                'konserzhka': log[3],
                'total': total
            })
            
            day = log[0].split('-')[2]
            period = 'first' if int(day) <= 15 else 'second'
            payments[period].append({
                'date': log[0],
                'date_ru': format_date_ru(log[0]),
                'employee': session['user_name'],
                'hours': log[1],
                'rate': log[2],
                'konserzhka': log[3],
                'total': total
            })
            payments[period + '_total'] = payments.get(period + '_total', 0) + total
    
    # Календарь
    year, month_num = map(int, month.split('-'))
    days_in_month = get_month_days(year, month_num)
    calendar_days = []
    month_name_ru = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'][month_num - 1]
    
    events_by_date = {}
    for ev in events_raw:
        events_by_date[ev[1]] = ev
    
    first_weekday = days_in_month[0].weekday()
    start_offset = (first_weekday - 0) % 7
    
    for i in range(start_offset):
        calendar_days.append({'day': '', 'is_weekend': False, 'is_today': False, 'event': None, 'date_str': ''})
    
    for d in days_in_month:
        date_str = d.strftime('%Y-%m-%d')
        is_weekend = d.weekday() >= 5
        is_today = date_str == today_str
        event = events_by_date.get(date_str)
        calendar_days.append({
            'day': d.day,
            'is_weekend': is_weekend,
            'is_today': is_today,
            'event': {'title': event[2], 'description': event[3]} if event else None,
            'date_str': date_str
        })
    
    prev_month_date = date(year, month_num, 1) - timedelta(days=1)
    next_month_date = date(year, month_num, 1) + timedelta(days=32)
    prev_month = prev_month_date.strftime('%Y-%m')
    next_month = next_month_date.strftime('%Y-%m')
    
    conn.close()
    
    return render_template_string(
        HTML,
        session=session,
        employees=employees,
        all_logs=all_logs[:200],
        all_bonuses=all_bonuses[:200],
        my_logs=[],
        stats=stats,
        payments=payments,
        events=events,
        calendar_days=calendar_days,
        chart_data=chart_data,
        audit_logs=audit_logs,
        today=today_str,
        selected_month=month,
        current_section=section,
        month_name=f'{month_name_ru} {year}',
        current_year=year,
        prev_month=prev_month,
        next_month=next_month,
        msg=request.args.get('msg')
    )

@app.route('/employee/<int:emp_id>')
def employee_detail(emp_id):
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='Войдите в систему!'))
    
    if not session.get('is_admin') and session['user_id'] != emp_id:
        return redirect(url_for('index', msg='Нет доступа!'))
    
    conn = get_db()
    today = date.today()
    month = request.args.get('month', today.strftime('%Y-%m'))
    
    employee = conn.execute("SELECT id, name, avatar FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not employee:
        conn.close()
        return redirect(url_for('index', msg='Сотрудник не найден!'))
    
    logs_raw = conn.execute(
        "SELECT work_date, hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date DESC",
        (emp_id, month + "%")
    ).fetchall()
    
    logs = []
    total_salary = 0
    total_konserzhka = 0
    for log in logs_raw:
        total = log[1] * log[2] + (1500 if log[3] == 1 else 0)
        total_salary += log[1] * log[2]
        total_konserzhka += 1500 if log[3] == 1 else 0
        logs.append({
            'date': log[0],
            'date_ru': format_date_ru(log[0]),
            'hours': log[1],
            'rate': log[2],
            'konserzhka': log[3],
            'total': total
        })
    
    bonuses_raw = conn.execute(
        "SELECT payment_date, amount, description FROM fixed_payments WHERE employee_id=? ORDER BY payment_date DESC",
        (emp_id,)
    ).fetchall()
    bonuses = []
    total_bonus = 0
    for bonus in bonuses_raw:
        total_bonus += bonus[1]
        bonuses.append({
            'date': bonus[0],
            'date_ru': format_date_ru(bonus[0]),
            'amount': bonus[1],
            'description': bonus[2]
        })
    
    month_hours = sum(l['hours'] for l in logs)
    month_total = total_salary + total_konserzhka + total_bonus
    
    all_logs = conn.execute(
        "SELECT hours, rate, konserzhka FROM hours_log WHERE employee_id=?",
        (emp_id,)
    ).fetchall()
    total_hours = sum(l[0] for l in all_logs)
    total_salary_all = sum(l[0] * l[1] for l in all_logs)
    total_konserzhka_all = sum(1500 for l in all_logs if l[2] == 1)
    
    all_bonuses = conn.execute(
        "SELECT amount FROM fixed_payments WHERE employee_id=?",
        (emp_id,)
    ).fetchall()
    total_bonus_all = sum(b[0] for b in all_bonuses)
    
    grand_total = total_salary_all + total_konserzhka_all + total_bonus_all
    
    conn.close()
    
    return render_template_string(
        EMPLOYEE_HTML,
        employee={'id': employee[0], 'name': employee[1], 'avatar': employee[2] or ''},
        logs=logs,
        bonuses=bonuses,
        total_hours=total_hours,
        total_salary=total_salary_all,
        total_konserzhka=total_konserzhka_all,
        total_bonus=total_bonus_all,
        grand_total=grand_total,
        month_hours=month_hours,
        month_konserzhka=total_konserzhka,
        month_total=month_total,
        selected_month=month,
        msg=request.args.get('msg')
    )

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
    employee = conn.execute("SELECT id, name, password FROM employees WHERE name=?", (name,)).fetchone()
    conn.close()
    
    if not employee:
        return redirect(url_for('index', msg='Сотрудник не найден!'))
    
    if employee[2] != password:
        return redirect(url_for('index', msg='Неверный пароль!'))
    
    session.permanent = True
    session['user_id'] = employee[0]
    session['user_name'] = employee[1]
    session['is_admin'] = False
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
        conn.execute("INSERT INTO employees (name, password) VALUES (?, ?)", (name, password))
        conn.commit()
        msg = f"Сотрудник {name} добавлен!"
        # Логируем действие
        log_audit(session['user_id'], session['user_name'], 'Добавление сотрудника', f'{name}')
    except sqlite3.IntegrityError:
        msg = f"Сотрудник '{name}' уже существует!"
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    conn.close()
    
    return redirect(url_for('section', section='add', msg=msg))

@app.route('/delete_employee', methods=['POST'])
def delete_employee():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='Только админ может удалять сотрудников!'))
    
    emp_id = int(request.form['emp_id'])
    conn = get_db()
    name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
    try:
        conn.execute("DELETE FROM hours_log WHERE employee_id=?", (emp_id,))
        conn.execute("DELETE FROM fixed_payments WHERE employee_id=?", (emp_id,))
        conn.execute("DELETE FROM employees WHERE id=?", (emp_id,))
        conn.commit()
        msg = f"Сотрудник {name} удалён!"
        log_audit(session['user_id'], session['user_name'], 'Удаление сотрудника', f'{name}')
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('section', section='employees', msg=msg))

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
        log_audit(session['user_id'], session['user_name'], 'Добавление мероприятия', f'{title} ({format_date_ru(event_date)})')
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('section', section='events', msg=msg))

@app.route('/delete_event', methods=['POST'])
def delete_event():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='Только админ может удалять мероприятия!'))
    
    event_id = int(request.form['event_id'])
    conn = get_db()
    try:
        title = conn.execute("SELECT title FROM events WHERE id=?", (event_id,)).fetchone()[0]
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        conn.commit()
        msg = "Мероприятие удалено!"
        log_audit(session['user_id'], session['user_name'], 'Удаление мероприятия', f'{title}')
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('section', section='events', msg=msg))

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
        name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
        conn.execute(
            "INSERT INTO hours_log (employee_id, work_date, hours, rate, konserzhka) VALUES (?, ?, ?, ?, ?)",
            (emp_id, work_date, hours, rate, konserzhka)
        )
        conn.commit()
        conn.close()
        
        total = hours * rate + (1500 if konserzhka else 0)
        msg = f"{name} ({format_date_ru(work_date)}): {hours}ч × {rate}₽ = {hours*rate}₽" + (" (+1500 консержка)" if konserzhka else "")
        log_audit(session['user_id'], session['user_name'], 'Добавление часов', f'{name} — {hours}ч ({format_date_ru(work_date)})')
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    
    return redirect(url_for('section', section='add', msg=msg))

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
        name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
        conn.execute(
            "INSERT INTO fixed_payments (employee_id, payment_date, amount, description) VALUES (?, ?, ?, ?)",
            (emp_id, payment_date, amount, description)
        )
        conn.commit()
        conn.close()
        
        msg = f"{name}: премия {amount}₽ ({description or 'без описания'})"
        log_audit(session['user_id'], session['user_name'], 'Добавление премии', f'{name} — {amount}₽')
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    
    return redirect(url_for('section', section='bonus', msg=msg))

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='Только админ может менять аватарки!'))
    
    emp_id = int(request.form['emp_id'])
    if 'avatar' not in request.files:
        return redirect(url_for('index', msg='Файл не выбран!'))
    
    file = request.files['avatar']
    if file.filename == '':
        return redirect(url_for('index', msg='Файл не выбран!'))
    
    if file:
        # Читаем файл и кодируем в base64
        file_data = file.read()
        base64_data = base64.b64encode(file_data).decode('utf-8')
        
        conn = get_db()
        conn.execute("UPDATE employees SET avatar = ? WHERE id = ?", (base64_data, emp_id))
        conn.commit()
        name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
        conn.close()
        
        msg = f"Аватар для {name} обновлён!"
        log_audit(session['user_id'], session['user_name'], 'Обновление аватара', f'{name}')
    else:
        msg = "Ошибка загрузки файла!"
    
    return redirect(url_for('section', section='employees', msg=msg))

@app.route('/export')
def export():
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='Войдите в систему!'))
    
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='Только администратор может экспортировать данные!'))
    
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    
    conn = get_db()
    logs = conn.execute(
        "SELECT h.work_date, e.name, h.hours, h.rate, h.konserzhka FROM hours_log h JOIN employees e ON h.employee_id=e.id WHERE h.work_date LIKE ? ORDER BY h.work_date",
        (month + "%",)
    ).fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Дата', 'Сотрудник', 'Часы', 'Ставка', 'Консержка', 'Итого'])
    
    for log in logs:
        total = log[2] * log[3] + (1500 if log[4] == 1 else 0)
        writer.writerow([
            format_date_ru(log[0]),
            log[1],
            log[2],
            f"{log[3]} ₽/ч",
            'Да' if log[4] == 1 else 'Нет',
            total
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'zarplata_{month}.csv'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

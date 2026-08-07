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

# === ГЛАВНАЯ СТРАНИЦА ===
HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎵 Зарплата Клуб</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            padding: 20px;
            position: relative;
            overflow-x: hidden;
        }
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(ellipse at 20% 50%, rgba(157, 78, 221, 0.15) 0%, transparent 60%),
                radial-gradient(ellipse at 80% 50%, rgba(255, 107, 107, 0.10) 0%, transparent 60%),
                radial-gradient(ellipse at 50% 100%, rgba(255, 217, 61, 0.08) 0%, transparent 40%),
                repeating-linear-gradient(0deg, transparent, transparent 50px, rgba(255,255,255,0.01) 50px, rgba(255,255,255,0.01) 51px),
                repeating-linear-gradient(90deg, transparent, transparent 50px, rgba(255,255,255,0.01) 50px, rgba(255,255,255,0.01) 51px);
            z-index: 0;
            pointer-events: none;
        }
        .disco-ball {
            position: fixed;
            border-radius: 50%;
            pointer-events: none;
            z-index: 0;
            opacity: 0.08;
        }
        .disco-ball.d1 { width: 400px; height: 400px; top: -100px; right: -100px; background: radial-gradient(circle, #9d4edd, transparent); animation: pulseGlow 8s ease-in-out infinite; }
        .disco-ball.d2 { width: 500px; height: 500px; bottom: -150px; left: -150px; background: radial-gradient(circle, #ff6b6b, transparent); animation: pulseGlow 10s ease-in-out infinite reverse; }
        .disco-ball.d3 { width: 250px; height: 250px; top: 50%; left: 50%; background: radial-gradient(circle, #ffd93d, transparent); transform: translate(-50%, -50%); animation: pulseGlow 6s ease-in-out infinite; }
        @keyframes pulseGlow {
            0%, 100% { opacity: 0.05; transform: scale(1); }
            50% { opacity: 0.12; transform: scale(1.1); }
        }
        .float-icon {
            position: fixed;
            font-size: 30px;
            opacity: 0.06;
            pointer-events: none;
            z-index: 0;
            animation: floatIcon 10s ease-in-out infinite;
        }
        .float-icon:nth-child(1) { top: 15%; left: 5%; animation-delay: 0s; }
        .float-icon:nth-child(2) { top: 75%; right: 8%; animation-delay: 3s; font-size: 24px; }
        .float-icon:nth-child(3) { bottom: 25%; left: 15%; animation-delay: 5s; font-size: 40px; }
        .float-icon:nth-child(4) { top: 45%; right: 15%; animation-delay: 2s; font-size: 20px; }
        .float-icon:nth-child(5) { top: 10%; right: 30%; animation-delay: 4s; font-size: 18px; }
        .float-icon:nth-child(6) { bottom: 10%; right: 25%; animation-delay: 1s; font-size: 28px; }
        @keyframes floatIcon {
            0%, 100% { transform: translateY(0) rotate(0deg) scale(1); }
            50% { transform: translateY(-25px) rotate(10deg) scale(1.1); }
        }
        .container {
            max-width: 1300px;
            margin: 0 auto;
            background: rgba(255,255,255,0.96);
            border-radius: 30px;
            padding: 30px;
            box-shadow: 0 30px 80px rgba(0,0,0,0.7);
            animation: slideIn 0.6s ease;
            position: relative;
            z-index: 1;
            backdrop-filter: blur(10px);
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(-50px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.02); }
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid rgba(157, 78, 221, 0.15);
        }
        .header .logo {
            font-size: 50px;
            display: block;
            animation: floatIcon 4s ease-in-out infinite;
        }
        h1 {
            font-size: 2.8em;
            font-weight: 900;
            background: linear-gradient(135deg, #9d4edd 0%, #ff6b6b 50%, #ffd93d 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 3px;
            letter-spacing: 4px;
            text-transform: uppercase;
        }
        .subtitle {
            color: #888;
            font-size: 1.05em;
            font-weight: 400;
        }
        .subtitle span { color: #9d4edd; font-weight: 700; }
        
        .events-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }
        .event-card {
            background: linear-gradient(135deg, #9d4edd10 0%, #ff6b6b10 100%);
            padding: 18px 20px;
            border-radius: 16px;
            border: 1px solid rgba(157, 78, 221, 0.15);
            transition: all 0.3s ease;
            text-align: center;
        }
        .event-card:hover {
            transform: translateY(-4px) scale(1.02);
            box-shadow: 0 8px 30px rgba(157, 78, 221, 0.2);
        }
        .event-card .event-date {
            font-size: 13px;
            color: #9d4edd;
            font-weight: 700;
        }
        .event-card .event-title {
            font-size: 22px;
            font-weight: 800;
            color: #333;
            margin: 5px 0;
        }
        .event-card .event-desc {
            font-size: 13px;
            color: #888;
        }
        .event-card .event-emoji {
            font-size: 32px;
            display: block;
            margin-bottom: 5px;
        }
        .add-event-form {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
            margin-top: 10px;
        }
        .add-event-form input {
            padding: 10px 14px;
            border: 2px solid #e0ddf0;
            border-radius: 12px;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            transition: all 0.3s ease;
            flex: 1;
            min-width: 120px;
            background: white;
        }
        .add-event-form input:focus {
            outline: none;
            border-color: #9d4edd;
            box-shadow: 0 0 0 4px rgba(157, 78, 221, 0.15);
        }
        .add-event-form input[type="date"] { min-width: 160px; cursor: pointer; }
        .btn {
            padding: 11px 24px;
            border: none;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 700;
            font-family: 'Inter', sans-serif;
            cursor: pointer;
            transition: all 0.3s ease;
            color: white;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            flex: 0 0 auto;
        }
        .btn:hover { transform: translateY(-3px) scale(1.02); box-shadow: 0 8px 25px rgba(0,0,0,0.25); }
        .btn:active { transform: scale(0.95); }
        .btn-purple { background: linear-gradient(135deg, #9d4edd 0%, #5a189a 100%); }
        .btn-green { background: linear-gradient(135deg, #6bcb77 0%, #2d8f47 100%); }
        .btn-gold { background: linear-gradient(135deg, #ffd93d 0%, #f6b93b 100%); color: #333; }
        .btn-red { background: linear-gradient(135deg, #ff6b6b 0%, #c0392b 100%); }
        .btn-sm { padding: 6px 14px; font-size: 12px; }
        .btn-pink { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); }
        
        .card {
            background: #f8f6ff;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid #9d4edd;
            transition: all 0.3s ease;
        }
        .card:hover { border-left-width: 6px; }
        .card h3 {
            color: #333;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 700;
            font-size: 1.2em;
        }
        .card h3 .icon { font-size: 24px; }
        .card.green { border-left-color: #6bcb77; }
        .card.pink { border-left-color: #ff6b6b; }
        .card.gold { border-left-color: #ffd93d; }
        .card.blue { border-left-color: #4facfe; }
        .card.red { border-left-color: #dc3545; }
        
        .form-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }
        input, select, textarea {
            padding: 11px 16px;
            border: 2px solid #e0ddf0;
            border-radius: 12px;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            transition: all 0.3s ease;
            flex: 1;
            min-width: 120px;
            background: white;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #9d4edd;
            box-shadow: 0 0 0 4px rgba(157, 78, 221, 0.15);
        }
        input[type="date"] { min-width: 160px; cursor: pointer; }
        input[type="checkbox"] {
            width: 22px;
            height: 22px;
            flex: 0 0 auto;
            min-width: unset;
            accent-color: #9d4edd;
            cursor: pointer;
        }
        .table-wrapper { overflow-x: auto; border-radius: 12px; }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        table th {
            background: linear-gradient(135deg, #9d4edd 0%, #5a189a 100%);
            color: white;
            padding: 11px 12px;
            text-align: left;
            font-weight: 700;
            font-size: 13px;
            text-transform: uppercase;
        }
        table td {
            padding: 10px 12px;
            border-bottom: 1px solid #eee;
        }
        table tr { transition: 0.2s; }
        table tr:hover { background: #f0edff; }
        .badge {
            display: inline-block;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
        }
        .badge-purple { background: #e8d5f5; color: #6c3483; }
        .badge-gold { background: #fff3cd; color: #856404; }
        .badge-red { background: #f8d7da; color: #721c24; }
        .badge-green { background: #d4edda; color: #155724; }
        .konserzhka-badge {
            display: inline-block;
            background: #ffd93d30;
            color: #856404;
            padding: 3px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
        }
        .rate-badge {
            display: inline-block;
            padding: 3px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
        }
        .rate-badge.r400 { background: #d4edda; color: #155724; }
        .rate-badge.r350 { background: #fff3cd; color: #856404; }
        .payment-period {
            display: inline-block;
            padding: 3px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
        }
        .payment-period.first { background: #d4edda; color: #155724; }
        .payment-period.second { background: #fff3cd; color: #856404; }
        .alert {
            padding: 14px 20px;
            border-radius: 14px;
            margin: 12px 0;
            animation: pulse 2s infinite;
            font-weight: 600;
        }
        .alert-success { background: #d4edda; color: #155724; border-left: 5px solid #28a745; }
        .alert-danger { background: #f8d7da; color: #721c24; border-left: 5px solid #dc3545; }
        .tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        .tab {
            padding: 10px 22px;
            border-radius: 25px;
            background: #f0edff;
            cursor: pointer;
            font-weight: 700;
            font-size: 14px;
            transition: all 0.3s ease;
            border: 2px solid transparent;
            font-family: 'Inter', sans-serif;
        }
        .tab:hover:not(.active) { background: #e0dbf5; transform: translateY(-2px); }
        .tab.active {
            background: linear-gradient(135deg, #9d4edd 0%, #5a189a 100%);
            color: white;
            border-color: #9d4edd;
            box-shadow: 0 4px 20px rgba(157, 78, 221, 0.3);
        }
        .hidden { display: none !important; }
        .month-selector {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }
        .month-selector input[type="month"] {
            flex: 0 0 auto;
            min-width: 180px;
        }
        .total-row {
            background: #f0edff !important;
            font-weight: 700;
        }
        .total-row td { border-top: 2px solid #9d4edd; }
        .clickable-row {
            cursor: pointer;
            transition: 0.2s;
        }
        .clickable-row:hover {
            background: #e8d5f5 !important;
            transform: scale(1.01);
        }
        .back-link {
            display: inline-block;
            margin-bottom: 15px;
            color: #9d4edd;
            font-weight: 700;
            text-decoration: none;
            font-size: 16px;
            transition: 0.3s;
        }
        .back-link:hover {
            transform: translateX(-5px);
            color: #5a189a;
        }
        .logout-btn {
            float: right;
            background: #ff6b6b;
            padding: 8px 16px;
            border-radius: 12px;
            color: white;
            text-decoration: none;
            font-weight: 700;
            transition: 0.3s;
            font-size: 14px;
        }
        .logout-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 15px rgba(255, 107, 107, 0.4);
        }
        .employee-card {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: white;
            border-radius: 12px;
            margin-bottom: 8px;
            border: 1px solid #e0ddf0;
            transition: 0.3s;
        }
        .employee-card:hover {
            border-color: #9d4edd;
            box-shadow: 0 4px 15px rgba(157, 78, 221, 0.15);
        }
        .employee-card .name {
            font-weight: 700;
            font-size: 16px;
        }
        .employee-card .stats {
            color: #888;
            font-size: 14px;
        }
        .employee-card .stats strong {
            color: #333;
        }
        .employee-card .actions {
            display: flex;
            gap: 6px;
        }
        .delete-btn {
            background: none;
            border: none;
            color: #ff6b6b;
            cursor: pointer;
            font-size: 18px;
            transition: 0.3s;
            padding: 0 5px;
        }
        .delete-btn:hover {
            transform: scale(1.2);
            color: #c0392b;
        }
        .period-group {
            margin-bottom: 15px;
        }
        .period-group h4 {
            color: #555;
            margin-bottom: 8px;
            font-size: 14px;
            padding: 8px 12px;
            border-radius: 10px;
        }
        .period-group h4.first { background: #d4edda; color: #155724; }
        .period-group h4.second { background: #fff3cd; color: #856404; }
        .delete-event {
            background: none;
            border: none;
            color: #ff6b6b;
            cursor: pointer;
            font-size: 16px;
            transition: 0.3s;
            padding: 0 5px;
        }
        .delete-event:hover {
            transform: scale(1.2);
            color: #c0392b;
        }
        .event-card .actions {
            margin-top: 8px;
        }
        @media (max-width: 700px) {
            .container { padding: 15px; }
            h1 { font-size: 2em; }
            .form-group { flex-direction: column; }
            .btn { width: 100%; justify-content: center; }
            .logout-btn { float: none; display: block; text-align: center; margin-bottom: 10px; }
            .employee-card { flex-direction: column; align-items: stretch; gap: 8px; }
            .employee-card .actions { justify-content: flex-end; }
            .events-grid { grid-template-columns: 1fr 1fr; }
        }
    </style>
</head>
<body>

<div class="disco-ball d1"></div>
<div class="disco-ball d2"></div>
<div class="disco-ball d3"></div>
<div class="float-icon">🎵</div>
<div class="float-icon">🎶</div>
<div class="float-icon">✨</div>
<div class="float-icon">🎧</div>
<div class="float-icon">🌟</div>
<div class="float-icon">💫</div>

<div class="container">
    <div class="header">
        <span class="logo">🏢</span>
        <h1>ЗАРПЛАТА КЛУБ</h1>
        <p class="subtitle">🎵 Учёт зарплаты · Ставка <span>400</span> или <span>350</span> ₽/ч · Консержка <span>+1500 ₽</span></p>
    </div>

    {% if session.get('user_id') is none %}
    <!-- ВХОД -->
    <div class="card" style="border-left-color: #4facfe;">
        <h3><span class="icon">🔐</span> Вход</h3>
        <form method="POST" action="/login" class="form-group">
            <input type="text" name="name" placeholder="Имя" required style="flex:1;">
            <input type="password" name="password" placeholder="Пароль" required style="flex:1;">
            <button type="submit" class="btn" style="background:linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">🚪 Войти</button>
        </form>
        {% if msg %}
        <div class="alert alert-danger">{{ msg }}</div>
        {% endif %}
    </div>
    {% else %}
    
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:15px;">
        <div style="font-weight:700;font-size:18px;color:#333;">
            👋 Добро пожаловать, <span style="color:#9d4edd;">{{ session.user_name }}</span>
            <span style="font-size:14px;color:#888;font-weight:400;margin-left:10px;">
                {% if session.is_admin %}👑 Админ{% endif %}
            </span>
        </div>
        <a href="/logout" class="logout-btn">🚪 Выйти</a>
    </div>

    <!-- ===== МЕРОПРИЯТИЯ (вместо статистики) ===== -->
    <div class="card" style="border-left-color: #ffd93d;">
        <h3><span class="icon">📅</span> Мероприятия</h3>
        <div class="events-grid">
            {% for event in events %}
            <div class="event-card">
                <span class="event-emoji">🎉</span>
                <div class="event-date">{{ event.date_ru }}</div>
                <div class="event-title">{{ event.title }}</div>
                <div class="event-desc">{{ event.description or '' }}</div>
                {% if session.is_admin %}
                <div class="actions">
                    <form method="POST" action="/delete_event" style="display:inline;" onsubmit="return confirm('Удалить мероприятие?')">
                        <input type="hidden" name="event_id" value="{{ event.id }}">
                        <button type="submit" class="delete-event" title="Удалить">🗑️</button>
                    </form>
                </div>
                {% endif %}
            </div>
            {% else %}
            <p style="color:#999;grid-column:1/-1;text-align:center;padding:15px;">📭 Нет мероприятий</p>
            {% endfor %}
        </div>
        {% if session.is_admin %}
        <form method="POST" action="/add_event" class="add-event-form">
            <input type="date" name="event_date" value="{{ today }}" required>
            <input type="text" name="title" placeholder="Название (например, PIZZA)" required>
            <input type="text" name="description" placeholder="Описание (необязательно)">
            <button type="submit" class="btn btn-gold">➕ Добавить</button>
        </form>
        {% endif %}
    </div>

    {% if session.is_admin %}
    <!-- ====== АДМИН ====== -->
    <div class="tabs">
        <div class="tab active" onclick="switchTab('admin_employees')">👥 Сотрудники</div>
        <div class="tab" onclick="switchTab('admin_hours')">⏱ Часы</div>
        <div class="tab" onclick="switchTab('admin_payments')">📅 Выплаты</div>
        <div class="tab" onclick="switchTab('admin_bonus')">🎁 Премии</div>
        <div class="tab" onclick="switchTab('admin_add')">➕ Добавить</div>
    </div>

    <!-- ВКЛАДКА: СОТРУДНИКИ -->
    <div id="tab-admin_employees">
        <div class="card">
            <h3><span class="icon">👥</span> Все сотрудники</h3>
            <p style="color:#888;margin-bottom:12px;font-size:14px;">📌 Нажмите на сотрудника для просмотра деталей</p>
            {% if employees %}
            {% for emp in employees %}
            <div class="employee-card">
                <div class="name" onclick="window.location.href='/employee/{{ emp.id }}'" style="cursor:pointer;flex:1;">
                    {{ emp.name }}
                </div>
                <div class="stats">
                    ⏱ <strong>{{ emp.month_hours|round(1) }}</strong> ч · 
                    🥫 <strong>{{ emp.month_konserzhka }}</strong> · 
                    💰 <strong>{{ emp.month_total|round(0) }}</strong> ₽
                </div>
                <div class="actions">
                    <form method="POST" action="/delete_employee" onsubmit="return confirm('Удалить {{ emp.name }}? Все данные будут потеряны!')">
                        <input type="hidden" name="emp_id" value="{{ emp.id }}">
                        <button type="submit" class="delete-btn" title="Удалить сотрудника">🗑️</button>
                    </form>
                </div>
            </div>
            {% endfor %}
            {% else %}
            <p style="text-align:center;color:#999;padding:20px;">😴 Нет сотрудников</p>
            {% endif %}
        </div>
    </div>

    <!-- ВКЛАДКА: ЧАСЫ -->
    <div id="tab-admin_hours" class="hidden">
        <div class="card pink">
            <h3><span class="icon">⏱</span> Все часы по дням</h3>
            <div class="month-selector">
                <form method="GET" action="/" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                    <input type="month" name="month" value="{{ selected_month }}">
                    <button type="submit" class="btn btn-purple btn-sm">Показать</button>
                </form>
            </div>
            {% if all_logs %}
            <div class="table-wrapper">
                <table>
                    <tr><th>Дата</th><th>Сотрудник</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
                    {% for log in all_logs %}
                    <tr>
                        <td>{{ log.date_ru }}</td>
                        <td><span class="badge badge-purple">{{ log.employee }}</span></td>
                        <td>{{ log.hours }}</td>
                        <td><span class="rate-badge r{{ log.rate|int }}">{{ log.rate }} ₽/ч</span></td>
                        <td>{% if log.konserzhka %}🥫 +1500 ₽{% else %}—{% endif %}</td>
                        <td><strong>{{ log.total }} ₽</strong></td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
            {% else %}
            <p style="text-align:center;color:#999;padding:20px;">📭 Нет записей</p>
            {% endif %}
        </div>
    </div>

    <!-- ВКЛАДКА: ВЫПЛАТЫ -->
    <div id="tab-admin_payments" class="hidden">
        <div class="card gold">
            <h3><span class="icon">📅</span> Выплаты по периодам (1–15 и 16–конец)</h3>
            <div class="month-selector">
                <form method="GET" action="/" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                    <input type="month" name="month" value="{{ selected_month }}">
                    <button type="submit" class="btn btn-purple btn-sm">Показать</button>
                </form>
            </div>
            
            <div class="period-group">
                <h4 class="first">📆 1–15 число</h4>
                {% if payments.first %}
                <div class="table-wrapper">
                    <table>
                        <tr><th>Дата</th><th>Сотрудник</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
                        {% for p in payments.first %}
                        <tr>
                            <td>{{ p.date_ru }}</td>
                            <td><span class="badge badge-purple">{{ p.employee }}</span></td>
                            <td>{{ p.hours }}</td>
                            <td><span class="rate-badge r{{ p.rate|int }}">{{ p.rate }} ₽/ч</span></td>
                            <td>{% if p.konserzhka %}🥫 +1500{% else %}—{% endif %}</td>
                            <td><strong>{{ p.total }} ₽</strong></td>
                        </tr>
                        {% endfor %}
                        <tr class="total-row">
                            <td colspan="5"><strong>ИТОГО за период</strong></td>
                            <td><strong>{{ payments.first_total|round(0) }} ₽</strong></td>
                        </tr>
                    </table>
                </div>
                {% else %}
                <p style="color:#999;font-size:13px;">Нет записей за этот период</p>
                {% endif %}
            </div>
            
            <div class="period-group">
                <h4 class="second">📆 16–конец месяца</h4>
                {% if payments.second %}
                <div class="table-wrapper">
                    <table>
                        <tr><th>Дата</th><th>Сотрудник</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
                        {% for p in payments.second %}
                        <tr>
                            <td>{{ p.date_ru }}</td>
                            <td><span class="badge badge-purple">{{ p.employee }}</span></td>
                            <td>{{ p.hours }}</td>
                            <td><span class="rate-badge r{{ p.rate|int }}">{{ p.rate }} ₽/ч</span></td>
                            <td>{% if p.konserzhka %}🥫 +1500{% else %}—{% endif %}</td>
                            <td><strong>{{ p.total }} ₽</strong></td>
                        </tr>
                        {% endfor %}
                        <tr class="total-row">
                            <td colspan="5"><strong>ИТОГО за период</strong></td>
                            <td><strong>{{ payments.second_total|round(0) }} ₽</strong></td>
                        </tr>
                    </table>
                </div>
                {% else %}
                <p style="color:#999;font-size:13px;">Нет записей за этот период</p>
                {% endif %}
            </div>
        </div>
    </div>

    <!-- ВКЛАДКА: ПРЕМИИ (вместо бонусов) -->
    <div id="tab-admin_bonus" class="hidden">
        <div class="card" style="border-left-color: #ffd93d;">
            <h3><span class="icon">🎁</span> Премии</h3>
            <form method="POST" action="/add_bonus" class="form-group" style="margin-bottom:15px;">
                <select name="emp_id" required>
                    <option value="">Выберите сотрудника</option>
                    {% for emp in employees %}
                    <option value="{{ emp.id }}">{{ emp.name }}</option>
                    {% endfor %}
                </select>
                <input type="number" name="amount" placeholder="Сумма ₽" step="0.1" required>
                <input type="text" name="description" placeholder="Описание">
                <input type="date" name="payment_date" value="{{ today }}">
                <button type="submit" class="btn" style="background:linear-gradient(135deg, #ffd93d 0%, #f6b93b 100%);color:#333;">🎁 Добавить</button>
            </form>
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
            <p style="color:#999;">🎁 Пока нет премий</p>
            {% endif %}
        </div>
    </div>

    <!-- ВКЛАДКА: ДОБАВИТЬ -->
    <div id="tab-admin_add" class="hidden">
        <div class="card green">
            <h3><span class="icon">👤</span> Новый сотрудник</h3>
            <form method="POST" action="/add_employee" class="form-group">
                <input type="text" name="name" placeholder="Имя" required>
                <input type="password" name="password" placeholder="Пароль" required>
                <button type="submit" class="btn btn-green">➕ Добавить</button>
            </form>
        </div>
        
        <div class="card" style="border-left-color: #6bcb77;">
            <h3><span class="icon">⏱</span> Добавить часы сотруднику</h3>
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
                    🥫 Консержка (+1500)
                </label>
                <button type="submit" class="btn btn-green">⏱ Добавить</button>
            </form>
        </div>
    </div>

    {% else %}
    <!-- ====== СОТРУДНИК ====== -->
    <div class="card">
        <h3><span class="icon">👤</span> Мои данные</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:15px;">
            <div style="background:white;padding:12px;border-radius:12px;text-align:center;border:1px solid #e0ddf0;">
                <div style="font-size:12px;color:#888;">⏱ Часов (мес)</div>
                <div style="font-size:24px;font-weight:800;color:#9d4edd;">{{ stats.total_hours|round(1) if stats else 0 }}</div>
            </div>
            <div style="background:white;padding:12px;border-radius:12px;text-align:center;border:1px solid #e0ddf0;">
                <div style="font-size:12px;color:#888;">💰 Зарплата (мес)</div>
                <div style="font-size:24px;font-weight:800;color:#9d4edd;">{{ stats.total_salary|round(0) if stats else 0 }} ₽</div>
            </div>
            <div style="background:white;padding:12px;border-radius:12px;text-align:center;border:1px solid #e0ddf0;">
                <div style="font-size:12px;color:#888;">🥫 Консержек</div>
                <div style="font-size:24px;font-weight:800;color:#9d4edd;">{{ stats.total_konserzhka if stats else 0 }}</div>
            </div>
            <div style="background:white;padding:12px;border-radius:12px;text-align:center;border:1px solid #e0ddf0;">
                <div style="font-size:12px;color:#888;">💎 ИТОГО</div>
                <div style="font-size:24px;font-weight:800;color:#9d4edd;">{{ stats.grand_total|round(0) if stats else 0 }} ₽</div>
            </div>
        </div>
        
        <h4 style="margin-top:10px;color:#333;">📅 Мои часы по дням</h4>
        <div class="month-selector">
            <form method="GET" action="/" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                <input type="month" name="month" value="{{ selected_month }}">
                <button type="submit" class="btn btn-purple btn-sm">Показать</button>
            </form>
        </div>
        {% if my_logs %}
        <div class="table-wrapper">
            <table>
                <tr><th>Дата</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
                {% for log in my_logs %}
                <tr>
                    <td>{{ log.date_ru }}</td>
                    <td>{{ log.hours }}</td>
                    <td><span class="rate-badge r{{ log.rate|int }}">{{ log.rate }} ₽/ч</span></td>
                    <td>{% if log.konserzhka %}🥫 +1500 ₽{% else %}—{% endif %}</td>
                    <td><strong>{{ log.total }} ₽</strong></td>
                </tr>
                {% endfor %}
                <tr class="total-row">
                    <td><strong>ИТОГО</strong></td>
                    <td><strong>{{ stats.total_hours|round(1) if stats else 0 }}</strong></td>
                    <td></td>
                    <td><strong>{{ stats.total_konserzhka if stats else 0 }}</strong></td>
                    <td><strong>{{ stats.total_salary|round(0) if stats else 0 }} ₽</strong></td>
                </tr>
            </table>
        </div>
        {% else %}
        <p style="color:#999;">📭 Нет записей за этот месяц</p>
        {% endif %}
        
        <div style="margin-top:15px;padding-top:15px;border-top:1px solid #eee;background:#f8f8f8;border-radius:12px;padding:15px;text-align:center;">
            <p style="color:#888;font-size:14px;">
                🔒 Добавление часов доступно только администратору
            </p>
        </div>
    </div>
    {% endif %}

    {% if msg and session.get('user_id') is not none %}
    <div class="alert alert-success">{{ msg }}</div>
    {% endif %}
    {% endif %}
</div>

<script>
function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('[id^="tab-"]').forEach(t => t.classList.add('hidden'));
    document.querySelector(`.tab[onclick*="${tab}"]`).classList.add('active');
    document.getElementById('tab-' + tab).classList.remove('hidden');
}
</script>
</body>
</html>
'''

EMPLOYEE_HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>👤 {{ employee.name }} — Зарплата Клуб</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            padding: 20px;
            position: relative;
            overflow-x: hidden;
        }
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(ellipse at 20% 50%, rgba(157, 78, 221, 0.12) 0%, transparent 60%),
                radial-gradient(ellipse at 80% 50%, rgba(255, 107, 107, 0.08) 0%, transparent 60%);
            z-index: 0;
            pointer-events: none;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: rgba(255,255,255,0.97);
            border-radius: 30px;
            padding: 30px;
            box-shadow: 0 30px 80px rgba(0,0,0,0.6);
            position: relative;
            z-index: 1;
            animation: slideIn 0.6s ease;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(-50px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        .header h1 {
            font-size: 2.2em;
            font-weight: 900;
            background: linear-gradient(135deg, #9d4edd 0%, #ff6b6b 50%, #ffd93d 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .back-link {
            color: #9d4edd;
            font-weight: 700;
            text-decoration: none;
            font-size: 16px;
            transition: 0.3s;
            display: inline-block;
        }
        .back-link:hover { transform: translateX(-5px); color: #5a189a; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: linear-gradient(135deg, #9d4edd10 0%, #ff6b6b10 100%);
            padding: 15px;
            border-radius: 14px;
            text-align: center;
            border: 1px solid rgba(157, 78, 221, 0.15);
        }
        .stat-card .number {
            font-size: 26px;
            font-weight: 800;
            background: linear-gradient(135deg, #9d4edd 0%, #ff6b6b 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-card .label { color: #888; font-size: 12px; font-weight: 600; }
        .stat-card .icon { font-size: 24px; display: block; margin-bottom: 4px; }
        .card {
            background: #f8f6ff;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid #9d4edd;
        }
        .card h3 {
            color: #333;
            margin-bottom: 12px;
            font-weight: 700;
            font-size: 1.2em;
        }
        .month-selector {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }
        .month-selector input[type="month"] {
            padding: 10px 14px;
            border: 2px solid #e0ddf0;
            border-radius: 12px;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            min-width: 180px;
        }
        .month-selector input[type="month"]:focus {
            outline: none;
            border-color: #9d4edd;
            box-shadow: 0 0 0 4px rgba(157, 78, 221, 0.15);
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 700;
            font-family: 'Inter', sans-serif;
            cursor: pointer;
            transition: all 0.3s ease;
            color: white;
        }
        .btn:hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 8px 25px rgba(0,0,0,0.2); }
        .btn-purple { background: linear-gradient(135deg, #9d4edd 0%, #5a189a 100%); }
        .table-wrapper { overflow-x: auto; }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        table th {
            background: linear-gradient(135deg, #9d4edd 0%, #5a189a 100%);
            color: white;
            padding: 10px 12px;
            text-align: left;
            font-weight: 700;
            font-size: 13px;
            text-transform: uppercase;
        }
        table td {
            padding: 9px 12px;
            border-bottom: 1px solid #eee;
        }
        table tr:hover { background: #f0edff; }
        .badge-purple { background: #e8d5f5; color: #6c3483; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; display: inline-block; }
        .rate-badge { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; }
        .rate-badge.r400 { background: #d4edda; color: #155724; }
        .rate-badge.r350 { background: #fff3cd; color: #856404; }
        .konserzhka-badge {
            background: #ffd93d30;
            color: #856404;
            padding: 2px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
        }
        .total-row {
            background: #f0edff !important;
            font-weight: 700;
        }
        .total-row td { border-top: 2px solid #9d4edd; }
        .alert {
            padding: 14px 20px;
            border-radius: 14px;
            margin: 12px 0;
            font-weight: 600;
        }
        .alert-success { background: #d4edda; color: #155724; border-left: 5px solid #28a745; }
        @media (max-width: 700px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.6em; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>👤 {{ employee.name }}</h1>
        <a href="/" class="back-link">← Назад</a>
    </div>

    <div class="stats-grid">
        <div class="stat-card"><span class="icon">⏱</span><div class="number">{{ total_hours|round(1) }}</div><div class="label">Часов</div></div>
        <div class="stat-card"><span class="icon">💰</span><div class="number">{{ total_salary|round(0) }} ₽</div><div class="label">По часам</div></div>
        <div class="stat-card"><span class="icon">🥫</span><div class="number">{{ total_konserzhka }}</div><div class="label">Консержек</div></div>
        <div class="stat-card"><span class="icon">🎁</span><div class="number">{{ total_bonus|round(0) }} ₽</div><div class="label">Премии</div></div>
        <div class="stat-card"><span class="icon">💎</span><div class="number">{{ grand_total|round(0) }} ₽</div><div class="label">ИТОГО</div></div>
    </div>

    <div class="card">
        <h3>📅 Детали по дням</h3>
        <div class="month-selector">
            <form method="GET" action="/employee/{{ employee.id }}" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                <input type="month" name="month" value="{{ selected_month }}">
                <button type="submit" class="btn btn-purple">Показать</button>
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
                    <td>{% if log.konserzhka %}🥫 +1500 ₽{% else %}—{% endif %}</td>
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
        <p style="color:#999;">📭 Нет записей за этот месяц</p>
        {% endif %}
    </div>

    <div class="card" style="border-left-color: #ffd93d;">
        <h3>🎁 Премии</h3>
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
        <p style="color:#999;">🎁 Нет премий</p>
        {% endif %}
    </div>

    {% if msg %}
    <div class="alert alert-success">{{ msg }}</div>
    {% endif %}
</div>
</body>
</html>
'''

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
            
            employees.append({
                'id': emp[0],
                'name': emp[1],
                'month_hours': month_hours,
                'month_salary': month_salary,
                'month_konserzhka': month_konserzhka,
                'month_bonus': month_bonus,
                'month_total': month_salary + month_konserzhka + month_bonus
            })
        
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
        
        stats = {}
        
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
            'total_hours': sum(l['hours'] for l in my_logs),
            'total_salary': total_salary,
            'total_konserzhka': total_konserzhka,
            'grand_total': total_salary + total_konserzhka + total_bonus
        }
    
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
        today=today_str,
        selected_month=month,
        msg=request.args.get('msg')
    )

@app.route('/employee/<int:emp_id>')
def employee_detail(emp_id):
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='❌ Войдите в систему!'))
    
    if not session.get('is_admin') and session['user_id'] != emp_id:
        return redirect(url_for('index', msg='❌ У вас нет доступа к этому сотруднику!'))
    
    conn = get_db()
    today = date.today()
    month = request.args.get('month', today.strftime('%Y-%m'))
    
    employee = conn.execute("SELECT id, name FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not employee:
        conn.close()
        return redirect(url_for('index', msg='❌ Сотрудник не найден!'))
    
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
        employee={'id': employee[0], 'name': employee[1]},
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
        return redirect(url_for('index', msg='❌ Введите имя и пароль!'))
    
    if name == 'admin' and password == 'admin123':
        session.permanent = True
        session['user_id'] = 0
        session['user_name'] = 'Admin'
        session['is_admin'] = True
        return redirect(url_for('index', msg='👑 Добро пожаловать, Админ!'))
    
    conn = get_db()
    employee = conn.execute("SELECT id, name, password FROM employees WHERE name=?", (name,)).fetchone()
    conn.close()
    
    if not employee:
        return redirect(url_for('index', msg='❌ Сотрудник не найден!'))
    
    if employee[2] != password:
        return redirect(url_for('index', msg='❌ Неверный пароль!'))
    
    session.permanent = True
    session['user_id'] = employee[0]
    session['user_name'] = employee[1]
    session['is_admin'] = False
    return redirect(url_for('index', msg=f'👋 Добро пожаловать, {employee[1]}!'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index', msg='🚪 Вы вышли из системы'))

@app.route('/add_employee', methods=['POST'])
def add_employee():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='❌ Только админ может добавлять сотрудников!'))
    
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '').strip()
    
    if not name or not password:
        return redirect(url_for('index', msg='❌ Введите имя и пароль!'))
    
    conn = get_db()
    try:
        conn.execute("INSERT INTO employees (name, password) VALUES (?, ?)", (name, password))
        conn.commit()
        msg = f"👤 {name} добавлен!"
    except sqlite3.IntegrityError:
        msg = f"❌ Сотрудник '{name}' уже существует!"
    except Exception as e:
        msg = f"❌ Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('index', msg=msg))

@app.route('/delete_employee', methods=['POST'])
def delete_employee():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='❌ Только админ может удалять сотрудников!'))
    
    emp_id = int(request.form['emp_id'])
    conn = get_db()
    try:
        conn.execute("DELETE FROM hours_log WHERE employee_id=?", (emp_id,))
        conn.execute("DELETE FROM fixed_payments WHERE employee_id=?", (emp_id,))
        conn.execute("DELETE FROM employees WHERE id=?", (emp_id,))
        conn.commit()
        msg = "🗑️ Сотрудник удалён!"
    except Exception as e:
        msg = f"❌ Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('index', msg=msg))

@app.route('/add_event', methods=['POST'])
def add_event():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='❌ Только админ может добавлять мероприятия!'))
    
    event_date = request.form.get('event_date', '')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    
    if not event_date or not title:
        return redirect(url_for('index', msg='❌ Введите дату и название мероприятия!'))
    
    conn = get_db()
    try:
        conn.execute("INSERT INTO events (event_date, title, description) VALUES (?, ?, ?)",
                    (event_date, title, description))
        conn.commit()
        msg = f"✅ Мероприятие '{title}' добавлено!"
    except Exception as e:
        msg = f"❌ Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('index', msg=msg))

@app.route('/delete_event', methods=['POST'])
def delete_event():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='❌ Только админ может удалять мероприятия!'))
    
    event_id = int(request.form['event_id'])
    conn = get_db()
    try:
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        conn.commit()
        msg = "🗑️ Мероприятие удалено!"
    except Exception as e:
        msg = f"❌ Ошибка: {str(e)}"
    conn.close()
    return redirect(url_for('index', msg=msg))

@app.route('/add_hours', methods=['POST'])
def add_hours():
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='❌ Войдите в систему!'))
    
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='❌ Только администратор может добавлять часы!'))
    
    try:
        emp_id = int(request.form['emp_id'])
        hours_str = request.form.get('hours', '').strip()
        work_date = request.form.get('work_date', '')
        rate = float(request.form.get('rate', 400))
        konserzhka = 1 if request.form.get('konserzhka') == '1' else 0
        
        if not hours_str:
            return redirect(url_for('index', msg='❌ Введите часы!'))
        try:
            hours = float(hours_str)
        except ValueError:
            return redirect(url_for('index', msg='❌ Часы должны быть числом!'))
        if hours <= 0:
            return redirect(url_for('index', msg='❌ Часы должны быть больше 0!'))
        
        if not work_date:
            work_date = str(date.today())
        
        conn = get_db()
        
        conn.execute(
            "INSERT INTO hours_log (employee_id, work_date, hours, rate, konserzhka) VALUES (?, ?, ?, ?, ?)",
            (emp_id, work_date, hours, rate, konserzhka)
        )
        conn.commit()
        
        name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
        conn.close()
        
        total = hours * rate + (1500 if konserzhka else 0)
        konserzhka_text = " 🥫+1500" if konserzhka else ""
        msg = f"✅ {name} ({format_date_ru(work_date)}): {hours}ч × {rate}₽ = {hours*rate}₽{konserzhka_text} (итого {total}₽)"
        
    except Exception as e:
        msg = f"❌ Ошибка: {str(e)}"
    
    return redirect(url_for('index', msg=msg))

@app.route('/add_bonus', methods=['POST'])
def add_bonus():
    if not session.get('is_admin'):
        return redirect(url_for('index', msg='❌ Только админ может добавлять премии!'))
    
    try:
        emp_id = int(request.form['emp_id'])
        amount_str = request.form.get('amount', '').strip()
        description = request.form.get('description', '').strip()
        payment_date = request.form.get('payment_date', '')
        
        if not amount_str:
            return redirect(url_for('index', msg='❌ Введите сумму премии!'))
        try:
            amount = float(amount_str)
        except ValueError:
            return redirect(url_for('index', msg='❌ Сумма должна быть числом!'))
        if amount <= 0:
            return redirect(url_for('index', msg='❌ Сумма должна быть больше 0!'))
        
        if not payment_date:
            payment_date = str(date.today())
        
        conn = get_db()
        conn.execute(
            "INSERT INTO fixed_payments (employee_id, payment_date, amount, description) VALUES (?, ?, ?, ?)",
            (emp_id, payment_date, amount, description)
        )
        conn.commit()
        
        name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
        conn.close()
        
        msg = f"🎁 {name}: премия {amount}₽ ({description or 'без описания'})"
        
    except Exception as e:
        msg = f"❌ Ошибка: {str(e)}"
    
    return redirect(url_for('index', msg=msg))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
import sqlite3
from datetime import date, datetime, timedelta
import os
import io
import csv

app = Flask(__name__)
app.secret_key = 'zarplata_club_secret_2024'
app.permanent_session_lifetime = timedelta(days=30)

# === БАЗА ДАННЫХ ===
def get_db():
    db_path = '/tmp/zarplata_club.db'
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
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎵 Зарплата Клуб</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
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
                radial-gradient(ellipse at 50% 100%, rgba(255, 217, 61, 0.08) 0%, transparent 40%);
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
            position: relative;
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
        
        /* ===== КНОПКА ВЫХОДА (МАЛЕНЬКАЯ, НЕ МЕШАЕТ) ===== */
        .logout-icon {
            position: absolute;
            top: 0;
            right: 0;
            font-size: 20px;
            color: #ff6b6b;
            text-decoration: none;
            padding: 8px 12px;
            border-radius: 12px;
            transition: 0.3s;
            background: rgba(255,107,107,0.08);
        }
        .logout-icon:hover {
            background: rgba(255,107,107,0.2);
            transform: scale(1.1);
        }
        .logout-icon i {
            margin-right: 4px;
        }
        
        /* ===== ГЛАВНОЕ МЕНЮ ===== */
        .main-menu {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .menu-card {
            background: linear-gradient(135deg, #9d4edd15 0%, #ff6b6b15 100%);
            padding: 30px 20px;
            border-radius: 20px;
            text-align: center;
            border: 2px solid rgba(157, 78, 221, 0.15);
            transition: all 0.3s ease;
            cursor: pointer;
            text-decoration: none;
            color: #333;
            display: block;
        }
        .menu-card:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 12px 40px rgba(157, 78, 221, 0.25);
            border-color: #9d4edd;
        }
        .menu-card .icon {
            font-size: 40px;
            display: block;
            margin-bottom: 10px;
            color: #9d4edd;
        }
        .menu-card .title {
            font-size: 17px;
            font-weight: 700;
            color: #333;
        }
        .menu-card .desc {
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }
        .menu-card.events {
            background: linear-gradient(135deg, #ffd93d15 0%, #ff6b6b15 100%);
            border-color: rgba(255, 217, 61, 0.3);
        }
        .menu-card.events:hover {
            border-color: #ffd93d;
            box-shadow: 0 12px 40px rgba(255, 217, 61, 0.25);
        }
        .menu-card.events .icon { color: #f6b93b; }
        .menu-card.add .icon { color: #6bcb77; }
        
        /* ===== КАЛЕНДАРЬ МЕРОПРИЯТИЙ ===== */
        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 4px;
            margin: 15px 0;
        }
        .calendar-day {
            background: white;
            padding: 8px 4px;
            border-radius: 10px;
            text-align: center;
            min-height: 60px;
            border: 1px solid #eee;
            position: relative;
            transition: 0.3s;
        }
        .calendar-day:hover {
            border-color: #9d4edd;
            box-shadow: 0 2px 12px rgba(157, 78, 221, 0.15);
        }
        .calendar-day .day-num {
            font-weight: 700;
            font-size: 14px;
            color: #333;
        }
        .calendar-day .day-event {
            font-size: 10px;
            background: #ffd93d30;
            color: #856404;
            border-radius: 8px;
            padding: 2px 6px;
            margin-top: 4px;
            display: inline-block;
            font-weight: 600;
            cursor: pointer;
        }
        .calendar-day .day-event:hover {
            background: #ffd93d60;
        }
        .calendar-day.weekend .day-num {
            color: #ff6b6b;
        }
        .calendar-day.today {
            border-color: #9d4edd;
            background: #f0edff;
        }
        .calendar-day .add-event-btn {
            font-size: 12px;
            color: #9d4edd;
            cursor: pointer;
            display: block;
            margin-top: 2px;
        }
        .calendar-day .add-event-btn:hover {
            color: #5a189a;
        }
        .month-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .month-nav .month-title {
            font-size: 22px;
            font-weight: 700;
            color: #333;
        }
        .month-nav .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 10px;
            background: #9d4edd;
            color: white;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
        }
        .month-nav .btn:hover {
            opacity: 0.8;
        }
        .events-list {
            margin-top: 15px;
        }
        .events-list .event-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 14px;
            background: #f8f6ff;
            border-radius: 10px;
            margin-bottom: 6px;
            border-left: 3px solid #ffd93d;
        }
        .events-list .event-item .event-date {
            font-weight: 600;
            color: #9d4edd;
            font-size: 13px;
        }
        .events-list .event-item .event-title {
            font-weight: 600;
            flex: 1;
            margin: 0 10px;
        }
        
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
        .card h3 .icon { font-size: 22px; color: #9d4edd; }
        .card.green { border-left-color: #6bcb77; }
        .card.pink { border-left-color: #ff6b6b; }
        .card.gold { border-left-color: #ffd93d; }
        .card.blue { border-left-color: #4facfe; }
        
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
        .chart-container {
            background: white;
            border-radius: 12px;
            padding: 15px;
            margin-top: 10px;
        }
        .chart-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }
        .chart-bar .bar-label {
            min-width: 80px;
            font-weight: 600;
            font-size: 13px;
            color: #555;
        }
        .chart-bar .bar-track {
            flex: 1;
            height: 24px;
            background: #f0edff;
            border-radius: 12px;
            overflow: hidden;
        }
        .chart-bar .bar-fill {
            height: 100%;
            border-radius: 12px;
            background: linear-gradient(90deg, #9d4edd, #ff6b6b);
            transition: width 1s ease;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 8px;
            color: white;
            font-weight: 700;
            font-size: 12px;
        }
        @media (max-width: 700px) {
            .container { padding: 15px; }
            h1 { font-size: 2em; }
            .form-group { flex-direction: column; }
            .btn { width: 100%; justify-content: center; }
            .main-menu { grid-template-columns: 1fr 1fr; }
            .calendar-grid { font-size: 12px; }
            .calendar-day { min-height: 40px; padding: 4px; }
            .logout-icon { font-size: 16px; padding: 4px 8px; }
            .employee-card { flex-direction: column; align-items: stretch; gap: 8px; }
            .employee-card .actions { justify-content: flex-end; }
        }
    </style>
</head>
<body>

<div class="disco-ball d1"></div>
<div class="disco-ball d2"></div>
<div class="disco-ball d3"></div>

<div class="container">
    <div class="header">
        <span class="logo">🏢</span>
        <h1>ЗАРПЛАТА КЛУБ</h1>
        <p class="subtitle">🎵 Учёт зарплаты · Ставка <span>400</span> или <span>350</span> ₽/ч · Консержка <span>+1500 ₽</span></p>
        
        {% if session.get('user_id') is not none %}
        <a href="/logout" class="logout-icon" title="Выйти">
            <i class="fas fa-sign-out-alt"></i>
        </a>
        {% endif %}
    </div>

    {% if session.get('user_id') is none %}
    <!-- ВХОД -->
    <div class="card" style="border-left-color: #4facfe;">
        <h3><span class="icon"><i class="fas fa-lock"></i></span> Вход</h3>
        <form method="POST" action="/login" class="form-group">
            <input type="text" name="name" placeholder="Имя" required style="flex:1;">
            <input type="password" name="password" placeholder="Пароль" required style="flex:1;">
            <button type="submit" class="btn" style="background:linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);"><i class="fas fa-sign-in-alt"></i> Войти</button>
        </form>
        {% if msg %}
        <div class="alert alert-danger">{{ msg }}</div>
        {% endif %}
    </div>
    {% else %}
    
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:15px;">
        <div style="font-weight:700;font-size:18px;color:#333;">
            <i class="fas fa-user" style="color:#9d4edd;"></i> 
            <span style="color:#9d4edd;">{{ session.user_name }}</span>
            <span style="font-size:14px;color:#888;font-weight:400;margin-left:10px;">
                {% if session.is_admin %}<i class="fas fa-crown" style="color:#ffd93d;"></i> Админ{% endif %}
            </span>
        </div>
    </div>

    <!-- ===== ГЛАВНОЕ МЕНЮ ===== -->
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
        {% endif %}
    </div>

    <!-- ДАШБОРД (статистика) -->
    <div class="card">
        <h3><span class="icon"><i class="fas fa-chart-bar"></i></span> Статистика месяца</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:15px;">
            <div style="background:white;padding:12px;border-radius:12px;text-align:center;border:1px solid #e0ddf0;">
                <div style="font-size:12px;color:#888;"><i class="fas fa-users"></i> Сотрудников</div>
                <div style="font-size:22px;font-weight:800;color:#9d4edd;">{{ stats.total_employees }}</div>
            </div>
            <div style="background:white;padding:12px;border-radius:12px;text-align:center;border:1px solid #e0ddf0;">
                <div style="font-size:12px;color:#888;"><i class="fas fa-clock"></i> Часов</div>
                <div style="font-size:22px;font-weight:800;color:#9d4edd;">{{ stats.total_hours|round(1) }}</div>
            </div>
            <div style="background:white;padding:12px;border-radius:12px;text-align:center;border:1px solid #e0ddf0;">
                <div style="font-size:12px;color:#888;"><i class="fas fa-ruble-sign"></i> Зарплата</div>
                <div style="font-size:22px;font-weight:800;color:#9d4edd;">{{ stats.total_salary|round(0) }} ₽</div>
            </div>
            <div style="background:white;padding:12px;border-radius:12px;text-align:center;border:1px solid #e0ddf0;">
                <div style="font-size:12px;color:#888;"><i class="fas fa-utensils"></i> Консержек</div>
                <div style="font-size:22px;font-weight:800;color:#9d4edd;">{{ stats.total_konserzhka }}</div>
            </div>
            <div style="background:white;padding:12px;border-radius:12px;text-align:center;border:1px solid #e0ddf0;">
                <div style="font-size:12px;color:#888;"><i class="fas fa-gem"></i> ИТОГО</div>
                <div style="font-size:22px;font-weight:800;color:#9d4edd;">{{ stats.grand_total|round(0) }} ₽</div>
            </div>
        </div>
        
        <!-- График по сотрудникам -->
        {% if chart_data %}
        <div class="chart-container">
            <h4 style="margin-bottom:10px;"><i class="fas fa-chart-simple" style="color:#9d4edd;"></i> Часы по сотрудникам</h4>
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

    <!-- ===== РАЗДЕЛЫ ===== -->
    {% if current_section == 'employees' %}
    <!-- СОТРУДНИКИ -->
    <div class="card">
        <h3><span class="icon"><i class="fas fa-users"></i></span> Все сотрудники</h3>
        <p style="color:#888;margin-bottom:12px;font-size:14px;">📌 Нажмите на сотрудника для просмотра деталей</p>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        {% if employees %}
        {% for emp in employees %}
        <div class="employee-card">
            <div class="name" onclick="window.location.href='/employee/{{ emp.id }}'" style="cursor:pointer;flex:1;">
                {{ emp.name }}
            </div>
            <div class="stats">
                <i class="fas fa-clock" style="color:#9d4edd;"></i> <strong>{{ emp.month_hours|round(1) }}</strong> ч · 
                <i class="fas fa-utensils" style="color:#f6b93b;"></i> <strong>{{ emp.month_konserzhka }}</strong> · 
                <i class="fas fa-ruble-sign" style="color:#6bcb77;"></i> <strong>{{ emp.month_total|round(0) }}</strong> ₽
            </div>
            <div class="actions">
                {% if session.is_admin %}
                <form method="POST" action="/delete_employee" onsubmit="return confirm('Удалить {{ emp.name }}? Все данные будут потеряны!')">
                    <input type="hidden" name="emp_id" value="{{ emp.id }}">
                    <button type="submit" class="delete-btn" title="Удалить сотрудника"><i class="fas fa-trash"></i></button>
                </form>
                {% endif %}
            </div>
        </div>
        {% endfor %}
        {% else %}
        <p style="text-align:center;color:#999;padding:20px;"><i class="fas fa-face-frown"></i> Нет сотрудников</p>
        {% endif %}
    </div>
    {% endif %}

    {% if current_section == 'events' %}
    <!-- МЕРОПРИЯТИЯ (КАЛЕНДАРЬ) -->
    <div class="card gold">
        <h3><span class="icon"><i class="fas fa-calendar-alt"></i></span> Календарь мероприятий</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        
        <div class="month-nav">
            <button class="btn btn-sm btn-purple" onclick="window.location.href='/section/events?month={{ prev_month }}'"><i class="fas fa-chevron-left"></i></button>
            <span class="month-title">{{ month_name }}</span>
            <button class="btn btn-sm btn-purple" onclick="window.location.href='/section/events?month={{ next_month }}'"><i class="fas fa-chevron-right"></i></button>
        </div>
        
        <div class="calendar-grid">
            <div style="font-weight:700;color:#888;text-align:center;font-size:12px;">Пн</div>
            <div style="font-weight:700;color:#888;text-align:center;font-size:12px;">Вт</div>
            <div style="font-weight:700;color:#888;text-align:center;font-size:12px;">Ср</div>
            <div style="font-weight:700;color:#888;text-align:center;font-size:12px;">Чт</div>
            <div style="font-weight:700;color:#888;text-align:center;font-size:12px;">Пт</div>
            <div style="font-weight:700;color:#888;text-align:center;font-size:12px;">Сб</div>
            <div style="font-weight:700;color:#888;text-align:center;font-size:12px;">Вс</div>
            
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
        
        <!-- Добавление события -->
        {% if session.is_admin %}
        <div style="margin-top:15px;padding-top:15px;border-top:1px solid #eee;">
            <h4><i class="fas fa-plus-circle" style="color:#9d4edd;"></i> Добавить мероприятие</h4>
            <form method="POST" action="/add_event" class="form-group">
                <input type="date" name="event_date" value="{{ today }}" required>
                <input type="text" name="title" placeholder="Название" required>
                <input type="text" name="description" placeholder="Описание">
                <button type="submit" class="btn btn-gold"><i class="fas fa-plus"></i> Добавить</button>
            </form>
        </div>
        {% endif %}
        
        <!-- Список всех событий -->
        <div class="events-list">
            <h4 style="margin:15px 0 10px;"><i class="fas fa-list" style="color:#9d4edd;"></i> Все события месяца</h4>
            {% if events %}
            {% for event in events %}
            <div class="event-item">
                <span class="event-date"><i class="far fa-calendar"></i> {{ event.date_ru }}</span>
                <span class="event-title">{{ event.title }}</span>
                <span style="font-size:13px;color:#888;">{{ event.description or '' }}</span>
                {% if session.is_admin %}
                <form method="POST" action="/delete_event" style="display:inline;" onsubmit="return confirm('Удалить мероприятие?')">
                    <input type="hidden" name="event_id" value="{{ event.id }}">
                    <button type="submit" class="delete-event" title="Удалить"><i class="fas fa-trash"></i></button>
                </form>
                {% endif %}
            </div>
            {% endfor %}
            {% else %}
            <p style="color:#999;text-align:center;padding:10px;"><i class="far fa-calendar-alt"></i> Нет событий на этот месяц</p>
            {% endif %}
        </div>
    </div>
    {% endif %}

    {% if current_section == 'hours' %}
    <!-- ЧАСЫ -->
    <div class="card pink">
        <h3><span class="icon"><i class="fas fa-clock"></i></span> Все часы по дням</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div class="month-selector">
            <form method="GET" action="/section/hours" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                <input type="month" name="month" value="{{ selected_month }}">
                <button type="submit" class="btn btn-purple btn-sm"><i class="fas fa-search"></i> Показать</button>
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
                    <td>{% if log.konserzhka %}<i class="fas fa-utensils" style="color:#f6b93b;"></i> +1500 ₽{% else %}—{% endif %}</td>
                    <td><strong>{{ log.total }} ₽</strong></td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% if session.is_admin %}
        <div style="margin-top:10px;">
            <a href="/export?month={{ selected_month }}" class="btn btn-green"><i class="fas fa-file-excel"></i> Скачать Excel</a>
        </div>
        {% endif %}
        {% else %}
        <p style="text-align:center;color:#999;padding:20px;"><i class="fas fa-inbox"></i> Нет записей</p>
        {% endif %}
    </div>
    {% endif %}

    {% if current_section == 'payments' %}
    <!-- ВЫПЛАТЫ -->
    <div class="card gold">
        <h3><span class="icon"><i class="fas fa-money-bill-wave"></i></span> Выплаты по периодам</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div class="month-selector">
            <form method="GET" action="/section/payments" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                <input type="month" name="month" value="{{ selected_month }}">
                <button type="submit" class="btn btn-purple btn-sm"><i class="fas fa-search"></i> Показать</button>
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
                        <td><span class="badge badge-purple">{{ p.employee }}</span></td>
                        <td>{{ p.hours }}</td>
                        <td><span class="rate-badge r{{ p.rate|int }}">{{ p.rate }} ₽/ч</span></td>
                        <td>{% if p.konserzhka %}<i class="fas fa-utensils" style="color:#f6b93b;"></i> +1500{% else %}—{% endif %}</td>
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
            <p style="color:#999;font-size:13px;">Нет записей за этот период</p>
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
                        <td><span class="badge badge-purple">{{ p.employee }}</span></td>
                        <td>{{ p.hours }}</td>
                        <td><span class="rate-badge r{{ p.rate|int }}">{{ p.rate }} ₽/ч</span></td>
                        <td>{% if p.konserzhka %}<i class="fas fa-utensils" style="color:#f6b93b;"></i> +1500{% else %}—{% endif %}</td>
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
            <p style="color:#999;font-size:13px;">Нет записей за этот период</p>
            {% endif %}
        </div>
    </div>
    {% endif %}

    {% if current_section == 'bonus' %}
    <!-- ПРЕМИИ -->
    <div class="card" style="border-left-color: #ffd93d;">
        <h3><span class="icon"><i class="fas fa-gift"></i></span> Премии</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        {% if session.is_admin %}
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
            <button type="submit" class="btn" style="background:linear-gradient(135deg, #ffd93d 0%, #f6b93b 100%);color:#333;"><i class="fas fa-plus"></i> Добавить</button>
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
        <p style="color:#999;"><i class="fas fa-gift"></i> Пока нет премий</p>
        {% endif %}
    </div>
    {% endif %}

    {% if current_section == 'add' and session.is_admin %}
    <!-- ДОБАВИТЬ -->
    <div class="card green">
        <h3><span class="icon"><i class="fas fa-user-plus"></i></span> Новый сотрудник</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <form method="POST" action="/add_employee" class="form-group">
            <input type="text" name="name" placeholder="Имя" required>
            <input type="password" name="password" placeholder="Пароль" required>
            <button type="submit" class="btn btn-green"><i class="fas fa-plus"></i> Добавить</button>
        </form>
    </div>
    
    <div class="card" style="border-left-color: #6bcb77;">
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
                <i class="fas fa-utensils" style="color:#f6b93b;"></i> Консержка (+1500)
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
function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('[id^="tab-"]').forEach(t => t.classList.add('hidden'));
    document.querySelector(`.tab[onclick*="${tab}"]`).classList.add('active');
    document.getElementById('tab-' + tab).classList.remove('hidden');
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
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ employee.name }} — Зарплата Клуб</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
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
        <h1><i class="fas fa-user" style="color:#9d4edd;"></i> {{ employee.name }}</h1>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> Назад</a>
    </div>

    <div class="stats-grid">
        <div class="stat-card"><span class="icon"><i class="fas fa-clock"></i></span><div class="number">{{ total_hours|round(1) }}</div><div class="label">Часов</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-ruble-sign"></i></span><div class="number">{{ total_salary|round(0) }} ₽</div><div class="label">По часам</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-utensils"></i></span><div class="number">{{ total_konserzhka }}</div><div class="label">Консержек</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-gift"></i></span><div class="number">{{ total_bonus|round(0) }} ₽</div><div class="label">Премии</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-gem"></i></span><div class="number">{{ grand_total|round(0) }} ₽</div><div class="label">ИТОГО</div></div>
    </div>

    <div class="card">
        <h3><i class="fas fa-calendar-day" style="color:#9d4edd;"></i> Детали по дням</h3>
        <div class="month-selector">
            <form method="GET" action="/employee/{{ employee.id }}" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
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
                    <td>{% if log.konserzhka %}<i class="fas fa-utensils" style="color:#f6b93b;"></i> +1500 ₽{% else %}—{% endif %}</td>
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
        <p style="color:#999;"><i class="fas fa-inbox"></i> Нет записей за этот месяц</p>
        {% endif %}
    </div>

    <div class="card" style="border-left-color: #ffd93d;">
        <h3><i class="fas fa-gift" style="color:#ffd93d;"></i> Премии</h3>
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
        <p style="color:#999;"><i class="fas fa-gift"></i> Нет премий</p>
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
        return render_template_string(HTML, session={}, employees=[], all_logs=[], all_bonuses=[], my_logs=[], stats={}, payments={'first': [], 'second': [], 'first_total': 0, 'second_total': 0}, events=[], calendar_days=[], chart_data=[], today=date.today().strftime('%Y-%m-%d'), selected_month=date.today().strftime('%Y-%m'), current_section='main', month_name='', current_year=0, prev_month='', next_month='', msg=request.args.get('msg'))
    
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
        employees_raw = conn.execute("SELECT id, name FROM employees").fetchall()
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
    
    employee = conn.execute("SELECT id, name FROM employees WHERE id=?", (emp_id,)).fetchone()
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
    except sqlite3.IntegrityError:
        msg = f"Сотрудник '{name}' уже существует!"
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    conn.close()
    
    # Возвращаемся в тот же раздел, а не на главную
    return redirect(url_for('section', section='add', msg=msg))

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
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        conn.commit()
        msg = "Мероприятие удалено!"
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
        conn.execute(
            "INSERT INTO hours_log (employee_id, work_date, hours, rate, konserzhka) VALUES (?, ?, ?, ?, ?)",
            (emp_id, work_date, hours, rate, konserzhka)
        )
        conn.commit()
        
        name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
        conn.close()
        
        total = hours * rate + (1500 if konserzhka else 0)
        msg = f"{name} ({format_date_ru(work_date)}): {hours}ч × {rate}₽ = {hours*rate}₽" + (" (+1500 консержка)" if konserzhka else "")
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
        conn.execute(
            "INSERT INTO fixed_payments (employee_id, payment_date, amount, description) VALUES (?, ?, ?, ?)",
            (emp_id, payment_date, amount, description)
        )
        conn.commit()
        
        name = conn.execute("SELECT name FROM employees WHERE id=?", (emp_id,)).fetchone()[0]
        conn.close()
        
        msg = f"{name}: премия {amount}₽ ({description or 'без описания'})"
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    
    return redirect(url_for('section', section='bonus', msg=msg))

@app.route('/export')
def export():
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='Войдите в систему!'))
    
    # Экспорт только для админа
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

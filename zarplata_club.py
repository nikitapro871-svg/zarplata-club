from flask import Flask, render_template_string, request, redirect, url_for, session, send_file, jsonify
import sqlite3
from datetime import date, datetime, timedelta
import os
import io
import csv
import base64
import random

app = Flask(__name__)
app.secret_key = 'zarplata_club_secret_2024'
app.permanent_session_lifetime = timedelta(days=30)

# === БАЗА ДАННЫХ ===
def get_db():
    db_path = '/tmp/zarplata_club.db'
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS employees
                   (id INTEGER PRIMARY KEY, name TEXT UNIQUE, password TEXT, is_admin INTEGER DEFAULT 0, avatar TEXT DEFAULT '', position TEXT DEFAULT '')''')

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

    cur.execute('''CREATE TABLE IF NOT EXISTS messages
                   (id INTEGER PRIMARY KEY, from_id INTEGER, to_id INTEGER, message TEXT, date TEXT, is_read INTEGER DEFAULT 0,
                    FOREIGN KEY(from_id) REFERENCES employees(id),
                    FOREIGN KEY(to_id) REFERENCES employees(id))''')

    cur.execute('''CREATE TABLE IF NOT EXISTS audit_log
                   (id INTEGER PRIMARY KEY, admin_id INTEGER, admin_name TEXT,
                    action_type TEXT, action_details TEXT, action_date TEXT,
                    FOREIGN KEY(admin_id) REFERENCES employees(id))''')

    conn.commit()
    return conn

# === ФУНКЦИИ ===
def log_audit(admin_id, admin_name, action_type, action_details):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit_log (admin_id, admin_name, action_type, action_details, action_date) VALUES (?, ?, ?, ?, ?)",
        (admin_id, admin_name, action_type, action_details, str(date.today()))
    )
    conn.commit()
    conn.close()

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

# === AI-ПОМОЩНИК (ВНУТРЕННИЙ, ТОЛЬКО ДЛЯ АДМИНА) ===
def generate_ai_insights(conn, employee_id=None):
    insights = []
    
    if employee_id:
        logs = conn.execute("SELECT hours, rate, konserzhka, work_date FROM hours_log WHERE employee_id=? ORDER BY work_date", (employee_id,)).fetchall()
        bonuses = conn.execute("SELECT amount FROM fixed_payments WHERE employee_id=?", (employee_id,)).fetchall()
        emp = conn.execute("SELECT name FROM employees WHERE id=?", (employee_id,)).fetchone()
        name = emp[0] if emp else 'Сотрудник'
    else:
        logs = conn.execute("SELECT hours, rate, konserzhka, work_date FROM hours_log ORDER BY work_date").fetchall()
        bonuses = conn.execute("SELECT amount FROM fixed_payments").fetchall()
        name = 'Все сотрудники'
    
    if not logs:
        insights.append("📊 Нет данных для анализа. Начните добавлять часы!")
        return insights
    
    total_hours = sum(l[0] for l in logs)
    total_salary = sum(l[0] * l[1] for l in logs)
    total_konserzhka = sum(1500 for l in logs if l[2] == 1)
    total_bonus = sum(b[0] for b in bonuses)
    total = total_salary + total_konserzhka + total_bonus
    days_worked = len(set(l[3] for l in logs))
    
    insights.append(f"📈 {name} отработал {total_hours} часов за {days_worked} дней.")
    insights.append(f"💰 Общая зарплата: {total} ₽ (из них {total_konserzhka} ₽ консержки и {total_bonus} ₽ премий).")
    
    if total_hours > 0 and days_worked > 0:
        avg_hours = total_hours / days_worked
        insights.append(f"⏱ Среднее количество часов в день: {avg_hours:.1f} ч.")
    
    today = date.today()
    current_month = today.strftime('%Y-%m')
    last_month = (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    
    current_logs = [l for l in logs if l[3].startswith(current_month)]
    last_logs = [l for l in logs if l[3].startswith(last_month)]
    
    current_hours = sum(l[0] for l in current_logs)
    last_hours = sum(l[0] for l in last_logs)
    
    if last_hours > 0:
        change = ((current_hours - last_hours) / last_hours) * 100
        if change > 5:
            insights.append(f"📈 Часы выросли на {change:.0f}% по сравнению с прошлым месяцем! Отличная работа!")
        elif change < -5:
            insights.append(f"📉 Часы упали на {abs(change):.0f}% по сравнению с прошлым месяцем. Возможно, стоит обратить внимание.")
        else:
            insights.append(f"📊 Часы остались примерно на уровне прошлого месяца ({change:.0f}%).")
    else:
        insights.append("📊 Это первый месяц работы. Отличный старт!")
    
    if total_hours > 150:
        insights.append(f"🔥 {name} отработал более 150 часов — это рекордный результат!")
    elif total_hours < 20 and total_hours > 0:
        insights.append(f"⚠️ {name} отработал всего {total_hours} часов. Возможно, стоит проверить, не пропущены ли записи.")
    
    if total_konserzhka > 5000:
        insights.append(f"🥫 Большое количество консержек ({total_konserzhka} ₽).")
    
    if total_bonus > 10000:
        insights.append(f"🎁 Высокая сумма премий ({total_bonus} ₽). Отличная мотивация!")
    
    if total_hours > 0:
        avg_rate = total_salary / total_hours if total_hours > 0 else 0
        insights.append(f"💡 Средняя ставка: {avg_rate:.1f} ₽/ч.")
    
    return insights

# === HTML ===
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
            background: #0b0b1a;
            min-height: 100vh;
            padding: 20px;
            position: relative;
            overflow-x: hidden;
            transition: background 0.3s ease, color 0.3s ease;
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
                radial-gradient(ellipse at 80% 50%, rgba(255, 107, 107, 0.12) 0%, transparent 60%),
                radial-gradient(ellipse at 50% 100%, rgba(252, 211, 77, 0.08) 0%, transparent 40%);
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
            50% { opacity: 0.15; transform: scale(1.1); }
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
            background: rgba(255,255,255,0.07);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 40px;
            padding: 35px;
            box-shadow: 0 30px 60px rgba(0,0,0,0.6);
            animation: slideIn 0.6s ease;
            position: relative;
            z-index: 1;
            border: 1px solid rgba(255,255,255,0.06);
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
            border-bottom: 1px solid rgba(255,255,255,0.06);
            position: relative;
        }
        .header .logo { font-size: 60px; display: block; animation: floatIcon 4s ease-in-out infinite; }
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
            color: rgba(255,255,255,0.6);
            font-size: 1.1em;
            font-weight: 300;
        }
        .subtitle span { color: #c084fc; font-weight: 600; }
        .theme-toggle {
            position: absolute;
            top: 0;
            left: 0;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 50%;
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: rgba(255,255,255,0.4);
            font-size: 18px;
            cursor: pointer;
            transition: 0.3s;
        }
        .theme-toggle:hover { border-color: #c084fc; color: #c084fc; transform: scale(1.05); }
        .logout-icon {
            position: absolute;
            top: 0;
            right: 0;
            font-size: 18px;
            color: rgba(255,255,255,0.4);
            text-decoration: none;
            padding: 8px 12px;
            border-radius: 50%;
            transition: 0.3s;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
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
            grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
            gap: 12px;
            margin: 35px 0;
        }
        .menu-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            padding: 18px 8px;
            border-radius: 20px;
            text-align: center;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            text-decoration: none;
            color: #fff;
            display: block;
        }
        .menu-card:hover {
            transform: translateY(-6px) scale(1.02);
            box-shadow: 0 20px 40px rgba(157, 78, 221, 0.2);
            border-color: rgba(157, 78, 221, 0.3);
        }
        .menu-card .icon { font-size: 28px; display: block; margin-bottom: 6px; color: #c084fc; }
        .menu-card .title { font-size: 12px; font-weight: 700; }
        .menu-card .desc { font-size: 10px; color: rgba(255,255,255,0.4); margin-top: 2px; }
        .menu-card.ai .icon { color: #60a5fa; }
        .menu-card.bonus .icon { color: #fcd34d; }
        .menu-card.payments .icon { color: #6bcb77; }
        .menu-card.hours .icon { color: #f472b6; }
        .menu-card.top .icon { color: #ffd93d; }
        .card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 24px;
            padding: 24px;
            margin-bottom: 24px;
            transition: 0.3s;
        }
        .card:hover { border-color: rgba(255,255,255,0.08); }
        .card h3 {
            color: #fff;
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
        .card.purple { border-left: 3px solid #9d4edd; }
        .card.top { border-left: 3px solid #ffd93d; }
        .card.ai-card { border-left: 3px solid #60a5fa; background: rgba(96,165,250,0.03); }
        .form-group {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
        }
        input, select, textarea {
            padding: 12px 18px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            color: #fff;
            transition: all 0.3s ease;
            flex: 1;
            min-width: 120px;
            outline: none;
        }
        input::placeholder, select { color: rgba(255,255,255,0.3); }
        input:focus, select:focus {
            border-color: #c084fc;
            box-shadow: 0 0 0 4px rgba(192,132,252,0.1);
            background: rgba(255,255,255,0.08);
        }
        input[type="date"] { min-width: 160px; cursor: pointer; color: #fff; }
        input[type="file"] { padding: 10px; color: rgba(255,255,255,0.4); }
        input[type="checkbox"] {
            width: 22px;
            height: 22px;
            flex: 0 0 auto;
            min-width: unset;
            accent-color: #c084fc;
            cursor: pointer;
        }
        select option { background: #1a1a2e; color: #fff; }
        label { color: rgba(255,255,255,0.6); font-size: 14px; display: flex; align-items: center; gap: 8px; cursor: pointer; }
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
        .btn:hover { transform: translateY(-3px) scale(1.02); box-shadow: 0 12px 30px rgba(0,0,0,0.3); }
        .btn-purple { background: linear-gradient(135deg, #9d4edd 0%, #6d28d9 100%); }
        .btn-green { background: linear-gradient(135deg, #6bcb77 0%, #2d8f47 100%); }
        .btn-gold { background: linear-gradient(135deg, #fcd34d 0%, #f59e0b 100%); color: #1a1a2e; }
        .btn-red { background: linear-gradient(135deg, #ff6b6b 0%, #dc2626 100%); }
        .btn-blue { background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%); }
        .btn-sm { padding: 8px 16px; font-size: 12px; border-radius: 10px; }
        .table-wrapper { overflow-x: auto; border-radius: 16px; border: 1px solid rgba(255,255,255,0.06); }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            color: rgba(255,255,255,0.9);
        }
        table th {
            background: rgba(255,255,255,0.04);
            color: rgba(255,255,255,0.4);
            padding: 12px 14px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        table td {
            padding: 11px 14px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        table tr:hover td { background: rgba(255,255,255,0.03); }
        .badge {
            display: inline-block;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            background: rgba(192,132,252,0.15);
            color: #c084fc;
        }
        .badge-gold { background: rgba(252,211,77,0.15); color: #fcd34d; }
        .badge-blue { background: rgba(96,165,250,0.15); color: #60a5fa; }
        .badge-green { background: rgba(107,203,119,0.15); color: #6bcb77; }
        .badge-red { background: rgba(255,107,107,0.15); color: #ff6b6b; }
        .rate-badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .rate-badge.r400 { background: rgba(107,203,119,0.15); color: #6bcb77; }
        .rate-badge.r350 { background: rgba(252,211,77,0.15); color: #fcd34d; }
        .position-badge {
            display: inline-block;
            padding: 3px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            background: rgba(192,132,252,0.15);
            color: #c084fc;
            border: 1px solid rgba(192,132,252,0.15);
        }
        .alert {
            padding: 14px 20px;
            border-radius: 16px;
            margin: 12px 0;
            font-weight: 600;
            border-left: 3px solid;
            background: rgba(255,255,255,0.04);
        }
        .alert-success { color: #6bcb77; border-color: #6bcb77; }
        .alert-danger { color: #ff6b6b; border-color: #ff6b6b; }
        .back-link {
            display: inline-block;
            margin-bottom: 16px;
            color: rgba(255,255,255,0.4);
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
            padding: 12px 16px;
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            margin-bottom: 8px;
            border: 1px solid rgba(255,255,255,0.04);
            transition: 0.3s;
            color: #fff;
            cursor: pointer;
        }
        .employee-card:hover {
            border-color: rgba(157,78,221,0.2);
            background: rgba(255,255,255,0.05);
        }
        .employee-card .employee-info { display: flex; align-items: center; flex: 1; }
        .employee-card .employee-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
            margin-right: 12px;
            border: 2px solid rgba(192,132,252,0.2);
        }
        .employee-card .employee-avatar-placeholder {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: rgba(255,255,255,0.06);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;
            color: rgba(255,255,255,0.3);
            font-size: 16px;
        }
        .employee-card .employee-name { font-weight: 600; }
        .employee-card .employee-position { margin-left: 10px; }
        .employee-card .employee-stats { color: rgba(255,255,255,0.4); font-size: 13px; margin-left: 12px; }
        .employee-card .actions { display: flex; gap: 6px; }
        .employee-card .delete-btn {
            background: none;
            border: none;
            color: rgba(255,255,255,0.3);
            cursor: pointer;
            font-size: 16px;
            transition: 0.3s;
            padding: 0 5px;
        }
        .employee-card .delete-btn:hover { color: #ff6b6b; transform: scale(1.2); }
        .chat-message { padding: 10px 14px; border-radius: 14px; margin-bottom: 8px; max-width: 80%; word-wrap: break-word; }
        .chat-message.outgoing { background: rgba(192,132,252,0.15); border: 1px solid rgba(192,132,252,0.2); margin-left: auto; color: #c084fc; }
        .chat-message.incoming { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.06); color: #fff; }
        .chat-message .msg-sender { font-weight: 700; font-size: 13px; }
        .chat-message .msg-text { margin: 4px 0; }
        .chat-message .msg-date { font-size: 10px; color: rgba(255,255,255,0.3); }
        .chat-select { min-width: 150px; }
        .chat-input { display: flex; gap: 10px; align-items: center; }
        .chat-input input { flex: 1; }
        .chat-messages { max-height: 400px; overflow-y: auto; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 16px; border: 1px solid rgba(255,255,255,0.04); }
        .ai-container {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .ai-container .ai-insights {
            background: rgba(96,165,250,0.05);
            border-radius: 16px;
            padding: 16px;
            border: 1px solid rgba(96,165,250,0.08);
        }
        .ai-container .ai-insight {
            padding: 8px 12px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            font-size: 14px;
            color: #fff;
        }
        .ai-container .ai-insight:last-child { border-bottom: none; }
        .ai-container .ai-insight i { margin-right: 8px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 12px;
            margin-bottom: 25px;
        }
        .stat-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            padding: 14px 8px;
            border-radius: 20px;
            text-align: center;
            transition: 0.3s;
        }
        .stat-card:hover { transform: translateY(-3px); border-color: rgba(157,78,221,0.15); }
        .stat-card .number {
            font-size: 22px;
            font-weight: 800;
            background: linear-gradient(135deg, #c084fc 0%, #f472b6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-card .label {
            color: rgba(255,255,255,0.4);
            font-size: 10px;
            font-weight: 600;
            margin-top: 3px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-card .icon { font-size: 18px; display: block; margin-bottom: 3px; color: rgba(255,255,255,0.2); }
        .month-selector {
            display: flex;
            gap: 12px;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 16px;
        }
        .month-selector input[type="month"] {
            flex: 0 0 auto;
            min-width: 180px;
            padding: 10px 16px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 12px;
            color: #fff;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            outline: none;
        }
        .month-selector input[type="month"]:focus {
            border-color: #c084fc;
            box-shadow: 0 0 0 4px rgba(192,132,252,0.1);
        }
        .month-selector input[type="month"]::-webkit-calendar-picker-indicator {
            filter: invert(1);
        }
        .month-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
        }
        .month-nav .month-title { font-size: 22px; font-weight: 700; color: #fff; }
        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 6px;
            margin: 15px 0;
        }
        .calendar-day {
            background: rgba(255,255,255,0.03);
            padding: 10px 4px;
            border-radius: 14px;
            text-align: center;
            min-height: 70px;
            border: 1px solid rgba(255,255,255,0.04);
            transition: 0.3s;
        }
        .calendar-day:hover { border-color: rgba(192,132,252,0.2); }
        .calendar-day .day-num { font-weight: 700; font-size: 16px; color: #fff; }
        .calendar-day .day-event {
            font-size: 10px;
            background: rgba(252,211,77,0.15);
            color: #fcd34d;
            border-radius: 8px;
            padding: 2px 8px;
            margin-top: 4px;
            display: inline-block;
            font-weight: 600;
            cursor: pointer;
        }
        .calendar-day.weekend .day-num { color: rgba(255,107,107,0.4); }
        .calendar-day.today { border-color: #c084fc; background: rgba(192,132,252,0.05); }
        .calendar-day .add-event-btn {
            font-size: 12px;
            color: rgba(255,255,255,0.3);
            cursor: pointer;
            display: block;
            margin-top: 2px;
        }
        .calendar-day .add-event-btn:hover { color: #c084fc; }
        .events-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
            margin-top: 15px;
        }
        .event-item {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 14px 16px;
            transition: 0.3s;
            border-left: 3px solid #fcd34d;
        }
        .event-item:hover {
            transform: translateY(-3px);
            border-color: rgba(252,211,77,0.3);
        }
        .event-item .event-date { font-weight: 600; color: #fcd34d; font-size: 13px; }
        .event-item .event-title { font-weight: 700; color: #fff; font-size: 16px; margin: 4px 0; }
        .event-item .event-desc { color: rgba(255,255,255,0.4); font-size: 12px; }
        .event-item .event-actions { margin-top: 8px; }
        .event-item .event-actions .delete-event-btn {
            background: none;
            border: none;
            color: rgba(255,255,255,0.3);
            cursor: pointer;
            font-size: 14px;
            transition: 0.3s;
            padding: 0;
        }
        .event-item .event-actions .delete-event-btn:hover { color: #ff6b6b; }
        .chart-container {
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            padding: 18px;
            margin-top: 12px;
            border: 1px solid rgba(255,255,255,0.04);
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
            color: rgba(255,255,255,0.5);
        }
        .chart-bar .bar-track {
            flex: 1;
            height: 26px;
            background: rgba(255,255,255,0.05);
            border-radius: 14px;
            overflow: hidden;
        }
        .chart-bar .bar-fill {
            height: 100%;
            border-radius: 14px;
            background: linear-gradient(90deg, #fcd34d, #f59e0b);
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
            color: rgba(255,255,255,0.4);
            margin-bottom: 10px;
            font-size: 14px;
            padding: 8px 14px;
            border-radius: 12px;
            background: rgba(255,255,255,0.03);
        }
        .period-group h4.first { border-left: 3px solid #6bcb77; }
        .period-group h4.second { border-left: 3px solid #fcd34d; }
        .total-row td { border-top: 1px solid rgba(255,255,255,0.06); color: #fff !important; font-weight: 700; }
        .audit-item {
            padding: 10px 14px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            margin-bottom: 6px;
            border-left: 3px solid #f472b6;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .audit-item .admin { color: #c084fc; font-weight: 600; }
        .audit-item .action { color: #fff; }
        .audit-item .date { color: rgba(255,255,255,0.3); font-size: 12px; }
        .search-box {
            display: flex;
            gap: 10px;
            align-items: center;
            margin-bottom: 15px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px;
            padding: 4px 16px;
            transition: 0.3s;
        }
        .search-box:focus-within {
            border-color: #c084fc;
            box-shadow: 0 0 0 4px rgba(192,132,252,0.05);
        }
        .search-box input {
            border: none;
            background: transparent;
            padding: 12px 0;
            flex: 1;
            font-size: 14px;
            color: #fff;
            outline: none;
        }
        .search-box i { color: rgba(255,255,255,0.3); font-size: 16px; }
        .export-btn { margin-top: 12px; }
        @media (max-width: 700px) {
            .container { padding: 16px; border-radius: 24px; }
            h1 { font-size: 2em; }
            .main-menu { grid-template-columns: 1fr 1fr; gap: 10px; }
            .menu-card { padding: 14px 8px; }
            .menu-card .icon { font-size: 24px; }
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
            .chat-message { max-width: 95%; }
            .chat-input { flex-direction: column; }
            .events-list { grid-template-columns: 1fr; }
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
        <div style="font-weight:600;font-size:18px;color:rgba(255,255,255,0.6);">
            <i class="fas fa-user" style="color:#c084fc;"></i>
            <span style="color:#fff;font-weight:700;">{{ session.user_name }}</span>
            {% if session.is_admin %}
            <span style="font-size:13px;color:rgba(255,255,255,0.3);margin-left:10px;">
                <i class="fas fa-crown" style="color:#fcd34d;"></i> Админ
            </span>
            {% endif %}
        </div>
        <a href="/" class="btn btn-sm" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);color:rgba(255,255,255,0.5);">
            <i class="fas fa-home"></i> Главная
        </a>
    </div>
    {% if not current_section or current_section == 'main' %}
    <div class="main-menu">
        {% if session.is_admin %}
        <a href="/section/ai" class="menu-card ai">
            <span class="icon"><i class="fas fa-brain"></i></span>
            <div class="title">AI-помощник</div>
            <div class="desc">Аналитика и советы</div>
        </a>
        {% endif %}
        <a href="/section/chat" class="menu-card">
            <span class="icon"><i class="fas fa-comments"></i></span>
            <div class="title">Чат</div>
            <div class="desc">Общение с коллегами</div>
        </a>
        <a href="/section/employees" class="menu-card">
            <span class="icon"><i class="fas fa-users"></i></span>
            <div class="title">Сотрудники</div>
            <div class="desc">Список коллег</div>
        </a>
        <a href="/section/bonus" class="menu-card bonus">
            <span class="icon"><i class="fas fa-gift"></i></span>
            <div class="title">Премии</div>
            <div class="desc">Управление премиями</div>
        </a>
        <a href="/section/hours" class="menu-card hours">
            <span class="icon"><i class="fas fa-clock"></i></span>
            <div class="title">Часы</div>
            <div class="desc">Все записи по дням</div>
        </a>
        <a href="/section/payments" class="menu-card payments">
            <span class="icon"><i class="fas fa-money-bill-wave"></i></span>
            <div class="title">Выплаты</div>
            <div class="desc">1–15 и 16–конец</div>
        </a>
        <a href="/section/events" class="menu-card">
            <span class="icon"><i class="fas fa-calendar-alt"></i></span>
            <div class="title">Мероприятия</div>
            <div class="desc">Календарь и события</div>
        </a>
        {% if session.is_admin %}
        <a href="/section/top" class="menu-card top">
            <span class="icon"><i class="fas fa-trophy"></i></span>
            <div class="title">Топ сотрудников</div>
            <div class="desc">Зарплатный рейтинг</div>
        </a>
        <a href="/section/add" class="menu-card">
            <span class="icon"><i class="fas fa-plus-circle"></i></span>
            <div class="title">Добавить</div>
            <div class="desc">Новый сотрудник / часы</div>
        </a>
        <a href="/section/audit" class="menu-card">
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
    </div>
    {% endif %}
    <!-- ===== AI-ПОМОЩНИК (ТОЛЬКО ДЛЯ АДМИНА) ===== -->
    {% if current_section == 'ai' and session.is_admin %}
    <div class="card ai-card">
        <h3><span class="icon"><i class="fas fa-brain" style="color:#60a5fa;"></i></span> AI-помощник</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div style="margin-bottom:16px;">
            <form method="GET" action="/section/ai" class="form-group">
                <select name="emp_id" style="flex:0 0 auto;min-width:200px;">
                    <option value="">Все сотрудники</option>
                    {% for emp in all_employees %}
                    <option value="{{ emp.id }}" {% if request.args.get('emp_id')|int == emp.id %}selected{% endif %}>{{ emp.name }}</option>
                    {% endfor %}
                </select>
                <button type="submit" class="btn btn-blue btn-sm"><i class="fas fa-robot"></i> Анализировать</button>
            </form>
        </div>
        <div class="ai-container">
            <div class="ai-insights">
                {% for insight in ai_insights %}
                <div class="ai-insight">
                    <i class="fas fa-robot" style="color:#60a5fa;"></i> {{ insight }}
                </div>
                {% else %}
                <div class="ai-insight" style="color:rgba(255,255,255,0.4);">
                    <i class="fas fa-robot"></i> Нет данных для анализа. Начните добавлять часы!
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    {% endif %}
    <!-- ===== ЧАТ ===== -->
    {% if current_section == 'chat' %}
    <div class="card blue">
        <h3><span class="icon"><i class="fas fa-comments"></i></span> Чат с сотрудниками</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div class="chat-container">
            <form method="GET" action="/section/chat" class="form-group">
                <select name="to_id" class="chat-select" onchange="this.form.submit()">
                    <option value="">Выберите сотрудника...</option>
                    {% for emp in chat_employees %}
                    <option value="{{ emp.id }}" {% if chat_to_id == emp.id %}selected{% endif %}>{{ emp.name }}</option>
                    {% endfor %}
                </select>
            </form>
            <div class="chat-messages" id="chatMessages">
                {% if chat_messages %}
                {% for msg in chat_messages %}
                <div class="chat-message {% if msg.from_id == session.user_id %}outgoing{% else %}incoming{% endif %}">
                    <div class="msg-sender">{{ msg.from_name }}</div>
                    <div class="msg-text">{{ msg.message }}</div>
                    <div class="msg-date">{{ msg.date_ru }}</div>
                </div>
                {% endfor %}
                {% else %}
                <p style="color:rgba(255,255,255,0.3);text-align:center;padding:20px;">Нет сообщений.</p>
                {% endif %}
            </div>
            {% if chat_to_id %}
            <form method="POST" action="/send_message" class="chat-input">
                <input type="hidden" name="to_id" value="{{ chat_to_id }}">
                <input type="text" name="message" placeholder="Введите сообщение..." required>
                <button type="submit" class="btn btn-blue btn-sm"><i class="fas fa-paper-plane"></i> Отправить</button>
            </form>
            {% else %}
            <p style="color:rgba(255,255,255,0.3);font-size:14px;text-align:center;padding:10px;">
                👆 Выберите сотрудника, чтобы начать чат
            </p>
            {% endif %}
        </div>
    </div>
    {% endif %}
    <!-- ===== ПРЕМИИ ===== -->
    {% if current_section == 'bonus' %}
    <div class="card gold">
        <h3><span class="icon"><i class="fas fa-gift" style="color:#fcd34d;"></i></span> Премии</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        {% if session.is_admin %}
        <form method="POST" action="/add_bonus" class="form-group" style="margin-bottom:18px;">
            <select name="emp_id" required>
                <option value="">Выберите сотрудника</option>
                {% for emp in all_employees %}
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
        <p style="color:rgba(255,255,255,0.4);"><i class="fas fa-gift"></i> Пока нет премий</p>
        {% endif %}
    </div>
    {% endif %}
    <!-- ===== ЧАСЫ ===== -->
    {% if current_section == 'hours' %}
    <div class="card pink">
        <h3><span class="icon"><i class="fas fa-clock" style="color:#f472b6;"></i></span> Часы</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div class="month-selector">
            <form method="GET" action="/section/hours" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
                <input type="month" name="month" value="{{ selected_month }}">
                <button type="submit" class="btn btn-sm btn-purple"><i class="fas fa-search"></i> Показать</button>
            </form>
        </div>
        {% if all_logs %}
        <div class="table-wrapper">
            <table>
                <tr><th>Дата</th><th>Сотрудник</th><th>Часы</th><th>Ставка</th><th>Консержка</th><th>Итого</th></tr>
                {% for log in all_logs %}
                <tr>
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
        <div class="export-btn">
            <a href="/export?month={{ selected_month }}" class="btn btn-green"><i class="fas fa-file-excel"></i> Скачать Excel</a>
        </div>
        {% endif %}
        {% else %}
        <p style="text-align:center;color:rgba(255,255,255,0.3);padding:30px;"><i class="fas fa-inbox"></i> Нет записей</p>
        {% endif %}
    </div>
    {% endif %}
    <!-- ===== ВЫПЛАТЫ ===== -->
    {% if current_section == 'payments' %}
    <div class="card green">
        <h3><span class="icon"><i class="fas fa-money-bill-wave" style="color:#6bcb77;"></i></span> Выплаты</h3>
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
            <p style="color:rgba(255,255,255,0.3);font-size:14px;padding:8px 0;">Нет записей за этот период</p>
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
            <p style="color:rgba(255,255,255,0.3);font-size:14px;padding:8px 0;">Нет записей за этот период</p>
            {% endif %}
        </div>
    </div>
    {% endif %}
    <!-- ===== СОТРУДНИКИ (С УДАЛЕНИЕМ) ===== -->
    {% if current_section == 'employees' %}
    <div class="card green">
        <h3><span class="icon"><i class="fas fa-users"></i></span> Сотрудники</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div class="search-box">
            <i class="fas fa-search"></i>
            <input type="text" id="employeeSearch" placeholder="Поиск по имени..." oninput="filterEmployees()">
        </div>
        <div id="employeeList">
        {% if all_employees %}
        {% for emp in all_employees %}
        <div class="employee-card" data-name="{{ emp.name|lower }}">
            <div class="employee-info" onclick="window.location.href='/profile/{{ emp.id }}'">
                {% if emp.avatar %}
                <img src="data:image/jpeg;base64,{{ emp.avatar }}" class="employee-avatar" alt="{{ emp.name }}">
                {% else %}
                <div class="employee-avatar-placeholder"><i class="fas fa-user"></i></div>
                {% endif %}
                <div>
                    <div class="employee-name">{{ emp.name }}</div>
                    {% if emp.position %}
                    <span class="position-badge">{{ emp.position }}</span>
                    {% endif %}
                </div>
            </div>
            <div class="employee-stats">
                {% if session.is_admin %}
                ⭐ {{ emp.month_hours|round(1) if emp.month_hours else 0 }}ч · {{ emp.month_total|round(0) if emp.month_total else 0 }}₽
                {% else %}
                👤 Сотрудник
                {% endif %}
            </div>
            {% if session.is_admin %}
            <div class="actions">
                <form method="POST" action="/delete_employee" onsubmit="return confirm('Удалить {{ emp.name }}? Все данные будут потеряны!')" onclick="event.stopPropagation();">
                    <input type="hidden" name="emp_id" value="{{ emp.id }}">
                    <button type="submit" class="delete-btn" title="Удалить сотрудника"><i class="fas fa-trash"></i></button>
                </form>
            </div>
            {% endif %}
        </div>
        {% endfor %}
        {% else %}
        <p style="text-align:center;color:rgba(255,255,255,0.3);padding:30px;"><i class="fas fa-face-frown"></i> Нет сотрудников</p>
        {% endif %}
        </div>
    </div>
    {% endif %}
    <!-- ===== МЕРОПРИЯТИЯ (С УДАЛЕНИЕМ) ===== -->
    {% if current_section == 'events' %}
    <div class="card gold">
        <h3><span class="icon"><i class="fas fa-calendar-alt" style="color:#fcd34d;"></i></span> Мероприятия</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div class="month-nav">
            <button class="btn btn-sm btn-purple" onclick="window.location.href='/section/events?month={{ prev_month }}'"><i class="fas fa-chevron-left"></i></button>
            <span class="month-title">{{ month_name }}</span>
            <button class="btn btn-sm btn-purple" onclick="window.location.href='/section/events?month={{ next_month }}'"><i class="fas fa-chevron-right"></i></button>
        </div>
        <div class="calendar-grid">
            <div style="font-weight:700;color:rgba(255,255,255,0.2);text-align:center;font-size:11px;text-transform:uppercase;">Пн</div>
            <div style="font-weight:700;color:rgba(255,255,255,0.2);text-align:center;font-size:11px;text-transform:uppercase;">Вт</div>
            <div style="font-weight:700;color:rgba(255,255,255,0.2);text-align:center;font-size:11px;text-transform:uppercase;">Ср</div>
            <div style="font-weight:700;color:rgba(255,255,255,0.2);text-align:center;font-size:11px;text-transform:uppercase;">Чт</div>
            <div style="font-weight:700;color:rgba(255,255,255,0.2);text-align:center;font-size:11px;text-transform:uppercase;">Пт</div>
            <div style="font-weight:700;color:rgba(255,255,255,0.2);text-align:center;font-size:11px;text-transform:uppercase;">Сб</div>
            <div style="font-weight:700;color:rgba(255,255,255,0.2);text-align:center;font-size:11px;text-transform:uppercase;">Вс</div>
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
        <div style="margin-top:20px;">
            <h4 style="color:rgba(255,255,255,0.4);margin-bottom:12px;"><i class="fas fa-list" style="color:#fcd34d;"></i> События месяца</h4>
            <div class="events-list">
                {% if events %}
                {% for event in events %}
                <div class="event-item">
                    <div class="event-date"><i class="far fa-calendar-alt"></i> {{ event.date_ru }}</div>
                    <div class="event-title">{{ event.title }}</div>
                    <div class="event-desc">{{ event.description or '' }}</div>
                    {% if session.is_admin %}
                    <div class="event-actions">
                        <form method="POST" action="/delete_event" style="display:inline;" onsubmit="return confirm('Удалить мероприятие?')">
                            <input type="hidden" name="event_id" value="{{ event.id }}">
                            <button type="submit" class="delete-event-btn"><i class="fas fa-trash"></i></button>
                        </form>
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
                {% else %}
                <p style="color:rgba(255,255,255,0.3);text-align:center;padding:16px;"><i class="far fa-calendar-alt"></i> Нет событий на этот месяц</p>
                {% endif %}
            </div>
        </div>
        {% if session.is_admin %}
        <div style="margin-top:18px;padding-top:18px;border-top:1px solid rgba(255,255,255,0.06);">
            <h4 style="color:rgba(255,255,255,0.5);margin-bottom:12px;"><i class="fas fa-plus-circle" style="color:#fcd34d;"></i> Добавить мероприятие</h4>
            <form method="POST" action="/add_event" class="form-group">
                <input type="date" name="event_date" value="{{ today }}" required>
                <input type="text" name="title" placeholder="Название" required>
                <input type="text" name="description" placeholder="Описание">
                <button type="submit" class="btn btn-gold"><i class="fas fa-plus"></i> Добавить</button>
            </form>
        </div>
        {% endif %}
    </div>
    {% endif %}
    <!-- ===== ТОП СОТРУДНИКОВ ===== -->
    {% if current_section == 'top' and session.is_admin %}
    <div class="card top">
        <h3><span class="icon"><i class="fas fa-trophy" style="color:#ffd93d;"></i></span> Топ сотрудников по зарплате</h3>
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> На главную</a>
        <div class="month-selector">
            <form method="GET" action="/section/top" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
                <input type="month" name="month" value="{{ selected_month }}">
                <button type="submit" class="btn btn-sm btn-purple"><i class="fas fa-search"></i> Показать</button>
            </form>
        </div>
        {% if top_employees %}
        <div class="chart-container">
            {% for emp in top_employees %}
            <div class="chart-bar">
                <div class="bar-label">{{ emp.name }} {% if loop.index == 1 %}🥇{% elif loop.index == 2 %}🥈{% elif loop.index == 3 %}🥉{% endif %}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width: {{ emp.percent }}%;">
                        {{ emp.total|round(0) }} ₽
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <p style="text-align:center;color:rgba(255,255,255,0.3);padding:30px;"><i class="fas fa-inbox"></i> Нет данных за этот месяц</p>
        {% endif %}
    </div>
    {% endif %}
    <!-- ===== ДОБАВИТЬ ===== -->
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
                {% for emp in all_employees %}
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
    <!-- ===== АУДИТ ===== -->
    {% if current_section == 'audit' and session.is_admin %}
    <div class="card" style="border-left: 3px solid #f472b6;">
        <h3><span class="icon"><i class="fas fa-history" style="color:#f472b6;"></i></span> История изменений (Аудит)</h3>
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
        <p style="color:rgba(255,255,255,0.3);"><i class="fas fa-inbox"></i> История пока пуста</p>
        {% endif %}
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
    btn.className = newTheme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
}
document.addEventListener('DOMContentLoaded', function() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        const btn = document.querySelector('.theme-toggle i');
        if (savedTheme === 'light') btn.className = 'fas fa-sun';
    }
    if (window.location.pathname.includes('/section/chat')) {
        setInterval(function() {
            var select = document.querySelector('.chat-select');
            if (select) {
                var toId = select.value;
                if (toId) {
                    fetch('/get_messages?to_id=' + toId)
                        .then(r => r.json())
                        .then(data => {
                            var container = document.getElementById('chatMessages');
                            if (container) {
                                container.innerHTML = data.html;
                            }
                        });
                }
            }
        }, 10000);
    }
});
function filterEmployees() {
    const input = document.getElementById('employeeSearch');
    const filter = input.value.toLowerCase();
    const cards = document.querySelectorAll('#employeeList .employee-card');
    cards.forEach(card => {
        const name = card.getAttribute('data-name');
        card.style.display = name && name.includes(filter) ? 'flex' : 'none';
    });
}
function addEvent(date) {
    var title = prompt('Введите название мероприятия:');
    if (title) {
        var desc = prompt('Описание (необязательно):');
        var form = document.createElement('form');
        form.method = 'POST';
        form.action = '/add_event';
        form.innerHTML = `
            <input type="hidden" name="event_date" value="${date}">
            <input type="hidden" name="title" value="${title}">
            <input type="hidden" name="description" value="${desc || ''}">
        `;
        document.body.appendChild(form);
        form.submit();
    }
}
</script>
</body>
</html>
'''

# === ПРОФИЛЬ ===
PROFILE_HTML = '''
<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ user.name }} — Зарплата Клуб</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: #0b0b1a;
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
            max-width: 900px;
            margin: 0 auto;
            background: rgba(255,255,255,0.06);
            backdrop-filter: blur(20px);
            border-radius: 40px;
            padding: 35px;
            box-shadow: 0 30px 60px rgba(0,0,0,0.5);
            position: relative;
            z-index: 1;
            border: 1px solid rgba(255,255,255,0.05);
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
        .back-link { color: rgba(255,255,255,0.4); font-weight: 600; text-decoration: none; transition: 0.3s; }
        .back-link:hover { color: #c084fc; transform: translateX(-4px); }
        .profile-avatar { width: 120px; height: 120px; border-radius: 50%; object-fit: cover; border: 3px solid rgba(192,132,252,0.2); }
        .profile-avatar-placeholder {
            width: 120px; height: 120px; border-radius: 50%;
            background: rgba(255,255,255,0.04);
            border: 3px solid rgba(255,255,255,0.06);
            display: flex; align-items: center; justify-content: center;
            font-size: 50px; color: rgba(255,255,255,0.2);
        }
        .btn-avatar { background: rgba(192,132,252,0.15); color: #c084fc; border: 1px solid rgba(192,132,252,0.2); padding: 8px 16px; border-radius: 12px; cursor: pointer; transition: 0.3s; font-size: 13px; }
        .btn-avatar:hover { background: rgba(192,132,252,0.25); }
        .btn-sm { padding: 6px 14px; font-size: 12px; border-radius: 10px; }
        .btn-purple { background: linear-gradient(135deg, #9d4edd 0%, #6d28d9 100%); color: #fff; border: none; cursor: pointer; font-weight: 700; transition: 0.3s; }
        .btn-purple:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(157,78,221,0.3); }
        .btn { padding: 10px 20px; border: none; border-radius: 12px; font-size: 14px; font-weight: 700; cursor: pointer; transition: all 0.3s ease; color: #fff; display: inline-flex; align-items: center; gap: 8px; }
        .btn:hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 12px 30px rgba(0,0,0,0.2); }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 12px;
            margin: 20px 0;
        }
        .stat-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            padding: 14px;
            border-radius: 16px;
            text-align: center;
        }
        .stat-card .number {
            font-size: 22px; font-weight: 800;
            background: linear-gradient(135deg, #c084fc 0%, #f472b6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-card .label { color: rgba(255,255,255,0.3); font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 3px; }
        .stat-card .icon { font-size: 18px; display: block; margin-bottom: 3px; color: rgba(255,255,255,0.1); }
        .position-badge {
            display: inline-block;
            padding: 4px 14px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: 600;
            background: rgba(192,132,252,0.15);
            color: #c084fc;
            border: 1px solid rgba(192,132,252,0.15);
            margin-top: 6px;
        }
        .form-group { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
        .form-group select, .form-group input {
            padding: 10px 14px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 12px;
            color: #fff;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            outline: none;
            flex: 1;
            min-width: 120px;
        }
        .form-group select option { background: #1a1a2e; color: #fff; }
        .form-group select:focus, .form-group input:focus { border-color: #c084fc; box-shadow: 0 0 0 4px rgba(192,132,252,0.1); }
        @media (max-width: 700px) {
            .container { padding: 16px; }
            .header h1 { font-size: 1.6em; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .form-group { flex-direction: column; }
            .form-group select, .form-group input { width: 100%; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1><i class="fas fa-user" style="color:#c084fc;"></i> Профиль</h1>
        <a href="/section/employees" class="back-link"><i class="fas fa-arrow-left"></i> Назад</a>
    </div>
    <div style="text-align:center;">
        {% if user.avatar %}
        <img src="data:image/jpeg;base64,{{ user.avatar }}" class="profile-avatar" alt="{{ user.name }}">
        {% else %}
        <div class="profile-avatar-placeholder"><i class="fas fa-user"></i></div>
        {% endif %}
        <h2 style="color:#fff;margin-top:15px;">{{ user.name }}</h2>
        <p style="color:rgba(255,255,255,0.4);">
            {% if user.id == 0 %}👑 Администратор
            {% elif session.is_admin %}⭐ Сотрудник
            {% else %}👤 Сотрудник
            {% endif %}
        </p>
        {% if user.position %}
        <div class="position-badge">{{ user.position }}</div>
        {% endif %}
        {% if session.user_id == user.id or session.is_admin %}
        <div style="margin-top:12px;">
            <form method="POST" action="/upload_avatar_self" enctype="multipart/form-data" style="display:inline;">
                <input type="file" name="avatar" accept="image/*" id="self-avatar-upload" style="display:none;" onchange="this.form.submit()">
                <label for="self-avatar-upload" class="btn-avatar"><i class="fas fa-camera"></i> Сменить аватар</label>
            </form>
        </div>
        {% endif %}
    </div>
    <div style="margin:20px 0;padding:16px;background:rgba(255,255,255,0.03);border-radius:16px;border:1px solid rgba(255,255,255,0.04);">
        <h4 style="color:rgba(255,255,255,0.6);margin-bottom:10px;"><i class="fas fa-briefcase" style="color:#c084fc;"></i> Моя должность</h4>
        <form method="POST" action="/update_position" class="form-group">
            <input type="text" name="position" placeholder="Введите свою должность (например, Бармен)" value="{{ user.position or '' }}" required>
            <button type="submit" class="btn btn-purple btn-sm"><i class="fas fa-save"></i> Сохранить</button>
        </form>
        <p style="color:rgba(255,255,255,0.2);font-size:12px;margin-top:6px;">Напишите свою должность — она будет отображаться в списке сотрудников.</p>
    </div>
    {% if can_view_stats %}
    <div class="stats-grid">
        <div class="stat-card"><span class="icon"><i class="fas fa-clock"></i></span><div class="number">{{ stats.total_hours|round(1) }}</div><div class="label">Часов</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-ruble-sign"></i></span><div class="number">{{ stats.total_salary|round(0) }}</div><div class="label">Зарплата</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-utensils"></i></span><div class="number">{{ stats.total_konserzhka }}</div><div class="label">Консержек</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-gift"></i></span><div class="number">{{ stats.total_bonus|round(0) }}</div><div class="label">Премии</div></div>
        <div class="stat-card"><span class="icon"><i class="fas fa-gem"></i></span><div class="number">{{ stats.grand_total|round(0) }}</div><div class="label">ИТОГО</div></div>
    </div>
    {% else %}
    <div style="text-align:center;padding:20px;color:rgba(255,255,255,0.3);">
        <i class="fas fa-lock"></i> Зарплата и часы скрыты
    </div>
    {% endif %}
</div>
</body>
</html>
'''

# === МАРШРУТЫ ===
@app.route('/')
def index():
    if session.get('user_id') is None:
        return render_template_string(HTML, session={}, all_employees=[], stats={}, audit_logs=[], chat_employees=[], chat_messages=[], chat_to_id=None, ai_insights=[], all_bonuses=[], all_logs=[], payments={'first': [], 'second': [], 'first_total': 0, 'second_total': 0}, top_employees=[], today=date.today().strftime('%Y-%m-%d'), selected_month=date.today().strftime('%Y-%m'), current_section='main', month_name='', prev_month='', next_month='', calendar_days=[], events=[], msg=request.args.get('msg'))

    conn = get_db()
    today = date.today()
    month = request.args.get('month', today.strftime('%Y-%m'))
    today_str = today.strftime('%Y-%m-%d')

    all_employees = []
    stats = {}
    audit_logs = []
    events = []
    all_bonuses = []
    all_logs = []
    payments = {'first': [], 'second': [], 'first_total': 0, 'second_total': 0}
    top_employees = []
    chat_employees = []
    chat_messages = []
    chat_to_id = None
    ai_insights = []

    employees_raw = conn.execute("SELECT id, name, avatar, is_admin, position FROM employees").fetchall()
    for emp in employees_raw:
        emp_data = {'id': emp[0], 'name': emp[1], 'avatar': emp[2] or '', 'is_admin': emp[3], 'position': emp[4] or ''}
        all_employees.append(emp_data)
        if emp[0] != session.get('user_id', -1):
            chat_employees.append({'id': emp[0], 'name': emp[1]})

    events_raw = conn.execute("SELECT id, event_date, title, description FROM events ORDER BY event_date DESC").fetchall()
    for ev in events_raw:
        events.append({'id': ev[0], 'date': ev[1], 'date_ru': format_date_ru(ev[1]), 'title': ev[2], 'description': ev[3]})

    bonuses_raw = conn.execute("SELECT f.payment_date, e.name, f.amount, f.description FROM fixed_payments f JOIN employees e ON f.employee_id=e.id ORDER BY f.payment_date DESC").fetchall()
    for b in bonuses_raw:
        all_bonuses.append({'date': b[0], 'date_ru': format_date_ru(b[0]), 'employee': b[1], 'amount': b[2], 'description': b[3]})

    if session.get('is_admin'):
        logs = conn.execute("SELECT h.work_date, e.name, h.hours, h.rate, h.konserzhka FROM hours_log h JOIN employees e ON h.employee_id=e.id WHERE h.work_date LIKE ? ORDER BY h.work_date DESC", (month + "%",)).fetchall()
        for log in logs:
            total = log[2] * log[3] + (1500 if log[4] == 1 else 0)
            all_logs.append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'employee': log[1], 'hours': log[2], 'rate': log[3], 'konserzhka': log[4], 'total': total})
            day = log[0].split('-')[2]
            period = 'first' if int(day) <= 15 else 'second'
            payments[period].append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'employee': log[1], 'hours': log[2], 'rate': log[3], 'konserzhka': log[4], 'total': total})
            payments[period + '_total'] = payments.get(period + '_total', 0) + total
    else:
        emp_id = session['user_id']
        logs = conn.execute("SELECT work_date, hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date DESC", (emp_id, month + "%")).fetchall()
        for log in logs:
            total = log[1] * log[2] + (1500 if log[3] == 1 else 0)
            all_logs.append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'employee': session['user_name'], 'hours': log[1], 'rate': log[2], 'konserzhka': log[3], 'total': total})
            day = log[0].split('-')[2]
            period = 'first' if int(day) <= 15 else 'second'
            payments[period].append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'employee': session['user_name'], 'hours': log[1], 'rate': log[2], 'konserzhka': log[3], 'total': total})
            payments[period + '_total'] = payments.get(period + '_total', 0) + total

    if session.get('is_admin'):
        total_emp = len(employees_raw)
        total_hours = 0
        total_salary = 0
        total_konserzhka = 0
        total_grand = 0
        for emp in employees_raw:
            logs_emp = conn.execute("SELECT hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ?", (emp[0], month + "%")).fetchall()
            month_hours = sum(l[0] for l in logs_emp)
            month_salary = sum(l[0] * l[1] for l in logs_emp)
            month_konserzhka = sum(1500 for l in logs_emp if l[2] == 1)
            total_hours += month_hours
            total_salary += month_salary
            total_konserzhka += month_konserzhka
            total_grand += month_salary + month_konserzhka
        stats = {'total_employees': total_emp, 'total_hours': total_hours, 'total_salary': total_salary, 'total_konserzhka': total_konserzhka, 'grand_total': total_grand}

        top_raw = []
        for emp in employees_raw:
            logs_emp = conn.execute("SELECT hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ?", (emp[0], month + "%")).fetchall()
            total_emp_salary = sum(l[0] * l[1] for l in logs_emp) + sum(1500 for l in logs_emp if l[2] == 1)
            top_raw.append({'id': emp[0], 'name': emp[1], 'total': total_emp_salary})
        top_raw.sort(key=lambda x: x['total'], reverse=True)
        max_top = top_raw[0]['total'] if top_raw else 1
        for emp in top_raw:
            emp['percent'] = (emp['total'] / max_top * 100) if max_top > 0 else 0
            top_employees = top_raw[:10]

        audit_raw = conn.execute("SELECT admin_name, action_type, action_details, action_date FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()
        for a in audit_raw:
            audit_logs.append({'admin_name': a[0], 'action_type': a[1], 'action_details': a[2], 'date_ru': format_date_ru(a[3])})
        
        ai_insights = generate_ai_insights(conn)
    else:
        stats = {'total_employees': len(employees_raw), 'total_hours': 0, 'total_salary': 0, 'total_konserzhka': 0, 'grand_total': 0}

    year, month_num = map(int, month.split('-'))
    days_in_month = get_month_days(year, month_num)
    calendar_days = []
    month_name_ru = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'][month_num - 1]
    events_by_date = {ev[1]: ev for ev in events_raw}
    first_weekday = days_in_month[0].weekday()
    start_offset = (first_weekday - 0) % 7
    for i in range(start_offset):
        calendar_days.append({'day': '', 'is_weekend': False, 'is_today': False, 'event': None, 'date_str': ''})
    for d in days_in_month:
        date_str = d.strftime('%Y-%m-%d')
        is_weekend = d.weekday() >= 5
        is_today = date_str == today_str
        event = events_by_date.get(date_str)
        calendar_days.append({'day': d.day, 'is_weekend': is_weekend, 'is_today': is_today, 'event': {'title': event[2], 'description': event[3]} if event else None, 'date_str': date_str})
    prev_month_date = date(year, month_num, 1) - timedelta(days=1)
    next_month_date = date(year, month_num, 1) + timedelta(days=32)
    prev_month = prev_month_date.strftime('%Y-%m')
    next_month = next_month_date.strftime('%Y-%m')

    conn.close()
    return render_template_string(
        HTML,
        session=session,
        all_employees=all_employees,
        stats=stats,
        audit_logs=audit_logs,
        chat_employees=chat_employees,
        chat_messages=chat_messages,
        chat_to_id=chat_to_id,
        ai_insights=ai_insights,
        all_bonuses=all_bonuses,
        all_logs=all_logs,
        payments=payments,
        top_employees=top_employees,
        today=today_str,
        selected_month=month,
        current_section='main',
        month_name=f'{month_name_ru} {year}',
        prev_month=prev_month,
        next_month=next_month,
        calendar_days=calendar_days,
        events=events,
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

    all_employees = []
    stats = {}
    audit_logs = []
    events = []
    all_bonuses = []
    all_logs = []
    payments = {'first': [], 'second': [], 'first_total': 0, 'second_total': 0}
    top_employees = []
    chat_employees = []
    chat_messages = []
    chat_to_id = None
    ai_insights = []

    employees_raw = conn.execute("SELECT id, name, avatar, is_admin, position FROM employees").fetchall()
    for emp in employees_raw:
        emp_data = {'id': emp[0], 'name': emp[1], 'avatar': emp[2] or '', 'is_admin': emp[3], 'position': emp[4] or ''}
        all_employees.append(emp_data)
        if emp[0] != session.get('user_id', -1):
            chat_employees.append({'id': emp[0], 'name': emp[1]})

    events_raw = conn.execute("SELECT id, event_date, title, description FROM events ORDER BY event_date DESC").fetchall()
    for ev in events_raw:
        events.append({'id': ev[0], 'date': ev[1], 'date_ru': format_date_ru(ev[1]), 'title': ev[2], 'description': ev[3]})

    bonuses_raw = conn.execute("SELECT f.payment_date, e.name, f.amount, f.description FROM fixed_payments f JOIN employees e ON f.employee_id=e.id ORDER BY f.payment_date DESC").fetchall()
    for b in bonuses_raw:
        all_bonuses.append({'date': b[0], 'date_ru': format_date_ru(b[0]), 'employee': b[1], 'amount': b[2], 'description': b[3]})

    if session.get('is_admin'):
        logs = conn.execute("SELECT h.work_date, e.name, h.hours, h.rate, h.konserzhka FROM hours_log h JOIN employees e ON h.employee_id=e.id WHERE h.work_date LIKE ? ORDER BY h.work_date DESC", (month + "%",)).fetchall()
        for log in logs:
            total = log[2] * log[3] + (1500 if log[4] == 1 else 0)
            all_logs.append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'employee': log[1], 'hours': log[2], 'rate': log[3], 'konserzhka': log[4], 'total': total})
            day = log[0].split('-')[2]
            period = 'first' if int(day) <= 15 else 'second'
            payments[period].append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'employee': log[1], 'hours': log[2], 'rate': log[3], 'konserzhka': log[4], 'total': total})
            payments[period + '_total'] = payments.get(period + '_total', 0) + total
    else:
        emp_id = session['user_id']
        logs = conn.execute("SELECT work_date, hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date DESC", (emp_id, month + "%")).fetchall()
        for log in logs:
            total = log[1] * log[2] + (1500 if log[3] == 1 else 0)
            all_logs.append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'employee': session['user_name'], 'hours': log[1], 'rate': log[2], 'konserzhka': log[3], 'total': total})
            day = log[0].split('-')[2]
            period = 'first' if int(day) <= 15 else 'second'
            payments[period].append({'date': log[0], 'date_ru': format_date_ru(log[0]), 'employee': session['user_name'], 'hours': log[1], 'rate': log[2], 'konserzhka': log[3], 'total': total})
            payments[period + '_total'] = payments.get(period + '_total', 0) + total

    if session.get('is_admin'):
        total_emp = len(employees_raw)
        total_hours = 0
        total_salary = 0
        total_konserzhka = 0
        total_grand = 0
        for emp in employees_raw:
            logs_emp = conn.execute("SELECT hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ?", (emp[0], month + "%")).fetchall()
            month_hours = sum(l[0] for l in logs_emp)
            month_salary = sum(l[0] * l[1] for l in logs_emp)
            month_konserzhka = sum(1500 for l in logs_emp if l[2] == 1)
            total_hours += month_hours
            total_salary += month_salary
            total_konserzhka += month_konserzhka
            total_grand += month_salary + month_konserzhka
        stats = {'total_employees': total_emp, 'total_hours': total_hours, 'total_salary': total_salary, 'total_konserzhka': total_konserzhka, 'grand_total': total_grand}

        top_raw = []
        for emp in employees_raw:
            logs_emp = conn.execute("SELECT hours, rate, konserzhka FROM hours_log WHERE employee_id=? AND work_date LIKE ?", (emp[0], month + "%")).fetchall()
            total_emp_salary = sum(l[0] * l[1] for l in logs_emp) + sum(1500 for l in logs_emp if l[2] == 1)
            top_raw.append({'id': emp[0], 'name': emp[1], 'total': total_emp_salary})
        top_raw.sort(key=lambda x: x['total'], reverse=True)
        max_top = top_raw[0]['total'] if top_raw else 1
        for emp in top_raw:
            emp['percent'] = (emp['total'] / max_top * 100) if max_top > 0 else 0
            top_employees = top_raw[:10]

        audit_raw = conn.execute("SELECT admin_name, action_type, action_details, action_date FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()
        for a in audit_raw:
            audit_logs.append({'admin_name': a[0], 'action_type': a[1], 'action_details': a[2], 'date_ru': format_date_ru(a[3])})
        
        ai_insights = generate_ai_insights(conn)
    else:
        stats = {'total_employees': len(employees_raw), 'total_hours': 0, 'total_salary': 0, 'total_konserzhka': 0, 'grand_total': 0}

    if section == 'chat':
        to_id = request.args.get('to_id', type=int)
        if to_id:
            chat_to_id = to_id
            msgs = conn.execute("SELECT m.*, e.name as from_name FROM messages m JOIN employees e ON m.from_id = e.id WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?) ORDER BY m.id", (session['user_id'], to_id, to_id, session['user_id'])).fetchall()
            for m in msgs:
                chat_messages.append({'id': m[0], 'from_id': m[1], 'to_id': m[2], 'message': m[3], 'date': m[4], 'date_ru': format_date_ru(m[4].split(' ')[0]), 'from_name': m[6]})
            conn.execute("UPDATE messages SET is_read = 1 WHERE from_id = ? AND to_id = ?", (to_id, session['user_id']))
            conn.commit()

    year, month_num = map(int, month.split('-'))
    days_in_month = get_month_days(year, month_num)
    calendar_days = []
    month_name_ru = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'][month_num - 1]
    events_by_date = {ev[1]: ev for ev in events_raw}
    first_weekday = days_in_month[0].weekday()
    start_offset = (first_weekday - 0) % 7
    for i in range(start_offset):
        calendar_days.append({'day': '', 'is_weekend': False, 'is_today': False, 'event': None, 'date_str': ''})
    for d in days_in_month:
        date_str = d.strftime('%Y-%m-%d')
        is_weekend = d.weekday() >= 5
        is_today = date_str == today_str
        event = events_by_date.get(date_str)
        calendar_days.append({'day': d.day, 'is_weekend': is_weekend, 'is_today': is_today, 'event': {'title': event[2], 'description': event[3]} if event else None, 'date_str': date_str})
    prev_month_date = date(year, month_num, 1) - timedelta(days=1)
    next_month_date = date(year, month_num, 1) + timedelta(days=32)
    prev_month = prev_month_date.strftime('%Y-%m')
    next_month = next_month_date.strftime('%Y-%m')

    conn.close()
    return render_template_string(
        HTML,
        session=session,
        all_employees=all_employees,
        stats=stats,
        audit_logs=audit_logs,
        chat_employees=chat_employees,
        chat_messages=chat_messages,
        chat_to_id=chat_to_id,
        ai_insights=ai_insights,
        all_bonuses=all_bonuses,
        all_logs=all_logs,
        payments=payments,
        top_employees=top_employees,
        today=today_str,
        selected_month=month,
        current_section=section,
        month_name=f'{month_name_ru} {year}',
        prev_month=prev_month,
        next_month=next_month,
        calendar_days=calendar_days,
        events=events,
        msg=request.args.get('msg')
    )

@app.route('/profile/<int:user_id>')
def profile(user_id):
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='Войдите в систему!'))
    conn = get_db()
    emp = conn.execute("SELECT id, name, avatar, is_admin, position FROM employees WHERE id=?", (user_id,)).fetchone()
    if not emp:
        conn.close()
        return redirect(url_for('section', section='employees', msg='Сотрудник не найден!'))
    can_view_stats = session.get('is_admin') or session['user_id'] == user_id
    stats = {}
    if can_view_stats:
        logs = conn.execute("SELECT hours, rate, konserzhka FROM hours_log WHERE employee_id=?", (user_id,)).fetchall()
        total_hours = sum(l[0] for l in logs)
        total_salary = sum(l[0] * l[1] for l in logs)
        total_konserzhka = sum(1500 for l in logs if l[2] == 1)
        bonuses = conn.execute("SELECT amount FROM fixed_payments WHERE employee_id=?", (user_id,)).fetchall()
        total_bonus = sum(b[0] for b in bonuses)
        stats = {'total_hours': total_hours, 'total_salary': total_salary, 'total_konserzhka': total_konserzhka, 'total_bonus': total_bonus, 'grand_total': total_salary + total_konserzhka + total_bonus}
    conn.close()
    return render_template_string(
        PROFILE_HTML,
        session=session,
        user={'id': emp[0], 'name': emp[1], 'avatar': emp[2] or '', 'is_admin': emp[3], 'position': emp[4] or ''},
        stats=stats,
        can_view_stats=can_view_stats
    )

@app.route('/update_position', methods=['POST'])
def update_position():
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='Войдите в систему!'))
    position = request.form.get('position', '').strip()
    user_id = session['user_id']
    conn = get_db()
    conn.execute("UPDATE employees SET position = ? WHERE id = ?", (position, user_id))
    conn.commit()
    conn.close()
    log_audit(session['user_id'], session['user_name'], 'Обновление должности', f'{session["user_name"]} — {position}')
    return redirect(url_for('profile', user_id=user_id, msg='Должность обновлена!'))

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

@app.route('/send_message', methods=['POST'])
def send_message():
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='Войдите в систему!'))
    to_id = int(request.form.get('to_id', 0))
    message = request.form.get('message', '').strip()
    if not to_id or not message:
        return redirect(url_for('section', section='chat', msg='Введите сообщение!'))
    conn = get_db()
    conn.execute("INSERT INTO messages (from_id, to_id, message, date) VALUES (?, ?, ?, ?)", (session['user_id'], to_id, message, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return redirect(url_for('section', section='chat', to_id=to_id))

@app.route('/get_messages')
def get_messages():
    if session.get('user_id') is None:
        return {'html': ''}
    to_id = request.args.get('to_id', type=int)
    if not to_id:
        return {'html': ''}
    conn = get_db()
    msgs = conn.execute("SELECT m.*, e.name as from_name FROM messages m JOIN employees e ON m.from_id = e.id WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?) ORDER BY m.id", (session['user_id'], to_id, to_id, session['user_id'])).fetchall()
    conn.close()
    html = ''
    for m in msgs:
        is_outgoing = m[1] == session['user_id']
        html += f'''<div class="chat-message {'outgoing' if is_outgoing else 'incoming'}"><div class="msg-sender">{m[6]}</div><div class="msg-text">{m[3]}</div><div class="msg-date">{format_date_ru(m[4].split(' ')[0])}</div></div>'''
    if not html:
        html = '<p style="color:rgba(255,255,255,0.3);text-align:center;padding:20px;">Нет сообщений.</p>'
    return {'html': html}

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
        conn.execute("INSERT INTO hours_log (employee_id, work_date, hours, rate, konserzhka) VALUES (?, ?, ?, ?, ?)", (emp_id, work_date, hours, rate, konserzhka))
        conn.commit()
        conn.close()
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
        conn.execute("INSERT INTO fixed_payments (employee_id, payment_date, amount, description) VALUES (?, ?, ?, ?)", (emp_id, payment_date, amount, description))
        conn.commit()
        conn.close()
        msg = f"{name}: премия {amount}₽ ({description or 'без описания'})"
        log_audit(session['user_id'], session['user_name'], 'Добавление премии', f'{name} — {amount}₽')
    except Exception as e:
        msg = f"Ошибка: {str(e)}"
    return redirect(url_for('section', section='bonus', msg=msg))

@app.route('/upload_avatar_self', methods=['POST'])
def upload_avatar_self():
    if session.get('user_id') is None:
        return redirect(url_for('index', msg='Войдите в систему!'))
    if 'avatar' not in request.files:
        return redirect(url_for('index', msg='Файл не выбран!'))
    file = request.files['avatar']
    if file.filename == '':
        return redirect(url_for('index', msg='Файл не выбран!'))
    if file:
        file_data = file.read()
        base64_data = base64.b64encode(file_data).decode('utf-8')
        conn = get_db()
        conn.execute("UPDATE employees SET avatar = ? WHERE id = ?", (base64_data, session['user_id']))
        conn.commit()
        conn.close()
        msg = "Аватар обновлён!"
        log_audit(session['user_id'], session['user_name'], 'Обновление аватара', f'{session["user_name"]}')
    else:
        msg = "Ошибка загрузки файла!"
    return redirect(url_for('profile', user_id=session['user_id'], msg=msg))

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
    logs = conn.execute("SELECT h.work_date, e.name, h.hours, h.rate, h.konserzhka FROM hours_log h JOIN employees e ON h.employee_id=e.id WHERE h.work_date LIKE ? ORDER BY h.work_date", (month + "%",)).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Дата', 'Сотрудник', 'Часы', 'Ставка', 'Консержка', 'Итого'])
    for log in logs:
        total = log[2] * log[3] + (1500 if log[4] == 1 else 0)
        writer.writerow([format_date_ru(log[0]), log[1], log[2], f"{log[3]} ₽/ч", 'Да' if log[4] == 1 else 'Нет', total])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name=f'zarplata_{month}.csv')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

import sqlite3
from flask import Flask, render_template, request, redirect, url_for, make_response
from datetime import datetime, date, timedelta
import uuid
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = "coworking_secret_2024"

# Конфигурация
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "coworking.db")

# Типы помещений
ALLOWED_TYPES = [
    ("workspace_open", "Открытое рабочее место"),
    ("office_light", "Кабинет «Лайт»"),
    ("office_premium", "Кабинет «Премиум»"),
    ("meeting_room", "Переговорная комната"),
]
ALLOWED_TYPE_KEYS = {t for t, _ in ALLOWED_TYPES}
ALLOWED_RENT_UNITS = {"days", "hours"}

# -----------------------
# Вспомогательные функции
# -----------------------

sessions = {}   # {session_id: {"username": "", "is_admin": bool}}

def get_user_info():
    session_id = request.cookies.get("session")
    if session_id:
        return sessions.get(session_id)
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_info = get_user_info()
        if not user_info:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_info = get_user_info()
        if not user_info or not user_info.get("is_admin"):
            return render_template("error.html", error="Доступ запрещен. Требуются права администратора.")
        return f(*args, **kwargs)
    return decorated_function

def can_book_date(desired_date: date) -> bool:
    return date.today() <= desired_date <= (date.today() + timedelta(days=30))

def period_end(start: date, rent_type: str, duration: int) -> date:
    if rent_type == "hours":
        return start
    return start + timedelta(days=duration - 1)

def overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return not (a_end < b_start or b_end < a_start)

def get_room_availability(room_type: str, target_date: date):
    """Проверяет доступность помещения на конкретную дату"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute("SELECT Date, RentType, Duration FROM Request WHERE RoomType=?", (room_type,))
    bookings = cur.fetchall()
    conn.close()
    
    for d_str, rtype, dur in bookings:
        start_date = datetime.strptime(d_str, "%Y-%m-%d").date()
        end_date = period_end(start_date, rtype, int(dur))
        
        if overlaps(target_date, target_date, start_date, end_date):
            return False
    
    return True

def find_alternative_date(room_type: str, desired_date: date, duration: int, rent_type: str):
    """Находит ближайшую доступную дату"""
    for i in range(1, 31):
        test_date = desired_date + timedelta(days=i)
        if can_book_date(test_date) and get_room_availability(room_type, test_date):
            return test_date
    return None

def find_alternative_type(target_date: date, duration: int, rent_type: str):
    """Находит доступные типы помещений на указанную дату"""
    available_types = []
    
    for room_type, room_label in ALLOWED_TYPES:
        if get_room_availability(room_type, target_date):
            end_date = period_end(target_date, rent_type, duration)
            available = True
            
            current_date = target_date
            while current_date <= end_date:
                if not get_room_availability(room_type, current_date):
                    available = False
                    break
                current_date += timedelta(days=1)
            
            if available:
                available_types.append(room_label)
    
    return available_types

def get_all_bookings(start_date=None, end_date=None):
    """Получает все заявки за период"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    query = """
        SELECT r.id, r.RoomType, r.Date, r.RentType, r.Duration, u.Login
        FROM Request r
        JOIN Users u ON r.id_users = u.id
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND r.Date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND r.Date <= ?"
        params.append(end_date)
    
    query += " ORDER BY r.Date DESC"
    
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    
    return rows

def get_available_rooms_for_date(target_date: date):
    """Получает список свободных помещений на дату"""
    available = {}
    
    for room_type, room_label in ALLOWED_TYPES:
        if get_room_availability(room_type, target_date):
            available[room_label] = "Свободно"
        else:
            available[room_label] = "Занято"
    
    return available

# -----------------------
# Основные маршруты
# -----------------------

@app.route("/")
def index():
    user_info = get_user_info()
    return render_template("index.html", user=user_info)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    
    login = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    
    if not login or not password:
        return render_template("register.html", error="Укажите логин и пароль.")
    
    if len(password) < 6:
        return render_template("register.html", error="Пароль должен содержать минимум 6 символов.")
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    try:
        cur.execute("INSERT INTO Users (Login, Password) VALUES (?, ?)", (login, password))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return render_template("register.html", error="Такой пользователь уже существует.")
    
    conn.close()
    return redirect(url_for("login", success="Регистрация успешна. Теперь войдите."))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        success = request.args.get("success")
        return render_template("login.html", success=success)
    
    login = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id FROM Users WHERE Login=? AND Password=?", (login, password))
    row = cur.fetchone()
    conn.close()
    
    if row:
        session_id = str(uuid.uuid4())
        # Проверяем, является ли пользователь администратором
        is_admin = (login == "admin")
        sessions[session_id] = {
            "username": login,
            "user_id": row[0],
            "is_admin": is_admin
        }
        
        resp = make_response(redirect(url_for("bookings_view")))
        resp.set_cookie("session", session_id, path="/", httponly=True, samesite="Lax")
        return resp
    
    return render_template("login.html", error="Неверные логин или пароль.")

@app.route("/logout")
def logout():
    session_id = request.cookies.get("session")
    if session_id in sessions:
        del sessions[session_id]
    
    resp = make_response(redirect(url_for("index")))
    resp.set_cookie("session", "", max_age=0, path="/")
    return resp

@app.route("/bookings")
@login_required
def bookings_view():
    user_info = get_user_info()
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, RoomType, Date, RentType, Duration 
        FROM Request 
        WHERE id_users=? 
        ORDER BY Date DESC
    """, (user_info["user_id"],))
    
    rows = cur.fetchall()
    conn.close()
    
    bookings = []
    type_dict = dict(ALLOWED_TYPES)
    for row in rows:
        room_type = type_dict.get(row[1], row[1])
        bookings.append(row[:1] + (room_type,) + row[2:])
    
    return render_template("bookings.html", 
                         user=user_info, 
                         bookings=bookings,
                         today=date.today().isoformat(),
                         max_date=(date.today() + timedelta(days=30)).isoformat())

@app.route("/book", methods=["POST"])
@login_required
def book():
    user_info = get_user_info()
    
    room_type = request.form.get("room_type", "").strip()
    date_str = request.form.get("start_date", "").strip()
    rent_type = request.form.get("duration_unit", "days").strip()
    duration_str = request.form.get("duration_value", "1").strip()
    
    if room_type not in ALLOWED_TYPE_KEYS:
        return render_template("bookings.html", 
                             user=user_info,
                             bookings=fetch_user_requests(user_info["user_id"]),
                             error="Некорректный тип помещения.")
    
    try:
        desired_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return render_template("bookings.html",
                             user=user_info,
                             bookings=fetch_user_requests(user_info["user_id"]),
                             error="Некорректная дата.")
    
    if not can_book_date(desired_date):
        return render_template("bookings.html",
                             user=user_info,
                             bookings=fetch_user_requests(user_info["user_id"]),
                             error="Можно бронировать только на ближайшие 30 дней.")
    
    try:
        duration = int(duration_str)
        if duration <= 0:
            raise ValueError
    except ValueError:
        return render_template("bookings.html",
                             user=user_info,
                             bookings=fetch_user_requests(user_info["user_id"]),
                             error="Длительность должна быть положительным числом.")
    
    # Проверяем доступность
    end_date = period_end(desired_date, rent_type, duration)
    current_date = desired_date
    available = True
    
    while current_date <= end_date:
        if not get_room_availability(room_type, current_date):
            available = False
            break
        current_date += timedelta(days=1)
    
    if not available:
        alt_date = find_alternative_date(room_type, desired_date, duration, rent_type)
        alt_types = find_alternative_type(desired_date, duration, rent_type)
        
        bookings = fetch_user_requests(user_info["user_id"])
        
        return render_template("bookings.html",
                             user=user_info,
                             bookings=bookings,
                             error="Помещение занято на выбранные даты.",
                             alt_date=alt_date,
                             alt_types=alt_types,
                             desired_room=room_type)
    
    # Создаем бронирование
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO Request (RoomType, Date, RentType, Duration, id_users)
        VALUES (?, ?, ?, ?, ?)
    """, (room_type, desired_date.isoformat(), rent_type, duration, user_info["user_id"]))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for("bookings_view"))

def fetch_user_requests(user_id):
    """Получает заявки пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, RoomType, Date, RentType, Duration 
        FROM Request 
        WHERE id_users=? 
        ORDER BY Date DESC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    
    bookings = []
    type_dict = dict(ALLOWED_TYPES)
    for row in rows:
        room_type = type_dict.get(row[1], row[1])
        bookings.append(row[:1] + (room_type,) + row[2:])
    
    return bookings

# -----------------------
# Админ-маршруты
# -----------------------

@app.route("/admin")
@admin_required
def admin_panel():
    user_info = get_user_info()
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM Users")
    total_users = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM Request")
    total_bookings = cur.fetchone()[0]
    
    today_str = date.today().isoformat()
    cur.execute("SELECT COUNT(*) FROM Request WHERE Date = ?", (today_str,))
    today_bookings = cur.fetchone()[0]
    
    conn.close()
    
    return render_template("admin.html",
                         user=user_info,
                         total_users=total_users,
                         total_bookings=total_bookings,
                         today_bookings=today_bookings,
                         get_all_bookings=get_all_bookings,
                         date=date)

@app.route("/admin/reports/bookings")
@admin_required
def admin_reports_bookings():
    user_info = get_user_info()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    
    if not start_date:
        start_date = (date.today() - timedelta(days=7)).isoformat()
    if not end_date:
        end_date = date.today().isoformat()
    
    bookings = get_all_bookings(start_date, end_date)
    
    return render_template("admin_reports.html",
                         user=user_info,
                         bookings=bookings,
                         start_date=start_date,
                         end_date=end_date)

@app.route("/admin/reports/availability")
@admin_required
def admin_reports_availability():
    user_info = get_user_info()
    target_date_str = request.args.get("date", date.today().isoformat())
    
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except ValueError:
        target_date = date.today()
    
    available_rooms = get_available_rooms_for_date(target_date)
    
    return render_template("admin_availability.html",
                         user=user_info,
                         target_date=target_date,
                         available_rooms=available_rooms,
                         rooms_list=ALLOWED_TYPES,
                         get_room_availability=get_room_availability)

@app.route("/admin/users")
@admin_required
def admin_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, Login FROM Users ORDER BY id")
    users_data = cur.fetchall()
    conn.close()
    
    users = []
    for user_id, login in users_data:
        is_admin = (login == "admin")
        users.append((user_id, login, 1 if is_admin else 0))
    
    return render_template("admin_users.html",
                         user=get_user_info(),
                         users=users)

if __name__ == "__main__":
    app.run(host="localhost", port=8000, debug=True)
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, make_response
from datetime import datetime, date, timedelta
import uuid
import os

app = Flask(__name__)
app.secret_key = "dev_secret"

# Всегда создаём БД в папке проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "coworking.db")
print(f"[INFO] Используется база данных: {DB_NAME}")

ALLOWED_TYPES = [
    ("workspace_open", "Открытое рабочее место"),
    ("office_light", "Кабинет «Лайт»"),
    ("office_premium", "Кабинет «Премиум»"),
    ("meeting_room", "Переговорная комната"),
]
ALLOWED_TYPE_KEYS = {t for t, _ in ALLOWED_TYPES}
ALLOWED_RENT_UNITS = {"days", "hours"}

# -----------------------
# Инициализация базы
# -----------------------

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Login TEXT UNIQUE,
        Password TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Request (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        RoomType TEXT,
        Date TEXT,              -- ISO: YYYY-MM-DD
        RentType TEXT,          -- 'days' | 'hours'
        Duration INTEGER,       -- целое положительное
        id_users INTEGER,
        FOREIGN KEY(id_users) REFERENCES Users(id)
    )
    """)
    # Индексы для ускорения проверок
    cur.execute("CREATE INDEX IF NOT EXISTS idx_request_room_date ON Request(RoomType, Date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_request_user ON Request(id_users)")
    conn.commit()
    conn.close()

init_db()

# -----------------------
# Вспомогательные
# -----------------------

sessions = {}   # {session_id: username}

def get_username():
    session_id = request.cookies.get("session")
    if session_id:
        return sessions.get(session_id)
    return None

def get_user_id(login):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id FROM Users WHERE Login=?", (login,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def can_book_date(desired_date: date) -> bool:
    # Не раньше сегодня, не позже чем через 30 дней
    return date.today() <= desired_date <= (date.today() + timedelta(days=30))

def period_end(start: date, rent_type: str, duration: int) -> date:
    # Часовые брони считаем занятием конкретного дня (без точного времени в схеме)
    if rent_type == "hours":
        return start
    # Дневные брони: включительно, duration>=1
    return start + timedelta(days=duration - 1)

def overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    # Пересечение периодов по датам
    return not (a_end < b_start or b_end < a_start)

def fetch_user_requests(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT RoomType, Date, RentType, Duration FROM Request WHERE id_users=?", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def fetch_room_requests(room_type: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT Date, RentType, Duration, id_users FROM Request WHERE RoomType=?", (room_type,))
    rows = cur.fetchall()
    conn.close()
    return rows

# -----------------------
# Маршруты
# -----------------------

@app.route("/")
def index():
    user = get_username()
    return render_template("index.html", user=user)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    login = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    if not login or not password:
        return render_template("register.html", error="Укажите логин и пароль.")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO Users (Login, Password) VALUES (?, ?)", (login, password))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return render_template("register.html", error="Такой пользователь уже существует.")
    conn.close()
    return render_template("login.html", success="Регистрация успешна. Теперь войдите.")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    login = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id FROM Users WHERE Login=? AND Password=?", (login, password))
        row = cur.fetchone()
        conn.close()
    except Exception as e:
        app.logger.error(f"Ошибка при чтении из базы: {e}")
        print(f"[DB ERROR] {e}")
        return render_template("login.html", error="Ошибка при подключении к базе данных.")
    if row:
        session_id = str(uuid.uuid4())
        sessions[session_id] = login
        resp = make_response(redirect(url_for("bookings_view")))
        resp.set_cookie("session", session_id, path="/", httponly=True, samesite="Lax")
        return resp
    return render_template("login.html", error="Неверные логин или пароль.")

@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("index")))
    resp.set_cookie("session", "", max_age=0, path="/")
    return resp

# Только свои заявки для текущего пользователя
@app.route("/bookings")
def bookings_view():
    user = get_username()
    if not user:
        return render_template("index.html", error="Войдите, чтобы бронировать помещения.")
    user_id = get_user_id(user)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM Request WHERE id_users=?", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return render_template("bookings.html", user=user, bookings=rows)

@app.route("/book", methods=["POST"])
def book():
    user = get_username()
    if not user:
        return render_template("index.html", error="Войдите, чтобы бронировать помещения.")

    # Сбор данных формы
    room_type = request.form.get("room_type", "").strip()
    date_str = request.form.get("start_date", "").strip()
    rent_type = request.form.get("duration_unit", "days").strip()
    duration_str = request.form.get("duration_value", "1").strip()

    # Валидации формы
    user_id_for_bookings = get_user_id(user)
    def render_with_bookings_error(msg):
        bookings = fetch_user_requests(user_id_for_bookings)
        return render_template("bookings.html", user=user, bookings=bookings, error=msg)

    if room_type not in ALLOWED_TYPE_KEYS:
        return render_with_bookings_error("Некорректный тип помещения.")
    if rent_type not in ALLOWED_RENT_UNITS:
        return render_with_bookings_error("Некорректная единица времени.")
    try:
        duration = int(duration_str)
        if duration <= 0:
            raise ValueError
    except ValueError:
        return render_with_bookings_error("Длительность должна быть положительным целым числом.")
    try:
        desired_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return render_with_bookings_error("Некорректная дата.")
    if not can_book_date(desired_date):
        return render_with_bookings_error("Бронирование доступно не ранее сегодня и не далее чем за месяц.")

    # Рассчитываем желаемый период
    start = desired_date
    end = period_end(desired_date, rent_type, duration)

    user_id = user_id_for_bookings

    # 1) Пересечения с заявками текущего пользователя:
    # Разрешаем перекрытие по периодам с другими типами помещений (чтобы можно было бронировать разные типы параллельно),
    # но запрещаем перекрытие с этим же типом помещения.
    user_requests = fetch_user_requests(user_id)
    for rt, d_str, rtype, dur in user_requests:
        s = datetime.strptime(d_str, "%Y-%m-%d").date()
        e = period_end(s, rtype, int(dur))
        if rt == room_type and overlaps(start, end, s, e):
            return render_with_bookings_error("Вы уже забронировали эту комнату на выбранный период.")

    # 2) Пересечения по выбранному типу помещения (другие пользователи)
    room_requests = fetch_room_requests(room_type)
    for d_str, rtype, dur, uid in room_requests:
        s = datetime.strptime(d_str, "%Y-%m-%d").date()
        e = period_end(s, rtype, int(dur))
        if overlaps(start, end, s, e):
            if uid != user_id:
                return render_with_bookings_error("Комната занята другим пользователем на этот период.")
            else:
                # собственная бронь того же пользователя — сообщение уже покрыто выше, но на всякий случай:
                return render_with_bookings_error("Вы уже забронировали эту комнату на выбранный период.")

    # Если конфликтов нет — сохраняем бронь
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO Request (RoomType, Date, RentType, Duration, id_users) VALUES (?, ?, ?, ?, ?)",
        (room_type, desired_date.isoformat(), rent_type, duration, user_id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("bookings_view"))

if __name__ == "__main__":
    app.run(host="localhost", port=8000, debug=True)

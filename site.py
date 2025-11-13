from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from datetime import datetime, date, timedelta
import uuid

# -----------------------
# Данные
# -----------------------

ALLOWED_TYPES = [
    ("workspace_open", "Открытое рабочее место"),
    ("office_light", "Кабинет «Лайт»"),
    ("office_premium", "Кабинет «Премиум»"),
    ("meeting_room", "Переговорная комната"),
]

rooms = [
    {"id": 1, "room_type": "workspace_open", "equipment_class": "Стандарт"},
    {"id": 2, "room_type": "office_light", "equipment_class": "Лайт"},
    {"id": 3, "room_type": "office_premium", "equipment_class": "Премиум"},
    {"id": 4, "room_type": "meeting_room", "equipment_class": "Переговорная"},
]

bookings = []
users = {}      # {username: password}
sessions = {}   # {session_id: username}

# -----------------------
# Вспомогательная логика
# -----------------------

def valid_room_type(room_type: str) -> bool:
    return any(t == room_type for t, _ in ALLOWED_TYPES)

def valid_unit(unit: str) -> bool:
    return unit in ("days", "hours")

def can_book_date(desired_date: date) -> bool:
    # Сегодня можно, в прошлом — нельзя, дальше 30 дней — нельзя
    return date.today() <= desired_date <= date.today() + timedelta(days=30)

def date_range(start: date, unit: str, value: int):
    # Возвращает множество занятых дат для заявки
    if unit == "days":
        return {start + timedelta(days=i) for i in range(value)}
    else:
        # Модель без часов — считаем, что бронирование “часами” занимает весь день
        return {start}

def is_room_available(room_id: int, start_date: date, unit: str, value: int) -> bool:
    wanted = date_range(start_date, unit, value)
    for b in bookings:
        if b["room_id"] != room_id or b["status"] != "accepted":
            continue
        occupied = date_range(b["start_date"], "days" if b["duration_days"] else "hours",
                              b["duration_days"] or b["duration_hours"])
        if wanted & occupied:
            return False
    return True

def find_room_by_type(room_type: str):
    return next((r for r in rooms if r["room_type"] == room_type), None)

def find_free_room(room_type: str, start_date: date, unit: str, value: int):
    # Для каждого типа у нас один room_id — проверяем его доступность
    room = find_room_by_type(room_type)
    if not room:
        return None
    return room if is_room_available(room["id"], start_date, unit, value) else None

def create_booking(room_id: int, desired_date: date, duration_unit: str, duration_value: int, username: str):
    booking = {
        "id": len(bookings) + 1,
        "room_id": room_id,
        "start_date": desired_date,
        "duration_hours": duration_value if duration_unit == "hours" else None,
        "duration_days": duration_value if duration_unit == "days" else None,
        "status": "accepted",
        "user": username,
    }
    bookings.append(booking)
    return booking

def user_duplicate_on_same_day(username: str, room_type: str, desired_date: date) -> bool:
    # Запрет дублей: тот же пользователь, тот же тип и та же дата (день)
    for b in bookings:
        if b["user"] != username or b["status"] != "accepted":
            continue
        room = next((r for r in rooms if r["id"] == b["room_id"]), None)
        if not room:
            continue
        if room["room_type"] != room_type:
            continue
        # Если любой из занятых дней заявки совпадает с desired_date — дубли запрещаем
        occupied = date_range(b["start_date"], "days" if b["duration_days"] else "hours",
                              b["duration_days"] or b["duration_hours"])
        if desired_date in occupied:
            return True
    return False

# -----------------------
# HTML шаблон
# -----------------------

def page(content: str):
    return f"""
    <!doctype html>
    <html lang="ru">
    <head>
      <meta charset="utf-8">
      <title>Coworking Booking</title>
      <style>
        body {{
          font-family: 'Segoe UI', sans-serif;
          background: linear-gradient(180deg, #eef4ff, #f5f8ff);
          color: #0f1b3d;
          margin: 0;
        }}
        header {{
          background:#e9f1ff;
          padding:15px;
          display:flex;
          justify-content:space-between;
          align-items:center;
          box-shadow:0 2px 6px rgba(0,0,0,0.1);
        }}
        nav a {{
          margin-left:15px;
          text-decoration:none;
          color:#2f6fed;
          font-weight:600;
        }}
        main {{
          max-width:900px;
          margin:30px auto;
          padding:20px;
        }}
        .card {{
          background:#fff;
          border-radius:12px;
          padding:20px;
          box-shadow:0 8px 20px rgba(47,111,237,0.15);
          margin-bottom:20px;
        }}
        label {{
          display:block;
          margin:10px 0;
        }}
        input, select {{
          width:100%;
          padding:10px;
          border:1px solid #cdd9f7;
          border-radius:8px;
          margin-top:5px;
        }}
        button {{
          background:#2f6fed;
          color:white;
          border:none;
          padding:12px 20px;
          border-radius:10px;
          cursor:pointer;
        }}
        button:hover {{ background:#5aa5ff; }}
        ul {{ padding-left:18px; }}
      </style>
    </head>
    <body>
      <header>
        <div><strong>Coworking</strong></div>
        <nav>
          <a href="/">Главная</a>
          <a href="/bookings">Бронирование</a>
          <a href="/register">Регистрация</a>
          <a href="/login">Вход</a>
          <a href="/logout">Выход</a>
        </nav>
      </header>
      <main>
        {content}
      </main>
    </body>
    </html>
    """

# -----------------------
# Сервер
# -----------------------

class Handler(BaseHTTPRequestHandler):
    def get_username(self):
        cookie = self.headers.get("Cookie")
        if cookie and "session=" in cookie:
            parts = cookie.split("session=")
            session_id = parts[-1].split(";")[0].strip()
            return sessions.get(session_id)
        return None

    def do_GET(self):
        if self.path == "/":
            user = self.get_username()
            if user:
                content = f"""
                <div class='card' style='text-align:center;'>
                  <h1>Привет, {user}!</h1>
                  <p>Добро пожаловать в коворкинг. Перейдите к бронированию или посмотрите свои заявки.</p>
                  <p><a href='/bookings'><button>Перейти к бронированию</button></a></p>
                </div>
                """
            else:
                content = """
                <div class='card' style='text-align:center;'>
                  <h1>Современный коворкинг</h1>
                  <p>Зарегистрируйтесь или войдите, чтобы бронировать помещения.</p>
                  <div style='margin-top:15px;'>
                    <a href='/register'><button>Регистрация</button></a>
                    <a href='/login'><button style='background:#5aa5ff; margin-left:10px;'>Вход</button></a>
                  </div>
                </div>
                <div class='card'>
                  <h2>Почему выбирают нас?</h2>
                  <ul>
                    <li>⚡ Быстрое онлайн‑бронирование</li>
                    <li>💻 Современные рабочие места</li>
                    <li>📅 Гибкие тарифы: часы или дни</li>
                    <li>☕ Зоны отдыха и кофе‑поинты</li>
                    <li>🌐 Высокоскоростной интернет</li>
                  </ul>
                </div>
                """
            html = page(content)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/register":
            form = """
            <div class="card">
              <h2>Регистрация</h2>
              <form method="POST" action="/register">
                <label>Логин <input type="text" name="username" required></label>
                <label>Пароль <input type="password" name="password" required></label>
                <button type="submit">Зарегистрироваться</button>
              </form>
            </div>
            """
            html = page(form)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/login":
            form = """
            <div class="card">
              <h2>Вход</h2>
              <form method="POST" action="/login">
                <label>Логин <input type="text" name="username" required></label>
                <label>Пароль <input type="password" name="password" required></label>
                <button type="submit">Войти</button>
              </form>
            </div>
            """
            html = page(form)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/logout":
            html = page("<div class='card'><p>Вы вышли из системы.</p><p><a href='/'><button>На главную</button></a></p></div>")
            self.send_response(200)
            self.send_header("Set-Cookie", "session=; Max-Age=0; Path=/")
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/bookings":
            user = self.get_username()
            if not user:
                html = page("<div class='card'><p style='color:red'>Войдите, чтобы бронировать помещения.</p><p><a href='/login'><button>Войти</button></a></p></div>")
            else:
                options_html = "".join([f'<option value="{t}">{label}</option>' for t, label in ALLOWED_TYPES])
                bookings_html = "".join([f"<li>#{b['id']} — комната {b['room_id']} — {b['start_date']}</li>" for b in bookings]) or "<li>Нет заявок</li>"
                form_html = f"""
                <div class="card">
                  <h2>Заявка на бронирование</h2>
                  <form method="POST" action="/book">
                    <label>Тип помещения <select name="room_type">{options_html}</select></label>
                    <label>Дата начала <input type="date" name="start_date" required></label>
                    <label>Единица 
                      <select name="duration_unit">
                        <option value="days">Дни</option>
                        <option value="hours">Часы</option>
                      </select>
                    </label>
                    <label>Длительность <input type="number" name="duration_value" value="1" min="1" required></label>
                    <button type="submit">Забронировать</button>
                  </form>
                </div>
                <div class="card">
                  <h2>Все заявки</h2>
                  <ul>{bookings_html}</ul>
                </div>
                """
                html = page(form_html)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found")

    def do_POST(self):
        if self.path == "/register":
            length = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(length).decode("utf-8")
            params = parse_qs(data)
            username = params.get("username", [""])[0].strip()
            password = params.get("password", [""])[0].strip()

            if not username or not password:
                html = page("<div class='card'><p style='color:red'>Укажите логин и пароль.</p><p><a href='/register'><button>Назад</button></a></p></div>")
            elif username in users:
                html = page("<div class='card'><p style='color:red'>Такой пользователь уже существует.</p><p><a href='/register'><button>Назад</button></a></p></div>")
            else:
                users[username] = password
                html = page("<div class='card'><p style='color:green'>Регистрация успешна. Теперь войдите.</p><p><a href='/login'><button>Войти</button></a></p></div>")

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/login":
            length = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(length).decode("utf-8")
            params = parse_qs(data)
            username = params.get("username", [""])[0].strip()
            password = params.get("password", [""])[0].strip()

            if users.get(username) == password:
                session_id = str(uuid.uuid4())
                sessions[session_id] = username
                html = page(f"<div class='card'><p style='color:green'>Вход выполнен. Привет, {username}!</p><p><a href='/bookings'><button>Перейти к бронированию</button></a></p></div>")
                self.send_response(200)
                self.send_header("Set-Cookie", f"session={session_id}; Path=/")
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
            else:
                html = page("<div class='card'><p style='color:red'>Неверные логин или пароль.</p><p><a href='/login'><button>Назад</button></a></p></div>")
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

        elif self.path == "/book":
            user = self.get_username()
            if not user:
                html = page("<div class='card'><p style='color:red'>Войдите, чтобы бронировать помещения.</p><p><a href='/login'><button>Войти</button></a></p></div>")
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
                return

            length = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(length).decode("utf-8")
            params = parse_qs(data)

            room_type = params.get("room_type", [""])[0]
            date_str = params.get("start_date", [""])[0]
            duration_unit = params.get("duration_unit", ["days"])[0]
            duration_value_str = params.get("duration_value", ["1"])[0]

            # Базовые проверки входных данных
            if not valid_room_type(room_type):
                html = page("<div class='card'><p style='color:red'>Некорректный тип помещения.</p><p><a href='/bookings'><button>Назад</button></a></p></div>")
                self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html.encode("utf-8")); return
            if not valid_unit(duration_unit):
                html = page("<div class='card'><p style='color:red'>Некорректная единица длительности.</p><p><a href='/bookings'><button>Назад</button></a></p></div>")
                self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html.encode("utf-8")); return
            try:
                duration_value = int(duration_value_str)
                if duration_value <= 0:
                    raise ValueError()
            except ValueError:
                html = page("<div class='card'><p style='color:red'>Длительность должна быть положительным числом.</p><p><a href='/bookings'><button>Назад</button></a></p></div>")
                self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html.encode("utf-8")); return

            try:
                desired_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                html = page("<div class='card'><p style='color:red'>Некорректная дата.</p><p><a href='/bookings'><button>Назад</button></a></p></div>")
                self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html.encode("utf-8")); return

            if not can_book_date(desired_date):
                html = page("<div class='card'><p style='color:red'>Бронирование доступно с сегодняшнего дня и не далее чем за месяц.</p><p><a href='/bookings'><button>Назад</button></a></p></div>")
                self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html.encode("utf-8")); return

            # Запрет дубля у пользователя на ту же дату и тип
            if user_duplicate_on_same_day(user, room_type, desired_date):
                html = page("<div class='card'><p style='color:red'>У вас уже есть заявка на этот тип в указанную дату.</p><p><a href='/bookings'><button>Назад</button></a></p></div>")
                self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html.encode("utf-8")); return

            # Проверяем наличие свободной комнаты
            room = find_free_room(room_type, desired_date, duration_unit, duration_value)
            if room:
                booking = create_booking(room["id"], desired_date, duration_unit, duration_value, user)
                message = f"""
                <div class='card' style='border-left:6px solid #0abf53;'>
                  <h2 style='color:#0abf53;'>✅ Заявка принята!</h2>
                  <p>Номер заявки: <strong>#{booking['id']}</strong></p>
                  <p>Комната: {booking['room_id']}</p>
                  <p>Дата начала: {booking['start_date']}</p>
                  <p>Длительность: {booking['duration_days'] or booking['duration_hours']} {duration_unit}</p>
                  <div style='margin-top:15px;'>
                    <a href='/bookings'><button>Вернуться к бронированию</button></a>
                  </div>
                </div>
                """
            else:
                # Предложить альтернативы
                alt_date = None
                for i in range(1, 31):
                    test_date = desired_date + timedelta(days=i)
                    if find_free_room(room_type, test_date, duration_unit, duration_value):
                        alt_date = test_date
                        break

                alt_type_label = None
                for t, label in ALLOWED_TYPES:
                    if t == room_type:
                        continue
                    if find_free_room(t, desired_date, duration_unit, duration_value):
                        alt_type_label = label
                        break

                suggestions = "<p style='color:red'>Нет свободных помещений выбранного типа.</p>"
                if alt_date:
                    suggestions += f"<p>📅 Ближайшая доступная дата для выбранного типа: {alt_date}</p>"
                if alt_type_label:
                    suggestions += f"<p>🏢 На выбранную дату доступен другой тип помещения: {alt_type_label}</p>"

                message = f"<div class='card'>{suggestions}<div style='margin-top:15px;'><a href='/bookings'><button>Назад</button></a></div></div>"

            html = page(message)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found")

# -----------------------
# Запуск
# -----------------------

if __name__ == "__main__":
    server = HTTPServer(("localhost", 8000), Handler)
    print("Сервер запущен: http://localhost:8000")
    server.serve_forever()

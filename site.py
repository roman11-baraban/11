from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from datetime import datetime, date, timedelta

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
    {"id": 2, "room_type": "workspace_open", "equipment_class": "Стандарт"},
    {"id": 3, "room_type": "office_light", "equipment_class": "Лайт"},
    {"id": 4, "room_type": "office_premium", "equipment_class": "Премиум"},
    {"id": 5, "room_type": "meeting_room", "equipment_class": "Проектор"},
    {"id": 6, "room_type": "meeting_room", "equipment_class": "Видеоконф"},
]

bookings = []

# -----------------------
# Логика
# -----------------------

def can_book_date(desired_date: date) -> bool:
    return desired_date - date.today() <= timedelta(days=30)

def find_free_room(room_type: str, desired_date: date):
    for room in rooms:
        if room["room_type"] == room_type:
            conflict = next((b for b in bookings if b["room_id"] == room["id"]
                             and b["start_date"] == desired_date
                             and b["status"] == "accepted"), None)
            if not conflict:
                return room
    return None

def create_booking(room_id: int, desired_date: date, duration_unit: str, duration_value: int):
    booking = {
        "id": len(bookings) + 1,
        "room_id": room_id,
        "start_date": desired_date,
        "duration_hours": duration_value if duration_unit == "hours" else None,
        "duration_days": duration_value if duration_unit == "days" else None,
        "status": "accepted"
    }
    bookings.append(booking)
    return booking

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
          transition:transform 0.2s;
        }}
        .card:hover {{ transform:translateY(-4px); }}
        label {{
          display:block;
          margin:10px 0;
          color:#0f1b3d;
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
          font-size:15px;
          transition:background 0.3s;
        }}
        button:hover {{ background:#5aa5ff; }}
        ul {{ list-style:none; padding:0; }}
        li {{ margin:5px 0; }}
      </style>
    </head>
    <body>
      <header>
        <div><strong>Coworking</strong></div>
        <nav>
          <a href="/">Главная</a>
          <a href="/bookings">Бронирование</a>
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
    def do_GET(self):
        if self.path == "/":
            html = page("<h1>Современный коворкинг</h1><p>Добро пожаловать! Забронируйте рабочее место или переговорную.</p>")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/bookings":
            options_html = "".join([f'<option value="{t}">{label}</option>' for t, label in ALLOWED_TYPES])
            bookings_html = "".join([f"<li>#{b['id']} — комната {b['room_id']} — {b['start_date']}</li>" for b in bookings])
            form_html = f"""
            <div class="card">
              <h2>Заявка на бронирование</h2>
              <form method="POST" action="/book">
                <label>Тип помещения <select name="room_type">{options_html}</select></label>
                <label>Дата начала <input type="date" name="start_date"></label>
                <label>Единица <select name="duration_unit"><option value="days">Дни</option><option value="hours">Часы</option></select></label>
                <label>Длительность <input type="number" name="duration_value" value="1"></label>
                <button type="submit">Забронировать</button>
              </form>
            </div>
            <div class="card">
              <h2>Все заявки</h2>
              <ul>{bookings_html if bookings_html else "<li>Нет заявок</li>"}</ul>
            </div>
            """
            html = page(form_html)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        if self.path == "/book":
            length = int(self.headers.get('Content-Length'))
            data = self.rfile.read(length).decode("utf-8")
            params = parse_qs(data)

            room_type = params.get("room_type", [""])[0]
            date_str = params.get("start_date", [""])[0]
            duration_unit = params.get("duration_unit", ["days"])[0]
            duration_value = int(params.get("duration_value", ["1"])[0])

            desired_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            message = ""
            if not can_book_date(desired_date):
                message = "<p style='color:red'>Бронирование доступно не далее чем за месяц.</p>"
            else:
                room = find_free_room(room_type, desired_date)
                if room:
                    create_booking(room["id"], desired_date, duration_unit, duration_value)
                    message = "<p style='color:green'>Заявка принята!</p>"
                else:
                    message = "<p style='color:red'>Нет свободных помещений.</p>"

            html = page(f"<div class='card'>{message}<p><a href='/bookings'>Назад</a></p></div>")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

# -----------------------
# Запуск
# -----------------------

if __name__ == "__main__":
    server = HTTPServer(("localhost", 8000), Handler)
    print("Сервер запущен: http://localhost:8000")
    server.serve_forever()

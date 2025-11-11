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

bookings = []  # заявки: {id, room_id, start_date, duration_days/hours, status}

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
# Веб‑сервер
# -----------------------

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            options_html = "".join([f'<option value="{t}">{label}</option>' for t, label in ALLOWED_TYPES])
            html = f"""
            <html><head><title>Coworking</title></head>
            <body style="font-family:sans-serif;background:#eef4ff;color:#0f1b3d;">
              <h1>Бронирование коворкинга</h1>
              <form method="POST" action="/book">
                <label>Тип помещения <select name="room_type">{options_html}</select></label><br>
                <label>Дата начала <input type="date" name="start_date"></label><br>
                <label>Единица <select name="duration_unit"><option value="days">Дни</option><option value="hours">Часы</option></select></label><br>
                <label>Длительность <input type="number" name="duration_value" value="1"></label><br>
                <button type="submit">Забронировать</button>
              </form>
              <h2>Все заявки:</h2>
              <ul>
                {''.join([f"<li>#{b['id']} комната {b['room_id']} дата {b['start_date']}</li>" for b in bookings])}
              </ul>
            </body></html>
            """
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

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body>{message}<br><a href='/'>Назад</a></body></html>".encode("utf-8"))

# -----------------------
# Запуск сервера
# -----------------------

if __name__ == "__main__":
    server = HTTPServer(("localhost", 8000), Handler)
    print("Сервер запущен: http://localhost:8000")
    server.serve_forever()

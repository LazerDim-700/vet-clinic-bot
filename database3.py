import os
import sqlite3
from datetime import date as dt_date, timedelta
from typing import Optional, List, Tuple

# =========================
# DB in project folder
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "vet_clinic.db")

print("USING DB FILE =", DB_NAME)
print("DATABASE.PY PATH =", os.path.abspath(__file__))

conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=30)
cursor = conn.cursor()

cursor.execute("PRAGMA busy_timeout = 30000")
cursor.execute("PRAGMA journal_mode = WAL")
conn.commit()


# =========================
# SCHEMA
# =========================

def create_tables() -> None:
    global cursor

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS specialists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            specialist_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            is_booked INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (specialist_id) REFERENCES specialists(id)
        )
    """)

    # ВАЖНО: tg_user_id и source есть сразу
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT NOT NULL,
            specialist_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            tg_user_id INTEGER,
            source TEXT,
            FOREIGN KEY (specialist_id) REFERENCES specialists(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_specialists (
            service_id INTEGER NOT NULL,
            specialist_id INTEGER NOT NULL,
            PRIMARY KEY (service_id, specialist_id),
            FOREIGN KEY(service_id) REFERENCES services(id),
            FOREIGN KEY(specialist_id) REFERENCES specialists(id)
        )
    """)

    conn.commit()


def ensure_appointments_columns() -> None:
    """
    На случай старой БД, где appointments без tg_user_id/source.
    Вызывай 1 раз при старте после create_tables().
    """
    global cursor

    cursor.execute("PRAGMA table_info(appointments)")
    cols = [r[1] for r in cursor.fetchall()]

    if "tg_user_id" not in cols:
        cursor.execute("ALTER TABLE appointments ADD COLUMN tg_user_id INTEGER")

    if "source" not in cols:
        cursor.execute("ALTER TABLE appointments ADD COLUMN source TEXT")

    conn.commit()


# =========================
# SEED
# =========================

def seed_data() -> None:
    global cursor

    cursor.execute("SELECT COUNT(*) FROM services")
    if cursor.fetchone()[0] > 0:
        return

    services = ["Терапия", "Хирургия", "Вакцинация", "УЗИ"]
    specialists = ["Иванов", "Петров", "Сидорова"]

    for s in services:
        cursor.execute("INSERT OR IGNORE INTO services(name) VALUES(?)", (s,))
    for sp in specialists:
        cursor.execute("INSERT OR IGNORE INTO specialists(name) VALUES(?)", (sp,))

    conn.commit()


def get_service_id(service_name: str) -> Optional[int]:
    global cursor
    cursor.execute("SELECT id FROM services WHERE name=?", (service_name,))
    row = cursor.fetchone()
    return row[0] if row else None


def get_specialist_id(name: str) -> Optional[int]:
    global cursor
    cursor.execute("SELECT id FROM specialists WHERE name = ?", (name,))
    row = cursor.fetchone()
    return row[0] if row else None


def seed_service_specialists() -> None:
    global cursor

    mapping = {
        "Терапия": ["Иванов", "Сидорова"],
        "Хирургия": ["Петров"],
        "Вакцинация": ["Иванов", "Петров"],
        "УЗИ": ["Сидорова"],
    }

    for service_name, spec_names in mapping.items():
        service_id = get_service_id(service_name)
        if not service_id:
            continue

        for spec_name in spec_names:
            spec_id = get_specialist_id(spec_name)
            if not spec_id:
                continue

            cursor.execute("""
                INSERT OR IGNORE INTO service_specialists(service_id, specialist_id)
                VALUES (?, ?)
            """, (service_id, spec_id))

    conn.commit()


def seed_schedule(days: int = 14) -> None:
    global cursor

    cursor.execute("SELECT COUNT(*) FROM work_schedule")
    if cursor.fetchone()[0] > 0:
        return

    cursor.execute("SELECT id FROM specialists")
    specialist_ids = [r[0] for r in cursor.fetchall()]

    times = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00"]
    start = dt_date.today()

    rows = []
    for d in range(days):
        day = (start + timedelta(days=d)).isoformat()
        for sid in specialist_ids:
            for t in times:
                rows.append((sid, day, t, 0))

    cursor.executemany("""
        INSERT INTO work_schedule(specialist_id, date, time, is_booked)
        VALUES (?, ?, ?, ?)
    """, rows)

    conn.commit()


# =========================
# GETTERS / FILTERS
# =========================

def get_services() -> List[str]:
    global cursor
    cursor.execute("SELECT name FROM services ORDER BY name")
    return [r[0] for r in cursor.fetchall()]


def get_specialists() -> List[str]:
    global cursor
    cursor.execute("SELECT name FROM specialists ORDER BY name")
    return [r[0] for r in cursor.fetchall()]


def get_specialist_name_by_id(specialist_id: int) -> Optional[str]:
    global cursor
    cursor.execute("SELECT name FROM specialists WHERE id = ?", (specialist_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def get_specialists_for_service(service_name: str) -> List[str]:
    global cursor
    cursor.execute("""
        SELECT sp.name
        FROM service_specialists ss
        JOIN services sv ON sv.id = ss.service_id
        JOIN specialists sp ON sp.id = ss.specialist_id
        WHERE sv.name = ?
        ORDER BY sp.name
    """, (service_name,))
    return [r[0] for r in cursor.fetchall()]


# =========================
# AVAILABILITY
# =========================

def get_free_dates_for_specialist(specialist_id: int) -> List[str]:
    global cursor
    cursor.execute("""
        SELECT DISTINCT date
        FROM work_schedule
        WHERE specialist_id = ? AND is_booked = 0
        ORDER BY date
    """, (specialist_id,))
    return [r[0] for r in cursor.fetchall()]


def get_free_slots(specialist_id: int, date: str) -> List[str]:
    global cursor
    cursor.execute("""
        SELECT time
        FROM work_schedule
        WHERE specialist_id = ? AND date = ? AND is_booked = 0
        ORDER BY time
    """, (specialist_id, date))
    return [r[0] for r in cursor.fetchall()]


def get_free_dates_all() -> List[str]:
    global cursor
    cursor.execute("""
        SELECT DISTINCT date
        FROM work_schedule
        WHERE is_booked = 0
        ORDER BY date
    """)
    return [r[0] for r in cursor.fetchall()]


def get_free_times_all_on_date(date: str) -> List[str]:
    global cursor
    cursor.execute("""
        SELECT DISTINCT time
        FROM work_schedule
        WHERE date = ? AND is_booked = 0
        ORDER BY time
    """, (date,))
    return [r[0] for r in cursor.fetchall()]


def get_specialists_free_on(date: str, time: str) -> List[Tuple[int, str]]:
    global cursor
    cursor.execute("""
        SELECT s.id, s.name
        FROM work_schedule ws
        JOIN specialists s ON s.id = ws.specialist_id
        WHERE ws.date = ? AND ws.time = ? AND ws.is_booked = 0
        ORDER BY s.name
    """, (date, time))
    return cursor.fetchall()


def get_specialists_free_on_for_service(service_name: str, date: str, time: str) -> List[Tuple[int, str]]:
    global cursor
    cursor.execute("""
        SELECT sp.id, sp.name
        FROM work_schedule ws
        JOIN specialists sp ON sp.id = ws.specialist_id
        JOIN service_specialists ss ON ss.specialist_id = sp.id
        JOIN services sv ON sv.id = ss.service_id
        WHERE sv.name = ?
          AND ws.date = ?
          AND ws.time = ?
          AND ws.is_booked = 0
        ORDER BY sp.name
    """, (service_name, date, time))
    return cursor.fetchall()


# =========================
# BOOKING
# =========================

def book_slot(specialist_id: int, date: str, time: str) -> bool:
    global cursor
    cursor.execute("""
        UPDATE work_schedule
        SET is_booked = 1
        WHERE specialist_id = ? AND date = ? AND time = ? AND is_booked = 0
    """, (specialist_id, date, time))
    conn.commit()
    return cursor.rowcount > 0


def unbook_slot(specialist_id: int, date: str, time: str) -> bool:
    global cursor
    cursor.execute("""
        UPDATE work_schedule
        SET is_booked = 0
        WHERE specialist_id = ? AND date = ? AND time = ? AND is_booked = 1
    """, (specialist_id, date, time))
    conn.commit()
    return cursor.rowcount > 0


# =========================
# APPOINTMENTS
# =========================

def save_appointment(
    service: str,
    specialist_id: int,
    date: str,
    time: str,
    name: str,
    phone: str,
    tg_user_id: Optional[int] = None,
    source: Optional[str] = None
) -> None:
    global cursor
    cursor.execute("""
        INSERT INTO appointments(service, specialist_id, date, time, name, phone, tg_user_id, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (service, specialist_id, date, time, name, phone, tg_user_id, source))
    conn.commit()


def get_user_appointments(tg_user_id: int):
    global cursor
    cursor.execute("""
        SELECT id, service, specialist_id, date, time
        FROM appointments
        WHERE tg_user_id = ?
        ORDER BY date, time
    """, (tg_user_id,))
    return cursor.fetchall()


def cancel_appointment(appointment_id: int, tg_user_id: int) -> bool:
    global cursor

    cursor.execute("""
        SELECT specialist_id, date, time
        FROM appointments
        WHERE id = ? AND tg_user_id = ?
    """, (appointment_id, tg_user_id))
    row = cursor.fetchone()
    if not row:
        return False

    specialist_id, date, time = row

    cursor.execute("DELETE FROM appointments WHERE id = ? AND tg_user_id = ?", (appointment_id, tg_user_id))
    conn.commit()

    unbook_slot(specialist_id, date, time)
    return True


def get_appointments_on(date: str):
    global cursor
    cursor.execute("""
        SELECT a.id, a.service, sp.name, a.time, a.name, a.phone, COALESCE(a.source,'')
        FROM appointments a
        JOIN specialists sp ON sp.id = a.specialist_id
        WHERE a.date = ?
        ORDER BY a.time
    """, (date,))
    return cursor.fetchall()


def admin_book_appointment(service: str, specialist_id: int, date: str, time: str, name: str, phone: str) -> bool:
    # бронируем слот
    if not book_slot(specialist_id, date, time):
        return False

    # сохраняем запись с source="phone"
    save_appointment(
        service=service,
        specialist_id=specialist_id,
        date=date,
        time=time,
        name=name,
        phone=phone,
        tg_user_id=None,
        source="phone"
    )
    return True

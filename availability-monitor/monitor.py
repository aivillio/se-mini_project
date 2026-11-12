import sqlite3
import time
import urllib.request
from datetime import datetime

DB_NAME = "availability.db"
HEALTH_URL = "http://127.0.0.1:5000/health"


def initialize_database():
    connection = sqlite3.connect(DB_NAME)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS health_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_time TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    connection.commit()
    connection.close()


def check_system():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=5) as response:
            return "UP" if response.status == 200 else "DOWN"
    except Exception:
        return "DOWN"


def record_status(status):
    connection = sqlite3.connect(DB_NAME)
    connection.execute(
        "INSERT INTO health_checks (check_time, status) VALUES (?, ?)",
        (datetime.now().isoformat(), status)
    )
    connection.commit()
    connection.close()


if __name__ == "__main__":
    initialize_database()
    print("Availability monitoring started...")

    while True:
        status = check_system()
        record_status(status)
        print(f"{datetime.now()} - System: {status}")
        time.sleep(10)
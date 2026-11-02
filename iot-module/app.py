
from flask import Flask, request, jsonify
import sqlite3
import time
from datetime import datetime

app = Flask(__name__)

DATABASE = "parking.db"
OCCUPIED_DISTANCE = 30  # Vehicle detected within 30 cm


def get_db():
    return sqlite3.connect(DATABASE)


def initialize_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots (
            slot_id TEXT PRIMARY KEY,
            distance_cm REAL,
            status TEXT,
            led_color TEXT,
            updated_at TEXT
        )
    """)

    for slot in ["P1", "P2", "P3", "P4"]:
        cursor.execute("""
            INSERT OR IGNORE INTO parking_slots
            (slot_id, distance_cm, status, led_color, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (slot, 100, "Vacant", "Green", datetime.now().isoformat()))

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return jsonify({
        "message": "IoT Parking Slot Monitoring System is running"
    })


@app.route("/api/slots", methods=["GET"])
def get_slots():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT slot_id, distance_cm, status, led_color, updated_at
        FROM parking_slots
    """)

    rows = cursor.fetchall()
    conn.close()

    slots = []
    for row in rows:
        slots.append({
            "slot_id": row[0],
            "distance_cm": row[1],
            "status": row[2],
            "led_color": row[3],
            "updated_at": row[4]
        })

    return jsonify(slots)


@app.route("/api/sensor", methods=["POST"])
def update_sensor():
    start_time = time.perf_counter()

    data = request.get_json(silent=True) or {}

    slot_id = data.get("slot_id")
    distance = data.get("distance_cm")

    if slot_id not in ["P1", "P2", "P3", "P4"]:
        return jsonify({"error": "Invalid parking slot"}), 400

    try:
        distance = float(distance)
        if not 2 <= distance <= 400:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "Distance must be between 2 and 400 cm"}), 400

    if distance <= OCCUPIED_DISTANCE:
        status = "Occupied"
        led_color = "Red"
    else:
        status = "Vacant"
        led_color = "Green"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE parking_slots
        SET distance_cm = ?, status = ?, led_color = ?, updated_at = ?
        WHERE slot_id = ?
    """, (distance, status, led_color, datetime.now().isoformat(), slot_id))

    conn.commit()
    conn.close()

    response_time_ms = (time.perf_counter() - start_time) * 1000

    return jsonify({
        "slot_id": slot_id,
        "distance_cm": distance,
        "status": status,
        "led_color": led_color,
        "response_time_ms": round(response_time_ms, 2)
    })


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)


from flask import Flask, jsonify, render_template, request
import sqlite3
import time

app = Flask(__name__)

DATABASE = "parking.db"


# Connect to SQLite database
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Create database and insert sample slots
def initialize_database():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots (
            slot_id TEXT PRIMARY KEY,
            status TEXT NOT NULL
        )
    """)

    sample_slots = [
        ("P1", "Vacant"),
        ("P2", "Occupied"),
        ("P3", "Vacant"),
        ("P4", "Occupied"),
        ("P5", "Vacant")
    ]

    conn.executemany("""
        INSERT OR IGNORE INTO parking_slots (slot_id, status)
        VALUES (?, ?)
    """, sample_slots)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return "Real-Time Parking Vacancy Display"


@app.route("/dashboard")
def dashboard():
    return render_template("index.html")


# Get vacancy count from database
@app.route("/api/vacancy")
def get_vacancy():
    start_time = time.time()

    conn = get_db_connection()

    total_slots = conn.execute(
        "SELECT COUNT(*) FROM parking_slots"
    ).fetchone()[0]

    vacant_slots = conn.execute(
        "SELECT COUNT(*) FROM parking_slots WHERE status = 'Vacant'"
    ).fetchone()[0]

    occupied_slots = total_slots - vacant_slots

    conn.close()

    response_time = round((time.time() - start_time) * 1000, 2)

    return jsonify({
        "total_slots": total_slots,
        "vacant_slots": vacant_slots,
        "occupied_slots": occupied_slots,
        "response_time_ms": response_time
    })


# Update slot status in database
@app.route("/api/update-slot", methods=["POST"])
def update_slot():
    data = request.get_json(silent=True) or {}

    slot_id = data.get("slot_id")
    new_status = data.get("status")

    if new_status not in ["Vacant", "Occupied"]:
        return jsonify({"error": "Invalid status"}), 400

    conn = get_db_connection()

    slot = conn.execute(
        "SELECT slot_id FROM parking_slots WHERE slot_id = ?",
        (slot_id,)
    ).fetchone()

    if slot is None:
        conn.close()
        return jsonify({"error": "Invalid parking slot"}), 404

    conn.execute(
        "UPDATE parking_slots SET status = ? WHERE slot_id = ?",
        (new_status, slot_id)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Slot updated successfully",
        "slot_id": slot_id,
        "status": new_status
    })


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)

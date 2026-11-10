import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_NAME = os.environ.get("QUEUE_DB", "offline_queue.db")
MAX_QUEUE_HOURS = 72

def initialize_queue():
    connection = sqlite3.connect(DB_NAME)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS offline_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            synced INTEGER DEFAULT 0
        )
    """)

    connection.commit()
    connection.close()


def add_to_queue(data):
    connection = sqlite3.connect(DB_NAME)

    connection.execute(
        "INSERT INTO offline_queue (data, created_at) VALUES (?, ?)",
        (json.dumps(data), datetime.now().isoformat())
    )

    connection.commit()
    connection.close()

    print("Data stored in offline queue.")


def get_pending_data():
    connection = sqlite3.connect(DB_NAME)

    cutoff_time = (
        datetime.now() - timedelta(hours=MAX_QUEUE_HOURS)
    ).isoformat()

    cursor = connection.execute("""
        SELECT id, data, created_at
        FROM offline_queue
        WHERE synced = 0 AND created_at >= ?
    """, (cutoff_time,))

    records = cursor.fetchall()
    connection.close()

    return records

def synchronize_queue():
    import urllib.request
    import urllib.error

    SERVER_SYNC_URL = "http://127.0.0.1:5000/sync"

    pending_records = get_pending_data()
    synced_count = 0

    for record_id, data, created_at in pending_records:
        payload = json.dumps([json.loads(data)]).encode("utf-8")

        request = urllib.request.Request(
            SERVER_SYNC_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status == 200:
                    connection = sqlite3.connect(DB_NAME)
                    connection.execute(
                        "UPDATE offline_queue SET synced = 1 WHERE id = ?",
                        (record_id,)
                    )
                    connection.commit()
                    connection.close()
                    synced_count += 1

        except (urllib.error.URLError, TimeoutError) as error:
            print(f"Synchronization failed for record {record_id}: {error}")
            break

    print(f"{synced_count} records synchronized successfully.")
    return synced_count
if __name__ == "__main__":
    initialize_queue()

    add_to_queue({
        "parking_slot": "P1",
        "status": "Occupied"
    })

    add_to_queue({
        "parking_slot": "P2",
        "status": "Vacant"
    })

    print("Pending records:", len(get_pending_data()))
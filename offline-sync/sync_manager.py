import time
import urllib.request
from offline_queue import get_pending_data, synchronize_queue

SERVER_URL = "http://127.0.0.1:5000/health"
SYNC_TIMEOUT = 300  # 5 minutes


def is_network_available():
    try:
        with urllib.request.urlopen(SERVER_URL, timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


def monitor_connection():
    print("Monitoring network connection...")

    while not is_network_available():
        print("Offline. Waiting for connection...")
        time.sleep(5)

    print("Connection restored!")

    pending_records = get_pending_data()
    print(f"Pending records: {len(pending_records)}")

    start_time = time.time()
    synced_count = synchronize_queue()
    elapsed = time.time() - start_time

    print(f"Records synchronized: {synced_count}")
    print(f"Synchronization time: {elapsed:.2f} seconds")

    if synced_count == len(pending_records) and elapsed <= SYNC_TIMEOUT:
        print("SUCCESS: All records synchronized within 5 minutes.")
    else:
        print("WARNING: Synchronization incomplete or exceeded 5 minutes.")


if __name__ == "__main__":
    monitor_connection()
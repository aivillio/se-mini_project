import sqlite3

DB_NAME = "availability.db"


def calculate_availability():
    connection = sqlite3.connect(DB_NAME)

    cursor = connection.cursor()
    cursor.execute("""
        SELECT
            COUNT(*) AS total_checks,
            SUM(CASE WHEN status = 'UP' THEN 1 ELSE 0 END) AS up_checks,
            SUM(CASE WHEN status = 'DOWN' THEN 1 ELSE 0 END) AS down_checks
        FROM health_checks
    """)

    total, up, down = cursor.fetchone()
    connection.close()

    if total == 0:
        print("No monitoring data available.")
        return

    availability = (up / total) * 100

    print("\n--- Availability Report ---")
    print(f"Total checks: {total}")
    print(f"Successful checks: {up}")
    print(f"Failed checks: {down}")
    print(f"Availability: {availability:.2f}%")
    print("Target: 99.9%")

    if availability >= 99.9:
        print("Status: Target achieved")
    else:
        print("Status: Target not achieved")


if __name__ == "__main__":
    calculate_availability()
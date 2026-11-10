from maintenance import calculate_availability

TARGET_AVAILABILITY = 99.9


def generate_monthly_report(
    total_seconds,
    downtime_seconds,
    maintenance_seconds
):
    availability = calculate_availability(
        total_seconds,
        downtime_seconds,
        maintenance_seconds
    )

    print("\n===== MONTHLY SYSTEM AVAILABILITY REPORT =====")
    print(f"Total period: {total_seconds} seconds")
    print(f"Downtime: {downtime_seconds} seconds")
    print(f"Scheduled maintenance: {maintenance_seconds} seconds")
    print(f"Availability: {availability:.4f}%")
    print(f"Required target: {TARGET_AVAILABILITY}%")

    if availability >= TARGET_AVAILABILITY:
        print("Result: TARGET ACHIEVED")
    else:
        print("Result: TARGET NOT ACHIEVED")

    return availability

if __name__ == "__main__":
    # Example: 30-day month
    total_seconds = 30 * 24 * 60 * 60

    # Example values for demonstration
    downtime_seconds = 40 * 60
    maintenance_seconds = 2 * 60 * 60

    generate_monthly_report(
        total_seconds,
        downtime_seconds,
        maintenance_seconds
    )
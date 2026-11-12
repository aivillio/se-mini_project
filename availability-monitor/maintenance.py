from datetime import datetime


def maintenance_duration(start_time, end_time):
    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    if end <= start:
        raise ValueError("End time must be after start time")

    return (end - start).total_seconds()


def calculate_availability(total_seconds, downtime_seconds, maintenance_seconds):
    if total_seconds <= 0:
        raise ValueError("Total time must be positive")

    if downtime_seconds < 0 or maintenance_seconds < 0:
        raise ValueError("Durations cannot be negative")

    if downtime_seconds + maintenance_seconds > total_seconds:
        raise ValueError("Downtime and maintenance exceed total time")

    eligible_time = total_seconds - maintenance_seconds
    availability = ((eligible_time - downtime_seconds) / eligible_time) * 100

    return availability

import heapq

# Parking-lot map: nodes represent entrance, junctions and slot locations.
PARKING_MAP = {
    "ENTRANCE": [("A", 5), ("B", 8)],
    "A": [("ENTRANCE", 5), ("C", 4), ("P1", 3)],
    "B": [("ENTRANCE", 8), ("C", 2), ("P3", 4)],
    "C": [("A", 4), ("B", 2), ("P2", 3), ("P4", 5)],
    "P1": [("A", 3)],
    "P2": [("C", 3)],
    "P3": [("B", 4)],
    "P4": [("C", 5)]
}

# Sample parking slots
PARKING_SLOTS = [
    {"slot_id": "P1", "vehicle_type": "2W", "status": "Vacant"},
    {"slot_id": "P2", "vehicle_type": "4W", "status": "Vacant"},
    {"slot_id": "P3", "vehicle_type": "EV", "status": "Occupied"},
    {"slot_id": "P4", "vehicle_type": "HANDICAP", "status": "Vacant"}
]


def shortest_path(start, destination):
    """Find the shortest route using Dijkstra's algorithm."""

    distances = {node: float("inf") for node in PARKING_MAP}
    distances[start] = 0

    priority_queue = [(0, start)]

    while priority_queue:
        current_distance, current_node = heapq.heappop(priority_queue)

        if current_distance > distances[current_node]:
            continue

        if current_node == destination:
            return current_distance

        for neighbour, weight in PARKING_MAP[current_node]:
            new_distance = current_distance + weight

            if new_distance < distances[neighbour]:
                distances[neighbour] = new_distance
                heapq.heappush(
                    priority_queue, (new_distance, neighbour)
                )

    return float("inf")


def allocate_slot(vehicle_type):
    """Allocate the nearest vacant slot for the vehicle category."""

    suitable_slots = []

    for slot in PARKING_SLOTS:
        if (
            slot["vehicle_type"] == vehicle_type
            and slot["status"] == "Vacant"
        ):
            distance = shortest_path("ENTRANCE", slot["slot_id"])

            suitable_slots.append((distance, slot))

    if not suitable_slots:
        return {"message": "No suitable vacant parking slot available"}

    distance, selected_slot = min(
        suitable_slots, key=lambda item: item[0]
    )

    selected_slot["status"] = "Occupied"

    return {
        "message": "Parking slot allocated successfully",
        "slot_id": selected_slot["slot_id"],
        "vehicle_type": vehicle_type,
        "distance": distance,
        "status": selected_slot["status"]
    }


if __name__ == "__main__":
    vehicle = input("Enter vehicle type (2W, 4W, EV, HANDICAP): ")
    result = allocate_slot(vehicle.upper())

    for key, value in result.items():
        print(f"{key}: {value}")

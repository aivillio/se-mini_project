
import unittest
import tempfile
import os

import app as parking_app


class ParkingIoTTests(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()

        parking_app.DATABASE = self.temp_db.name
        parking_app.initialize_database()

        self.client = parking_app.app.test_client()

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    def test_vehicle_detected(self):
        response = self.client.post(
            "/api/sensor",
            json={"slot_id": "P1", "distance_cm": 15}
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertEqual(data["status"], "Occupied")
        self.assertEqual(data["led_color"], "Red")

    def test_vehicle_leaves(self):
        response = self.client.post(
            "/api/sensor",
            json={"slot_id": "P1", "distance_cm": 100}
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertEqual(data["status"], "Vacant")
        self.assertEqual(data["led_color"], "Green")

    def test_invalid_slot(self):
        response = self.client.post(
            "/api/sensor",
            json={"slot_id": "P9", "distance_cm": 15}
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_distance(self):
        response = self.client.post(
            "/api/sensor",
            json={"slot_id": "P1", "distance_cm": 500}
        )

        self.assertEqual(response.status_code, 400)

    def test_response_time(self):
        response = self.client.post(
            "/api/sensor",
            json={"slot_id": "P1", "distance_cm": 15}
        )

        data = response.get_json()

        self.assertLess(data["response_time_ms"], 2000)


if __name__ == "__main__":
    unittest.main(verbosity=2)

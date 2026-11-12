import unittest
from maintenance import (
    maintenance_duration,
    calculate_availability
)


class TestMaintenance(unittest.TestCase):

    def test_one_hour_maintenance(self):
        duration = maintenance_duration(
            "2026-11-10T01:00:00",
            "2026-11-10T02:00:00"
        )
        self.assertEqual(duration, 3600)

    def test_invalid_time_range(self):
        with self.assertRaises(ValueError):
            maintenance_duration(
                "2026-11-10T02:00:00",
                "2026-11-10T01:00:00"
            )

    def test_availability_without_maintenance(self):
        result = calculate_availability(10000, 10, 0)
        self.assertEqual(result, 99.9)

    def test_availability_with_maintenance(self):
        result = calculate_availability(10000, 10, 1000)
        self.assertAlmostEqual(result, 99.88888888888889, places=6)

if __name__ == "__main__":
    unittest.main()
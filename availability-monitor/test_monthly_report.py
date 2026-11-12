import unittest
from monthly_report import generate_monthly_report


class TestMonthlyReport(unittest.TestCase):

    def test_monthly_target_achieved(self):
        total_seconds = 30 * 24 * 60 * 60
        downtime_seconds = 40 * 60
        maintenance_seconds = 2 * 60 * 60

        result = generate_monthly_report(
            total_seconds,
            downtime_seconds,
            maintenance_seconds
        )

        self.assertGreaterEqual(result, 99.9)


if __name__ == "__main__":
    unittest.main()
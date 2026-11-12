
import unittest
import os
import tempfile
import sqlite3
from datetime import datetime, timedelta

import offline_queue


class TestOfflineQueue(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()

        offline_queue.DB_NAME = self.temp_db.name
        offline_queue.initialize_queue()

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    def test_queue_storage(self):
        offline_queue.add_to_queue({
            "parking_slot": "P1",
            "status": "Occupied"
        })

        self.assertEqual(len(offline_queue.get_pending_data()), 1)

    def test_synchronization(self):
        offline_queue.add_to_queue({
            "parking_slot": "P2",
            "status": "Vacant"
        })

        synced_count = offline_queue.synchronize_queue()

        self.assertEqual(synced_count, 1)
        self.assertEqual(len(offline_queue.get_pending_data()), 0)

    def test_72_hour_queue_limit(self):
        offline_queue.add_to_queue({
            "parking_slot": "P3",
            "status": "Occupied"
        })

        connection = sqlite3.connect(offline_queue.DB_NAME)

        old_time = (
            datetime.now() - timedelta(hours=73)
        ).isoformat()

        connection.execute(
            "UPDATE offline_queue SET created_at = ?",
            (old_time,)
        )

        connection.commit()
        connection.close()

        self.assertEqual(len(offline_queue.get_pending_data()), 0)


if __name__ == "__main__":
    unittest.main()

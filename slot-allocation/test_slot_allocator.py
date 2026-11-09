import unittest
from slot_allocator import allocate_slot, PARKING_SLOTS


class SlotAllocationTests(unittest.TestCase):

    def setUp(self):
        PARKING_SLOTS[0]["status"] = "Vacant"
        PARKING_SLOTS[1]["status"] = "Vacant"
        PARKING_SLOTS[2]["status"] = "Occupied"
        PARKING_SLOTS[3]["status"] = "Vacant"

    def test_two_wheeler_allocation(self):
        result = allocate_slot("2W")
        self.assertEqual(result["slot_id"], "P1")

    def test_four_wheeler_allocation(self):
        result = allocate_slot("4W")
        self.assertEqual(result["slot_id"], "P2")

    def test_handicap_allocation(self):
        result = allocate_slot("HANDICAP")
        self.assertEqual(result["slot_id"], "P4")

    def test_unavailable_ev_slot(self):
        result = allocate_slot("EV")
        self.assertIn("message", result)


if __name__ == "__main__":
    unittest.main()
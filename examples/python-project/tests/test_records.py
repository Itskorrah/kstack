import unittest
from records import valid_record


class RecordTest(unittest.TestCase):
    def test_accepts_good_data(self):
        self.assertTrue(valid_record({"id": 2, "name": "Alice"}))

    def test_rejects_boolean_as_identifier(self):
        self.assertFalse(valid_record({"id": True, "name": "Alice"}))

    def test_rejects_missing_values(self):
        self.assertFalse(valid_record({"id": 0, "name": "Alice"}))
        self.assertFalse(valid_record({"id": 1, "name": " "}))
        self.assertFalse(valid_record({"id": 1}))

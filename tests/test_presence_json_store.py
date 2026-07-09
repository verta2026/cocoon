import tempfile
import unittest
from pathlib import Path

from presence.json_store import read_json, write_json


class PresenceJsonStoreTest(unittest.TestCase):
    def test_write_json_creates_parent_and_replaces_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "data.json"

            write_json(path, {"value": "one"})
            write_json(str(path), {"value": "two"})

            self.assertEqual(read_json(path), {"value": "two"})

    def test_read_json_returns_default_for_missing_or_invalid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"

            self.assertEqual(read_json(path, default=[]), [])
            path.write_text("{bad", encoding="utf-8")
            self.assertEqual(read_json(path, default=[]), [])


if __name__ == "__main__":
    unittest.main()

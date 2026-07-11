import tempfile
import unittest
from pathlib import Path

from bridge.json_store import read_json, write_json_atomic


class JsonStoreTest(unittest.TestCase):
    def test_write_json_atomic_creates_parent_and_replaces_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "state.json"

            write_json_atomic(path, {"value": "one"})
            write_json_atomic(path, {"value": "two"})

            self.assertEqual(read_json(path), {"value": "two"})
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_read_json_returns_default_for_missing_or_invalid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"

            self.assertEqual(read_json(path, default={"ok": False}), {"ok": False})
            path.write_text("{bad", encoding="utf-8")
            self.assertEqual(read_json(path, default={"ok": False}), {"ok": False})

    def test_read_json_handles_utf8_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bom.json"
            path.write_text('\ufeff{"ok": true}', encoding="utf-8")

            self.assertEqual(read_json(path), {"ok": True})


if __name__ == "__main__":
    unittest.main()

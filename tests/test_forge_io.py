import hashlib
import tempfile
import unittest
from pathlib import Path

from bridge.forge_io import atomic_write_text, read_json, read_text, sha_text


class ForgeIoTests(unittest.TestCase):
    def test_sha_text_treats_none_as_empty(self):
        empty_hash = hashlib.sha256(b"").hexdigest()

        self.assertEqual(sha_text(None), empty_hash)
        self.assertEqual(sha_text(""), empty_hash)
        self.assertEqual(sha_text("hello"), hashlib.sha256(b"hello").hexdigest())

    def test_read_text_strips_and_tolerates_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            path.write_text(" hello \n", encoding="utf-8")

            self.assertEqual(read_text(path), "hello")
            self.assertEqual(read_text(Path(tmp) / "missing.txt"), "")

    def test_read_json_returns_dict_or_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "good.json"
            bad = root / "bad.json"
            array = root / "array.json"
            good.write_text('{"ok": true}', encoding="utf-8")
            bad.write_text("{bad", encoding="utf-8")
            array.write_text("[1, 2]", encoding="utf-8")

            self.assertEqual(read_json(good), {"ok": True})
            self.assertEqual(read_json(bad), {})
            self.assertEqual(read_json(array), {})
            self.assertEqual(read_json(root / "missing.json"), {})

    def test_atomic_write_text_creates_parent_and_replaces_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "file.txt"

            atomic_write_text(path, "first")
            atomic_write_text(path, "second")

            self.assertEqual(path.read_text(encoding="utf-8"), "second")
            self.assertFalse(path.with_name(path.name + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()

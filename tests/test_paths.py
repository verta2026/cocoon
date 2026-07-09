import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from bridge.paths import safe_child_path


class PathsTest(unittest.TestCase):
    def test_safe_child_path_returns_file_under_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "file.txt"
            path.write_text("ok", encoding="utf-8")

            self.assertEqual(safe_child_path(root, "file.txt"), path.resolve())

    def test_safe_child_path_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            with self.assertRaises(HTTPException) as ctx:
                safe_child_path(root, "../secret.txt")

            self.assertEqual(ctx.exception.status_code, 404)

    def test_safe_child_path_can_allow_subdirs_and_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "dm" / "session.jsonl"
            path.parent.mkdir()
            path.write_text("{}", encoding="utf-8")

            self.assertEqual(
                safe_child_path(root, "dm/session.jsonl", allow_subdirs=True, suffix=".jsonl"),
                path.resolve(),
            )

    def test_safe_child_path_rejects_wrong_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "session.txt"
            path.write_text("{}", encoding="utf-8")

            with self.assertRaises(HTTPException):
                safe_child_path(root, "session.txt", suffix=".jsonl")


if __name__ == "__main__":
    unittest.main()

import io
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from bridge.uploads import save_upload_file, serve_upload_file


class FakeUpload:
    def __init__(self, filename, data):
        self.filename = filename
        self.file = io.BytesIO(data)


class UploadsTest(unittest.TestCase):
    def test_same_original_name_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            first = save_upload_file(upload_dir, FakeUpload("image.png", b"one"))
            second = save_upload_file(upload_dir, FakeUpload("image.png", b"two"))

            self.assertNotEqual(first["filename"], second["filename"])
            self.assertEqual(first["original_filename"], "image.png")
            self.assertEqual(second["original_filename"], "image.png")
            self.assertEqual(Path(first["path"]).read_bytes(), b"one")
            self.assertEqual(Path(second["path"]).read_bytes(), b"two")

    def test_upload_size_limit_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            with self.assertRaises(HTTPException) as ctx:
                save_upload_file(upload_dir, FakeUpload("large.txt", b"abcdef"), max_bytes=3)

            self.assertEqual(ctx.exception.status_code, 413)
            self.assertEqual(list(upload_dir.iterdir()), [])

    def test_serve_does_not_escape_upload_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upload_dir = root / "uploads"
            upload_dir.mkdir()
            (root / "secret.txt").write_text("secret", encoding="utf-8")

            with self.assertRaises(HTTPException) as ctx:
                serve_upload_file(upload_dir, "../secret.txt")

            self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()

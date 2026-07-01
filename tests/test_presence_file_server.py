import io
import os
import tempfile
import unittest
from pathlib import Path

from presence.file_server import (
    list_shared_file_metadata,
    resolve_shared_file_path,
    send_attachment,
)


class FakeHandler:
    def __init__(self):
        self.status = None
        self.headers = []
        self.ended = False
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.headers.append((name, value))

    def end_headers(self):
        self.ended = True


class PresenceFileServerTests(unittest.TestCase):
    def test_resolve_shared_file_path_rejects_unsafe_names(self):
        self.assertIsNone(resolve_shared_file_path("/data", "../secret"))
        self.assertIsNone(resolve_shared_file_path("/data", "nested/file.txt"))
        self.assertEqual(resolve_shared_file_path("/data", "safe.txt"), os.path.join("/data", "shared", "safe.txt"))

    def test_list_shared_file_metadata_sorts_files_and_ignores_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            shared = Path(tmp) / "shared"
            shared.mkdir()
            (shared / "b.txt").write_text("bb", encoding="utf-8")
            (shared / "a.txt").write_text("a", encoding="utf-8")
            (shared / "folder").mkdir()

            self.assertEqual(
                list_shared_file_metadata(tmp),
                [{"name": "a.txt", "size": 1}, {"name": "b.txt", "size": 2}],
            )

    def test_list_shared_file_metadata_tolerates_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(list_shared_file_metadata(tmp), [])

    def test_send_attachment_writes_headers_and_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "note.txt"
            fp.write_bytes(b"hello")
            handler = FakeHandler()

            send_attachment(handler, str(fp), "note.txt", include_body=True)

            self.assertEqual(handler.status, 200)
            self.assertTrue(handler.ended)
            self.assertEqual(handler.wfile.getvalue(), b"hello")
            self.assertIn(("Content-Type", "application/octet-stream"), handler.headers)
            self.assertIn(('Content-Disposition', 'attachment; filename="note.txt"'), handler.headers)
            self.assertIn(("Content-Length", "5"), handler.headers)

    def test_send_attachment_can_send_head_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "note.txt"
            fp.write_bytes(b"hello")
            handler = FakeHandler()

            send_attachment(handler, str(fp), "note.txt", include_body=False)

            self.assertEqual(handler.status, 200)
            self.assertEqual(handler.wfile.getvalue(), b"")


if __name__ == "__main__":
    unittest.main()

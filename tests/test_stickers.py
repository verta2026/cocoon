import io
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from bridge.stickers import (
    delete_sticker_file,
    edit_sticker_meta,
    list_sticker_items,
    load_sticker_meta,
    serve_sticker_file,
    upload_sticker_data,
    upload_sticker_file,
)


class FakeUpload:
    def __init__(self, filename, data):
        self.filename = filename
        self.file = io.BytesIO(data)


class StickersTest(unittest.TestCase):
    def test_upload_list_edit_and_delete_sticker(self):
        with tempfile.TemporaryDirectory() as tmp:
            sticker_dir = Path(tmp)
            meta_path = sticker_dir / "meta.json"

            uploaded = upload_sticker_file(sticker_dir, meta_path, FakeUpload("../wave.png", b"png"), "Wave", "hello")
            self.assertEqual(uploaded, {"file": "wave.png", "name": "Wave"})
            self.assertEqual((sticker_dir / "wave.png").read_bytes(), b"png")

            self.assertEqual(list_sticker_items(sticker_dir, meta_path), [
                {"file": "wave.png", "name": "Wave", "desc": "hello"}
            ])

            self.assertEqual(edit_sticker_meta(meta_path, "wave.png", desc="updated"), {"ok": True})
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(meta["wave.png"], {"name": "Wave", "desc": "updated"})

            self.assertEqual(delete_sticker_file(sticker_dir, meta_path, "wave.png"), {"ok": True})
            self.assertFalse((sticker_dir / "wave.png").exists())
            self.assertEqual(json.loads(meta_path.read_text(encoding="utf-8")), {})

    def test_list_ignores_missing_and_unsafe_meta_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            sticker_dir = Path(tmp)
            (sticker_dir / "ok.png").write_bytes(b"ok")
            meta_path = sticker_dir / "meta.json"
            meta_path.write_text(
                json.dumps({
                    "ok.png": {"name": "OK", "desc": ""},
                    "missing.png": {"name": "Missing", "desc": ""},
                    "../secret.png": {"name": "Secret", "desc": ""},
                }),
                encoding="utf-8",
            )

            self.assertEqual(list_sticker_items(sticker_dir, meta_path), [
                {"file": "ok.png", "name": "OK", "desc": ""}
            ])

    def test_serve_does_not_escape_sticker_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sticker_dir = root / "stickers"
            sticker_dir.mkdir()
            (root / "secret.png").write_bytes(b"secret")

            with self.assertRaises(HTTPException) as ctx:
                serve_sticker_file(sticker_dir, "../secret.png")

            self.assertEqual(ctx.exception.status_code, 404)


class StickerDataUploadTest(unittest.TestCase):
    PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

    def test_data_url_upload_saves_file_and_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sticker_dir = root / "stickers"
            meta_path = sticker_dir / "meta.json"

            result = upload_sticker_data(
                sticker_dir,
                meta_path,
                data_url="data:image/png;base64," + self.PNG_B64,
                name="dot",
                filename="my dot.png",
            )

            self.assertEqual(result["ok"], True)
            self.assertEqual(result["file"], "my_dot.png")
            self.assertTrue((sticker_dir / "my_dot.png").exists())
            self.assertEqual(load_sticker_meta(meta_path)["my_dot.png"]["name"], "dot")

    def test_data_url_upload_rejects_non_image_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(HTTPException) as ctx:
                upload_sticker_data(
                    root / "stickers",
                    root / "meta.json",
                    data_url="data:text/html;base64,PGI+",
                )
            self.assertEqual(ctx.exception.status_code, 400)

    def test_data_url_upload_rejects_bad_base64(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(HTTPException) as ctx:
                upload_sticker_data(
                    root / "stickers",
                    root / "meta.json",
                    data_url="data:image/png;base64,@@not-base64@@",
                )
            self.assertEqual(ctx.exception.status_code, 400)

    def test_data_url_upload_sanitizes_traversal_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sticker_dir = root / "stickers"
            result = upload_sticker_data(
                sticker_dir,
                sticker_dir / "meta.json",
                data_url="data:image/png;base64," + self.PNG_B64,
                filename="../../etc/passwd",
            )
            self.assertNotIn("..", result["file"])
            self.assertTrue((sticker_dir / result["file"]).exists())


if __name__ == "__main__":
    unittest.main()

import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace

from bridge.sticker_routes import StickerUpdate, register_sticker_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._decorator("GET", path)

    def post(self, path):
        return self._decorator("POST", path)

    def _decorator(self, method, path):
        def decorate(func):
            self.routes[(method, path)] = func
            return func
        return decorate


class StickerRoutesTest(unittest.TestCase):
    def test_registers_sticker_routes(self):
        app = FakeApp()
        calls = []

        def verify_token(request):
            calls.append(("verify", request.name))

        def verify_media_token(request, expected, token):
            calls.append(("media", request.name, expected, token))

        def serve_sticker_file(sticker_dir, name):
            return {"serve": str(sticker_dir), "name": name}

        def list_sticker_items(sticker_dir, sticker_meta):
            return [{"file": "wave.png"}]

        def upload_sticker_file(sticker_dir, sticker_meta, file, name, desc, max_bytes=None):
            return {"file": file.filename, "name": name, "desc": desc}

        def edit_sticker_meta(sticker_meta, file_name, name, desc):
            return {"edit": file_name, "name": name, "desc": desc}

        def delete_sticker_file(sticker_dir, sticker_meta, file_name):
            return {"delete": file_name}

        register_sticker_routes(
            app,
            verify_token=verify_token,
            verify_media_token=verify_media_token,
            bridge_token="server-secret",
            sticker_dir=Path("/tmp/stickers"),
            sticker_meta=Path("/tmp/stickers/meta.json"),
            serve_sticker_file=serve_sticker_file,
            list_sticker_items=list_sticker_items,
            upload_sticker_file=upload_sticker_file,
            edit_sticker_meta=edit_sticker_meta,
            delete_sticker_file=delete_sticker_file,
        )

        served = asyncio.run(
            app.routes[("GET", "/stickers/{name}")](
                "wave.png", SimpleNamespace(name="serve"), token="user-supplied"
            )
        )
        listed = asyncio.run(app.routes[("GET", "/stickers-list")](SimpleNamespace(name="list")))
        class FakeRequest(SimpleNamespace):
            headers = {}

            async def form(self):
                return {
                    "file": SimpleNamespace(filename="wave.png"),
                    "name": "Wave",
                    "desc": "hello",
                }

        uploaded = asyncio.run(app.routes[("POST", "/stickers-upload")](FakeRequest(name="upload")))
        edited = asyncio.run(
            app.routes[("POST", "/stickers-edit")](
                StickerUpdate(file="wave.png", name="Wave", desc="updated"),
                SimpleNamespace(name="edit"),
            )
        )
        deleted = asyncio.run(
            app.routes[("POST", "/stickers-delete")](
                StickerUpdate(file="wave.png"),
                SimpleNamespace(name="delete"),
            )
        )

        self.assertEqual(served["name"], "wave.png")
        self.assertEqual(listed, [{"file": "wave.png"}])
        self.assertEqual(uploaded, {"file": "wave.png", "name": "Wave", "desc": "hello"})
        self.assertEqual(edited, {"edit": "wave.png", "name": "Wave", "desc": "updated"})
        self.assertEqual(deleted, {"delete": "wave.png"})
        self.assertEqual(calls, [
            # The expected slot must carry the server secret, never the
            # caller-supplied ?token= (that mixup was the TTS auth bypass).
            ("media", "serve", "server-secret", "user-supplied"),
            ("verify", "list"),
            ("verify", "upload"),
            ("verify", "edit"),
            ("verify", "delete"),
        ])


if __name__ == "__main__":
    unittest.main()


class AnnotateStickersTest(unittest.TestCase):
    def _meta(self, tmp, data):
        import json
        meta = Path(tmp) / "meta.json"
        meta.write_text(json.dumps(data), encoding="utf-8")
        return meta

    def test_marker_becomes_name_and_desc(self):
        from bridge.stickers import annotate_stickers
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            meta = self._meta(tmp, {"cat.png": {"name": "happy", "desc": "paw on hand"}})
            out = annotate_stickers("hi [sticker:cat.png]", meta)
            self.assertEqual(out, 'hi [sticker cat.png "happy": paw on hand]')
            # 翻译后的形态不能再命中可发送标记的语法
            self.assertNotIn("[sticker:", out)

    def test_unknown_or_empty_meta_left_untouched(self):
        from bridge.stickers import annotate_stickers
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            meta = self._meta(tmp, {"cat.png": {"name": "", "desc": ""}})
            self.assertEqual(annotate_stickers("[sticker:cat.png]", meta), "[sticker:cat.png]")
            self.assertEqual(annotate_stickers("[sticker:dog.png]", meta), "[sticker:dog.png]")
            self.assertEqual(annotate_stickers("no marker", Path(tmp) / "none.json"), "no marker")

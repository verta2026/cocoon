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

        def serve_sticker_file(sticker_dir, name):
            return {"serve": str(sticker_dir), "name": name}

        def list_sticker_items(sticker_dir, sticker_meta):
            return [{"file": "wave.png"}]

        def upload_sticker_file(sticker_dir, sticker_meta, file, name, desc):
            return {"file": file.filename, "name": name, "desc": desc}

        def edit_sticker_meta(sticker_meta, file_name, name, desc):
            return {"edit": file_name, "name": name, "desc": desc}

        def delete_sticker_file(sticker_dir, sticker_meta, file_name):
            return {"delete": file_name}

        register_sticker_routes(
            app,
            verify_token=verify_token,
            sticker_dir=Path("/tmp/stickers"),
            sticker_meta=Path("/tmp/stickers/meta.json"),
            serve_sticker_file=serve_sticker_file,
            list_sticker_items=list_sticker_items,
            upload_sticker_file=upload_sticker_file,
            edit_sticker_meta=edit_sticker_meta,
            delete_sticker_file=delete_sticker_file,
        )

        served = asyncio.run(app.routes[("GET", "/stickers/{name}")]("wave.png", token="ignored"))
        listed = asyncio.run(app.routes[("GET", "/stickers-list")](SimpleNamespace(name="list")))
        uploaded = asyncio.run(
            app.routes[("POST", "/stickers-upload")](
                SimpleNamespace(name="upload"),
                SimpleNamespace(filename="wave.png"),
                name="Wave",
                desc="hello",
            )
        )
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
            ("verify", "list"),
            ("verify", "upload"),
            ("verify", "edit"),
            ("verify", "delete"),
        ])


if __name__ == "__main__":
    unittest.main()

import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from bridge.upload_routes import register_upload_routes


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


class UploadRoutesTest(unittest.TestCase):
    def test_registers_upload_list_and_file_routes(self):
        app = FakeApp()
        calls = []

        def verify_token(request):
            calls.append(("verify", request.name))

        def verify_media_token(request, bridge_token, token):
            calls.append(("media", request.name, bridge_token, token))

        def save_upload_file(upload_dir, file, max_bytes):
            return {"upload_dir": str(upload_dir), "file": file.filename, "max": max_bytes}

        def serve_upload_file(upload_dir, filename):
            return {"upload_dir": str(upload_dir), "filename": filename}

        def list_upload_files(upload_dir):
            return [{"name": "a.txt"}]

        register_upload_routes(
            app,
            verify_token=verify_token,
            verify_media_token=verify_media_token,
            save_upload_file=save_upload_file,
            serve_upload_file=serve_upload_file,
            list_upload_files=list_upload_files,
            upload_dir=Path("/tmp/uploads"),
            max_upload_bytes=123,
            bridge_token="secret",
        )

        class FakeRequest(SimpleNamespace):
            headers = {}

            async def form(self):
                return {"file": SimpleNamespace(filename="a.txt")}

        upload = asyncio.run(app.routes[("POST", "/upload")](FakeRequest(name="upload")))
        listed = asyncio.run(app.routes[("GET", "/files")](SimpleNamespace(name="list")))
        served = asyncio.run(
            app.routes[("GET", "/files/{filename}")](
                "a.txt",
                SimpleNamespace(name="file"),
                token="secret",
            )
        )

        self.assertEqual(upload["max"], 123)
        self.assertEqual(listed, {"files": [{"name": "a.txt"}]})
        self.assertEqual(served["filename"], "a.txt")
        self.assertEqual(calls, [
            ("verify", "upload"),
            ("verify", "list"),
            ("media", "file", "secret", "secret"),
        ])

    def test_file_route_propagates_media_auth_failure(self):
        app = FakeApp()

        def reject_media(request, bridge_token, token):
            raise HTTPException(403, "Bad token")

        register_upload_routes(
            app,
            verify_token=lambda request: None,
            verify_media_token=reject_media,
            save_upload_file=lambda upload_dir, file, max_bytes: {},
            serve_upload_file=lambda upload_dir, filename: {},
            upload_dir=Path("/tmp/uploads"),
            max_upload_bytes=0,
            bridge_token="secret",
        )

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                app.routes[("GET", "/files/{filename}")](
                    "a.txt",
                    SimpleNamespace(name="file"),
                    token="wrong",
                )
            )

        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()

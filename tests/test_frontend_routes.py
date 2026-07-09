import unittest

from fastapi import HTTPException

from bridge.auth import login_payload
from bridge.frontend_routes import config_js_path


class LoginPayloadTest(unittest.TestCase):
    def test_login_exchanges_password_for_token(self):
        self.assertEqual(
            login_payload("secret", "secret"), {"ok": True, "token": "secret"}
        )

    def test_login_rejects_wrong_password(self):
        with self.assertRaises(HTTPException) as ctx:
            login_payload("nope", "secret")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_login_rejects_empty_expected_token(self):
        with self.assertRaises(HTTPException) as ctx:
            login_payload("", "")
        self.assertEqual(ctx.exception.status_code, 403)


class ConfigJsPathTest(unittest.TestCase):
    def test_prefers_instance_config(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.example.js").write_text("window.CFG={};", encoding="utf-8")
            self.assertEqual(config_js_path(root).name, "config.example.js")

            (root / "config.js").write_text("window.CFG={};", encoding="utf-8")
            self.assertEqual(config_js_path(root).name, "config.js")


class FrontendServingTest(unittest.TestCase):
    def test_frontend_routes_serve_bundled_files(self):
        import asyncio
        import tempfile
        from pathlib import Path

        from fastapi import FastAPI

        from bridge.frontend_routes import register_frontend_routes

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "chat.html").write_text("<html>chat</html>", encoding="utf-8")
            (root / "login.html").write_text("<html>login</html>", encoding="utf-8")
            (root / "config.example.js").write_text("window.CFG={};", encoding="utf-8")
            (root / "src" / "mood.css").write_text("body{}", encoding="utf-8")
            (root / "avatar_ai.png").write_bytes(b"png")

            app = FastAPI()
            register_frontend_routes(app, frontend_dir=root)

            routes = {r.path for r in app.routes}
            self.assertIn("/", routes)
            self.assertIn("/login.html", routes)
            self.assertIn("/config.js", routes)
            self.assertIn("/src/{name}", routes)
            self.assertIn("/{name}.png", routes)

            handlers = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}
            resp = asyncio.run(handlers["/"]())
            self.assertEqual(str(resp.path), str(root / "chat.html"))
            self.assertEqual(resp.media_type, "text/html; charset=utf-8")

            resp = asyncio.run(handlers["/src/{name}"]("mood.css"))
            self.assertEqual(resp.media_type, "text/css; charset=utf-8")

            with self.assertRaises(HTTPException):
                asyncio.run(handlers["/src/{name}"]("../chat.html"))

            resp = asyncio.run(handlers["/{name}.png"]("avatar_ai"))
            self.assertEqual(str(resp.path), str(root / "avatar_ai.png"))


if __name__ == "__main__":
    unittest.main()

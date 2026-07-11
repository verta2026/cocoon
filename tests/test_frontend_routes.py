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
            (root / "login.html").write_text("<html>login</html>", encoding="utf-8")
            (root / "config.example.js").write_text("window.CFG={};", encoding="utf-8")
            (root / "avatar_ai.png").write_bytes(b"png")

            app = FastAPI()
            register_frontend_routes(app, frontend_dir=root)

            routes = {r.path for r in app.routes}
            self.assertIn("/", routes)
            self.assertIn("/login.html", routes)
            self.assertIn("/config.js", routes)
            self.assertIn("/{name}.png", routes)

            handlers = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}
            # 根路径直通 React 构建（旧内嵌聊天页已退役）
            resp = asyncio.run(handlers["/"]())
            self.assertEqual(resp.status_code, 307)
            self.assertEqual(resp.headers["location"], "/app/")

            with self.assertRaises(HTTPException):
                asyncio.run(handlers["/{name}.png"]("../chat"))

            resp = asyncio.run(handlers["/{name}.png"]("avatar_ai"))
            self.assertEqual(str(resp.path), str(root / "avatar_ai.png"))


class WebappFallbackTest(unittest.TestCase):
    def test_app_index_explains_missing_build(self):
        import asyncio
        import tempfile
        from pathlib import Path

        from fastapi import FastAPI

        from bridge.frontend_routes import register_webapp_routes

        with tempfile.TemporaryDirectory() as tmp:
            app = FastAPI()
            register_webapp_routes(app, webapp_dist=Path(tmp) / "dist")
            handlers = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}
            resp = asyncio.run(handlers["/app/"]())
            self.assertEqual(resp.status_code, 503)
            self.assertIn(b"npm run build", resp.body)


class AppConfigTest(unittest.TestCase):
    def test_app_config_requires_auth_and_serves_private_json(self):
        import asyncio
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace

        from fastapi import FastAPI

        from bridge.frontend_routes import register_frontend_routes

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "login.html").write_text("<html>login</html>", encoding="utf-8")
            (root / "config.private.json").write_text(
                '{"aiName": "Nova", "channelNames": {"123": "friend"}}',
                encoding="utf-8",
            )

            calls = []

            def verify_token(request):
                calls.append(request.name)

            app = FastAPI()
            register_frontend_routes(app, frontend_dir=root, verify_token=verify_token)

            handlers = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}
            self.assertIn("/app-config", handlers)
            data = asyncio.run(handlers["/app-config"](SimpleNamespace(name="cfg")))
            self.assertEqual(calls, ["cfg"])
            self.assertEqual(data["aiName"], "Nova")
            self.assertEqual(data["channelNames"], {"123": "friend"})

    def test_app_config_missing_or_broken_file_yields_empty(self):
        import tempfile
        from pathlib import Path

        from bridge.frontend_routes import load_private_config

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(load_private_config(root), {})
            (root / "config.private.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(load_private_config(root), {})
            (root / "config.private.json").write_text('["list"]', encoding="utf-8")
            self.assertEqual(load_private_config(root), {})

    def test_app_config_not_registered_without_verify(self):
        import tempfile
        from pathlib import Path

        from fastapi import FastAPI

        from bridge.frontend_routes import register_frontend_routes

        with tempfile.TemporaryDirectory() as tmp:
            app = FastAPI()
            register_frontend_routes(app, frontend_dir=Path(tmp))
            self.assertNotIn("/app-config", {r.path for r in app.routes})


if __name__ == "__main__":
    unittest.main()

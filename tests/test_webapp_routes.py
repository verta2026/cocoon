"""React webapp (/app/) parallel-route serving."""

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bridge.frontend_routes import register_webapp_routes


def _build_dist(root: Path) -> Path:
    dist = root / "webapp" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (dist / "login.html").write_text("<html>login</html>", encoding="utf-8")
    (dist / "assets" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
    return dist


class TestWebappRoutes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dist = _build_dist(Path(self._tmp.name))
        app = FastAPI()
        register_webapp_routes(app, webapp_dist=self.dist)
        self.client = TestClient(app)

    def tearDown(self):
        self._tmp.cleanup()

    def test_bare_app_redirects_to_slash(self):
        r = self.client.get("/app", follow_redirects=False)
        self.assertEqual(r.status_code, 307)
        self.assertEqual(r.headers["location"], "/app/")

    def test_index_and_login_served(self):
        self.assertIn("app", self.client.get("/app/").text)
        self.assertIn("login", self.client.get("/app/login.html").text)

    def test_asset_served_with_js_media_type(self):
        r = self.client.get("/app/assets/index-abc.js")
        self.assertEqual(r.status_code, 200)
        self.assertIn("javascript", r.headers["content-type"])

    def test_asset_traversal_rejected(self):
        secret = Path(self._tmp.name) / "secret.txt"
        secret.write_text("top", encoding="utf-8")
        r = self.client.get("/app/assets/..%2F..%2Fsecret.txt")
        self.assertNotEqual(r.status_code, 200)

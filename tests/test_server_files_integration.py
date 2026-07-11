"""Integration test hitting the real server.app file route.

Regression guard for the wrapper/caller signature mismatch: server.py's
verify_media_token wrapper must accept the (request, expected, query_token)
call that register_upload_routes makes, or GET /files/<name> raises TypeError
and every media read 500s. The unit test in test_upload_routes.py injects a
fake 3-arg verifier and therefore cannot catch a wrong real wrapper — this
test drives the actual application.
"""

import unittest

from fastapi.testclient import TestClient


class ServerFileRouteIntegrationTest(unittest.TestCase):
    def setUp(self):
        import server

        self.server = server
        self.client = TestClient(server.app)

    def test_serve_missing_file_is_404_not_500(self):
        headers = {"Authorization": "Bearer " + self.server.TOKEN}
        r = self.client.get("/files/does-not-exist.png", headers=headers)
        self.assertNotEqual(r.status_code, 500, r.text)
        self.assertEqual(r.status_code, 404)

    def test_serve_file_without_token_is_rejected_not_500(self):
        r = self.client.get("/files/does-not-exist.png")
        self.assertNotEqual(r.status_code, 500, r.text)
        self.assertIn(r.status_code, (401, 403))

    def test_media_url_query_token_is_rejected(self):
        # blocker #5: a token in the URL must not authenticate media.
        from fastapi.testclient import TestClient

        fresh = TestClient(self.server.app)
        r = fresh.get("/files/does-not-exist.png?token=" + self.server.TOKEN)
        self.assertEqual(r.status_code, 403, r.text)

    def test_login_sets_httponly_cookie_and_media_then_authenticates(self):
        from fastapi.testclient import TestClient

        client = TestClient(self.server.app)
        r = client.post("/login", json={"password": self.server.TOKEN})
        self.assertEqual(r.status_code, 200)
        set_cookie = r.headers.get("set-cookie", "")
        self.assertIn("token=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        # TestClient now carries the cookie; media auth passes (404 = missing file).
        r2 = client.get("/files/does-not-exist.png")
        self.assertEqual(r2.status_code, 404, r2.text)


if __name__ == "__main__":
    unittest.main()

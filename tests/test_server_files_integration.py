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


if __name__ == "__main__":
    unittest.main()

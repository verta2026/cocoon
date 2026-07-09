import io
import unittest
import urllib.error

from fastapi import HTTPException

from bridge.plugin_proxy import json_proxy_request, proxy_path


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class PluginProxyTest(unittest.TestCase):
    def test_proxy_path_uses_allowlisted_get_and_post_paths(self):
        self.assertEqual(
            proxy_path("/status", "GET", get_paths={"status": "/api/status"}, post_paths={}),
            "/api/status",
        )
        self.assertEqual(
            proxy_path("command", "POST", get_paths={}, post_paths={"command": "/api/command"}),
            "/api/command",
        )

    def test_proxy_path_can_use_dynamic_get_path(self):
        def dynamic(path):
            if path.startswith("items/"):
                return f"/api/{path}"
            return ""

        self.assertEqual(
            proxy_path("items/abc", "GET", get_paths={}, post_paths={}, dynamic_get_path=dynamic),
            "/api/items/abc",
        )

    def test_proxy_path_rejects_unexposed_paths(self):
        with self.assertRaises(HTTPException) as ctx:
            proxy_path("secret", "GET", get_paths={}, post_paths={}, service_name="Example")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("Example", ctx.exception.detail)

    def test_json_proxy_request_encodes_payload_and_decodes_json(self):
        seen = {}

        def opener(req, timeout):
            seen["url"] = req.full_url
            seen["method"] = req.get_method()
            seen["body"] = req.data
            seen["content_type"] = req.headers["Content-type"]
            seen["timeout"] = timeout
            return FakeResponse(b'{"ok": true}')

        result = json_proxy_request(
            "http://127.0.0.1:9000",
            "/api/command",
            method="POST",
            payload={"text": "hello"},
            timeout=3,
            opener=opener,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(seen["url"], "http://127.0.0.1:9000/api/command")
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["body"], b'{"text": "hello"}')
        self.assertEqual(seen["content_type"], "application/json; charset=utf-8")
        self.assertEqual(seen["timeout"], 3)

    def test_json_proxy_request_preserves_http_error_payload(self):
        def opener(req, timeout):
            raise urllib.error.HTTPError(
                req.full_url,
                409,
                "conflict",
                hdrs=None,
                fp=io.BytesIO(b'{"error": "busy"}'),
            )

        with self.assertRaises(HTTPException) as ctx:
            json_proxy_request("http://plugin", "/api/action", opener=opener)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, {"error": "busy"})

    def test_json_proxy_request_maps_unavailable_service(self):
        def opener(req, timeout):
            raise TimeoutError("slow")

        with self.assertRaises(HTTPException) as ctx:
            json_proxy_request("http://plugin", "/api/action", service_name="Example", opener=opener)

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("Example service unavailable", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()

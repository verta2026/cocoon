import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from bridge.look_routes import apply_look_update, load_look, register_look_routes


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


class FakeRequest:
    def __init__(self, body=None):
        self._body = body

    async def json(self):
        return self._body


def _run(coro):
    return asyncio.run(coro)


class LookHelpersTest(unittest.TestCase):
    def test_load_look_missing_file_and_bad_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "look.json"
            self.assertEqual(load_look(path), {})
            path.write_text('["not a dict"]', encoding="utf-8")
            self.assertEqual(load_look(path), {})
            path.write_text('{"bg": "/files/a.jpg", "bgDark": 5, "junk": "x", "userAvatar": ""}', encoding="utf-8")
            self.assertEqual(load_look(path), {"bg": "/files/a.jpg"})

    def test_apply_look_update_merges_and_clears(self):
        current = {"bg": "/files/a.jpg", "aiAvatar": "/files/ai.png"}
        updated = apply_look_update(current, {"bg": "/files/b.jpg", "aiAvatar": "", "junk": "x"})
        self.assertEqual(updated, {"bg": "/files/b.jpg"})
        # keys absent from the body stay untouched
        self.assertEqual(apply_look_update(current, {}), current)


class LookRoutesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.look_file = Path(self.tmp.name) / "chat_look.json"
        self.app = FakeApp()
        self.auth_calls = []

        def verify_token(request):
            self.auth_calls.append(request)

        register_look_routes(self.app, verify_token=verify_token, look_file=self.look_file)

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_and_post_roundtrip(self):
        get = self.app.routes[("GET", "/look")]
        post = self.app.routes[("POST", "/look")]

        self.assertEqual(_run(get(SimpleNamespace())), {"look": {}})

        result = _run(post(FakeRequest({"bg": "/files/w.jpg", "userAvatar": "/files/u.png"})))
        self.assertEqual(result["look"], {"bg": "/files/w.jpg", "userAvatar": "/files/u.png"})
        self.assertTrue(self.look_file.exists())

        # survives a "restart" — state comes from the file, not memory
        self.assertEqual(_run(get(SimpleNamespace()))["look"]["bg"], "/files/w.jpg")

        # empty value clears one key, leaves the rest
        result = _run(post(FakeRequest({"userAvatar": ""})))
        self.assertEqual(result["look"], {"bg": "/files/w.jpg"})
        self.assertEqual(len(self.auth_calls), 4)

    def test_post_tolerates_non_dict_body(self):
        result = _run(self.app.routes[("POST", "/look")](FakeRequest(["nope"])))
        self.assertEqual(result, {"ok": True, "look": {}})


if __name__ == "__main__":
    unittest.main()

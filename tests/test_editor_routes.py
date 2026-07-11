import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from bridge.editor_routes import register_editor_routes, resolve_editor_path


BLOCKED_PREFIXES = {".git", "node_modules", "private"}
BLOCKED_FILES = {"config.private.json", ".env"}


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
    """Carries a pre-parsed JSON body for the write route."""

    def __init__(self, body=None):
        self._body = body or {}

    async def json(self):
        return self._body


def _run(coro):
    return asyncio.run(coro)


def _payload(result):
    """Route handlers return either plain dicts or JSONResponse."""
    if isinstance(result, dict):
        return 200, result
    return result.status_code, json.loads(result.body)


class ResolveEditorPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "notes").mkdir()
        (self.root / "notes" / "a.md").write_text("hello", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _resolve(self, rel):
        return resolve_editor_path(
            self.root, rel, blocked_prefixes=BLOCKED_PREFIXES, blocked_files=BLOCKED_FILES
        )

    def test_plain_paths_resolve_inside_root(self):
        self.assertEqual(self._resolve("notes/a.md"), (self.root / "notes" / "a.md").resolve())
        self.assertEqual(self._resolve(""), self.root.resolve())

    def test_traversal_and_blocked_paths_rejected(self):
        self.assertIsNone(self._resolve("../outside"))
        self.assertIsNone(self._resolve("notes/../../outside"))
        self.assertIsNone(self._resolve(".git/config"))
        self.assertIsNone(self._resolve("private/key.pem"))
        self.assertIsNone(self._resolve("notes/config.private.json"))
        self.assertIsNone(self._resolve("notes/.env"))

    def test_symlink_escaping_root_rejected(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        secret = Path(outside.name) / "secret.txt"
        secret.write_text("top secret", encoding="utf-8")
        (self.root / "leak.txt").symlink_to(secret)
        self.assertIsNone(self._resolve("leak.txt"))

    def test_symlink_inside_root_allowed(self):
        (self.root / "alias.md").symlink_to(self.root / "notes" / "a.md")
        self.assertEqual(self._resolve("alias.md"), (self.root / "notes" / "a.md").resolve())


class EditorRoutesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "notes").mkdir()
        (self.root / "notes" / "a.md").write_text("hello", encoding="utf-8")
        (self.root / "readme.txt").write_text("root file", encoding="utf-8")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "config").write_text("nope", encoding="utf-8")
        (self.root / "config.private.json").write_text("{}", encoding="utf-8")
        (self.root / "binary.bin").write_bytes(b"\xff\xfe\x00\x01")

        self.app = FakeApp()
        self.auth_calls = []
        self.media_calls = []

        def verify_token(request):
            self.auth_calls.append(request)

        def verify_media_token(request, expected, token):
            self.media_calls.append((expected, token))

        register_editor_routes(
            self.app,
            verify_token=verify_token,
            verify_media_token=verify_media_token,
            bridge_token="tok",
            root=self.root,
            blocked_prefixes=BLOCKED_PREFIXES,
            blocked_files=BLOCKED_FILES,
            max_bytes=64,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_registers_all_routes(self):
        self.assertEqual(
            set(self.app.routes),
            {
                ("GET", "/editor/ls"),
                ("GET", "/editor/read"),
                ("POST", "/editor/write"),
                ("GET", "/editor/download"),
            },
        )

    def test_ls_lists_root_and_hides_blocked_and_dotfiles(self):
        status, data = _payload(_run(self.app.routes[("GET", "/editor/ls")](SimpleNamespace(), path="")))
        self.assertEqual(status, 200)
        names = [it["name"] for it in data["items"]]
        self.assertIn("notes", names)
        self.assertIn("readme.txt", names)
        self.assertNotIn(".git", names)
        self.assertNotIn("config.private.json", names)
        self.assertEqual(len(self.auth_calls), 1)

    def test_ls_blocked_and_missing_dirs(self):
        status, data = _payload(_run(self.app.routes[("GET", "/editor/ls")](SimpleNamespace(), path=".git")))
        self.assertEqual(status, 403)
        status, data = _payload(_run(self.app.routes[("GET", "/editor/ls")](SimpleNamespace(), path="nope")))
        self.assertEqual(status, 404)

    def test_read_roundtrip_and_errors(self):
        read = self.app.routes[("GET", "/editor/read")]
        status, data = _payload(_run(read(SimpleNamespace(), path="notes/a.md")))
        self.assertEqual(status, 200)
        self.assertEqual(data["content"], "hello")

        status, _ = _payload(_run(read(SimpleNamespace(), path="")))
        self.assertEqual(status, 403)
        status, _ = _payload(_run(read(SimpleNamespace(), path="../etc/passwd")))
        self.assertEqual(status, 403)
        status, _ = _payload(_run(read(SimpleNamespace(), path="notes/missing.md")))
        self.assertEqual(status, 404)
        status, data = _payload(_run(read(SimpleNamespace(), path="binary.bin")))
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "binary file")

    def test_read_respects_max_bytes(self):
        (self.root / "big.txt").write_text("x" * 100, encoding="utf-8")
        status, _ = _payload(_run(self.app.routes[("GET", "/editor/read")](SimpleNamespace(), path="big.txt")))
        self.assertEqual(status, 413)

    def test_write_updates_existing_file_only(self):
        write = self.app.routes[("POST", "/editor/write")]
        status, data = _payload(_run(write(FakeRequest({"path": "notes/a.md", "content": "updated"}))))
        self.assertEqual(status, 200)
        self.assertEqual((self.root / "notes" / "a.md").read_text(encoding="utf-8"), "updated")

        status, _ = _payload(_run(write(FakeRequest({"path": "notes/new.md", "content": "x"}))))
        self.assertEqual(status, 404)
        self.assertFalse((self.root / "notes" / "new.md").exists())

        status, _ = _payload(_run(write(FakeRequest({"path": "config.private.json", "content": "x"}))))
        self.assertEqual(status, 403)

        status, _ = _payload(_run(write(FakeRequest({"path": "notes/a.md"}))))
        self.assertEqual(status, 400)

        status, _ = _payload(_run(write(FakeRequest({"path": "notes/a.md", "content": "y" * 100}))))
        self.assertEqual(status, 413)

    def test_download_sets_headers_and_bom(self):
        dl = self.app.routes[("GET", "/editor/download")]
        result = _run(dl(SimpleNamespace(), path="notes/a.md", token="qtok"))
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.body.startswith(b"\xef\xbb\xbf"))
        self.assertIn("attachment", result.headers["content-disposition"])
        self.assertEqual(self.media_calls, [("tok", "qtok")])

        status, _ = _payload(_run(dl(SimpleNamespace(), path=".git/config", token=None)))
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()

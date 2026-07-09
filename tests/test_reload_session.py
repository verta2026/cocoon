import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

import server


class ReloadSessionRouteTest(unittest.IsolatedAsyncioTestCase):
    async def test_reload_session_requires_configured_command(self):
        originals = {
            "verify_token": server.verify_token,
            "tmux_exists": server.tmux_exists,
            "reload_command": server.RELOAD_COMMAND,
            "lock_dir": server.RELOAD_LOCK_DIR,
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                server.verify_token = lambda request: None
                server.tmux_exists = lambda: True
                server.RELOAD_COMMAND = ""
                server.RELOAD_LOCK_DIR = Path(tmp) / ".reload.lock"

                with self.assertRaises(HTTPException) as ctx:
                    await server.reload_session(object())

                self.assertEqual(ctx.exception.status_code, 501)
        finally:
            server.verify_token = originals["verify_token"]
            server.tmux_exists = originals["tmux_exists"]
            server.RELOAD_COMMAND = originals["reload_command"]
            server.RELOAD_LOCK_DIR = originals["lock_dir"]

    async def test_reload_session_sends_configured_command_under_lock(self):
        originals = {
            "verify_token": server.verify_token,
            "tmux_exists": server.tmux_exists,
            "reload_command": server.RELOAD_COMMAND,
            "lock_dir": server.RELOAD_LOCK_DIR,
            "tmux_clear_input": server.tmux_clear_input,
            "tmux_clear_scrollback": server.tmux_clear_scrollback,
            "tmux_send": server.tmux_send,
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                calls = []
                server.verify_token = lambda request: None
                server.tmux_exists = lambda: True
                server.RELOAD_COMMAND = "./reload.sh --mode forge"
                server.RELOAD_LOCK_DIR = Path(tmp) / ".reload.lock"
                server.tmux_clear_input = lambda: calls.append("clear-input")
                server.tmux_clear_scrollback = lambda: calls.append("clear-scrollback")
                server.tmux_send = lambda text: calls.append(("send", text))

                result = await server.reload_session(object())

                self.assertEqual(
                    result,
                    {"message": "Reload command sent", "command": "./reload.sh --mode forge"},
                )
                self.assertEqual(
                    calls,
                    [
                        "clear-input",
                        "clear-scrollback",
                        ("send", "./reload.sh --mode forge"),
                    ],
                )
                self.assertFalse(server.RELOAD_LOCK_DIR.exists())
        finally:
            server.verify_token = originals["verify_token"]
            server.tmux_exists = originals["tmux_exists"]
            server.RELOAD_COMMAND = originals["reload_command"]
            server.RELOAD_LOCK_DIR = originals["lock_dir"]
            server.tmux_clear_input = originals["tmux_clear_input"]
            server.tmux_clear_scrollback = originals["tmux_clear_scrollback"]
            server.tmux_send = originals["tmux_send"]

    async def test_reload_session_refuses_when_lock_exists(self):
        originals = {
            "verify_token": server.verify_token,
            "tmux_exists": server.tmux_exists,
            "reload_command": server.RELOAD_COMMAND,
            "lock_dir": server.RELOAD_LOCK_DIR,
            "stale_seconds": server.RELOAD_LOCK_STALE_SECONDS,
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                lock_dir = Path(tmp) / ".reload.lock"
                lock_dir.mkdir()
                server.verify_token = lambda request: None
                server.tmux_exists = lambda: True
                server.RELOAD_COMMAND = "./reload.sh"
                server.RELOAD_LOCK_DIR = lock_dir
                server.RELOAD_LOCK_STALE_SECONDS = 3600

                with self.assertRaises(HTTPException) as ctx:
                    await server.reload_session(object())

                self.assertEqual(ctx.exception.status_code, 409)
        finally:
            server.verify_token = originals["verify_token"]
            server.tmux_exists = originals["tmux_exists"]
            server.RELOAD_COMMAND = originals["reload_command"]
            server.RELOAD_LOCK_DIR = originals["lock_dir"]
            server.RELOAD_LOCK_STALE_SECONDS = originals["stale_seconds"]

    async def test_forge_reload_session_uses_reload_session_alias(self):
        original_reload_session = server.reload_session
        try:
            async def fake_reload_session(request):
                return {"ok": True}

            server.reload_session = fake_reload_session

            self.assertEqual(await server.forge_reload_session(object()), {"ok": True})
        finally:
            server.reload_session = original_reload_session


if __name__ == "__main__":
    unittest.main()

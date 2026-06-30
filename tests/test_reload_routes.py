import tempfile
import unittest
from pathlib import Path

import server


class ReloadRoutesTest(unittest.IsolatedAsyncioTestCase):
    async def test_reload_status_reports_non_secret_reload_state(self):
        originals = {
            "verify_token": server.verify_token,
            "pause_file": server.AUTO_RELOAD_PAUSE_FILE,
            "reload_command": server.RELOAD_COMMAND,
            "lock_dir": server.RELOAD_LOCK_DIR,
            "stale_seconds": server.RELOAD_LOCK_STALE_SECONDS,
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                pause_file = root / ".paused"
                lock_dir = root / ".reload.lock"
                pause_file.write_text("manual-pause\n", encoding="utf-8")
                lock_dir.mkdir()

                server.verify_token = lambda request: None
                server.AUTO_RELOAD_PAUSE_FILE = pause_file
                server.RELOAD_COMMAND = "./private/reload.sh --secret value"
                server.RELOAD_LOCK_DIR = lock_dir
                server.RELOAD_LOCK_STALE_SECONDS = 123

                result = await server.reload_status(object())

                self.assertEqual(
                    result,
                    {
                        "reload_configured": True,
                        "auto_reload_paused": True,
                        "reload_lock_exists": True,
                        "reload_lock_stale_seconds": 123,
                    },
                )
        finally:
            server.verify_token = originals["verify_token"]
            server.AUTO_RELOAD_PAUSE_FILE = originals["pause_file"]
            server.RELOAD_COMMAND = originals["reload_command"]
            server.RELOAD_LOCK_DIR = originals["lock_dir"]
            server.RELOAD_LOCK_STALE_SECONDS = originals["stale_seconds"]

    async def test_forge_auto_reload_routes_read_and_write_pause_state(self):
        originals = {
            "verify_token": server.verify_token,
            "pause_file": server.AUTO_RELOAD_PAUSE_FILE,
            "log_file": server.AUTO_RELOAD_LOG_FILE,
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                server.verify_token = lambda request: None
                server.AUTO_RELOAD_PAUSE_FILE = root / ".paused"
                server.AUTO_RELOAD_LOG_FILE = root / "reload.log"

                self.assertEqual(await server.get_forge_auto_reload(object()), {"paused": False})
                self.assertEqual(
                    await server.set_forge_auto_reload(server.AutoReloadRequest(paused=True), object()),
                    {"paused": True},
                )
                self.assertEqual(await server.get_forge_auto_reload(object()), {"paused": True})
                self.assertEqual(
                    await server.set_forge_auto_reload(server.AutoReloadRequest(paused=False), object()),
                    {"paused": False},
                )
        finally:
            server.verify_token = originals["verify_token"]
            server.AUTO_RELOAD_PAUSE_FILE = originals["pause_file"]
            server.AUTO_RELOAD_LOG_FILE = originals["log_file"]


if __name__ == "__main__":
    unittest.main()

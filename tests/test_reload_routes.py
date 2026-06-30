import tempfile
import unittest
from pathlib import Path

import server


class ReloadRoutesTest(unittest.IsolatedAsyncioTestCase):
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

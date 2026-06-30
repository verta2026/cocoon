import tempfile
import unittest
from pathlib import Path

from bridge.reload_control import auto_reload_status, log_auto_reload, set_auto_reload_paused


class ReloadControlTest(unittest.TestCase):
    def test_pause_state_can_be_enabled_and_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pause_file = root / "state" / ".paused"
            log_file = root / "state" / "reload.log"

            self.assertEqual(auto_reload_status(pause_file), {"paused": False})
            self.assertEqual(set_auto_reload_paused(pause_file, log_file, True), {"paused": True})
            self.assertTrue(pause_file.exists())

            self.assertEqual(set_auto_reload_paused(pause_file, log_file, False), {"paused": False})
            self.assertFalse(pause_file.exists())
            self.assertIn("manual pause enabled", log_file.read_text(encoding="utf-8"))
            self.assertIn("manual pause disabled", log_file.read_text(encoding="utf-8"))

    def test_log_auto_reload_throttle_skips_recent_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "reload.log"

            log_auto_reload(log_file, "first")
            log_auto_reload(log_file, "second", throttle=3600)

            text = log_file.read_text(encoding="utf-8")
            self.assertIn("first", text)
            self.assertNotIn("second", text)


if __name__ == "__main__":
    unittest.main()

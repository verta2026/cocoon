import tempfile
import unittest
import os
import time
from pathlib import Path

from bridge.reload_control import (
    auto_reload_status,
    log_auto_reload,
    normalized_reload_command,
    reload_lock,
    send_reload_command,
    set_auto_reload_paused,
)


class ReloadControlTest(unittest.TestCase):
    def test_normalized_reload_command_strips_empty_values(self):
        self.assertEqual(normalized_reload_command(None), "")
        self.assertEqual(normalized_reload_command("  "), "")
        self.assertEqual(normalized_reload_command("  ./reload.sh  "), "./reload.sh")

    def test_send_reload_command_clears_then_sends_command(self):
        calls = []

        sent = send_reload_command(
            " ./reload.sh --mode compact ",
            lambda: calls.append("clear-input"),
            lambda: calls.append("clear-scrollback"),
            lambda text: calls.append(("send", text)),
        )

        self.assertEqual(sent, "./reload.sh --mode compact")
        self.assertEqual(
            calls,
            [
                "clear-input",
                "clear-scrollback",
                ("send", "./reload.sh --mode compact"),
            ],
        )

    def test_send_reload_command_does_nothing_without_command(self):
        calls = []

        sent = send_reload_command(
            "",
            lambda: calls.append("clear-input"),
            lambda: calls.append("clear-scrollback"),
            lambda text: calls.append(("send", text)),
        )

        self.assertEqual(sent, "")
        self.assertEqual(calls, [])

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

    def test_reload_lock_blocks_concurrent_acquire(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / ".reload.lock"

            with reload_lock(lock_dir, stale_seconds=60) as first:
                self.assertTrue(first)
                with reload_lock(lock_dir, stale_seconds=60) as second:
                    self.assertFalse(second)

            self.assertFalse(lock_dir.exists())

    def test_reload_lock_reclaims_stale_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / ".reload.lock"
            lock_dir.mkdir()
            old = time.time() - 120
            os.utime(lock_dir, (old, old))

            with reload_lock(lock_dir, stale_seconds=60) as acquired:
                self.assertTrue(acquired)
                owner = (lock_dir / "owner.json").read_text(encoding="utf-8")
                self.assertIn("stale_reclaimed", owner)

            self.assertFalse(lock_dir.exists())


if __name__ == "__main__":
    unittest.main()

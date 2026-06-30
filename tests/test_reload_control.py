import tempfile
import unittest
import os
import time
from pathlib import Path

from bridge.reload_control import (
    active_context_threshold,
    actual_model_from_session,
    auto_reload_status,
    context_window_is_1m,
    log_auto_reload,
    mark_auto_reload,
    normalized_reload_command,
    recent_auto_reload,
    reload_lock,
    send_reload_command,
    set_auto_reload_paused,
    session_idle_seconds,
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

    def test_mark_and_recent_auto_reload_track_cooldown(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "reload.json"

            data = mark_auto_reload(state_file, "manual-force", context_tokens=123)

            self.assertEqual(data["reason"], "manual-force")
            self.assertEqual(data["tokens"], 123)
            self.assertTrue(recent_auto_reload(state_file, cooldown_seconds=3600))
            self.assertFalse(recent_auto_reload(state_file, cooldown_seconds=0))

    def test_recent_auto_reload_ignores_missing_or_invalid_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "reload.json"

            self.assertFalse(recent_auto_reload(state_file, cooldown_seconds=3600))
            state_file.write_text("{bad", encoding="utf-8")
            self.assertFalse(recent_auto_reload(state_file, cooldown_seconds=3600))

    def test_session_idle_seconds_returns_age_for_existing_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text("{}", encoding="utf-8")
            old = time.time() - 90
            os.utime(path, (old, old))

            idle = session_idle_seconds(lambda: path)

            self.assertGreaterEqual(idle, 80)
            self.assertLess(idle, 120)
            self.assertEqual(session_idle_seconds(lambda: None), 0)

    def test_actual_model_from_session_uses_latest_assistant_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            rows = [
                {"type": "assistant", "message": {"model": "claude-sonnet"}},
                {"type": "assistant", "isSidechain": True, "message": {"model": "ignored[1m]"}},
                {"type": "user", "message": {"model": "ignored-user"}},
                {"type": "assistant", "message": {"model": "claude-opus[1m]"}},
            ]
            path.write_text("\n".join(json_dumps(row) for row in rows), encoding="utf-8")

            self.assertEqual(actual_model_from_session(lambda: path), "claude-opus[1m]")

    def test_context_window_uses_session_model_then_settings_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_path = root / "session.jsonl"
            settings_file = root / "settings.json"

            session_path.write_text(
                json_dumps({"type": "assistant", "message": {"model": "claude-sonnet"}}),
                encoding="utf-8",
            )
            settings_file.write_text('{"model": "claude-opus[1m]"}', encoding="utf-8")

            self.assertFalse(context_window_is_1m(lambda: session_path, settings_file))
            self.assertEqual(active_context_threshold(lambda: session_path, settings_file, 100, 500), 100)

            self.assertTrue(context_window_is_1m(lambda: None, settings_file))
            self.assertEqual(active_context_threshold(lambda: None, settings_file, 100, 500), 500)

    def test_context_window_helpers_tolerate_missing_or_invalid_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_session = Path(tmp) / "missing.jsonl"
            settings_file = Path(tmp) / "settings.json"
            settings_file.write_text("{bad", encoding="utf-8")

            self.assertEqual(actual_model_from_session(lambda: missing_session), "")
            self.assertFalse(context_window_is_1m(lambda: missing_session, settings_file))

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


def json_dumps(data):
    import json

    return json.dumps(data, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()

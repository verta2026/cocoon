import tempfile
import unittest
import os
import time
from pathlib import Path

from bridge.reload_control import (
    active_context_threshold,
    actual_model_from_session,
    auto_reload_status,
    build_reload_decision,
    choose_reload_action,
    choose_reload_reason,
    consume_reload_marker,
    context_window_is_1m,
    log_auto_reload,
    mark_auto_reload,
    normalized_reload_command,
    recent_auto_reload,
    reload_lock,
    reload_monitor_interval,
    reload_marker_pending,
    send_reload_command,
    set_auto_reload_paused,
    set_reload_marker,
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

    def test_reload_monitor_interval_speeds_up_near_threshold(self):
        self.assertEqual(reload_monitor_interval(79, 100, 30), 30)
        self.assertEqual(reload_monitor_interval(80, 100, 30), 10)
        self.assertEqual(reload_monitor_interval(500, 0, 30), 30)
        self.assertEqual(reload_monitor_interval(1, 100, 1), 5)

    def test_choose_reload_reason_prioritizes_manual_force(self):
        reason = choose_reload_reason(
            force=True,
            tail_text="API Error:",
            context_tokens=999,
            active_threshold=100,
            idle_seconds=9999,
            idle_min_context=10,
            idle_threshold_seconds=60,
        )

        self.assertEqual(reason, "manual-force")

    def test_choose_reload_reason_detects_api_error(self):
        reason = choose_reload_reason(
            force=False,
            tail_text="tail\nAPI Error: overloaded",
            context_tokens=10,
            active_threshold=100,
            idle_seconds=0,
            idle_min_context=50,
            idle_threshold_seconds=60,
        )

        self.assertEqual(reason, "api-error")

    def test_choose_reload_reason_detects_context_threshold(self):
        reason = choose_reload_reason(
            force=False,
            tail_text="ok",
            context_tokens=125,
            active_threshold=100,
            idle_seconds=0,
            idle_min_context=50,
            idle_threshold_seconds=60,
        )

        self.assertEqual(reason, "context-tokens:125/100")

    def test_choose_reload_reason_detects_idle_cache_expiry(self):
        reason = choose_reload_reason(
            force=False,
            tail_text="ok",
            context_tokens=80,
            active_threshold=100,
            idle_seconds=3600,
            idle_min_context=50,
            idle_threshold_seconds=1800,
        )

        self.assertEqual(reason, "idle-cache-expired:80@60min")

    def test_choose_reload_reason_returns_empty_when_no_trigger_matches(self):
        reason = choose_reload_reason(
            force=False,
            tail_text="ok",
            context_tokens=49,
            active_threshold=100,
            idle_seconds=3600,
            idle_min_context=50,
            idle_threshold_seconds=1800,
        )

        self.assertEqual(reason, "")

    def test_choose_reload_action_skips_without_reason(self):
        self.assertEqual(choose_reload_action("", recent=False, force=False, dryrun=False), "skip")

    def test_choose_reload_action_skips_recent_non_force_reload(self):
        self.assertEqual(choose_reload_action("api-error", recent=True, force=False, dryrun=False), "skip")

    def test_choose_reload_action_dryruns_non_force_reload(self):
        self.assertEqual(choose_reload_action("api-error", recent=False, force=False, dryrun=True), "dry-run")

    def test_choose_reload_action_force_bypasses_recent_and_dryrun(self):
        self.assertEqual(choose_reload_action("manual-force", recent=True, force=True, dryrun=True), "fire")

    def test_choose_reload_action_fires_regular_reload(self):
        self.assertEqual(choose_reload_action("api-error", recent=False, force=False, dryrun=False), "fire")

    def test_build_reload_decision_combines_reason_and_action(self):
        decision = build_reload_decision(
            force=False,
            tail_text="API Error: overloaded",
            context_tokens=25,
            active_threshold=100,
            idle_seconds=0,
            idle_min_context=50,
            idle_threshold_seconds=60,
            recent=False,
            dryrun=True,
        )

        self.assertEqual(
            decision,
            {
                "action": "dry-run",
                "reason": "api-error",
                "force": False,
                "recent": False,
                "dryrun": True,
                "context_tokens": 25,
                "active_threshold": 100,
            },
        )

    def test_build_reload_decision_reports_skip_when_no_trigger_matches(self):
        decision = build_reload_decision(
            force=False,
            tail_text="ok",
            context_tokens=25,
            active_threshold=100,
            idle_seconds=0,
            idle_min_context=50,
            idle_threshold_seconds=60,
            recent=False,
            dryrun=False,
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "")

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

    def test_set_reload_marker_creates_and_clears_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / ".force"

            self.assertEqual(set_reload_marker(marker, True, "manual-force"), {"pending": True})
            self.assertIn("manual-force", marker.read_text(encoding="utf-8"))

            self.assertEqual(set_reload_marker(marker, False, "manual-force"), {"pending": False})
            self.assertFalse(marker.exists())

    def test_reload_marker_pending_and_consume_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / ".force"

            self.assertFalse(reload_marker_pending(marker))
            self.assertFalse(consume_reload_marker(marker))

            marker.write_text("manual-force\n", encoding="utf-8")

            self.assertTrue(reload_marker_pending(marker))
            self.assertTrue(consume_reload_marker(marker))
            self.assertFalse(reload_marker_pending(marker))

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

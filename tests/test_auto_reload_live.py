import asyncio
import json
import tempfile
import unittest
from pathlib import Path

import server
from bridge.reload_control import (
    auto_reload_monitor_loop,
    current_context_tokens,
    run_live_auto_reload_tick,
)


def _jsonl(events):
    return "\n".join(json.dumps(e) for e in events) + "\n"


class CurrentContextTokensTest(unittest.TestCase):
    def test_reads_last_mainchain_assistant_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            path.write_text(
                _jsonl(
                    [
                        {
                            "type": "assistant",
                            "message": {"usage": {"input_tokens": 10, "cache_read_input_tokens": 90}},
                        },
                        {"type": "user", "message": {}},
                        {
                            "type": "assistant",
                            "isSidechain": True,
                            "message": {"usage": {"input_tokens": 999999}},
                        },
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual(current_context_tokens(lambda: path), 100)

    def test_returns_zero_without_session_file(self):
        self.assertEqual(current_context_tokens(lambda: None), 0)

    def test_returns_zero_on_unparseable_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            path.write_text("not json\n", encoding="utf-8")
            self.assertEqual(current_context_tokens(lambda: path), 0)


class LiveTickTest(unittest.TestCase):
    def _deps(self, tmp, **overrides):
        sent = []
        deps = {
            "pause_file": Path(tmp) / "pause",
            "force_file": Path(tmp) / "force",
            "dryrun_file": Path(tmp) / "dryrun",
            "state_file": Path(tmp) / "state.json",
            "log_file": Path(tmp) / "log",
            "cooldown_seconds": 600,
            "idle_min_context": 200000,
            "idle_threshold_seconds": 3600,
            "lock_dir": Path(tmp) / "lock",
            "lock_stale_seconds": 300,
            "tmux_exists_func": lambda: True,
            "pane_command_func": lambda: "claude",
            "dismiss_resume_summary_prompt_func": lambda: False,
            "dismiss_rating_prompt_func": lambda: False,
            "claude_busy_func": lambda: False,
            "tmux_capture_func": lambda lines: "idle screen",
            "context_tokens_func": lambda: 130000,
            "active_threshold_func": lambda: 125000,
            "idle_seconds_func": lambda: 60.0,
            "send_reload_command_func": lambda: sent.append("cmd") or "cmd",
        }
        deps.update(overrides)
        return deps, sent

    def test_fires_over_threshold_and_marks_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            deps, sent = self._deps(tmp)
            decision = run_live_auto_reload_tick(**deps)
            self.assertEqual(decision["action"], "fire")
            self.assertIn("context-tokens", decision["reason"])
            self.assertEqual(sent, ["cmd"])
            state = json.loads(deps["state_file"].read_text(encoding="utf-8"))
            self.assertEqual(state["tokens"], 130000)

    def test_cooldown_blocks_second_fire(self):
        with tempfile.TemporaryDirectory() as tmp:
            deps, sent = self._deps(tmp)
            run_live_auto_reload_tick(**deps)
            decision = run_live_auto_reload_tick(**deps)
            self.assertEqual(decision["action"], "skip")
            self.assertEqual(sent, ["cmd"])

    def test_guards_stop_before_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            for overrides, guard in [
                ({"tmux_exists_func": lambda: False}, "no-claude"),
                ({"pane_command_func": lambda: "bash"}, "no-claude"),
                ({"dismiss_resume_summary_prompt_func": lambda: True}, "resume-summary-prompt"),
                ({"claude_busy_func": lambda: True}, "busy"),
                ({"idle_seconds_func": lambda: 1.0}, "not-quiet"),
            ]:
                deps, sent = self._deps(tmp, **overrides)
                decision = run_live_auto_reload_tick(**deps)
                self.assertEqual(decision["action"], "skip")
                self.assertEqual(decision["guard"], guard)
                self.assertEqual(sent, [])

    def test_pause_file_blocks_fire(self):
        with tempfile.TemporaryDirectory() as tmp:
            deps, sent = self._deps(tmp)
            deps["pause_file"].touch()
            decision = run_live_auto_reload_tick(**deps)
            self.assertEqual(decision["guard"], "paused")
            self.assertEqual(sent, [])

    def test_dry_run_logs_without_firing(self):
        with tempfile.TemporaryDirectory() as tmp:
            deps, sent = self._deps(tmp)
            deps["dryrun_file"].touch()
            decision = run_live_auto_reload_tick(**deps)
            self.assertEqual(decision["action"], "dry-run")
            self.assertEqual(sent, [])
            self.assertIn("DRY-RUN", deps["log_file"].read_text(encoding="utf-8"))

    def test_unconfigured_command_is_loud_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            deps, _ = self._deps(tmp, send_reload_command_func=lambda: "")
            decision = run_live_auto_reload_tick(**deps)
            self.assertEqual(decision["action"], "skip")
            self.assertEqual(decision["guard"], "no-command")
            self.assertIn("not configured", deps["log_file"].read_text(encoding="utf-8"))

    def test_below_threshold_skips_quietly(self):
        with tempfile.TemporaryDirectory() as tmp:
            deps, sent = self._deps(tmp, context_tokens_func=lambda: 1000)
            decision = run_live_auto_reload_tick(**deps)
            self.assertEqual(decision["action"], "skip")
            self.assertEqual(sent, [])


class MonitorLoopTest(unittest.IsolatedAsyncioTestCase):
    async def test_decision_history_is_bounded(self):
        ticks = {"n": 0}

        def tick():
            ticks["n"] += 1
            return {"action": "skip", "reason": ""}

        async def no_sleep(_seconds):
            return None

        decisions = await auto_reload_monitor_loop(
            tick_func=tick,
            context_tokens_func=lambda: 0,
            active_threshold_func=lambda: 125000,
            default_interval_seconds=30,
            sleep_func=no_sleep,
            print_func=lambda *a, **k: None,
            stop_func=lambda: ticks["n"] >= 200,
        )
        self.assertLessEqual(len(decisions), 50)
        self.assertEqual(ticks["n"], 200)


class StartupWiringTest(unittest.IsolatedAsyncioTestCase):
    async def _run_startup(self, *, enabled, command):
        originals = {
            "enabled": server.AUTO_RELOAD_ENABLED,
            "command": server.RELOAD_COMMAND,
            "task": server.AUTO_RELOAD_TASK,
        }
        try:
            server.AUTO_RELOAD_ENABLED = enabled
            server.RELOAD_COMMAND = command
            server.AUTO_RELOAD_TASK = None
            task = await server.startup_auto_reload_monitor()
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            return task
        finally:
            server.AUTO_RELOAD_ENABLED = originals["enabled"]
            server.RELOAD_COMMAND = originals["command"]
            server.AUTO_RELOAD_TASK = originals["task"]

    async def test_disabled_does_not_start(self):
        self.assertIsNone(await self._run_startup(enabled=False, command="reload"))

    async def test_enabled_without_command_does_not_start(self):
        self.assertIsNone(await self._run_startup(enabled=True, command=""))

    async def test_enabled_with_command_starts_monitor_task(self):
        task = await self._run_startup(enabled=True, command="bash reload.sh")
        self.assertIsNotNone(task)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

import server


class ReloadRoutesTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_auto_reload_monitor_is_disabled_by_default(self):
        originals = {
            "enabled": server.AUTO_RELOAD_ENABLED,
            "task": server.AUTO_RELOAD_TASK,
        }
        try:
            server.AUTO_RELOAD_ENABLED = False
            server.AUTO_RELOAD_TASK = None

            self.assertIsNone(server.start_auto_reload_monitor(create_task=lambda coro: "task", monitor_coro=object()))
        finally:
            server.AUTO_RELOAD_ENABLED = originals["enabled"]
            server.AUTO_RELOAD_TASK = originals["task"]

    async def test_start_auto_reload_monitor_requires_injected_coroutine_when_enabled(self):
        originals = {
            "enabled": server.AUTO_RELOAD_ENABLED,
            "task": server.AUTO_RELOAD_TASK,
        }
        try:
            server.AUTO_RELOAD_ENABLED = True
            server.AUTO_RELOAD_TASK = None

            with self.assertRaisesRegex(RuntimeError, "not configured"):
                server.start_auto_reload_monitor(create_task=lambda coro: "task")
        finally:
            server.AUTO_RELOAD_ENABLED = originals["enabled"]
            server.AUTO_RELOAD_TASK = originals["task"]

    async def test_start_auto_reload_monitor_creates_and_reuses_task(self):
        originals = {
            "enabled": server.AUTO_RELOAD_ENABLED,
            "task": server.AUTO_RELOAD_TASK,
        }

        class FakeTask:
            def __init__(self):
                self.done_calls = 0

            def done(self):
                self.done_calls += 1
                return False

        try:
            task = FakeTask()
            calls = []
            server.AUTO_RELOAD_ENABLED = True
            server.AUTO_RELOAD_TASK = None

            created = server.start_auto_reload_monitor(
                create_task=lambda coro: calls.append(coro) or task,
                monitor_coro=object(),
            )
            reused = server.start_auto_reload_monitor(create_task=lambda coro: "new", monitor_coro=object())

            self.assertIs(created, task)
            self.assertIs(reused, task)
            self.assertEqual(len(calls), 1)
        finally:
            server.AUTO_RELOAD_ENABLED = originals["enabled"]
            server.AUTO_RELOAD_TASK = originals["task"]

    async def test_reload_status_reports_non_secret_reload_state(self):
        originals = {
            "verify_token": server.verify_token,
            "pause_file": server.AUTO_RELOAD_PAUSE_FILE,
            "dryrun_file": server.AUTO_RELOAD_DRYRUN_FILE,
            "force_file": server.AUTO_RELOAD_FORCE_FILE,
            "reload_command": server.RELOAD_COMMAND,
            "lock_dir": server.RELOAD_LOCK_DIR,
            "stale_seconds": server.RELOAD_LOCK_STALE_SECONDS,
            "enabled": server.AUTO_RELOAD_ENABLED,
            "state_file": server.AUTO_RELOAD_STATE_FILE,
            "threshold": server.AUTO_RELOAD_CONTEXT_THRESHOLD,
            "threshold_1m": server.AUTO_RELOAD_CONTEXT_THRESHOLD_1M,
            "idle_min_context": server.AUTO_RELOAD_IDLE_MIN_CONTEXT,
            "idle_seconds": server.AUTO_RELOAD_IDLE_SECONDS,
            "cooldown": server.AUTO_RELOAD_COOLDOWN_SECONDS,
            "check_interval": server.AUTO_RELOAD_CHECK_INTERVAL_SECONDS,
            "task": server.AUTO_RELOAD_TASK,
            "context_tokens_func": server.current_context_tokens,
            "active_threshold_func": server.auto_reload_active_threshold,
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                pause_file = root / ".paused"
                dryrun_file = root / ".dryrun"
                force_file = root / ".force"
                lock_dir = root / ".reload.lock"
                state_file = root / "state.json"
                pause_file.write_text("manual-pause\n", encoding="utf-8")
                dryrun_file.write_text("dry-run\n", encoding="utf-8")
                force_file.write_text("manual-force\n", encoding="utf-8")
                lock_dir.mkdir()

                server.verify_token = lambda request: None
                server.AUTO_RELOAD_PAUSE_FILE = pause_file
                server.AUTO_RELOAD_DRYRUN_FILE = dryrun_file
                server.AUTO_RELOAD_FORCE_FILE = force_file
                server.RELOAD_COMMAND = "./private/reload.sh --secret value"
                server.RELOAD_LOCK_DIR = lock_dir
                server.RELOAD_LOCK_STALE_SECONDS = 123
                server.AUTO_RELOAD_ENABLED = True
                server.AUTO_RELOAD_STATE_FILE = state_file
                server.AUTO_RELOAD_CONTEXT_THRESHOLD = 100
                server.AUTO_RELOAD_CONTEXT_THRESHOLD_1M = 500
                server.AUTO_RELOAD_IDLE_MIN_CONTEXT = 50
                server.AUTO_RELOAD_IDLE_SECONDS = 60
                server.AUTO_RELOAD_COOLDOWN_SECONDS = 30
                server.AUTO_RELOAD_CHECK_INTERVAL_SECONDS = 5
                server.AUTO_RELOAD_TASK = None
                server.current_context_tokens = lambda: 42
                server.auto_reload_active_threshold = lambda: 100

                result = await server.reload_status(object())

                self.assertEqual(
                    result,
                    {
                        "reload_configured": True,
                        "auto_reload_enabled": True,
                        "auto_reload_monitor_running": False,
                        "context_tokens": 42,
                        "active_context_threshold": 100,
                        "auto_reload_paused": True,
                        "auto_reload_dryrun": True,
                        "auto_reload_force_pending": True,
                        "reload_lock_exists": True,
                        "reload_lock_stale_seconds": 123,
                        "auto_reload_state_file": str(state_file),
                        "auto_reload_thresholds": {
                            "context_tokens": 100,
                            "context_tokens_1m": 500,
                            "idle_min_context": 50,
                            "idle_seconds": 60,
                            "cooldown": 30,
                            "check_interval": 5,
                        },
                    },
                )
        finally:
            server.verify_token = originals["verify_token"]
            server.AUTO_RELOAD_PAUSE_FILE = originals["pause_file"]
            server.AUTO_RELOAD_DRYRUN_FILE = originals["dryrun_file"]
            server.AUTO_RELOAD_FORCE_FILE = originals["force_file"]
            server.RELOAD_COMMAND = originals["reload_command"]
            server.RELOAD_LOCK_DIR = originals["lock_dir"]
            server.RELOAD_LOCK_STALE_SECONDS = originals["stale_seconds"]
            server.AUTO_RELOAD_ENABLED = originals["enabled"]
            server.AUTO_RELOAD_STATE_FILE = originals["state_file"]
            server.AUTO_RELOAD_CONTEXT_THRESHOLD = originals["threshold"]
            server.AUTO_RELOAD_CONTEXT_THRESHOLD_1M = originals["threshold_1m"]
            server.AUTO_RELOAD_IDLE_MIN_CONTEXT = originals["idle_min_context"]
            server.AUTO_RELOAD_IDLE_SECONDS = originals["idle_seconds"]
            server.AUTO_RELOAD_COOLDOWN_SECONDS = originals["cooldown"]
            server.AUTO_RELOAD_CHECK_INTERVAL_SECONDS = originals["check_interval"]
            server.AUTO_RELOAD_TASK = originals["task"]
            server.current_context_tokens = originals["context_tokens_func"]
            server.auto_reload_active_threshold = originals["active_threshold_func"]

    async def test_reload_force_routes_set_and_clear_marker(self):
        originals = {
            "verify_token": server.verify_token,
            "force_file": server.AUTO_RELOAD_FORCE_FILE,
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                force_file = Path(tmp) / ".force"
                server.verify_token = lambda request: None
                server.AUTO_RELOAD_FORCE_FILE = force_file

                self.assertEqual(await server.set_reload_force(object()), {"pending": True})
                self.assertTrue(force_file.exists())

                self.assertEqual(await server.clear_reload_force(object()), {"pending": False})
                self.assertFalse(force_file.exists())
        finally:
            server.verify_token = originals["verify_token"]
            server.AUTO_RELOAD_FORCE_FILE = originals["force_file"]

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
                    await server.set_forge_auto_reload(server.AutoReloadRequest(paused=False, force=True), object()),
                    {"paused": False},
                )
        finally:
            server.verify_token = originals["verify_token"]
            server.AUTO_RELOAD_PAUSE_FILE = originals["pause_file"]
            server.AUTO_RELOAD_LOG_FILE = originals["log_file"]


if __name__ == "__main__":
    unittest.main()

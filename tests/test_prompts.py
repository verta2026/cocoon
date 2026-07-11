import unittest

import bridge.prompts as prompts


class PromptHelpersTest(unittest.TestCase):
    def test_wait_for_ready_can_skip_auto_dismiss(self):
        calls = []
        originals = {
            "claude_running": prompts.claude_running,
            "tmux_capture": prompts.tmux_capture,
            "dismiss_resume_summary_prompt": prompts.dismiss_resume_summary_prompt,
            "dismiss_rating_prompt": prompts.dismiss_rating_prompt,
            "dismiss_settings_warning_prompt": prompts.dismiss_settings_warning_prompt,
            "dismiss_trust_prompt": prompts.dismiss_trust_prompt,
            "time": prompts.time.time,
            "sleep": prompts.time.sleep,
        }
        times = iter([0, 0])
        try:
            prompts.claude_running = lambda session_name: True
            prompts.tmux_capture = lambda session_name, lines=80: "? for shortcuts"
            prompts.dismiss_resume_summary_prompt = lambda session_name: calls.append("resume") or False
            prompts.dismiss_rating_prompt = lambda session_name: calls.append("rating") or False
            prompts.dismiss_settings_warning_prompt = lambda session_name: calls.append("settings") or False
            prompts.dismiss_trust_prompt = lambda session_name: calls.append("trust") or False
            prompts.time.time = lambda: next(times)
            prompts.time.sleep = lambda seconds: None

            self.assertTrue(prompts.wait_for_claude_ready("test", timeout=1, auto_dismiss=False))
            self.assertEqual(calls, [])

            # default: routine prompts handled, settings warning left alone
            times = iter([0, 0])
            prompts.time.time = lambda: next(times)
            self.assertTrue(prompts.wait_for_claude_ready("test", timeout=1, auto_dismiss=True))
            self.assertEqual(calls, ["resume", "rating", "trust"])

            calls.clear()
            times = iter([0, 0])
            prompts.time.time = lambda: next(times)
            self.assertTrue(prompts.wait_for_claude_ready(
                "test", timeout=1, auto_dismiss=True, auto_accept_settings_warning=True))
            self.assertEqual(calls, ["resume", "rating", "settings", "trust"])
        finally:
            prompts.claude_running = originals["claude_running"]
            prompts.tmux_capture = originals["tmux_capture"]
            prompts.dismiss_resume_summary_prompt = originals["dismiss_resume_summary_prompt"]
            prompts.dismiss_rating_prompt = originals["dismiss_rating_prompt"]
            prompts.dismiss_settings_warning_prompt = originals["dismiss_settings_warning_prompt"]
            prompts.dismiss_trust_prompt = originals["dismiss_trust_prompt"]
            prompts.time.time = originals["time"]
            prompts.time.sleep = originals["sleep"]


class WaitForClaudeTuiTest(unittest.TestCase):
    """TUI-drawn gate: boot window blocks, idle prompt and generation pass."""

    def _run(self, screens, timeout=5):
        originals = (prompts.tmux_capture, prompts.time.time, prompts.time.sleep)
        seq = iter(screens)
        last = screens[-1]
        clock = {"t": 0}

        def fake_time():
            return clock["t"]

        def fake_sleep(seconds):
            clock["t"] += seconds

        try:
            prompts.tmux_capture = lambda session_name, lines=80: next(seq, last)
            prompts.time.time = fake_time
            prompts.time.sleep = fake_sleep
            return prompts.wait_for_claude_tui("test", timeout=timeout)
        finally:
            prompts.tmux_capture, prompts.time.time, prompts.time.sleep = originals

    def test_idle_prompt_passes_immediately(self):
        self.assertTrue(self._run(["❯ Try \"how does x work?\""]))

    def test_generation_counts_as_drawn(self):
        self.assertTrue(self._run(["✻ Crunching… (esc to interrupt)"]))

    def test_boot_window_blocks_then_passes(self):
        self.assertTrue(self._run(["", "", "? for shortcuts"]))

    def test_never_drawn_times_out(self):
        self.assertFalse(self._run([""], timeout=3))


if __name__ == "__main__":
    unittest.main()

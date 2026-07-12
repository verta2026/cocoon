import json
import os
import tempfile
import unittest
from pathlib import Path

from bridge.channel_preflight import (
    clean_stale_channel_state,
    sidecar_trim_cutoff,
    trim_sidecar_rows,
)
from bridge.session import compose_start_command


DEAD_PID = "999999999"  # pid_max on Linux caps well below this


class ComposeStartCommandTest(unittest.TestCase):
    def test_appends_channel_args(self):
        self.assertEqual(
            compose_start_command("claude", "--channels plugin:telegram@claude-plugins-official"),
            "claude --channels plugin:telegram@claude-plugins-official",
        )

    def test_no_channel_args_leaves_command_alone(self):
        self.assertEqual(compose_start_command("claude", ""), "claude")
        self.assertEqual(compose_start_command("claude", None), "claude")

    def test_does_not_duplicate_channels_flag(self):
        command = "claude --channels plugin:telegram@claude-plugins-official"
        self.assertEqual(compose_start_command(command, "--channels plugin:x@y"), command)

    def test_default_command_still_normalized(self):
        self.assertEqual(compose_start_command("", "--channels plugin:x@y"), "claude --channels plugin:x@y")


class ChannelPreflightTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.channels = self.home / "channels" / "telegram"
        self.plugin = self.home / "plugins" / "cache" / "claude-plugins-official" / "telegram" / "0.0.6"
        self.in_use = self.plugin / ".in_use"
        self.channels.mkdir(parents=True)
        self.in_use.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_dead_pid_file_is_removed(self):
        pid_file = self.channels / "bot.pid"
        pid_file.write_text(DEAD_PID, encoding="utf-8")
        actions = clean_stale_channel_state(self.home)
        self.assertFalse(pid_file.exists())
        self.assertTrue(any("bot.pid" in a for a in actions))

    def test_live_pid_file_is_kept(self):
        pid_file = self.channels / "bot.pid"
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
        clean_stale_channel_state(self.home)
        self.assertTrue(pid_file.exists())

    def test_garbage_pid_file_is_removed(self):
        pid_file = self.channels / "bot.pid"
        pid_file.write_text("not-a-pid", encoding="utf-8")
        clean_stale_channel_state(self.home)
        self.assertFalse(pid_file.exists())

    def test_dead_marker_removed_live_marker_kept(self):
        dead = self.in_use / DEAD_PID
        live = self.in_use / str(os.getpid())
        dead.touch()
        live.touch()
        clean_stale_channel_state(self.home)
        self.assertFalse(dead.exists())
        self.assertTrue(live.exists())

    def test_orphan_flag_cleared_when_no_live_markers_remain(self):
        (self.in_use / DEAD_PID).touch()
        orphan = self.plugin / ".orphaned_at"
        orphan.touch()
        clean_stale_channel_state(self.home)
        self.assertFalse(orphan.exists())

    def test_orphan_flag_kept_while_a_live_marker_exists(self):
        (self.in_use / str(os.getpid())).touch()
        orphan = self.plugin / ".orphaned_at"
        orphan.touch()
        clean_stale_channel_state(self.home)
        self.assertTrue(orphan.exists())

    def test_missing_dirs_are_fine(self):
        empty_home = self.home / "nothing-here"
        self.assertEqual(clean_stale_channel_state(empty_home), [])


if __name__ == "__main__":
    unittest.main()


class SidecarTrimTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sidecar = Path(self._tmp.name) / "_telegram_sends.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rows):
        self.sidecar.write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
        )

    def test_cutoff_is_newest_archive_timestamp(self):
        rows = [{"timestamp": "2026-07-01T10:00:00"}, {"timestamp": "2026-07-02T09:00:00"}, {}]
        self.assertEqual(sidecar_trim_cutoff(rows), "2026-07-02T09:00:00")
        self.assertEqual(sidecar_trim_cutoff([]), "")

    def test_drops_archived_rows_keeps_newer(self):
        self._write([
            {"timestamp": "2026-07-01T10:00:00", "content": "old"},
            {"timestamp": "2026-07-02T09:00:00", "content": "at-cutoff"},
            {"timestamp": "2026-07-02T09:00:01", "content": "new"},
        ])
        kept = trim_sidecar_rows(self.sidecar, "2026-07-02T09:00:00")
        self.assertEqual(kept, 1)
        lines = self.sidecar.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("new", lines[0])

    def test_empty_cutoff_is_noop(self):
        self._write([{"timestamp": "2026-07-01T10:00:00", "content": "x"}])
        self.assertIsNone(trim_sidecar_rows(self.sidecar, ""))
        self.assertEqual(len(self.sidecar.read_text(encoding="utf-8").splitlines()), 1)

    def test_missing_file_is_noop(self):
        self.assertIsNone(trim_sidecar_rows(self.sidecar, "2026-07-02T09:00:00"))

    def test_malformed_lines_are_dropped(self):
        self.sidecar.write_text(
            'not-json\n{"timestamp": "2026-07-03T00:00:00", "content": "keep"}\n',
            encoding="utf-8",
        )
        kept = trim_sidecar_rows(self.sidecar, "2026-07-02T00:00:00")
        self.assertEqual(kept, 1)

    def test_all_archived_leaves_empty_file(self):
        self._write([{"timestamp": "2026-07-01T00:00:00", "content": "x"}])
        kept = trim_sidecar_rows(self.sidecar, "2026-07-02T00:00:00")
        self.assertEqual(kept, 0)
        self.assertEqual(self.sidecar.read_text(encoding="utf-8"), "")

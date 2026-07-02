import unittest
from pathlib import Path

from bridge.forge_summary_state import (
    apply_provider_result,
    apply_summary_skip_status,
    build_summary_info,
    summary_cache_matches,
)


class ForgeSummaryStateTest(unittest.TestCase):
    def test_build_summary_info_tracks_public_status_fields(self):
        info = build_summary_info(
            skip_summary=False,
            summary_file=Path("summary.md"),
            summary_meta=Path("meta.json"),
            summary_provider="provider",
            summary_prompt_file=Path("prompt.md"),
            previous_summary="old",
            dropped_text="new text",
            dropped_hash="abcdef1234567890",
        )

        self.assertEqual(info["status"], "pending")
        self.assertEqual(info["file"], "summary.md")
        self.assertEqual(info["meta"], "meta.json")
        self.assertIsNone(info["dropped_events"])
        self.assertEqual(info["dropped_chars"], 8)
        self.assertEqual(info["previous_chars"], 3)
        self.assertEqual(info["summary_chars"], 3)
        self.assertFalse(info["write_summary"])
        self.assertEqual(info["dropped_hash"], "abcdef1234567890")
        self.assertEqual(info["provider"], "provider")
        self.assertEqual(info["prompt_file"], "prompt.md")

    def test_apply_summary_skip_status_handles_all_skip_modes(self):
        info = {}
        self.assertTrue(apply_summary_skip_status(info, True, True, "drop", "old"))
        self.assertEqual(info["status"], "disabled")

        info = {}
        self.assertTrue(apply_summary_skip_status(info, False, False, "drop", "old"))
        self.assertEqual(info["status"], "dry-run-skipped")

        info = {}
        self.assertTrue(apply_summary_skip_status(info, False, True, "", "old"))
        self.assertEqual(info["status"], "previous-only")

        info = {}
        self.assertTrue(apply_summary_skip_status(info, False, True, "", ""))
        self.assertEqual(info["status"], "skipped-no-dropped")

        info = {}
        self.assertFalse(apply_summary_skip_status(info, False, True, "drop", "old"))
        self.assertEqual(info, {})

    def test_summary_cache_matches_requires_all_cache_keys(self):
        meta = {"source": "session.jsonl", "dropped_hash": "drop", "previous_hash": "prev"}

        self.assertTrue(summary_cache_matches(meta, Path("session.jsonl"), "drop", "prev"))
        self.assertFalse(summary_cache_matches(meta, "other.jsonl", "drop", "prev"))
        self.assertFalse(summary_cache_matches(meta, "session.jsonl", "other", "prev"))
        self.assertFalse(summary_cache_matches(meta, "session.jsonl", "drop", "other"))

    def test_apply_provider_result_updates_or_falls_back(self):
        info = {"summary_chars": 3, "write_summary": False}
        summary = apply_provider_result(info, "old", "prevhash", "fresh summary", "updated")

        self.assertEqual(summary, "fresh summary")
        self.assertEqual(info["status"], "updated")
        self.assertEqual(info["summary_chars"], 13)
        self.assertTrue(info["write_summary"])
        self.assertEqual(info["previous_hash"], "prevhash")

        info = {}
        summary = apply_provider_result(info, "old", "prevhash", "", "provider-error")
        self.assertEqual(summary, "old")
        self.assertEqual(info["status"], "provider-error-previous-fallback")

        info = {}
        summary = apply_provider_result(info, "", "prevhash", "", "provider-error")
        self.assertEqual(summary, "")
        self.assertEqual(info["status"], "provider-error")


if __name__ == "__main__":
    unittest.main()

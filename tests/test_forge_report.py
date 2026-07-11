import unittest
from pathlib import Path

from bridge.forge_report import build_forge_report, count_thinking_blocks


def assistant(blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": blocks}}


class ForgeReportTest(unittest.TestCase):
    def test_count_thinking_blocks_counts_resume_safe_thinking(self):
        events = [
            assistant(
                [
                    {"type": "thinking", "thinking": "..."},
                    {"type": "redacted_thinking", "data": "..."},
                    {"type": "text", "text": "reply"},
                ]
            ),
            {"type": "user", "message": {"role": "user", "content": "plain"}},
        ]

        self.assertEqual(count_thinking_blocks(events), 2)

    def test_build_forge_report_preserves_public_summary_shape(self):
        forged = [
            assistant(
                [
                    {"type": "thinking", "thinking": "..."},
                    {"type": "text", "text": "reply"},
                ]
            )
        ]
        warnings = ["manual warning"]
        skipped = [{"path": "newer.jsonl", "reason": "no usable turn"}]

        report = build_forge_report(
            source=Path("source.jsonl"),
            new_sid="sid-1",
            rows=[{}, {}, {}],
            forged=forged,
            retained=[{}],
            summary_injected=True,
            summary_info={
                "status": "updated",
                "file": "summary.md",
                "meta": "meta.json",
                "summary_chars": 7,
                "dropped_events": 2,
                "dropped_chars": 20,
                "provider": "provider",
                "prompt_file": "prompt.md",
            },
            window={
                "clean_events": 2,
                "raw_zone_events": 1,
                "raw_start_index": 1,
                "dialogue_zone_events": 1,
                "dialogue_start_index": 0,
                "tool_pair_repairs": 0,
            },
            trimmed_tail=[{}],
            replay={"messages": ["hello"]},
            terminal_type="assistant",
            warnings=warnings,
            skipped_candidates=skipped,
            token_estimator=lambda event: 5,
        )

        self.assertEqual(report["source"], "source.jsonl")
        self.assertEqual(report["new_sid"], "sid-1")
        self.assertEqual(report["source_events"], 3)
        self.assertEqual(report["kept_events"], 1)
        self.assertEqual(report["retained_events"], 1)
        self.assertTrue(report["summary_injected"])
        self.assertEqual(report["summary_status"], "updated")
        self.assertEqual(report["summary_file"], "summary.md")
        self.assertEqual(report["summary_meta"], "meta.json")
        self.assertEqual(report["summary_dropped_events"], 2)
        self.assertEqual(report["summary_dropped_chars"], 20)
        self.assertEqual(report["clean_events"], 2)
        self.assertEqual(report["raw_zone_events"], 1)
        self.assertEqual(report["dialogue_zone_events"], 1)
        self.assertEqual(report["trimmed_tail_events"], 1)
        self.assertEqual(report["replay_messages"], 1)
        self.assertEqual(report["estimated_tokens_kept"], 5)
        self.assertEqual(report["thinking_blocks_kept"], 1)
        self.assertFalse(report["written"])

        warnings.append("mutated")
        skipped.append({"path": "other.jsonl"})
        self.assertEqual(report["warnings"], ["manual warning"])
        self.assertEqual(report["skipped_candidates"], [{"path": "newer.jsonl", "reason": "no usable turn"}])

    def test_build_forge_report_handles_absent_replay_and_skipped_candidates(self):
        report = build_forge_report(
            source="source.jsonl",
            new_sid="sid-1",
            rows=[],
            forged=[],
            retained=[],
            summary_injected=False,
            summary_info={
                "status": "disabled",
                "file": "",
                "meta": "",
                "summary_chars": 0,
                "dropped_events": 0,
                "dropped_chars": 0,
                "provider": "",
                "prompt_file": "",
            },
            window={
                "clean_events": 0,
                "raw_zone_events": 0,
                "raw_start_index": 0,
                "dialogue_zone_events": 0,
                "dialogue_start_index": 0,
                "tool_pair_repairs": 0,
            },
            trimmed_tail=[],
            replay=None,
            terminal_type=None,
            warnings=[],
            skipped_candidates=None,
            token_estimator=lambda event: 1,
        )

        self.assertEqual(report["replay_messages"], 0)
        self.assertEqual(report["skipped_candidates"], [])
        self.assertEqual(report["terminal_type"], None)


if __name__ == "__main__":
    unittest.main()

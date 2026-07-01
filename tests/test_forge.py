import unittest
import tempfile
from pathlib import Path

from bridge.forge import (
    content_blocks,
    build_forge_summary,
    build_manifest_payload,
    build_summary_meta_payload,
    choose_kept,
    close_at_final_assistant,
    count_thinking_blocks,
    execute_forge_write,
    estimate_tokens,
    event_text,
    filter_runtime_noise_turns,
    forge_write_paths,
    forge_events,
    is_real_user,
    sanitize_content,
    sanitize_event,
    sanitize_events,
    validate_chain,
    write_json_atomic,
    write_jsonl_atomic,
    write_text_atomic,
)


def user(text):
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def assistant(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


class ForgeTest(unittest.TestCase):
    def test_sanitize_content_keeps_only_resume_safe_blocks(self):
        self.assertEqual(sanitize_content("user", "hello"), "hello")
        self.assertIsNone(sanitize_content("user", "  "))
        self.assertEqual(
            sanitize_content(
                "assistant",
                [
                    {"type": "text", "text": "ok"},
                    {"type": "tool_use", "name": "read"},
                    {"type": "thinking", "thinking": "..."},
                ],
            ),
            [{"type": "text", "text": "ok"}, {"type": "thinking", "thinking": "..."}],
        )

    def test_sanitize_event_removes_runtime_fields_and_meta(self):
        event = {
            "type": "assistant",
            "requestId": "private-id",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "reply"}, {"type": "tool_use", "name": "x"}],
                "usage": {"tokens": 1},
                "diagnostics": {"trace": "x"},
            },
        }

        clean = sanitize_event(event)

        self.assertNotIn("requestId", clean)
        self.assertNotIn("usage", clean["message"])
        self.assertNotIn("diagnostics", clean["message"])
        self.assertEqual(clean["message"]["content"], [{"type": "text", "text": "reply"}])
        self.assertIsNone(sanitize_event({"type": "user", "isMeta": True, "message": {"role": "user", "content": "hidden"}}))

    def test_sanitize_events_filters_runtime_noise_turn_and_reply(self):
        rows = [
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "FORGE_CONTEXT_SUMMARY:\nhidden"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "also hidden"}]}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "keep me"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "kept reply"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "API Error: hidden"}]}},
        ]

        cleaned = sanitize_events(rows)

        self.assertEqual([event_text(event) for event in cleaned], ["keep me", "kept reply"])

    def test_filter_runtime_noise_turns_resumes_at_next_user(self):
        rows = [
            {"type": "user", "message": {"role": "user", "content": "FORGE_RESUME_READY_hidden"}},
            {"type": "assistant", "message": {"role": "assistant", "content": "hidden"}},
            {"type": "user", "message": {"role": "user", "content": "visible"}},
        ]

        self.assertEqual([event_text(event) for event in filter_runtime_noise_turns(rows)], ["visible"])

    def test_real_user_and_token_estimate(self):
        user_event = user("hello")
        assistant_event = {"type": "assistant", "message": {"role": "assistant", "content": "hello"}}

        self.assertEqual(content_blocks(user_event["message"]["content"]), ["text"])
        self.assertTrue(is_real_user(user_event))
        self.assertFalse(is_real_user(assistant_event))
        self.assertGreaterEqual(estimate_tokens(user_event), 1)

    def test_choose_kept_starts_at_first_real_user_after_cut(self):
        events = [user("old"), assistant("old reply"), user("new"), assistant("new reply")]
        selection = choose_kept(events, 2, token_estimator=lambda event: 1)

        self.assertEqual([event_text(event) for event in selection.kept], ["new", "new reply"])
        self.assertEqual(selection.raw_cut_index, 2)
        self.assertEqual(selection.keep_start_index, 2)
        self.assertEqual(selection.estimated_tokens_scanned, 3)

    def test_choose_kept_raises_when_tail_has_no_real_user(self):
        events = [user("old"), assistant("tail")]

        with self.assertRaisesRegex(ValueError, "no real user"):
            choose_kept(events, 1, token_estimator=lambda event: 1)

    def test_close_at_final_assistant_trims_open_tail(self):
        events = [user("first"), assistant("reply"), user("open tail")]
        selection = close_at_final_assistant(events, allow_open_turn=True)

        self.assertEqual([event_text(event) for event in selection.kept], ["first", "reply"])
        self.assertEqual(selection.terminal_type_before_trim, "user")
        self.assertEqual(selection.terminal_type, "assistant")
        self.assertEqual(len(selection.warnings), 2)
        self.assertIn("trimmed 1 trailing", selection.warnings[0])

    def test_close_at_final_assistant_requires_assistant(self):
        with self.assertRaisesRegex(ValueError, "no assistant"):
            close_at_final_assistant([user("only user")])

    def test_forge_events_rewrites_session_and_parent_chain(self):
        events = [
            {**user("first"), "uuid": "old-1", "sessionId": "old-session", "parentUuid": "old-parent"},
            {**assistant("reply"), "uuid": "old-2", "sessionId": "old-session", "parentUuid": "old-1"},
        ]
        ids = iter(["new-1", "new-2"])

        forged, uuid_map = forge_events(events, "new-session", uuid_factory=lambda: next(ids))

        self.assertEqual(uuid_map, {"old-1": "new-1", "old-2": "new-2"})
        self.assertEqual([event["uuid"] for event in forged], ["new-1", "new-2"])
        self.assertEqual([event["sessionId"] for event in forged], ["new-session", "new-session"])
        self.assertEqual([event["parentUuid"] for event in forged], [None, "new-1"])
        validate_chain(forged)

    def test_forge_events_can_preserve_existing_uuids(self):
        events = [{**user("first"), "uuid": "old-1"}, {**assistant("reply"), "uuid": "old-2"}]

        forged, uuid_map = forge_events(events, "new-session", rewrite_event_uuids=False)

        self.assertEqual(uuid_map, {})
        self.assertEqual([event["uuid"] for event in forged], ["old-1", "old-2"])
        self.assertEqual([event["parentUuid"] for event in forged], [None, "old-1"])

    def test_validate_chain_rejects_duplicate_or_missing_parents(self):
        with self.assertRaisesRegex(ValueError, "duplicate uuid"):
            validate_chain([{"uuid": "same", "parentUuid": None}, {"uuid": "same", "parentUuid": "same"}])

        with self.assertRaisesRegex(ValueError, "missing parents"):
            validate_chain([{"uuid": "child", "parentUuid": "missing"}])

    def test_count_thinking_blocks_counts_resume_safe_thinking(self):
        events = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "..."},
                        {"type": "redacted_thinking", "data": "..."},
                        {"type": "text", "text": "reply"},
                    ],
                },
            }
        ]

        self.assertEqual(count_thinking_blocks(events), 2)

    def test_build_forge_summary_reports_dry_run_metadata(self):
        events = [user("first"), assistant("reply")]
        retain = choose_kept(events, 10, token_estimator=lambda event: 1)
        closed = close_at_final_assistant(retain.kept)
        forged, _ = forge_events(closed.kept, "new-session", uuid_factory=iter(["new-1", "new-2"]).__next__)
        summary = build_forge_summary(
            source="source.jsonl",
            new_session_id="new-session",
            source_events=3,
            sanitized_events=2,
            forged=forged,
            retained=closed.kept,
            summary_injected=False,
            summary_info={
                "status": "dry-run-skipped",
                "file": "summary.md",
                "meta": "summary.json",
                "summary_chars": 7,
                "dropped_events": 1,
                "dropped_chars": 12,
                "provider": "none",
                "prompt_file": "",
            },
            retain_selection=retain,
            closed_selection=closed,
            warnings=["manual warning"],
        )

        self.assertEqual(summary["source"], "source.jsonl")
        self.assertEqual(summary["new_sid"], "new-session")
        self.assertEqual(summary["source_events"], 3)
        self.assertEqual(summary["sanitized_events"], 2)
        self.assertEqual(summary["kept_events"], 2)
        self.assertEqual(summary["retained_events"], 2)
        self.assertEqual(summary["summary_status"], "dry-run-skipped")
        self.assertEqual(summary["summary_file"], "summary.md")
        self.assertEqual(summary["summary_meta"], "summary.json")
        self.assertEqual(summary["summary_dropped_events"], 1)
        self.assertEqual(summary["summary_dropped_chars"], 12)
        self.assertEqual(summary["terminal_type"], "assistant")
        self.assertEqual(summary["warnings"], ["manual warning"])
        self.assertFalse(summary["written"])

    def test_forge_write_paths_are_derived_without_touching_disk(self):
        paths = forge_write_paths(Path("/project"), Path("/manifest"), "sid-1")

        self.assertEqual(paths["dest"], Path("/project/sid-1.jsonl"))
        self.assertEqual(paths["tmp_dest"], Path("/project/sid-1.jsonl.tmp"))
        self.assertEqual(paths["manifest"], Path("/manifest/sid-1.manifest.json"))
        self.assertEqual(paths["tmp_manifest"], Path("/manifest/sid-1.manifest.json.tmp"))
        self.assertEqual(paths["summary_snapshot"], Path("/manifest/sid-1.summary.md"))

    def test_build_summary_meta_payload_matches_public_summary_fields(self):
        payload = build_summary_meta_payload(
            source="source.jsonl",
            new_session_id="sid-1",
            summary_text="summary",
            summary_info={
                "dropped_events": 2,
                "dropped_chars": 40,
                "dropped_hash": "abc",
                "previous_hash": "prev",
                "status": "updated",
                "provider": "custom",
                "prompt_file": "prompt.md",
            },
            updated_at="2026-07-01T00:00:00Z",
        )

        self.assertEqual(payload["updated_at"], "2026-07-01T00:00:00Z")
        self.assertEqual(payload["source"], "source.jsonl")
        self.assertEqual(payload["new_sid"], "sid-1")
        self.assertEqual(payload["dropped_events"], 2)
        self.assertEqual(payload["summary_chars"], 7)
        self.assertEqual(payload["status"], "updated")
        self.assertEqual(payload["provider"], "custom")
        self.assertEqual(payload["prompt_file"], "prompt.md")
        self.assertEqual(len(payload["summary_hash"]), 64)

    def test_build_manifest_payload_adds_created_at_without_mutating_summary(self):
        summary = {"new_sid": "sid-1", "written": True}
        payload = build_manifest_payload(summary, created_at="2026-07-01T00:00:00Z")

        self.assertEqual(payload, {"new_sid": "sid-1", "written": True, "created_at": "2026-07-01T00:00:00Z"})
        self.assertNotIn("created_at", summary)

    def test_write_jsonl_atomic_writes_compact_jsonl_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "nested" / "session.jsonl"
            events = [user("hello"), assistant("reply")]

            result = write_jsonl_atomic(dest, events)

            self.assertEqual(result, dest)
            self.assertTrue(dest.exists())
            self.assertFalse(dest.with_name(dest.name + ".tmp").exists())
            self.assertEqual(dest.read_text(encoding="utf-8").count("\n"), 2)
            self.assertIn('"content":[{"type":"text","text":"hello"}]', dest.read_text(encoding="utf-8"))

            with self.assertRaises(FileExistsError):
                write_jsonl_atomic(dest, events)

    def test_write_text_atomic_writes_and_replaces_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "summary" / "forge.md"

            write_text_atomic(dest, "first\n")
            write_text_atomic(dest, "second\n")

            self.assertEqual(dest.read_text(encoding="utf-8"), "second\n")
            self.assertFalse(dest.with_name(dest.name + ".tmp").exists())

    def test_write_json_atomic_writes_pretty_json_with_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "manifest" / "sid.manifest.json"
            payload = {"new_sid": "sid", "written": True}

            write_json_atomic(dest, payload)

            text = dest.read_text(encoding="utf-8")
            self.assertTrue(text.endswith("\n"))
            self.assertIn('"new_sid": "sid"', text)
            self.assertIn('"written": true', text)
            self.assertFalse(dest.with_name(dest.name + ".tmp").exists())

    def test_execute_forge_write_writes_jsonl_and_manifest_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {
                "dest": root / "project" / "sid.jsonl",
                "manifest": root / "manifest" / "sid.manifest.json",
            }
            summary = {"new_sid": "sid", "written": False}
            manifest_payload = {"new_sid": "sid", "created_at": "now"}

            updated = execute_forge_write(
                paths=paths,
                forged_events=[user("hello")],
                summary=summary,
                manifest_payload=manifest_payload,
            )

            self.assertTrue(paths["dest"].exists())
            self.assertTrue(paths["manifest"].exists())
            self.assertTrue(updated["written"])
            self.assertEqual(updated["dest"], str(paths["dest"]))
            self.assertEqual(updated["manifest"], str(paths["manifest"]))
            self.assertFalse(summary["written"])
            self.assertIn('"created_at": "now"', paths["manifest"].read_text(encoding="utf-8"))

    def test_execute_forge_write_optionally_writes_summary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {
                "dest": root / "project" / "sid.jsonl",
                "manifest": root / "manifest" / "sid.manifest.json",
                "summary_file": root / "state" / "summary.md",
                "summary_meta": root / "state" / "summary-meta.json",
                "summary_snapshot": root / "manifest" / "sid.summary.md",
            }
            updated = execute_forge_write(
                paths=paths,
                forged_events=[user("hello")],
                summary={"new_sid": "sid", "written": False},
                manifest_payload={"new_sid": "sid", "created_at": "now"},
                summary_text="summary",
                summary_meta_payload={"summary_chars": 7},
            )

            self.assertEqual(paths["summary_file"].read_text(encoding="utf-8"), "summary\n")
            self.assertEqual(paths["summary_snapshot"].read_text(encoding="utf-8"), "summary\n")
            self.assertIn('"summary_chars": 7', paths["summary_meta"].read_text(encoding="utf-8"))
            self.assertEqual(updated["summary_snapshot"], str(paths["summary_snapshot"]))


if __name__ == "__main__":
    unittest.main()

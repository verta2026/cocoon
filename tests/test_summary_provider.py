import json
import tempfile
import unittest
from pathlib import Path

from bridge.summary_provider import (
    build_summary_messages,
    call_openai_compatible_summary,
    call_summary_provider,
    extract_summary_marker,
    load_deepseek_config,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class SummaryProviderTest(unittest.TestCase):
    def test_load_deepseek_config_accepts_nested_or_flat_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "nested.json"
            nested.write_text(
                json.dumps({"deepseek": {"api_key": "key", "base_url": "https://api.example", "model": "chat"}}),
                encoding="utf-8",
            )
            flat = Path(tmp) / "flat.json"
            flat.write_text(
                json.dumps({"api_key": "key", "base_url": "https://api.example", "model": "chat"}),
                encoding="utf-8",
            )
            missing = Path(tmp) / "missing.json"
            missing.write_text(json.dumps({"deepseek": {"api_key": "key"}}), encoding="utf-8")

            self.assertEqual(load_deepseek_config(nested)["model"], "chat")
            self.assertEqual(load_deepseek_config(flat)["base_url"], "https://api.example")
            self.assertIsNone(load_deepseek_config(missing))
            self.assertIsNone(load_deepseek_config(Path(tmp) / "absent.json"))

    def test_marker_and_message_helpers_are_provider_neutral(self):
        self.assertEqual(extract_summary_marker("note\nMARK\nsummary", "MARK"), "summary")
        self.assertEqual(extract_summary_marker("plain", "MARK"), "plain")

        messages = build_summary_messages("old", "raw", "system prompt")

        self.assertEqual(messages[0], {"role": "system", "content": "system prompt"})
        self.assertIn("old", messages[1]["content"])
        self.assertIn("raw", messages[1]["content"])
        self.assertNotIn("DeepSeek", messages[1]["content"])

    def test_call_openai_compatible_summary_sends_request_and_extracts_marker(self):
        captured = {}

        def fake_urlopen(request, timeout, context):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["auth"] = request.get_header("Authorization")
            return FakeResponse({"choices": [{"message": {"content": "MARK\nnew summary"}}]})

        summary, status = call_openai_compatible_summary(
            "old",
            "raw",
            {"api_key": "key", "base_url": "https://api.example/", "model": "chat"},
            "system prompt",
            "MARK",
            urlopen=fake_urlopen,
            timeout=12,
        )

        self.assertEqual((summary, status), ("new summary", "updated"))
        self.assertEqual(captured["url"], "https://api.example/chat/completions")
        self.assertEqual(captured["timeout"], 12)
        self.assertEqual(captured["auth"], "Bearer key")
        self.assertEqual(captured["payload"]["model"], "chat")
        self.assertFalse(captured["payload"]["stream"])

    def test_call_openai_compatible_summary_handles_empty_and_error_paths(self):
        self.assertEqual(
            call_openai_compatible_summary(
                "old",
                "raw",
                {"api_key": "key", "base_url": "https://api.example", "model": "chat"},
                "system",
                "MARK",
                urlopen=lambda *args, **kwargs: FakeResponse({"choices": []}),
            ),
            ("", "deepseek-empty"),
        )

        def failing_urlopen(*args, **kwargs):
            raise TimeoutError("slow")

        self.assertEqual(
            call_openai_compatible_summary(
                "old",
                "raw",
                {"api_key": "key", "base_url": "https://api.example", "model": "chat"},
                "system",
                "MARK",
                urlopen=failing_urlopen,
            ),
            ("", "deepseek-error:TimeoutError"),
        )

    def test_call_summary_provider_enforces_provider_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                json.dumps({"deepseek": {"api_key": "key", "base_url": "https://api.example", "model": "chat"}}),
                encoding="utf-8",
            )

            self.assertEqual(
                call_summary_provider("none", "old", "raw", config_path=config_path, system_prompt="system", marker="MARK"),
                ("", "provider-disabled"),
            )
            self.assertEqual(
                call_summary_provider("other", "old", "raw", config_path=config_path, system_prompt="system", marker="MARK"),
                ("", "unsupported-provider:other"),
            )
            self.assertEqual(
                call_summary_provider(
                    "deepseek",
                    "old",
                    "raw",
                    config_path=Path(tmp) / "missing.json",
                    system_prompt="system",
                    marker="MARK",
                ),
                ("", "missing-config"),
            )

            summary, status = call_summary_provider(
                "deepseek",
                "old",
                "raw",
                config_path=config_path,
                system_prompt="system",
                marker="MARK",
                urlopen=lambda *args, **kwargs: FakeResponse({"choices": [{"message": {"reasoning_content": "MARK\nok"}}]}),
            )

            self.assertEqual((summary, status), ("ok", "updated"))


if __name__ == "__main__":
    unittest.main()

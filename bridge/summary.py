"""Generic summary boundary for forge-style session handoff."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Callable
from dataclasses import dataclass


FORGE_SUMMARY_MARKER = "FORGE_CONTEXT_SUMMARY:"
DISABLED_PROVIDERS = {"", "none", "off", "disabled"}
ASSISTANT_RUNTIME_NOISE_PREFIXES = (
    "API Error:",
    "Please run /login",
    "OAuth error:",
)
USER_RUNTIME_NOISE_MARKERS = (
    "FORGE_RESUME_READY_",
    FORGE_SUMMARY_MARKER,
    "<local-command-caveat>",
    "<command-name>",
    "<command-message>",
    "<command-args>",
    "<local-command-stdout>",
    "<local-command-stderr>",
)


@dataclass(frozen=True)
class SummaryInput:
    previous_summary: str
    dropped_text: str
    source_id: str = ""
    provider: str = "none"
    write: bool = False
    skip: bool = False


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    info: dict


SummaryProvider = Callable[[str, str], tuple[str, str]]


def sha_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def clamp_middle(text: str, max_chars: int) -> str:
    text = text or ""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head
    omitted = len(text) - head - tail
    return (
        text[:head].rstrip()
        + f"\n\n[... omitted {omitted} chars from the middle ...]\n\n"
        + text[-tail:].lstrip()
    )


def event_role(event: dict) -> str:
    message = event.get("message")
    role = message.get("role") if isinstance(message, dict) else ""
    return role if isinstance(role, str) else ""


def content_text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def is_channel_event(event: dict) -> bool:
    message = event.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content", "")
    return isinstance(content, str) and "<channel source=" in content


def event_speaker(event: dict) -> str:
    if is_channel_event(event):
        return "channel"
    role = event_role(event)
    return role if role in {"assistant", "user"} else "unknown"


def event_timestamp(event: dict) -> str:
    return event.get("timestamp") or event.get("created_at") or ""


# Bare plumbing tokens (resume/summary markers, deployment-supplied) are matched
# first-line + length-capped, not as free substrings: a real user message that
# merely *mentions* the token — e.g. asking what "FORGE_RESUME_READY_" is — must
# not be dropped from the summary. Structural "<...>" command tags stay substring
# matches: they never occur in prose, and their blocks can be long/multi-line.
def _user_marker_hit(text: str, markers) -> bool:
    first_line = text.lstrip().split("\n", 1)[0]
    for marker in markers:
        if not marker:
            continue
        if marker.startswith("<"):
            if marker in text:
                return True
        elif first_line.startswith(marker):
            return True
    return False


def is_runtime_noise(role: str, content, *, extra_user_markers: tuple[str, ...] = ()) -> bool:
    text = content_text(content).strip()
    if role == "assistant":
        return any(text.startswith(prefix) for prefix in ASSISTANT_RUNTIME_NOISE_PREFIXES)
    if role == "user":
        markers = USER_RUNTIME_NOISE_MARKERS + tuple(extra_user_markers)
        return _user_marker_hit(text, markers)
    return False


def format_events_for_summary(
    events: list[dict],
    max_chars: int,
    *,
    extra_user_noise_markers: tuple[str, ...] = (),
) -> str:
    lines = []
    for event in events:
        message = event.get("message") or {}
        role = event_role(event)
        content = message.get("content")
        if is_runtime_noise(role, content, extra_user_markers=extra_user_noise_markers):
            continue
        text = content_text(content).strip()
        if not text:
            continue
        timestamp = event_timestamp(event)
        speaker = event_speaker(event)
        heading = f"[{timestamp}] {speaker}" if timestamp else speaker
        lines.append(f"{heading}:\n{text}")
    return clamp_middle("\n\n".join(lines).strip(), max_chars)


def extract_summary_marker(text: str, marker: str = FORGE_SUMMARY_MARKER) -> str:
    text = (text or "").strip()
    if marker and marker in text:
        return text.split(marker, 1)[1].strip()
    return text


def default_summary_system_prompt(marker: str = FORGE_SUMMARY_MARKER) -> str:
    return (
        "You maintain a cumulative handoff summary for a long-running chat session. "
        "Merge the previous summary with the raw conversation that is about to be "
        "dropped. Preserve decisions, unresolved threads, user preferences, and "
        "important context. Do not write an architecture report unless the technical "
        "details matter for continuing the conversation. "
        f"Start the output with {marker}"
    )


def build_summary_messages(
    previous_summary: str,
    dropped_text: str,
    *,
    system_prompt: str | None = None,
) -> list[dict]:
    return [
        {
            "role": "system",
            "content": system_prompt or default_summary_system_prompt(),
        },
        {
            "role": "user",
            "content": (
                "Previous cumulative summary:\n"
                f"{previous_summary or '(none)'}\n\n"
                "Raw conversation that will be dropped:\n"
                f"{dropped_text or '(none)'}\n\n"
                "Return the new cumulative summary."
            ),
        },
    ]


def call_summary_provider(
    provider: str,
    previous_summary: str,
    dropped_text: str,
    call_provider: SummaryProvider | None = None,
) -> tuple[str, str]:
    provider_name = (provider or "").strip().lower()
    if provider_name in DISABLED_PROVIDERS:
        return "", "provider-disabled"
    if call_provider is None:
        return "", f"unsupported-provider:{provider_name}"
    summary, status = call_provider(previous_summary, dropped_text)
    summary = extract_summary_marker(summary)
    if not summary:
        return "", status or "provider-empty"
    return summary, status or "updated"


def prepare_summary(
    summary_input: SummaryInput,
    *,
    meta: dict | None = None,
    call_provider: SummaryProvider | None = None,
) -> SummaryResult:
    previous = summary_input.previous_summary or ""
    dropped = summary_input.dropped_text or ""
    dropped_hash = sha_text(dropped)
    previous_hash = sha_text(previous)
    provider = (summary_input.provider or "").strip().lower()
    info = {
        "status": "disabled" if summary_input.skip else "pending",
        "dropped_chars": len(dropped),
        "previous_chars": len(previous),
        "summary_chars": len(previous),
        "write_summary": False,
        "dropped_hash": dropped_hash[:24],
        "provider": provider,
    }

    if summary_input.skip:
        return SummaryResult(previous, info)
    if not summary_input.write:
        info["status"] = "dry-run-skipped"
        return SummaryResult(previous, info)
    if not dropped:
        info["status"] = "previous-only" if previous else "skipped-no-dropped"
        return SummaryResult(previous, info)

    meta = meta or {}
    same_source = meta.get("source") == summary_input.source_id
    same_hash = meta.get("dropped_hash") == dropped_hash and meta.get("previous_hash") == previous_hash
    if previous and same_source and same_hash:
        info["status"] = "reused"
        return SummaryResult(previous, info)

    new_summary, status = call_summary_provider(provider, previous, dropped, call_provider)
    if new_summary:
        info.update(
            {
                "status": status,
                "summary_chars": len(new_summary),
                "write_summary": True,
                "previous_hash": previous_hash,
            }
        )
        return SummaryResult(new_summary, info)

    info["status"] = f"{status}-previous-fallback" if previous else status
    return SummaryResult(previous, info)


def synthetic_summary_event(
    summary_text: str,
    template: dict | None = None,
    *,
    timestamp: str = "",
    marker: str = FORGE_SUMMARY_MARKER,
) -> dict:
    event = copy.deepcopy(template) if isinstance(template, dict) else {}
    text = (
        f"{marker}\n"
        "This is an internal cumulative handoff summary produced before forge truncation. "
        "Treat it as prior conversation context, not as a new user request.\n\n"
        f"{(summary_text or '').strip()}"
    )
    event.update(
        {
            "type": "user",
            "isMeta": False,
            "message": {"role": "user", "content": [{"type": "text", "text": text}]},
        }
    )
    if timestamp:
        event["timestamp"] = timestamp
    else:
        event.pop("timestamp", None)
    event.pop("requestId", None)
    return event


def inject_summary_event(
    kept: list[dict],
    summary_text: str,
    *,
    timestamp: str = "",
) -> tuple[list[dict], bool]:
    if not (summary_text or "").strip() or not kept:
        return kept, False
    template = next((event for event in kept if event.get("type") == "user"), kept[0])
    return [synthetic_summary_event(summary_text, template, timestamp=timestamp)] + kept, True

"""Generic summary boundary for forge-style session handoff."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass


FORGE_SUMMARY_MARKER = "FORGE_CONTEXT_SUMMARY:"
DISABLED_PROVIDERS = {"", "none", "off", "disabled"}


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

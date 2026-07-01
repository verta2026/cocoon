"""Generic Claude jsonl helpers for forge-style session handoff."""

from __future__ import annotations

import copy
import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from bridge.summary import content_text, event_role, inject_summary_event, is_channel_event, is_runtime_noise, sha_text


ASSISTANT_BLOCKS = {"thinking", "redacted_thinking", "text"}
USER_BLOCKS = {"text"}


@dataclass(frozen=True)
class RetainSelection:
    kept: list[dict]
    raw_cut_index: int
    keep_start_index: int
    estimated_tokens_scanned: int


@dataclass(frozen=True)
class ClosedTurnSelection:
    kept: list[dict]
    warnings: list[str]
    terminal_type_before_trim: str | None
    terminal_type: str | None


@dataclass(frozen=True)
class ForgePlan:
    source: str
    new_session_id: str
    sanitized: list[dict]
    retained: list[dict]
    dropped_events: list[dict]
    forged: list[dict]
    uuid_map: dict[str, str]
    summary: dict
    summary_injected: bool


def content_blocks(content) -> list[str]:
    if isinstance(content, str):
        return ["string"] if content.strip() else []
    if isinstance(content, list):
        return [block.get("type") for block in content if isinstance(block, dict)]
    return []


def sanitize_content(role: str, content):
    if isinstance(content, str):
        return content if content.strip() else None
    if not isinstance(content, list):
        return None
    allowed = ASSISTANT_BLOCKS if role == "assistant" else USER_BLOCKS
    kept = []
    for block in content:
        if isinstance(block, dict) and block.get("type") in allowed:
            kept.append(copy.deepcopy(block))
    return kept or None


def sanitize_event(event: dict) -> dict | None:
    if event.get("type") not in {"user", "assistant"}:
        return None
    if event.get("isMeta") is True and not is_channel_event(event):
        return None

    role = event_role(event)
    if role not in {"user", "assistant"}:
        return None
    if event.get("type") != role:
        return None

    message = event.get("message")
    if not isinstance(message, dict):
        return None
    content = sanitize_content(role, message.get("content"))
    if content is None:
        return None
    if role == "assistant" and is_runtime_noise(role, content):
        return None

    clean = copy.deepcopy(event)
    clean["message"]["content"] = content
    clean["message"].pop("usage", None)
    clean["message"].pop("diagnostics", None)
    clean.pop("requestId", None)
    return clean


def is_runtime_noise_event(event: dict) -> bool:
    message = event.get("message") or {}
    return is_runtime_noise(event_role(event), message.get("content"))


def filter_runtime_noise_turns(events: list[dict]) -> list[dict]:
    filtered = []
    skip_assistant_replies = False
    for event in events:
        if event.get("type") == "user":
            if is_runtime_noise_event(event):
                skip_assistant_replies = True
                continue
            skip_assistant_replies = False
        elif skip_assistant_replies and event.get("type") == "assistant":
            continue
        filtered.append(event)
    return filtered


def sanitize_events(rows: list[dict]) -> list[dict]:
    sanitized = [event for event in (sanitize_event(row) for row in rows) if event is not None]
    return filter_runtime_noise_turns(sanitized)


def is_real_user(event: dict) -> bool:
    if event.get("type") != "user" or event_role(event) != "user":
        return False
    if event.get("isMeta") is True and not is_channel_event(event):
        return False
    message = event.get("message") or {}
    blocks = content_blocks(message.get("content"))
    return any(block_type in {"string", "text"} for block_type in blocks)


def estimate_tokens(event: dict) -> int:
    return max(1, len(json.dumps(event, ensure_ascii=False, separators=(",", ":"))) // 3)


def event_text(event: dict) -> str:
    message = event.get("message") or {}
    return content_text(message.get("content")).strip()


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"bad json at {path}:{line_number}: {exc}") from exc
    return rows


def count_thinking_blocks(events: list[dict]) -> int:
    count = 0
    for event in events:
        content = (event.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        count += sum(
            1
            for block in content
            if isinstance(block, dict) and block.get("type") in {"thinking", "redacted_thinking"}
        )
    return count


def choose_kept(
    events: list[dict],
    retain_tokens: int,
    *,
    token_estimator: Callable[[dict], int] = estimate_tokens,
) -> RetainSelection:
    accumulated = 0
    raw_cut_index = 0
    for index in range(len(events) - 1, -1, -1):
        accumulated += token_estimator(events[index])
        if accumulated > retain_tokens:
            raw_cut_index = index + 1
            break

    keep_start_index = None
    for index in range(raw_cut_index, len(events)):
        if is_real_user(events[index]):
            keep_start_index = index
            break
    if keep_start_index is None:
        raise ValueError("no real user message found after cut point")

    return RetainSelection(
        kept=events[keep_start_index:],
        raw_cut_index=raw_cut_index,
        keep_start_index=keep_start_index,
        estimated_tokens_scanned=accumulated,
    )


def close_at_final_assistant(events: list[dict], *, allow_open_turn: bool = False) -> ClosedTurnSelection:
    terminal_type_before_trim = events[-1].get("type") if events else None
    last_assistant = None
    for index in range(len(events) - 1, -1, -1):
        if events[index].get("type") == "assistant":
            last_assistant = index
            break
    if last_assistant is None:
        raise ValueError("no assistant message found in kept history")

    warnings = []
    kept = events
    if last_assistant != len(events) - 1:
        trailing = len(events) - last_assistant - 1
        warnings.append(
            f"trimmed {trailing} trailing non-assistant event(s) after final assistant; "
            f"previous terminal type was {terminal_type_before_trim}"
        )
        if allow_open_turn:
            warnings.append("allow_open_turn was provided, but trailing events were still trimmed for resume safety")
        kept = events[: last_assistant + 1]

    terminal_type = kept[-1].get("type") if kept else None
    return ClosedTurnSelection(
        kept=kept,
        warnings=warnings,
        terminal_type_before_trim=terminal_type_before_trim,
        terminal_type=terminal_type,
    )


def forge_events(
    kept: list[dict],
    new_session_id: str,
    *,
    rewrite_event_uuids: bool = True,
    uuid_factory: Callable[[], str] | None = None,
) -> tuple[list[dict], dict[str, str]]:
    uuid_factory = uuid_factory or (lambda: str(uuid.uuid4()))
    forged = []
    previous_uuid = None
    uuid_map = {}
    for event in kept:
        new_event = copy.deepcopy(event)
        old_uuid = new_event.get("uuid")
        if rewrite_event_uuids or not old_uuid:
            new_uuid = uuid_factory()
            if old_uuid:
                uuid_map[old_uuid] = new_uuid
            new_event["uuid"] = new_uuid
        else:
            new_uuid = old_uuid
        new_event["sessionId"] = new_session_id
        new_event["parentUuid"] = previous_uuid
        previous_uuid = new_uuid
        forged.append(new_event)
    return forged, uuid_map


def validate_chain(events: list[dict]) -> None:
    seen = set()
    missing = []
    for index, event in enumerate(events):
        parent = event.get("parentUuid")
        event_uuid = event.get("uuid")
        if parent is not None and parent not in seen:
            missing.append({"index": index, "parentUuid": parent, "uuid": event_uuid})
        if event_uuid in seen:
            raise ValueError(f"duplicate uuid in forged events: {event_uuid}")
        seen.add(event_uuid)
    if missing:
        raise ValueError(f"forged chain has missing parents: {missing[:3]}")


def build_forge_summary(
    *,
    source: str,
    new_session_id: str,
    source_events: int,
    sanitized_events: int,
    forged: list[dict],
    retained: list[dict],
    summary_injected: bool,
    summary_info: dict,
    retain_selection: RetainSelection,
    closed_selection: ClosedTurnSelection,
    warnings: list[str] | None = None,
) -> dict:
    warnings = list(warnings or []) + list(closed_selection.warnings)
    return {
        "source": source,
        "new_sid": new_session_id,
        "source_events": source_events,
        "sanitized_events": sanitized_events,
        "kept_events": len(forged),
        "retained_events": len(retained),
        "summary_injected": summary_injected,
        "summary_status": summary_info.get("status", ""),
        "summary_file": summary_info.get("file", ""),
        "summary_meta": summary_info.get("meta", ""),
        "summary_chars": summary_info.get("summary_chars", 0),
        "summary_dropped_events": summary_info.get("dropped_events", 0),
        "summary_dropped_chars": summary_info.get("dropped_chars", 0),
        "summary_provider": summary_info.get("provider", ""),
        "summary_prompt_file": summary_info.get("prompt_file", ""),
        "raw_cut_index": retain_selection.raw_cut_index,
        "keep_start_index": retain_selection.keep_start_index,
        "estimated_tokens_scanned": retain_selection.estimated_tokens_scanned,
        "estimated_tokens_kept": sum(estimate_tokens(event) for event in forged),
        "terminal_type": closed_selection.terminal_type,
        "thinking_blocks_kept": count_thinking_blocks(forged),
        "warnings": warnings,
        "written": False,
    }


def build_forge_plan(
    *,
    rows: list[dict],
    source: str,
    retain_tokens: int,
    new_session_id: str,
    summary_text: str = "",
    summary_info: dict | None = None,
    allow_open_turn: bool = False,
    rewrite_event_uuids: bool = True,
    uuid_factory: Callable[[], str] | None = None,
    token_estimator: Callable[[dict], int] = estimate_tokens,
    warnings: list[str] | None = None,
) -> ForgePlan:
    sanitized = sanitize_events(rows)
    if not sanitized:
        raise ValueError("no user/assistant text-bearing events found")
    retain_selection = choose_kept(sanitized, retain_tokens, token_estimator=token_estimator)
    closed_selection = close_at_final_assistant(retain_selection.kept, allow_open_turn=allow_open_turn)
    dropped_events = sanitized[: retain_selection.keep_start_index]
    events_to_forge, summary_injected = inject_summary_event(closed_selection.kept, summary_text)
    forged, uuid_map = forge_events(
        events_to_forge,
        new_session_id,
        rewrite_event_uuids=rewrite_event_uuids,
        uuid_factory=uuid_factory,
    )
    validate_chain(forged)
    summary = build_forge_summary(
        source=source,
        new_session_id=new_session_id,
        source_events=len(rows),
        sanitized_events=len(sanitized),
        forged=forged,
        retained=closed_selection.kept,
        summary_injected=summary_injected,
        summary_info=summary_info or {},
        retain_selection=retain_selection,
        closed_selection=closed_selection,
        warnings=warnings,
    )
    return ForgePlan(
        source=source,
        new_session_id=new_session_id,
        sanitized=sanitized,
        retained=closed_selection.kept,
        dropped_events=dropped_events,
        forged=forged,
        uuid_map=uuid_map,
        summary=summary,
        summary_injected=summary_injected,
    )


def forge_write_paths(project_dir: Path, manifest_dir: Path, new_session_id: str) -> dict:
    dest = project_dir / f"{new_session_id}.jsonl"
    manifest = manifest_dir / f"{new_session_id}.manifest.json"
    return {
        "dest": dest,
        "tmp_dest": dest.with_name(dest.name + ".tmp"),
        "manifest": manifest,
        "tmp_manifest": manifest.with_name(manifest.name + ".tmp"),
        "summary_snapshot": manifest_dir / f"{new_session_id}.summary.md",
    }


def build_summary_meta_payload(
    *,
    source: str,
    new_session_id: str,
    summary_text: str,
    summary_info: dict,
    updated_at: str,
) -> dict:
    return {
        "updated_at": updated_at,
        "source": source,
        "new_sid": new_session_id,
        "dropped_events": summary_info.get("dropped_events", 0),
        "dropped_chars": summary_info.get("dropped_chars", 0),
        "dropped_hash": summary_info.get("dropped_hash", ""),
        "previous_hash": summary_info.get("previous_hash", ""),
        "summary_hash": sha_text(summary_text),
        "summary_chars": len(summary_text or ""),
        "status": summary_info.get("status", ""),
        "provider": summary_info.get("provider", ""),
        "prompt_file": summary_info.get("prompt_file", ""),
    }


def build_manifest_payload(summary: dict, *, created_at: str) -> dict:
    return {**summary, "created_at": created_at}


def write_jsonl_atomic(path: Path, events: list[dict]) -> Path:
    if path.exists():
        raise FileExistsError(f"destination already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(tmp_path, path)
    return path


def write_text_atomic(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)
    return path


def write_json_atomic(path: Path, payload: dict, *, indent: int = 2) -> Path:
    return write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=indent) + "\n")


def execute_forge_write(
    *,
    paths: dict,
    forged_events: list[dict],
    summary: dict,
    manifest_payload: dict,
    summary_text: str = "",
    summary_meta_payload: dict | None = None,
) -> dict:
    updated_summary = dict(summary)
    write_jsonl_atomic(paths["dest"], forged_events)

    if summary_text.strip() and summary_meta_payload is not None:
        write_text_atomic(paths["summary_file"], summary_text.strip() + "\n")
        write_json_atomic(paths["summary_meta"], summary_meta_payload)
        write_text_atomic(paths["summary_snapshot"], summary_text.strip() + "\n")
        updated_summary["summary_snapshot"] = str(paths["summary_snapshot"])

    updated_summary["dest"] = str(paths["dest"])
    updated_summary["manifest"] = str(paths["manifest"])
    updated_summary["written"] = True
    write_json_atomic(paths["manifest"], manifest_payload)
    return updated_summary

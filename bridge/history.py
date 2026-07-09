"""Read-only JSONL conversation history helpers."""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from bridge.paths import safe_child_path


def conversation_files(conversations_dir: Path) -> list[Path]:
    if not conversations_dir.exists():
        return []
    files = [p for p in conversations_dir.glob("*.jsonl") if not p.name.startswith("_")]
    for subdir in ("dm", "group"):
        directory = conversations_dir / subdir
        if directory.exists():
            files.extend(p for p in directory.glob("*.jsonl") if not p.name.startswith("_"))
    return files


def conversation_file_id(path: Path, conversations_dir: Path) -> str:
    return path.relative_to(conversations_dir).as_posix()


def conversation_date_key(path: Path) -> float:
    stem = path.stem.replace("_session", "").replace("_dm", "").replace("_group", "")
    for fmt in ("%Y-%m-%d_%H%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(stem, fmt)
            return dt.replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            pass
    try:
        return path.stat().st_mtime
    except OSError:
        return 0


def conversation_kind_rank(path: Path, conversations_dir: Path) -> int:
    if path.parent == conversations_dir:
        return 0
    if path.parent.name == "dm":
        return 1
    if path.parent.name == "group":
        return 2
    return 3


def safe_conversation_path(conversations_dir: Path, file_id: str) -> Path:
    return safe_child_path(
        conversations_dir,
        file_id,
        not_found="Session not found",
        allow_subdirs=True,
        suffix=".jsonl",
    )


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []


def _preview_from_lines(lines: list[str]) -> str:
    for line in lines:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            text = msg["content"].strip()
            if text:
                return text[:80]
    return ""


def _timestamp_sort_key(row: dict, idx: int = 0) -> tuple[float, int]:
    timestamp = row.get("timestamp") or ""
    try:
        ts = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).timestamp()
    except ValueError:
        ts = 0
    return (ts, idx)


def list_conversation_sessions(conversations_dir: Path) -> list[dict]:
    sessions = []
    seen_hashes = set()
    files = sorted(
        conversation_files(conversations_dir),
        key=lambda p: (
            conversation_date_key(p),
            -conversation_kind_rank(p, conversations_dir),
            conversation_file_id(p, conversations_dir),
        ),
        reverse=True,
    )
    for file_path in files:
        lines = [line for line in _read_lines(file_path) if line.strip()]
        if not lines:
            continue
        content_hash = hashlib.md5("\n".join(lines).encode("utf-8", "ignore")).hexdigest()
        if content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)
        file_id = conversation_file_id(file_path, conversations_dir)
        date_part = file_path.stem.replace("_session", "").replace("_dm", "").replace("_group", "")
        kind = file_path.parent.name if file_path.parent != conversations_dir else "main"
        sessions.append(
            {
                "file": file_id,
                "date": date_part,
                "kind": kind,
                "messages": len(lines),
                "preview": _preview_from_lines(lines),
                "title": "",
            }
        )
    return sessions


def read_conversation_messages(conversations_dir: Path, file_id: str) -> list[dict]:
    path = safe_conversation_path(conversations_dir, file_id)
    messages = []
    for idx, line in enumerate(_read_lines(path)):
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        msg["_order"] = idx
        messages.append(msg)
    messages = sorted(messages, key=lambda msg: (_timestamp_sort_key(msg, msg["_order"]), msg["_order"]))
    for msg in messages:
        msg.pop("_order", None)
    return messages


DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CHANNEL_TAG_RE = re.compile(r"<channel\s([^>]*)>(.*?)</channel>", re.S)
GROUP_SENDER_RE = re.compile(r"\[([^\]\n:]{1,32})\]\s*(.*)", re.S)


def session_day(path: Path) -> str:
    """Calendar day encoded in an archive filename, or '' when absent."""
    stem = path.stem.replace("_session", "").replace("_dm", "").replace("_group", "")
    day = stem[:10]
    return day if DAY_RE.match(day) else ""


def _parse_rows(path: Path) -> list[dict]:
    rows = []
    for line in _read_lines(path):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("role") in {"user", "assistant"} and row.get("content"):
            rows.append(row)
    return rows


def _tag_attr(attrs: str, name: str) -> str:
    found = re.search(rf'{name}="([^"]*)"', attrs)
    return found.group(1) if found else ""


def normalize_history_row(
    row: dict,
    kind: str,
    *,
    main_user_id: str = "",
    sender_placeholders: frozenset[str] = frozenset(),
) -> dict:
    """Resolve channel senders so other people's messages don't render as the main user.

    Handles both raw ``<channel ...>`` tags (main-session archives) and the
    ``[sender] text`` prefix convention for archived group rows. Rows from
    senders other than ``main_user_id`` get ``role="channel"`` plus a
    ``sender`` field. ``sender_placeholders`` lists bracket prefixes that are
    media placeholders rather than sender names.
    """
    if row.get("role") != "user":
        return row
    content = row.get("content", "")
    channel = row.get("channel", row.get("telegram", ""))
    if "<channel" in content:
        first = CHANNEL_TAG_RE.search(content)
        if first:
            chat_id = _tag_attr(first.group(1), "chat_id")
            if _tag_attr(first.group(1), "source") != "web" and chat_id:
                channel = "group" if chat_id.startswith("-") else "dm"
                row["channel"] = channel

            def _untag(found: re.Match) -> str:
                attrs = found.group(1)
                inner = html.unescape(found.group(2).strip())
                user = _tag_attr(attrs, "user")
                user_id = _tag_attr(attrs, "user_id") or user
                if user and user_id != main_user_id and _tag_attr(attrs, "chat_id").startswith("-"):
                    return f"[{user}] {inner}"
                return inner

            content = CHANNEL_TAG_RE.sub(_untag, content).strip()
            row["content"] = content
    if channel == "group" or kind == "group":
        found = GROUP_SENDER_RE.match(content)
        if found and found.group(1) not in sender_placeholders:
            row["role"] = "channel"
            row["sender"] = found.group(1)
            row["content"] = found.group(2).strip()
    return row


def list_conversation_days(conversations_dir: Path) -> list[dict]:
    """Archive summary grouped by calendar day, newest first."""
    days: dict[str, dict] = {}
    for path in conversation_files(conversations_dir):
        day = session_day(path)
        if not day:
            continue
        lines = [line for line in _read_lines(path) if line.strip()]
        if not lines:
            continue
        entry = days.setdefault(day, {"date": day, "sessions": 0, "messages": 0})
        entry["sessions"] += 1
        entry["messages"] += len(lines)
    return [days[day] for day in sorted(days, reverse=True)]


def read_conversation_day(
    conversations_dir: Path,
    date: str,
    *,
    main_user_id: str = "",
    sender_placeholders: frozenset[str] = frozenset(),
) -> list[dict]:
    """All messages archived for one calendar day, merged across sessions."""
    if not DAY_RE.match(date or ""):
        raise HTTPException(404, "Bad date")
    files = sorted(
        (p for p in conversation_files(conversations_dir) if session_day(p) == date),
        key=lambda p: (conversation_date_key(p), conversation_file_id(p, conversations_dir)),
    )
    merged = []
    seen = set()
    for path in files:
        kind = path.parent.name if path.parent != conversations_dir else "main"
        for row in _parse_rows(path):
            key = hashlib.sha256(
                f"{row.get('role', '')}\0{row.get('timestamp', '')}\0{row.get('content', '')}".encode("utf-8", "ignore")
            ).hexdigest()[:24]
            if key in seen:
                continue
            seen.add(key)
            row["kind"] = kind
            merged.append(
                normalize_history_row(
                    row, kind, main_user_id=main_user_id, sender_placeholders=sender_placeholders
                )
            )
    return [
        row
        for _, row in sorted(
            enumerate(merged),
            key=lambda pair: (_timestamp_sort_key(pair[1], pair[0]), pair[0]),
        )
    ]


def search_conversations(
    conversations_dir: Path,
    query: str,
    limit: int = 120,
    *,
    main_user_id: str = "",
    sender_placeholders: frozenset[str] = frozenset(),
) -> list[dict]:
    """Case-insensitive substring search across all archived sessions, newest first."""
    q = (query or "").strip().lower()
    if not q:
        return []
    files = sorted(
        conversation_files(conversations_dir),
        key=lambda p: (
            conversation_date_key(p),
            -conversation_kind_rank(p, conversations_dir),
            conversation_file_id(p, conversations_dir),
        ),
        reverse=True,
    )
    results = []
    seen = set()
    for path in files:
        day = session_day(path)
        kind = path.parent.name if path.parent != conversations_dir else "main"
        for row in _parse_rows(path):
            row = normalize_history_row(
                row, kind, main_user_id=main_user_id, sender_placeholders=sender_placeholders
            )
            content = row.get("content", "")
            pos = content.lower().find(q)
            if pos == -1:
                continue
            key = hashlib.sha256(
                f"{row.get('role', '')}\0{row.get('timestamp', '')}\0{content}".encode("utf-8", "ignore")
            ).hexdigest()[:24]
            if key in seen:
                continue
            seen.add(key)
            start = max(0, pos - 40)
            snippet = content[start : pos + len(q) + 80]
            if start > 0:
                snippet = "…" + snippet
            if pos + len(q) + 80 < len(content):
                snippet = snippet + "…"
            results.append(
                {
                    "file": conversation_file_id(path, conversations_dir),
                    "date": day,
                    "kind": kind,
                    "role": row.get("role", ""),
                    "sender": row.get("sender", ""),
                    "timestamp": row.get("timestamp", ""),
                    "snippet": snippet,
                }
            )
            if len(results) >= limit:
                return results
    return results

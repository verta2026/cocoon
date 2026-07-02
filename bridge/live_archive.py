from __future__ import annotations

"""Mirror a Claude Code session transcript into a chat-friendly live archive.

This is the provider side of the optional ``/messages`` route: it turns the
session jsonl that Claude Code writes (plus an optional sidecar of externally
sent replies, e.g. recorded by a messaging plugin) into ordered chat rows with
stable keys, so the chat UI can render incrementally instead of re-parsing
terminal output.

Everything deployment-specific — noise filters, voice-marker formats, sidecar
paths, sender identities — is injected by the deployment. The defaults are
generic and safe for a fresh install.
"""

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

VOICE_MARKER_RE = re.compile(r"\[\[(?:cocoon_)?voice:([a-f0-9]{8,64})\]\]")
VOICE_MARKER_OUT = "[[voice:{id}]]"
SEND_SOURCE = "external-send"
SEND_DEDUP_WINDOW_SECONDS = 300

_COMMAND_TAG_MARKERS = (
    "<local-command-caveat>",
    "<command-name>",
    "<command-message>",
    "<command-args>",
    "<local-command-stdout>",
    "<local-command-stderr>",
)


def default_reply_tool_match(name: str) -> bool:
    """Match MCP channel-reply tools whose input text mirrors an outgoing send."""
    return bool(name) and name.endswith("__reply")


def default_transcript_noise(role: str, text: str) -> bool:
    """Baseline filter for rows that are transport plumbing, not conversation."""
    if not (text or "").strip():
        return True
    if any(marker in text for marker in _COMMAND_TAG_MARKERS):
        return True
    if "This session is being continued from a previous conversation" in text:
        return True
    if "Continue the conversation from where it left off" in text:
        return True
    return False


def archive_parts_from_message(
    role,
    content,
    *,
    voice_marker_re: re.Pattern = VOICE_MARKER_RE,
    voice_marker_out: str = VOICE_MARKER_OUT,
    reply_tool_match: Callable[[str], bool] = default_reply_tool_match,
    send_source: str = SEND_SOURCE,
):
    """Split one transcript message into displayable parts.

    Text blocks become plain parts. Voice markers found in tool results become
    standalone voice parts. Channel-reply tool calls become send parts so the
    chat mirror shows what was sent to an external channel.
    """
    if isinstance(content, str):
        text = content.strip()
        return [{"content": text, "channel": ""}] if text else []
    if not isinstance(content, list):
        return []
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = block.get("text", "").strip()
            if text:
                parts.append({"content": text, "channel": ""})
        elif block.get("type") == "tool_result":
            raw = block.get("content", "")
            if isinstance(raw, list):
                raw = "\n".join(
                    item.get("text", "")
                    for item in raw
                    if isinstance(item, dict) and item.get("type") == "text"
                )
            if isinstance(raw, str):
                for match in voice_marker_re.finditer(raw):
                    parts.append({
                        "content": voice_marker_out.format(id=match.group(1)),
                        "channel": "",
                        "source": "voice",
                    })
        elif role == "assistant" and block.get("type") == "tool_use":
            name = block.get("name", "")
            input_data = block.get("input") if isinstance(block.get("input"), dict) else {}
            if reply_tool_match(name) and isinstance(input_data.get("text"), str):
                text = input_data.get("text", "").strip()
                chat_id = str(input_data.get("chat_id", ""))
                channel = ("group" if chat_id.startswith("-") else "dm") if chat_id else ""
                if text:
                    parts.append({"content": text, "channel": channel, "source": send_source})
    return parts


def archive_key(row) -> str:
    raw = f"{row.get('role', '')}\0{row.get('timestamp', '')}\0{row.get('content', '')}"
    return hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()[:24]


def timestamp_epoch(row) -> float:
    try:
        stamp = (row.get("timestamp") or "").replace("Z", "+00:00")
        return datetime.fromisoformat(stamp).timestamp()
    except Exception:
        return 0.0


def timestamp_sort_key(row, idx: int = 0):
    return (timestamp_epoch(row), idx)


def read_live_archive_rows(live_archive_file: Path):
    if not live_archive_file.exists():
        return []
    try:
        lines = live_archive_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    rows = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("role") in {"user", "assistant"} and row.get("content"):
            rows.append(row)
    return rows


def archive_rows_from_claude_jsonl(
    path: Path,
    *,
    is_noise: Callable[[str, str], bool] = default_transcript_noise,
    voice_marker_re: re.Pattern = VOICE_MARKER_RE,
    voice_marker_out: str = VOICE_MARKER_OUT,
    reply_tool_match: Callable[[str], bool] = default_reply_tool_match,
    send_source: str = SEND_SOURCE,
):
    rows = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("type") not in {"user", "assistant"}:
            continue
        msg = obj.get("message") or {}
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or obj.get("type")
        if role not in {"user", "assistant"}:
            continue
        parts = archive_parts_from_message(
            role,
            msg.get("content"),
            voice_marker_re=voice_marker_re,
            voice_marker_out=voice_marker_out,
            reply_tool_match=reply_tool_match,
            send_source=send_source,
        )
        if not parts:
            continue
        part_count = len(parts)
        for part_idx, part in enumerate(parts):
            content = part.get("content", "")
            if not content or is_noise(role, content):
                continue
            if obj.get("isMeta") is True and "<channel " not in content:
                continue
            row = {
                "role": "assistant" if part.get("source") == "voice" else role,
                "content": content,
                "timestamp": obj.get("timestamp", ""),
                "source": part.get("source") or "claude-code-jsonl",
            }
            if part.get("channel"):
                row["channel"] = part["channel"]
            if obj.get("sessionId"):
                row["session_id"] = obj.get("sessionId")
            if obj.get("uuid"):
                row["uuid"] = obj.get("uuid") if part_count == 1 else f"{obj.get('uuid')}:{part_idx}"
            rows.append(row)
    return rows


def read_send_sidecar_rows(sidecar_file: Path | None, *, send_source: str = SEND_SOURCE):
    """Read rows a plugin recorded for sends that bypass the transcript."""
    if sidecar_file is None or not sidecar_file.exists():
        return []
    try:
        lines = sidecar_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    rows = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("role") == "assistant" and row.get("content") and row.get("source") == send_source:
            rows.append(row)
    return rows


def dedup_external_send_rows(
    rows,
    *,
    window_seconds: int = SEND_DEDUP_WINDOW_SECONDS,
    send_source: str = SEND_SOURCE,
):
    """Collapse the same outgoing reply recorded by two writers.

    A channel reply can be recorded twice: a plugin sidecar stamps it at send
    time, the session jsonl tool_use block at message time. The timestamps
    differ by a few seconds, so exact-key dedup misses the pair. Rows must be
    sorted by timestamp before calling.
    """
    deduped = []
    last = {}
    for row in rows:
        if row.get("source") == send_source:
            key = (row.get("role"), (row.get("content") or "").strip())
            ts = timestamp_epoch(row)
            prev = last.get(key)
            if prev is not None and abs(ts - prev[0]) <= window_seconds:
                kept = deduped[prev[1]]
                for field in ("channel", "chat_id", "message_ids", "uuid", "session_id"):
                    if row.get(field) and not kept.get(field):
                        kept[field] = row[field]
                last[key] = (ts, prev[1])
                continue
            last[key] = (ts, len(deduped))
        deduped.append(row)
    return deduped


def sync_live_archive(
    live_archive_file: Path,
    state: dict,
    sync_interval_seconds: int,
    current_jsonl_path: Callable[[], Path | None],
    *,
    sidecar_file: Path | None = None,
    force: bool = False,
    is_noise: Callable[[str, str], bool] = default_transcript_noise,
    voice_marker_re: re.Pattern = VOICE_MARKER_RE,
    voice_marker_out: str = VOICE_MARKER_OUT,
    reply_tool_match: Callable[[str], bool] = default_reply_tool_match,
    send_source: str = SEND_SOURCE,
    dedup_window_seconds: int = SEND_DEDUP_WINDOW_SECONDS,
):
    """Merge the current session jsonl (and send sidecar) into the archive.

    ``state`` is a mutable dict carrying {"path", "mtime", "checked"} between
    calls so unchanged sources are skipped cheaply.
    """
    now = time.time()
    if not force and now - state.get("checked", 0.0) < sync_interval_seconds:
        return {"updated": False, "reason": "throttled"}
    path = current_jsonl_path()
    if not path or not path.exists():
        return {"updated": False, "reason": "no-source"}
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {"updated": False, "reason": "stat-failed"}

    try:
        sidecar_mtime = sidecar_file.stat().st_mtime if sidecar_file and sidecar_file.exists() else 0.0
    except OSError:
        sidecar_mtime = 0.0
    combined_mtime = max(mtime, sidecar_mtime)

    state["checked"] = now
    archive_exists = live_archive_file.exists()
    if not force and archive_exists and state.get("path") == str(path) and state.get("mtime") == combined_mtime:
        return {"updated": False, "reason": "unchanged"}
    incoming = archive_rows_from_claude_jsonl(
        path,
        is_noise=is_noise,
        voice_marker_re=voice_marker_re,
        voice_marker_out=voice_marker_out,
        reply_tool_match=reply_tool_match,
        send_source=send_source,
    )
    sidecar_rows = read_send_sidecar_rows(sidecar_file, send_source=send_source)
    if not incoming and not sidecar_rows:
        state.update({"path": str(path), "mtime": combined_mtime})
        return {"updated": False, "reason": "empty-source", "path": str(path)}

    current_sid = path.stem
    existing = [
        row for row in read_live_archive_rows(live_archive_file)
        if row.get("session_id") != current_sid
        and not is_noise(row.get("role", ""), row.get("content", ""))
    ]
    merged = []
    seen = set()
    for row in existing + incoming + sidecar_rows:
        key = archive_key(row)
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    merged = [row for _, row in sorted(enumerate(merged), key=lambda p: timestamp_sort_key(p[1], p[0]))]
    merged = dedup_external_send_rows(
        merged, window_seconds=dedup_window_seconds, send_source=send_source
    )
    live_archive_file.parent.mkdir(parents=True, exist_ok=True)
    with live_archive_file.open("w", encoding="utf-8") as f:
        for row in merged:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    state.update({"path": str(path), "mtime": combined_mtime})
    return {"updated": True, "messages": len(merged), "path": str(path)}


def parse_channel_message(text):
    """Parse an inbound ``<channel ...>`` tag injected by a messaging plugin."""
    found = re.search(r"<channel\s([^>]*)>(.*?)</channel>", text or "", flags=re.S)
    if not found:
        return None
    attrs = found.group(1)
    import html as _html

    meta = {"content": _html.unescape(found.group(2).strip())}
    for key in ("source", "chat_id", "message_id", "user", "user_id", "ts"):
        m = re.search(rf'{key}="([^"]*)"', attrs)
        if m:
            meta[key] = m.group(1)
    chat_id = str(meta.get("chat_id", ""))
    if meta.get("source") == "web":
        meta["channel"] = ""
    else:
        meta["channel"] = "group" if chat_id.startswith("-") else "dm"
    return meta


def live_messages(
    rows,
    limit: int,
    *,
    primary_sender_id: str = "",
    is_noise: Callable[[str, str], bool] = default_transcript_noise,
):
    """Shape archive rows into the /messages payload the chat UI renders.

    Inbound channel tags become role "user" when they come from the primary
    sender (or the web UI), and role "channel" for everyone else so group
    traffic renders as third-party bubbles.
    """
    rows = [row for _, row in sorted(enumerate(rows), key=lambda p: timestamp_sort_key(p[1], p[0]))]
    messages = []
    for row in rows[-limit:]:
        role = row.get("role", "")
        content = row.get("content", "")
        if role not in {"user", "assistant"} or not content:
            continue
        if is_noise(role, content):
            continue
        item = {
            "id": row.get("uuid") or archive_key(row),
            "role": role,
            "content": content,
            "timestamp": row.get("timestamp", ""),
            "channel": row.get("channel", ""),
            "sender": "",
        }
        channel = parse_channel_message(content)
        if channel:
            source = channel.get("source", "")
            sender_id = channel.get("user_id") or channel.get("user") or channel.get("chat_id") or ""
            item["content"] = channel.get("content", "")
            item["source"] = source
            item["sender"] = sender_id
            item["channel"] = channel.get("channel", "")
            if source == "web":
                item["role"] = "user"
                item["sender"] = "web"
            elif sender_id and primary_sender_id and sender_id != primary_sender_id:
                item["role"] = "channel"
            else:
                item["role"] = "user"
        if not (item["content"] or "").strip():
            continue
        messages.append(item)
    return messages

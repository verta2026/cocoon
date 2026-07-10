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
RECV_SOURCE = "external-recv"
TRANSCRIPT_SOURCE = "claude-code-jsonl"
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


# Short cap for line-anchored marker matching. Real ping/echo rows carrying a
# bare marker are single short lines; genuine messages are longer or multi-line.
BARE_MARKER_MAX_LEN = 200


def bare_marker_noise(text: str, markers, max_len: int = BARE_MARKER_MAX_LEN) -> bool:
    """True only when a bare token marker *is* the message, not merely quoted in it.

    Deployments inject their own plumbing markers (verification pings, resume
    tokens, launcher paths). The naive ``any(m in text for m in markers)`` is a
    footgun: a real chat message that happens to *mention* the marker string —
    e.g. a report explaining "I replaced the ``FOO_VERIFY_`` token" — gets eaten
    whole. Anchor the match to the first line and cap the length instead, so the
    filter only fires on the plumbing rows it was meant for.
    """
    if not markers:
        return False
    if len(text) > max_len:
        return False
    first_line = text.lstrip().split("\n", 1)[0]
    return any(marker in first_line for marker in markers)


# Assistant heartbeat rows ("Group quiet — no need to reply.") are short. A
# mid-line status *phrase* is often natural language, so match it only on very
# short rows to keep a real sentence that merely uses those words alive.
STATUS_MARKER_MAX_LEN = 80


def make_transcript_noise(
    *,
    bare_markers=(),
    status_prefixes=(),
    status_markers=(),
    max_len: int = BARE_MARKER_MAX_LEN,
    status_max_len: int = STATUS_MARKER_MAX_LEN,
    base=default_transcript_noise,
) -> Callable[[str, str], bool]:
    """Build a deployment noise filter without hand-rolling the substring footgun.

    ``bare_markers`` are distinctive plumbing tokens matched via
    :func:`bare_marker_noise` (line-anchored + length-capped). ``status_prefixes``
    are assistant heartbeat lines matched by first-line ``startswith`` (safe: real
    messages rarely open with "Replied"). ``status_markers`` are mid-line
    heartbeat phrases — often natural language, so they only fire on rows no
    longer than ``status_max_len``, letting a real sentence that reuses the same
    words survive. ``base`` runs first for the always-safe tag/continuation checks.
    """
    def _is_noise(role: str, text: str) -> bool:
        text = text or ""
        if base(role, text):
            return True
        if bare_marker_noise(text, bare_markers, max_len):
            return True
        if role == "assistant":
            first_line = text.lstrip().split("\n", 1)[0]
            if len(text) <= max_len and any(first_line.startswith(p) for p in status_prefixes):
                return True
            if len(text) <= status_max_len and any(m in first_line for m in status_markers):
                return True
        return False

    return _is_noise


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


def read_recv_sidecar_rows(sidecar_file: Path | None, *, recv_source: str = RECV_SOURCE):
    """Read rows a plugin recorded for inbound messages that may miss the transcript.

    Inbound channel messages normally land in the session jsonl as ``<channel>``
    tags, but they can be dropped around thinking blocks or session-reload seams.
    A receive sidecar written at delivery time is the trusted fallback record.
    """
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
        if row.get("role") == "user" and row.get("content") and row.get("source") == recv_source:
            rows.append(row)
    return rows


def dedup_cross_source_rows(
    rows,
    *,
    window_seconds: int = SEND_DEDUP_WINDOW_SECONDS,
    recv_source: str = RECV_SOURCE,
    transcript_source: str = TRANSCRIPT_SOURCE,
    send_source: str = SEND_SOURCE,
):
    """Collapse duplicate records of one message across recording sources.

    Outgoing: the same assistant reply can exist as a send-sidecar row (stamped
    at send time) and as the transcript echo (stamped at turn boundary); exact
    timestamps differ, so pairs are matched by content within ``window_seconds``
    and the sidecar row (which carries channel metadata) is kept.

    Inbound: a receive-sidecar row and the transcript ``<channel>`` row record
    the same message. The channel row wins when present (the display layer
    renders it); the sidecar row only fills the gap when the transcript missed
    the message. Matching prefers exact (chat_id, message_id) pairs and falls
    back to content within ``window_seconds`` for rows without a message_id.

    Rows must be sorted by timestamp before calling.
    """
    reply_ts = {}
    chan_ids = set()
    chan_content_ts = {}
    for row in rows:
        content = (row.get("content") or "").strip()
        if row.get("source") == send_source and row.get("role") == "assistant":
            reply_ts.setdefault(content, []).append(timestamp_epoch(row))
        elif row.get("role") == "user" and "<channel " in content:
            meta = parse_channel_message(content)
            if not meta or meta.get("source") == "web":
                continue
            if meta.get("chat_id") and meta.get("message_id"):
                chan_ids.add((str(meta["chat_id"]), str(meta["message_id"])))
            # Bucket the content-window fallback by chat_id: two chats can send the
            # same short text ("OK") seconds apart, and a chat-agnostic content key
            # would drop the second chat's message as a phantom duplicate.
            chan_content_ts.setdefault(
                (str(meta.get("chat_id", "")), meta.get("content", "")), []
            ).append(timestamp_epoch(row))
    out = []
    for row in rows:
        content = (row.get("content") or "").strip()
        src = row.get("source") or ""
        if src == transcript_source and row.get("role") == "assistant":
            ts = timestamp_epoch(row)
            if any(abs(ts - t) <= window_seconds for t in reply_ts.get(content, ())):
                continue
        elif src == recv_source:
            cid = str(row.get("chat_id") or "")
            mid = str(row.get("message_id") or "")
            if cid and mid and (cid, mid) in chan_ids:
                continue
            ts = timestamp_epoch(row)
            if any(
                abs(ts - t) <= window_seconds
                for t in chan_content_ts.get((cid, content), ())
            ):
                continue
        out.append(row)
    return out


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
    recv_sidecar_file: Path | None = None,
    force: bool = False,
    is_noise: Callable[[str, str], bool] = default_transcript_noise,
    voice_marker_re: re.Pattern = VOICE_MARKER_RE,
    voice_marker_out: str = VOICE_MARKER_OUT,
    reply_tool_match: Callable[[str], bool] = default_reply_tool_match,
    send_source: str = SEND_SOURCE,
    recv_source: str = RECV_SOURCE,
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
    try:
        recv_mtime = recv_sidecar_file.stat().st_mtime if recv_sidecar_file and recv_sidecar_file.exists() else 0.0
    except OSError:
        recv_mtime = 0.0
    combined_mtime = max(mtime, sidecar_mtime, recv_mtime)

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
    recv_rows = read_recv_sidecar_rows(recv_sidecar_file, recv_source=recv_source)
    if not incoming and not sidecar_rows and not recv_rows:
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
    for row in existing + incoming + sidecar_rows + recv_rows:
        key = archive_key(row)
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    merged = [row for _, row in sorted(enumerate(merged), key=lambda p: timestamp_sort_key(p[1], p[0]))]
    merged = dedup_external_send_rows(
        merged, window_seconds=dedup_window_seconds, send_source=send_source
    )
    merged = dedup_cross_source_rows(
        merged,
        window_seconds=dedup_window_seconds,
        recv_source=recv_source,
        send_source=send_source,
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


def _normalize_chat_row(row, *, primary_sender_id: str, is_noise, recv_source: str):
    """Archive row -> display item, or None for noise/plumbing rows."""
    role = row.get("role", "")
    content = row.get("content", "")
    if role not in {"user", "assistant"} or not content:
        return None
    if is_noise(role, content):
        return None
    item = {
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
    elif row.get("source") == recv_source:
        sender_id = str(row.get("user_id") or row.get("user") or "")
        item["sender"] = sender_id
        if sender_id and primary_sender_id and sender_id != primary_sender_id:
            item["role"] = "channel"
    if not (item["content"] or "").strip():
        return None
    return item


def pure_chat_messages(
    rows,
    since: str = "",
    *,
    primary_sender_id: str = "",
    is_noise: Callable[[str, str], bool] = default_transcript_noise,
    voice_marker_re: re.Pattern = VOICE_MARKER_RE,
    recv_source: str = RECV_SOURCE,
):
    """Incremental natural-language chat stream for structured chat UIs.

    Ids are stable and time-monotonic (fixed-width millisecond epoch prefix +
    content fingerprint suffix), so a client keeps its local max id and pulls
    increments with ``since=<max id>`` using plain string comparison.

    Rows carrying the same timestamp/role/content are collapsed; when a
    duplicate pair has one row with a named (non-numeric) sender, that name
    wins so external-channel senders display by name rather than id.
    """
    rows = [row for _, row in sorted(enumerate(rows), key=lambda p: timestamp_sort_key(p[1], p[0]))]
    out = []
    seen_dedup = {}
    for row in rows:
        item = _normalize_chat_row(
            row, primary_sender_id=primary_sender_id, is_noise=is_noise, recv_source=recv_source
        )
        if item is None:
            continue
        text = voice_marker_re.sub("", item["content"]).strip()
        if not text:
            continue
        epoch_ms = int(timestamp_epoch(row) * 1000)
        fingerprint = archive_key(row)[:8]
        # Per-message identity keeps distinct external messages apart even when
        # their text, second and role coincide (two chats both say "OK"). A row
        # without an identity (assistant text, a transcript echo, a recv row that
        # only carries a name) is treated as a twin of any row in the same content
        # bucket, so genuine cross-source duplicates still collapse and the named
        # sender still wins. Two rows are kept apart only when both carry an
        # identity and the identities differ.
        cid = str(row.get("chat_id") or "")
        mid = str(row.get("message_id") or "")
        if not (cid or mid) and "<channel " in (row.get("content") or ""):
            meta = parse_channel_message(row.get("content") or "") or {}
            cid = str(meta.get("chat_id") or "")
            mid = str(meta.get("message_id") or "")
        identity = f"{cid}\x1f{mid}" if (cid or mid) else ""
        content_key = f"{epoch_ms}|{item['role']}|{text[:80]}"
        sender = item.get("sender", "")
        sender_is_name = bool(sender) and not sender.isdigit()
        twin = None
        for candidate in seen_dedup.get(content_key, ()):
            cand_id = candidate["_identity"]
            if not cand_id or not identity or cand_id == identity:
                twin = candidate
                break
        if twin is not None:
            if sender_is_name and not twin.get("_named"):
                twin["sender"] = sender
                twin["_named"] = True
            if identity and not twin["_identity"]:
                twin["_identity"] = identity
            continue
        entry = {
            "id": f"{epoch_ms:015d}-{fingerprint}",
            "role": item["role"],
            "content": text,
            "ts": item["timestamp"],
            "channel": item.get("channel", ""),
            "sender": sender,
            "_named": sender_is_name,
            "_identity": identity,
        }
        seen_dedup.setdefault(content_key, []).append(entry)
        if entry["id"] > (since or ""):
            out.append(entry)
    for entry in out:
        entry.pop("_named", None)
        entry.pop("_identity", None)
    return out

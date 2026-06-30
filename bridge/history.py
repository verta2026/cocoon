"""Read-only JSONL conversation history helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException


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
    rel = Path(file_id or "")
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(404, "Session not found")
    path = (conversations_dir / rel).resolve()
    root = conversations_dir.resolve()
    if not path.is_relative_to(root) or not path.exists() or path.suffix != ".jsonl":
        raise HTTPException(404, "Session not found")
    return path


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

"""Generic Claude jsonl session file discovery helpers."""

from __future__ import annotations

import json
from pathlib import Path


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


def iter_project_jsonl(project_dir: Path) -> list[Path]:
    return [path for path in project_dir.glob("*.jsonl")]


def latest_jsonl(project_dir: Path) -> Path:
    files = iter_project_jsonl(project_dir)
    if not files:
        raise ValueError(f"no jsonl files under {project_dir}")
    return max(files, key=session_sort_key)


def session_last_timestamp(path: Path) -> str:
    last = ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                timestamp = event.get("timestamp") or event.get("created_at") or ""
                if timestamp:
                    last = timestamp
    except OSError:
        return ""
    return last


def session_sort_key(path: Path) -> tuple[str, float]:
    return (session_last_timestamp(path), path.stat().st_mtime)

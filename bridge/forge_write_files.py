"""Generic forge output write helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


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


def write_json_atomic(path: Path, payload: dict[str, Any], *, indent: int = 2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)
    return path


def build_summary_meta_payload(
    *,
    source: str,
    new_session_id: str,
    summary_text: str,
    summary_info: dict[str, Any],
    updated_at: str,
    summary_hash: str,
) -> dict[str, Any]:
    return {
        "updated_at": updated_at,
        "source": str(source),
        "new_sid": new_session_id,
        "dropped_events": summary_info["dropped_events"],
        "dropped_chars": summary_info["dropped_chars"],
        "dropped_hash": summary_info["dropped_hash"],
        "previous_hash": summary_info.get("previous_hash", ""),
        "summary_hash": summary_hash,
        "summary_chars": len(summary_text),
        "status": summary_info["status"],
        "provider": summary_info["provider"],
        "prompt_file": summary_info["prompt_file"],
    }


def build_manifest_payload(summary: dict[str, Any], *, created_at: str) -> dict[str, Any]:
    return {**summary, "created_at": created_at}

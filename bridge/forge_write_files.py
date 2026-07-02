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
    return write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=indent) + "\n")


def write_text_atomic(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
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


def execute_forge_write(
    *,
    project_dir: Path,
    manifest_dir: Path,
    replay_file: Path,
    summary_file: Path,
    summary_meta: Path,
    new_sid: str,
    forged: list[dict],
    replay: dict | None,
    summary: dict[str, Any],
    forge_summary: str,
    summary_info: dict[str, Any],
    source: str | Path,
    summary_updated_at: str,
    manifest_created_at: str,
    summary_hash: str,
) -> dict[str, Any]:
    updated_summary = dict(summary)
    dest = project_dir / f"{new_sid}.jsonl"
    write_jsonl_atomic(dest, forged)

    if replay:
        replay_payload = dict(replay)
        replay_payload["new_sid"] = new_sid
        write_json_atomic(replay_file, replay_payload)
        updated_summary["replay_file"] = str(replay_file)

    if summary_info.get("write_summary") and forge_summary.strip():
        write_text_atomic(summary_file, forge_summary.strip() + "\n")
        write_json_atomic(
            summary_meta,
            build_summary_meta_payload(
                source=str(source),
                new_session_id=new_sid,
                summary_text=forge_summary,
                summary_info=summary_info,
                updated_at=summary_updated_at,
                summary_hash=summary_hash,
            ),
        )
        summary_snapshot = manifest_dir / f"{new_sid}.summary.md"
        write_text_atomic(summary_snapshot, forge_summary.strip() + "\n")
        updated_summary["summary_snapshot"] = str(summary_snapshot)

    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / f"{new_sid}.manifest.json"
    updated_summary["dest"] = str(dest)
    updated_summary["manifest"] = str(manifest)
    updated_summary["written"] = True
    write_json_atomic(manifest, build_manifest_payload(updated_summary, created_at=manifest_created_at))
    return updated_summary

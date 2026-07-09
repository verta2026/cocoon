"""Generic forge summary state helpers."""

from __future__ import annotations

from pathlib import Path


def build_summary_info(
    *,
    skip_summary: bool,
    summary_file: str | Path,
    summary_meta: str | Path,
    summary_provider: str,
    summary_prompt_file: str | Path | None,
    previous_summary: str,
    dropped_text: str,
    dropped_hash: str,
) -> dict:
    return {
        "status": "disabled" if skip_summary else "pending",
        "file": str(summary_file),
        "meta": str(summary_meta),
        "dropped_events": None,
        "dropped_chars": len(dropped_text),
        "previous_chars": len(previous_summary),
        "summary_chars": len(previous_summary),
        "write_summary": False,
        "dropped_hash": dropped_hash[:24],
        "provider": summary_provider,
        "prompt_file": str(summary_prompt_file or ""),
    }


def apply_summary_skip_status(
    info: dict,
    skip_summary: bool,
    write_enabled: bool,
    dropped_text: str,
    previous_summary: str,
) -> bool:
    if skip_summary:
        info["status"] = "disabled"
        return True
    if not write_enabled:
        info["status"] = "dry-run-skipped"
        return True
    if not dropped_text:
        info["status"] = "previous-only" if previous_summary else "skipped-no-dropped"
        return True
    return False


def summary_cache_matches(meta: dict, source: str | Path, dropped_hash: str, previous_hash: str) -> bool:
    return (
        meta.get("source") == str(source)
        and meta.get("dropped_hash") == dropped_hash
        and meta.get("previous_hash") == previous_hash
    )


def apply_provider_result(
    info: dict,
    previous_summary: str,
    previous_hash: str,
    new_summary: str,
    status: str,
) -> str:
    if new_summary:
        info.update(
            {
                "status": status,
                "summary_chars": len(new_summary),
                "write_summary": True,
                "previous_hash": previous_hash,
            }
        )
        return new_summary
    info["status"] = f"{status}-previous-fallback" if previous_summary else status
    return previous_summary

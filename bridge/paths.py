"""Path safety helpers for files under configured roots."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException


def safe_child_path(
    root: Path,
    name: str,
    *,
    not_found: str = "File not found",
    allow_subdirs: bool = False,
    suffix: str | None = None,
) -> Path:
    rel = Path(name or "")
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(404, not_found)
    if not allow_subdirs:
        rel = Path(rel.name)
    path = (root / rel).resolve()
    resolved_root = root.resolve()
    if not path.is_relative_to(resolved_root):
        raise HTTPException(404, not_found)
    if suffix is not None and path.suffix != suffix:
        raise HTTPException(404, not_found)
    if not path.exists():
        raise HTTPException(404, not_found)
    return path

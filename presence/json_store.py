"""Presence-compatible JSON storage helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bridge.json_store import read_json as _read_json
from bridge.json_store import write_json_atomic


def read_json(path: str | Path, default: Any = None) -> Any:
    return _read_json(Path(path), default=default)


def write_json(path: str | Path, data: Any) -> None:
    write_json_atomic(Path(path), data, indent=None)

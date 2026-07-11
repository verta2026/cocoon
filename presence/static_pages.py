"""Static page helpers for optional presence-style services."""

from __future__ import annotations

from pathlib import Path


def static_page_path(route_path: str, *, page_map: dict[str, str], root_dir: Path) -> Path | None:
    filename = page_map.get(route_path)
    if not filename:
        return None
    candidate = (Path(root_dir) / filename).resolve()
    root = Path(root_dir).resolve()
    if not candidate.is_relative_to(root):
        return None
    return candidate


def read_static_page(route_path: str, *, page_map: dict[str, str], root_dir: Path) -> tuple[int, bytes, str] | None:
    page_path = static_page_path(route_path, page_map=page_map, root_dir=root_dir)
    if page_path is None:
        return None
    if not page_path.is_file():
        return 404, b'{"error": "not found"}', "application/json"
    return 200, page_path.read_bytes(), "text/html; charset=utf-8"

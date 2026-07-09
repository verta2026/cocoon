"""Message reactions and recent-image listing."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .json_store import read_json, write_json_atomic

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def load_reactions(path: Path) -> dict:
    data = read_json(path, {})
    return data if isinstance(data, dict) else {}


def toggle_reaction(data: dict, *, msg_id: str, emoji: str, sender: str) -> tuple[dict, bool]:
    """Toggle one sender's emoji on a message. Returns (data, added)."""
    entries = list(data.get(msg_id, []))
    remaining = [
        r for r in entries if not (r.get("emoji") == emoji and r.get("from") == sender)
    ]
    added = len(remaining) == len(entries)
    if added:
        remaining.append({"emoji": emoji, "from": sender})
    if remaining:
        data[msg_id] = remaining
    else:
        data.pop(msg_id, None)
    return data, added


def apply_reaction(path: Path, *, msg_id: str, emoji: str, sender: str) -> tuple[dict, bool]:
    data, added = toggle_reaction(load_reactions(path), msg_id=msg_id, emoji=emoji, sender=sender)
    write_json_atomic(path, data, indent=None)
    return data, added


def recent_image_entries(sources: Iterable[tuple[Path, str]], *, limit: int = 30) -> list[dict]:
    """List newest images across (directory, url_prefix) sources."""
    entries: list[dict] = []
    for directory, prefix in sources:
        directory = Path(directory)
        if not directory.is_dir():
            continue
        try:
            files = sorted(
                directory.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True
            )
        except OSError:
            continue
        for item in files:
            if item.suffix.lower() in IMAGE_SUFFIXES and item.is_file():
                entries.append({"src": prefix + item.name, "name": item.name})
            if len(entries) >= limit:
                break
    return entries[:limit]


def register_reaction_routes(app, *, get_reactions, post_reaction, recent_images) -> None:
    app.get("/reactions")(get_reactions)
    app.post("/reactions")(post_reaction)
    app.get("/recent-images")(recent_images)

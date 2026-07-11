"""Cloud-backed appearance choice (wallpaper/avatar selection).

The image files already live on the server (/upload → /files), but "which
one is currently chosen" used to live only in localStorage — cleared
storage or a new device lost it. These routes store the choice server-side;
the chat pages and the editor read it back on load, so the server is the
source of truth and localStorage is just a cache.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Request

from bridge.json_store import read_json, write_json_atomic

LOOK_KEYS = ("bg", "bgDark", "userAvatar", "aiAvatar")


def load_look(look_file: Path) -> dict:
    data = read_json(look_file, default={})
    if not isinstance(data, dict):
        return {}
    return {k: data[k] for k in LOOK_KEYS if isinstance(data.get(k), str) and data[k]}


def apply_look_update(current: dict, body: dict) -> dict:
    """Merge a partial update; an explicitly empty value clears the key
    (back to the built-in default)."""
    updated = dict(current)
    for k in LOOK_KEYS:
        if k not in body:
            continue
        v = body.get(k)
        if isinstance(v, str) and v:
            updated[k] = v
        else:
            updated.pop(k, None)
    return updated


def register_look_routes(app, *, verify_token, look_file: Path) -> None:
    look_file = Path(look_file)

    @app.get("/look")
    async def look_get(request: Request):
        verify_token(request)
        return {"look": load_look(look_file)}

    @app.post("/look")
    async def look_post(request: Request):
        verify_token(request)
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
        updated = apply_look_update(load_look(look_file), body)
        write_json_atomic(look_file, updated)
        return {"ok": True, "look": updated}

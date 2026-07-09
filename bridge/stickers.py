"""Named asset catalog helpers for stickers or small UI media."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

from bridge.paths import safe_child_path


def load_sticker_meta(sticker_meta: Path) -> dict:
    if sticker_meta.exists():
        return json.loads(sticker_meta.read_text(encoding="utf-8"))
    return {}


def save_sticker_meta(sticker_meta: Path, meta: dict) -> None:
    sticker_meta.parent.mkdir(parents=True, exist_ok=True)
    sticker_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def serve_sticker_file(sticker_dir: Path, name: str):
    path = safe_child_path(sticker_dir, name, not_found="Sticker not found")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})


def list_sticker_items(sticker_dir: Path, sticker_meta: Path) -> list[dict]:
    meta = load_sticker_meta(sticker_meta)
    items = []
    for file_name, info in meta.items():
        safe_name = Path(file_name).name
        if safe_name != file_name:
            continue
        if (sticker_dir / safe_name).is_file():
            items.append({"file": safe_name, "name": info.get("name", ""), "desc": info.get("desc", "")})
    return items


def upload_sticker_data(
    sticker_dir: Path,
    sticker_meta: Path,
    *,
    data_url: str,
    name: str = "",
    filename: str = "",
) -> dict:
    """Save a base64 data-URL sticker (the chat page's paste/resize upload)."""
    import base64
    import re
    import time

    match = re.match(r"data:image/(png|jpeg|webp|gif);base64,(.+)$", data_url or "", re.S)
    if not match:
        raise HTTPException(400, "Expected a base64 image data URL")
    ext = {"jpeg": "jpg"}.get(match.group(1), match.group(1))
    stem = re.sub(r"[^\w\-]", "_", Path(filename or "").stem).strip("._")
    stem = stem or f"sticker-{int(time.time())}"
    safe_name = f"{stem}.{ext}"
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except Exception:
        raise HTTPException(400, "Invalid base64 payload")
    sticker_dir.mkdir(parents=True, exist_ok=True)
    (sticker_dir / safe_name).write_bytes(raw)
    meta = load_sticker_meta(sticker_meta)
    meta[safe_name] = {"name": name or stem, "desc": ""}
    save_sticker_meta(sticker_meta, meta)
    return {"ok": True, "file": safe_name, "name": meta[safe_name]["name"]}


def upload_sticker_file(sticker_dir: Path, sticker_meta: Path, file: UploadFile, name: str = "", desc: str = ""):
    sticker_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "").name
    if not safe_name:
        raise HTTPException(400, "Missing filename")
    dest = sticker_dir / safe_name
    with open(dest, "wb") as handle:
        shutil.copyfileobj(file.file, handle)
    meta = load_sticker_meta(sticker_meta)
    meta[safe_name] = {"name": name or safe_name.rsplit(".", 1)[0], "desc": desc}
    save_sticker_meta(sticker_meta, meta)
    return {"file": safe_name, "name": meta[safe_name]["name"]}


def edit_sticker_meta(sticker_meta: Path, file_name: str, name: str = "", desc: str = ""):
    safe_name = Path(file_name or "").name
    meta = load_sticker_meta(sticker_meta)
    if safe_name not in meta:
        raise HTTPException(404, "Sticker not found")
    if name:
        meta[safe_name]["name"] = name
    if desc:
        meta[safe_name]["desc"] = desc
    save_sticker_meta(sticker_meta, meta)
    return {"ok": True}


def delete_sticker_file(sticker_dir: Path, sticker_meta: Path, file_name: str):
    safe_name = Path(file_name or "").name
    meta = load_sticker_meta(sticker_meta)
    path = sticker_dir / safe_name
    if path.is_file():
        path.unlink()
    meta.pop(safe_name, None)
    save_sticker_meta(sticker_meta, meta)
    return {"ok": True}

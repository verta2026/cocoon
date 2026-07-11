"""Named asset catalog helpers for stickers or small UI media."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

from bridge.paths import safe_child_path


def load_sticker_meta(sticker_meta: Path) -> dict:
    if sticker_meta.exists():
        return json.loads(sticker_meta.read_text(encoding="utf-8"))
    return {}


_STICKER_MARKUP = re.compile(r"\[sticker:([^\]\n]+)\]")


def annotate_stickers(text: str, sticker_meta: Path) -> str:
    """Translate [sticker:<file>] markers into name+description before the text
    reaches the agent's terminal. The agent never sees sticker images; meta.json
    is its eyes. The stored message keeps the raw marker so the frontend still
    renders the image — only the terminal-bound copy is annotated. The rewritten
    form deliberately drops the ``sticker:`` prefix so it can never be re-parsed
    as a sendable marker."""
    if "[sticker:" not in (text or ""):
        return text
    try:
        meta = load_sticker_meta(sticker_meta)
    except Exception:
        return text

    def _sub(match):
        fname = match.group(1).strip()
        info = meta.get(fname)
        if not isinstance(info, dict):
            return match.group(0)
        name = str(info.get("name") or "").strip()
        desc = str(info.get("desc") or "").strip()
        if not name and not desc:
            return match.group(0)
        label = name or fname
        return f'[sticker {fname} "{label}"' + (f": {desc}]" if desc else "]")

    return _STICKER_MARKUP.sub(_sub, text)


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
    desc: str = "",
    filename: str = "",
    max_bytes: int = 5 * 1024 * 1024,
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
    if max_bytes and len(match.group(2)) > max_bytes * 4 // 3 + 4:
        raise HTTPException(413, "Sticker too large")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except Exception:
        raise HTTPException(400, "Invalid base64 payload")
    _require_image_magic(raw[:12])
    sticker_dir.mkdir(parents=True, exist_ok=True)
    (sticker_dir / safe_name).write_bytes(raw)
    meta = load_sticker_meta(sticker_meta)
    meta[safe_name] = {"name": name or stem, "desc": desc}
    save_sticker_meta(sticker_meta, meta)
    return {"ok": True, "file": safe_name, "name": meta[safe_name]["name"]}


def _require_image_magic(head: bytes) -> None:
    # 只认真实图片字节头：png/jpeg/gif/webp。贴纸目录是静态可服务的，
    # 放任意类型进来等于开了个带鉴权的任意文件投放点
    ok = (
        head.startswith(b"\x89PNG\r\n\x1a\n")
        or head.startswith(b"\xff\xd8\xff")
        or head.startswith((b"GIF87a", b"GIF89a"))
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )
    if not ok:
        raise HTTPException(400, "Not a supported image (png/jpeg/gif/webp)")


def upload_sticker_file(sticker_dir: Path, sticker_meta: Path, file: UploadFile, name: str = "", desc: str = "", *, max_bytes: int = 5 * 1024 * 1024):
    sticker_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "").name
    if not safe_name:
        raise HTTPException(400, "Missing filename")
    head = file.file.read(12)
    _require_image_magic(head)
    dest = sticker_dir / safe_name
    written = 0
    with open(dest, "wb") as handle:
        handle.write(head)
        written = len(head)
        while True:
            chunk = file.file.read(1024 * 256)
            if not chunk:
                break
            written += len(chunk)
            if max_bytes and written > max_bytes:
                handle.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "Sticker too large")
            handle.write(chunk)
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

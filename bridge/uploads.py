"""File upload handling."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

from bridge.paths import safe_child_path


def enforce_content_length(request, limit_bytes: int) -> None:
    """带 Content-Length 的超限请求在解析 body 前直接 413。

    这不是完整防线（chunked 请求没有该头），落盘侧仍有流式上限；
    但它让"鉴权通过前"的巨大请求无法触发 multipart/base64 解析。
    """
    if not limit_bytes:
        return
    raw = request.headers.get("content-length", "")
    if raw.isdigit() and int(raw) > limit_bytes + 1024 * 1024:
        raise HTTPException(413, "Request body too large")


def _stored_filename(original_name: str) -> str:
    suffix = Path(original_name).suffix.lower()
    if len(suffix) > 16 or any(not (ch.isalnum() or ch == ".") for ch in suffix):
        suffix = ""
    return f"{uuid.uuid4().hex}{suffix}"


def save_upload_file(upload_dir: Path, file: UploadFile, max_bytes: int = 0):
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "").name
    if not safe_name:
        raise HTTPException(400, "Missing filename")
    stored_name = _stored_filename(safe_name)
    dest = upload_dir / stored_name
    total = 0
    with open(dest, "wb") as f:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if max_bytes > 0 and total > max_bytes:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "Upload too large")
            f.write(chunk)
    return {"path": str(dest), "filename": stored_name, "original_filename": safe_name}


def list_upload_files(upload_dir: Path) -> list[dict]:
    if not upload_dir.exists():
        return []
    files = []
    for path in sorted(upload_dir.iterdir(), key=lambda p: p.name):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append({"name": path.name, "size": stat.st_size, "mtime": stat.st_mtime})
    return files


def serve_upload_file(upload_dir: Path, filename: str):
    path = safe_child_path(upload_dir, filename, not_found="File not found")
    safe_name = Path(filename).name
    return FileResponse(path, filename=safe_name)

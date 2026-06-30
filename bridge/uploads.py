"""File upload handling."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse


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


def serve_upload_file(upload_dir: Path, filename: str):
    path = (upload_dir / Path(filename).name).resolve()
    if not path.is_relative_to(upload_dir.resolve()):
        raise HTTPException(403, "Forbidden")
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)

"""File upload handling."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse


def save_upload_file(upload_dir: Path, file: UploadFile):
    upload_dir.mkdir(exist_ok=True)
    safe_name = Path(file.filename).name
    dest = upload_dir / safe_name
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": str(dest), "filename": safe_name}


def serve_upload_file(upload_dir: Path, filename: str):
    path = (upload_dir / Path(filename).name).resolve()
    if not path.is_relative_to(upload_dir.resolve()):
        raise HTTPException(403, "Forbidden")
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)

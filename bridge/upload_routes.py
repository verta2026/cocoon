"""Upload and authenticated file route registration."""

from __future__ import annotations

from pathlib import Path

from fastapi import File, Request, UploadFile


def register_upload_routes(
    app,
    *,
    verify_token,
    verify_media_token,
    save_upload_file,
    serve_upload_file,
    upload_dir: Path,
    max_upload_bytes: int,
    bridge_token: str,
    list_upload_files=None,
) -> None:
    @app.post("/upload")
    async def upload_file(request: Request, file: UploadFile = File(...)):
        verify_token(request)
        return save_upload_file(upload_dir, file, max_upload_bytes)

    if list_upload_files is not None:
        @app.get("/files")
        async def list_files(request: Request):
            verify_token(request)
            return {"files": list_upload_files(upload_dir)}

    @app.get("/files/{filename}")
    async def serve_file(filename: str, request: Request, token: str = None):
        verify_media_token(request, bridge_token, token)
        return serve_upload_file(upload_dir, filename)

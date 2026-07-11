"""Upload and authenticated file route registration."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request

from bridge.uploads import enforce_content_length


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
    async def upload_file(request: Request):
        # 鉴权必须先于 body 解析：UploadFile 参数会让 FastAPI 在进函数前
        # 就把匿名 multipart 全量读完（实测匿名畸形 POST 返回 422 而非 403）
        verify_token(request)
        enforce_content_length(request, max_upload_bytes)
        form = await request.form()
        file = form.get("file")
        if file is None or isinstance(file, str):
            raise HTTPException(400, "file field required")
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

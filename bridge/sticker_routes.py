"""Sticker or named asset route registration."""

from __future__ import annotations

from fastapi import HTTPException, Request

from bridge.uploads import enforce_content_length
from pydantic import BaseModel


class StickerUpdate(BaseModel):
    file: str
    name: str = ""
    desc: str = ""


class StickerDataUpload(BaseModel):
    data: str
    name: str = ""
    desc: str = ""
    filename: str = ""


def register_sticker_routes(
    app,
    *,
    verify_token,
    verify_media_token,
    bridge_token,
    sticker_dir,
    sticker_meta,
    serve_sticker_file,
    list_sticker_items,
    upload_sticker_file,
    edit_sticker_meta,
    delete_sticker_file,
    sticker_max_bytes: int = 5 * 1024 * 1024,
    load_sticker_meta=None,
    upload_sticker_data=None,
) -> None:
    @app.get("/stickers/{name}")
    async def serve_sticker(name: str, request: Request, token: str = None):
        verify_media_token(request, bridge_token, token)
        return serve_sticker_file(sticker_dir, name)

    @app.get("/stickers-list")
    async def list_stickers(request: Request):
        verify_token(request)
        return list_sticker_items(sticker_dir, sticker_meta)

    @app.post("/stickers-upload")
    async def upload_sticker(request: Request):
        # 鉴权先于 body 解析（同 /upload），贴纸另有独立小上限
        verify_token(request)
        enforce_content_length(request, sticker_max_bytes)
        form = await request.form()
        file = form.get("file")
        if file is None or isinstance(file, str):
            raise HTTPException(400, "file field required")
        return upload_sticker_file(
            sticker_dir, sticker_meta, file,
            str(form.get("name") or ""), str(form.get("desc") or ""),
            max_bytes=sticker_max_bytes,
        )

    @app.post("/stickers-edit")
    async def edit_sticker(update: StickerUpdate, request: Request):
        verify_token(request)
        return edit_sticker_meta(sticker_meta, update.file, update.name, update.desc)

    @app.post("/stickers-delete")
    async def delete_sticker(update: StickerUpdate, request: Request):
        verify_token(request)
        return delete_sticker_file(sticker_dir, sticker_meta, update.file)

    # Aliases the chat page uses: the raw meta map, and base64 data-URL upload.
    if load_sticker_meta is not None:
        @app.get("/stickers-meta")
        async def stickers_meta(request: Request):
            verify_token(request)
            return load_sticker_meta(sticker_meta)

    if upload_sticker_data is not None:
        @app.post("/sticker-upload")
        async def sticker_upload(request: Request):
            verify_token(request)
            enforce_content_length(request, sticker_max_bytes * 2)  # base64 膨胀留裕量
            body = await request.json()
            payload = StickerDataUpload(**{k: body.get(k) or "" for k in ("data", "name", "desc", "filename")})
            return upload_sticker_data(
                sticker_dir,
                sticker_meta,
                data_url=payload.data,
                name=payload.name,
                desc=payload.desc,
                filename=payload.filename,
                max_bytes=sticker_max_bytes,
            )

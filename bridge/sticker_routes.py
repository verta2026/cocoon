"""Sticker or named asset route registration."""

from __future__ import annotations

from fastapi import File, Request, UploadFile
from pydantic import BaseModel


class StickerUpdate(BaseModel):
    file: str
    name: str = ""
    desc: str = ""


class StickerDataUpload(BaseModel):
    data: str
    name: str = ""
    filename: str = ""


def register_sticker_routes(
    app,
    *,
    verify_token,
    sticker_dir,
    sticker_meta,
    serve_sticker_file,
    list_sticker_items,
    upload_sticker_file,
    edit_sticker_meta,
    delete_sticker_file,
    load_sticker_meta=None,
    upload_sticker_data=None,
) -> None:
    @app.get("/stickers/{name}")
    async def serve_sticker(name: str, token: str = None):
        return serve_sticker_file(sticker_dir, name)

    @app.get("/stickers-list")
    async def list_stickers(request: Request):
        verify_token(request)
        return list_sticker_items(sticker_dir, sticker_meta)

    @app.post("/stickers-upload")
    async def upload_sticker(request: Request, file: UploadFile = File(...), name: str = "", desc: str = ""):
        verify_token(request)
        return upload_sticker_file(sticker_dir, sticker_meta, file, name, desc)

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
        async def sticker_upload(payload: StickerDataUpload, request: Request):
            verify_token(request)
            return upload_sticker_data(
                sticker_dir,
                sticker_meta,
                data_url=payload.data,
                name=payload.name,
                filename=payload.filename,
            )

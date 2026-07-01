"""Sticker or named asset route registration."""

from __future__ import annotations

from fastapi import File, Request, UploadFile
from pydantic import BaseModel


class StickerUpdate(BaseModel):
    file: str
    name: str = ""
    desc: str = ""


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

"""Conversation history route registration."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request


def register_history_routes(
    app,
    *,
    verify_token,
    list_conversation_sessions,
    read_conversation_messages,
    conversations_dir: Path,
    wrap_sessions: bool = False,
    wrap_messages: bool = False,
) -> None:
    @app.get("/history")
    async def history(request: Request):
        verify_token(request)
        sessions = list_conversation_sessions(conversations_dir)
        if wrap_sessions:
            return {"sessions": sessions}
        return sessions

    @app.get("/history/{file_id:path}")
    async def history_messages(file_id: str, request: Request):
        verify_token(request)
        messages = read_conversation_messages(conversations_dir, file_id)
        if wrap_messages:
            return {"file": file_id, "messages": messages}
        return messages

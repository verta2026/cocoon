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
    list_conversation_days=None,
    read_conversation_day=None,
    search_conversations=None,
) -> None:
    """Register read-only history routes.

    The day-grouped and search routes are optional: pass the corresponding
    helpers (curried with deployment-specific options such as main_user_id)
    to enable them.
    """

    @app.get("/history")
    async def history(request: Request):
        verify_token(request)
        sessions = list_conversation_sessions(conversations_dir)
        if wrap_sessions:
            return {"sessions": sessions}
        return sessions

    if list_conversation_days is not None:
        @app.get("/history-days")
        async def history_days(request: Request):
            verify_token(request)
            return list_conversation_days(conversations_dir)

    if read_conversation_day is not None:
        @app.get("/history-day/{date}")
        async def history_day(date: str, request: Request):
            verify_token(request)
            return read_conversation_day(conversations_dir, date)

    if search_conversations is not None:
        @app.get("/history-search")
        async def history_search(request: Request, q: str = "", limit: int = 120):
            verify_token(request)
            return search_conversations(conversations_dir, q, min(max(limit, 1), 500))

    @app.get("/history/{file_id:path}")
    async def history_messages(file_id: str, request: Request):
        verify_token(request)
        messages = read_conversation_messages(conversations_dir, file_id)
        if wrap_messages:
            return {"file": file_id, "messages": messages}
        return messages

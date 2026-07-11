"""Month index / full-text search / three-cursor paging over the chat stream.

The React frontend's History page and scroll-back paging speak the
``/chat_history_*`` protocol. These adapters serve that protocol from the
same message list ``/chat-pure`` renders, so message ids line up and work
as jump anchors across live chat, history browsing and search results.

Ids are ``{epoch_ms:015d}-{fingerprint}`` (see ``pure_chat_messages``),
so plain string comparison is time ordering and the first 15 chars give
the message's date without re-parsing timestamps.
"""

from __future__ import annotations

from datetime import datetime


def _msg_local_date(msg: dict) -> str:
    """Server-local calendar date for a message (id prefix is epoch ms)."""
    try:
        epoch_s = int(str(msg["id"])[:15]) / 1000
        return datetime.fromtimestamp(epoch_s).strftime("%Y-%m-%d")
    except Exception:
        return str(msg.get("ts") or "")[:10]


def chat_history_months(msgs: list) -> dict:
    """Month → day index: per-day count, first message id (jump anchor), preview."""
    days: dict[str, dict] = {}
    for m in msgs:
        d = _msg_local_date(m)
        if len(d) != 10:
            continue
        rec = days.setdefault(d, {"date": d, "count": 0, "first_id": m["id"], "preview": ""})
        rec["count"] += 1
        if not rec["preview"]:
            text = (m.get("content") or "").strip()
            if text:
                rec["preview"] = text[:80]
    months: dict[str, list] = {}
    for d in sorted(days, reverse=True):
        months.setdefault(d[:7], []).append(days[d])
    return {"months": [
        {"month": k, "count": sum(x["count"] for x in v), "days": v}
        for k, v in months.items()
    ]}


def chat_history_search(msgs: list, q: str = "", limit: int = 120) -> dict:
    """Case-insensitive substring search, newest first, with a hit snippet."""
    q = (q or "").strip()
    if not q:
        return {"results": []}
    ql = q.lower()
    try:
        limit = max(1, min(int(limit), 300))
    except Exception:
        limit = 120
    out = []
    for m in reversed(msgs):
        text = m.get("content") or ""
        pos = text.lower().find(ql)
        if pos < 0:
            continue
        start = max(0, pos - 30)
        snippet = ("…" if start > 0 else "") + text[start:start + 90] + ("…" if start + 90 < len(text) else "")
        out.append({
            "id": m["id"], "date": _msg_local_date(m), "role": m.get("role", ""),
            "sender": m.get("sender", ""), "snippet": snippet,
        })
        if len(out) >= limit:
            break
    return {"results": out}


def chat_history_page(msgs: list, before: str = "", limit: int = 50, after: str = "", around: str = "") -> dict:
    """Three-cursor paging: before=older page, after=newer page, around=window
    centred on a message (jump-to-search-hit)."""
    try:
        limit = max(1, min(int(limit), 500))
    except Exception:
        limit = 50
    if around:
        idx = next((i for i, m in enumerate(msgs) if m["id"] == around), None)
        if idx is None:
            idx = next((i for i, m in enumerate(msgs) if m["id"] >= around), len(msgs) - 1)
        if idx < 0:
            idx = 0
        half = limit // 2
        start = max(0, idx - half)
        end = min(len(msgs), start + limit)
        return {
            "messages": msgs[start:end],
            "has_more": start > 0,
            "has_more_after": end < len(msgs),
            "target": msgs[idx]["id"] if msgs else "",
        }
    if after:
        newer = [m for m in msgs if m["id"] > after]
        page = newer[:limit]
        return {"messages": page, "has_more_after": len(newer) > len(page)}
    if before:
        msgs = [m for m in msgs if m["id"] < before]
    page = msgs[-limit:]
    return {"messages": page, "has_more": len(msgs) > len(page)}

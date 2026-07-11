"""AskUserQuestion bridge: surface Claude Code's interactive question prompts
in the web UI and answer them on the user's behalf.

The archive layer only carries text blocks, so an AskUserQuestion tool_use is
invisible to the frontend while the question sits waiting in the terminal.
Two pieces close the loop:

1. Detection — NOT via the session jsonl. Measured live (2026-07-11, probes
   sampling both the file and this parser every 2s during a real pendency):
   Claude Code does not flush the AskUserQuestion tool_use row while the
   question is open. The row and its tool_result are written together at
   resolution, with the timestamp back-dated to generation time — so any
   after-the-fact replay "detects" the question, but scanning during the
   pendency never can. The only place the payload exists before the prompt
   renders is the PreToolUse hook: hooks/ask_pending.py writes the questions
   to a small state file, the bridge reads that file and attaches it to the
   /chat_pure payload as ``ask``. Cleanup is layered: PostToolUse deletes the
   file when the question is answered, UserPromptSubmit deletes it on any new
   input (declining in the terminal never fires PostToolUse), and a 15-minute
   TTL keeps a ghost prompt from sticking if no hook ran.
2. Answering — POST /ask_answer drives the terminal UI with tmux keystrokes.
   Key behavior verified against Claude Code v2.1.195 in a throwaway session:
   - row layout: options 0..n-1, then "Type something." at row n, and (multi
     select only) a "Submit" row after that
   - single select: Down x idx + Enter; a lone single-select question submits
     immediately with no review page
   - multi select: Space toggles rows (Enter toggles too — it does NOT
     submit!); navigate to the Submit row and press Enter there
   - free text: move onto the "Type something." row and type directly —
     pressing Enter first with an empty input declines the whole question;
     Enter after typing confirms
   - with multiple questions or any multi select the TUI shows a final
     "Ready to submit your answers?" review page needing one more Enter
   The answer is verified by waiting for the tool_result to land in the jsonl.

Driving a TUI is inherently version-fragile, so POST /ask_escape is always
available: one Esc dismisses the question and the user falls back to typing.

Do NOT add ``from __future__ import annotations`` here: it turns the
``request: Request`` annotations into strings, and since Request is imported
locally inside register_ask_routes, FastAPI cannot resolve them from module
globals — both POST endpoints then degrade into 422s demanding a ``request``
query parameter, and every click in the web picker silently does nothing.
"""

import json
import subprocess
import time
from pathlib import Path

ASK_TTL_SECONDS = 900


def pending_ask(state_file, ttl_seconds=ASK_TTL_SECONDS):
    """Return the question currently awaiting an answer as
    ``{id, questions, ts}``, or None.

    ``state_file`` is written by the PreToolUse hook and deleted by the
    PostToolUse/UserPromptSubmit hooks. Entries older than the TTL are ghosts
    (no hook got to clean up) and are not served."""
    if not state_file:
        return None
    try:
        data = json.loads(Path(state_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        ts = float(data.get("ts") or 0)
    except (TypeError, ValueError):
        return None
    if not ts or time.time() - ts > ttl_seconds:
        return None
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        return None
    return {"id": str(data.get("id") or "ask"), "questions": questions, "ts": ts}


def drive_answer(session_name, questions, answers, run_func=subprocess.run, sleep_func=time.sleep):
    """Type the chosen answers into the terminal UI. ``answers`` matches
    ``questions`` in length; each item is one of:

    ``{"index": 0}``        single select: pick option ``index`` (0-based)
    ``{"indexes": [0, 2]}`` multi select: toggle these options
    ``{"other": "text"}``   free text via the trailing Other row
    """

    def key(name):
        run_func(["tmux", "send-keys", "-t", session_name, name], check=True)

    def literal(text):
        run_func(["tmux", "send-keys", "-t", session_name, "-l", text], check=True)

    def screen():
        result = run_func(
            ["tmux", "capture-pane", "-t", session_name, "-p"],
            capture_output=True, text=True,
        )
        return getattr(result, "stdout", "") or ""

    for qi, (question, answer) in enumerate(zip(questions, answers)):
        if qi:
            sleep_func(0.7)  # let the TUI advance to the next question
        answer = answer or {}
        options = question.get("options") or []
        n = len(options)
        other = str(answer.get("other") or "").strip()
        if question.get("multiSelect"):
            want = {int(i) for i in (answer.get("indexes") or []) if 0 <= int(i) < n}
            for row in range(n):
                if row:
                    key("Down")
                    sleep_func(0.05)
                if row in want:
                    key("Space")  # Enter toggles too, but Space can't be mistaken for submit
                    sleep_func(0.08)
            key("Down")  # -> "Type something." row
            sleep_func(0.05)
            if other:
                literal(other)  # type in place; Enter first would decline the question
                sleep_func(0.15)
                key("Enter")  # confirm the text (also checks the row in multi select)
                sleep_func(0.15)
            key("Down")  # -> Submit row
            sleep_func(0.1)
            key("Enter")
        elif other:
            # the "Type something." row sits right after the listed options;
            # type in place, Enter only after the text is in
            for _ in range(n):
                key("Down")
                sleep_func(0.05)
            literal(other)
            sleep_func(0.15)
            key("Enter")
        else:
            idx = int(answer.get("index") or 0)
            idx = max(0, min(idx, n - 1))
            for _ in range(idx):
                key("Down")
                sleep_func(0.05)
            key("Enter")

    # Review page: with multiple questions or any multi select the TUI asks
    # "Ready to submit your answers?" with the cursor on Submit — one more
    # Enter. A lone single-select question submits directly; no page to find.
    for _ in range(6):
        sleep_func(0.35)
        snap = screen()
        if "Ready to submit" in snap:
            key("Enter")
            break
        if "Esc to cancel" not in snap:
            break  # selector already gone (direct-submit case)


def register_ask_routes(
    app,
    *,
    verify_token,
    session_name: str,
    state_file,
    tmux_exists,
    run_func=subprocess.run,
):
    import asyncio
    import traceback

    from fastapi import HTTPException, Request

    state_file = Path(state_file)

    def _clear_state():
        try:
            state_file.unlink()
        except OSError:
            pass

    @app.get("/ask_debug")
    async def ask_debug(request: Request):
        """X-ray for the picker chain: where the state file lives, what
        detection returns on it, and the raw traceback if it blows."""
        verify_token(request)
        info = {}
        try:
            info["state_file"] = str(state_file)
            info["exists"] = state_file.exists()
            info["mtime"] = state_file.stat().st_mtime if info["exists"] else None
            pend = pending_ask(state_file)
            info["pending"] = {"id": pend["id"], "questions": len(pend["questions"])} if pend else None
        except Exception:
            info["error"] = traceback.format_exc()[-800:]
        return info

    @app.post("/ask_answer")
    async def ask_answer(request: Request):
        verify_token(request)
        body = await request.json()
        tool_id = str(body.get("id") or "")
        answers = body.get("answers")
        pend = pending_ask(state_file)
        if not pend or (tool_id and pend["id"] != tool_id):
            raise HTTPException(409, "question no longer pending")
        if not tmux_exists():
            raise HTTPException(404, "no active session")
        questions = pend["questions"]
        if not isinstance(answers, list) or len(answers) != len(questions):
            raise HTTPException(400, "answers must match questions length")
        await asyncio.to_thread(drive_answer, session_name, questions, answers, run_func)
        # verify: once answered, the PostToolUse hook deletes the state file
        for _ in range(20):
            await asyncio.sleep(0.4)
            now = pending_ask(state_file)
            if not now or now["id"] != pend["id"]:
                return {"ok": True}
        return {"ok": False, "reason": "no-result"}

    @app.post("/ask_escape")
    async def ask_escape(request: Request):
        verify_token(request)
        if not tmux_exists():
            raise HTTPException(404, "no active session")
        run_func(["tmux", "send-keys", "-t", session_name, "Escape"], check=True)
        # declining never fires PostToolUse; clear here so the picker closes
        _clear_state()
        return {"ok": True}

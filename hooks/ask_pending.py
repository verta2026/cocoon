#!/usr/bin/env python3
"""AskUserQuestion pending-state hook — the only reliable signal source for
the web question picker.

Why this exists: measured live (2026-07-11), Claude Code does not flush the
AskUserQuestion tool_use row to the session jsonl while the question is open.
The row and its tool_result are written together at resolution, with the
timestamp back-dated to generation time. A bridge scanning the jsonl can
never see an open question; the only place the payload exists before the
prompt renders is the PreToolUse hook.

PreToolUse(AskUserQuestion)  -> write the questions to the state file; the
                                bridge serves them to the frontend picker
PostToolUse(AskUserQuestion) -> question answered, delete the state file
UserPromptSubmit             -> any new input means no question is open
                                (declining in the terminal never fires
                                PostToolUse; this layer cleans that up)

Install: register this script in .claude/settings.json of the project the
bridged Claude Code session runs in:

    {
      "hooks": {
        "PreToolUse": [{"matcher": "AskUserQuestion",
          "hooks": [{"type": "command", "command": "python3 /path/to/cocoon/hooks/ask_pending.py"}]}],
        "PostToolUse": [{"matcher": "AskUserQuestion",
          "hooks": [{"type": "command", "command": "python3 /path/to/cocoon/hooks/ask_pending.py"}]}],
        "UserPromptSubmit": [
          {"hooks": [{"type": "command", "command": "python3 /path/to/cocoon/hooks/ask_pending.py"}]}]
      }
    }

Hook config is snapshotted when a Claude Code session starts, so restart the
session after installing. COCOON_ASK_STATE_FILE (or COCOON_STATE_DIR) must
resolve to the same path the bridge uses — see config.py.

Hooks must never break the main loop: fail silently, always.
"""

import json
import os
import sys
import time
from pathlib import Path

STATE_DIR = Path(os.environ.get("COCOON_STATE_DIR", str(Path.cwd() / ".cocoon")))
STATE_FILE = Path(os.environ.get("COCOON_ASK_STATE_FILE", str(STATE_DIR / ".ask_pending.json")))


def handle(event, state_file=STATE_FILE):
    name = event.get("hook_event_name", "")
    if name == "PreToolUse":
        if event.get("tool_name") != "AskUserQuestion":
            return
        questions = (event.get("tool_input") or {}).get("questions")
        if not isinstance(questions, list) or not questions:
            return
        payload = {
            "id": f"ask-{int(time.time() * 1000)}",
            "ts": time.time(),
            "questions": questions,
        }
        state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(state_file)
    elif name == "PostToolUse":
        if event.get("tool_name") != "AskUserQuestion":
            return
        state_file.unlink(missing_ok=True)
    else:  # UserPromptSubmit and anything else: no question survives new input
        state_file.unlink(missing_ok=True)


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        return
    try:
        handle(event)
    except Exception:
        pass


if __name__ == "__main__":
    main()

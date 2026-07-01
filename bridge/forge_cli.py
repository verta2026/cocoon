"""Minimal dry-run CLI for generic forge planning."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from bridge.forge import build_forge_plan, load_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a dry-run forge plan from an explicit Claude jsonl source.")
    parser.add_argument("--source", type=Path, required=True, help="Claude jsonl source to inspect")
    parser.add_argument("--project-dir", type=Path, required=True, help="Target project directory, reported only")
    parser.add_argument("--manifest-dir", type=Path, required=True, help="Target manifest directory, reported only")
    parser.add_argument("--retain-tokens", type=int, default=100_000)
    parser.add_argument("--allow-open-turn", action="store_true")
    parser.add_argument("--new-session-id", default="")
    return parser


def run(argv: list[str] | None = None) -> dict:
    args = build_parser().parse_args(argv)
    rows = load_jsonl(args.source)
    new_session_id = args.new_session_id or str(uuid.uuid4())
    plan = build_forge_plan(
        rows=rows,
        source=str(args.source),
        retain_tokens=args.retain_tokens,
        new_session_id=new_session_id,
        allow_open_turn=args.allow_open_turn,
    )
    summary = dict(plan.summary)
    summary["project_dir"] = str(args.project_dir)
    summary["manifest_dir"] = str(args.manifest_dir)
    return summary


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(run(argv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

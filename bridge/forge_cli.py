"""Minimal explicit-source CLI for generic forge planning."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from bridge.forge import build_forge_plan, build_manifest_payload, execute_forge_write, forge_write_paths, load_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a forge plan from an explicit Claude jsonl source.")
    parser.add_argument("--source", type=Path, required=True, help="Claude jsonl source to inspect")
    parser.add_argument("--project-dir", type=Path, required=True, help="Target project directory")
    parser.add_argument("--manifest-dir", type=Path, required=True, help="Target manifest directory")
    parser.add_argument("--retain-tokens", type=int, default=100_000)
    parser.add_argument("--allow-open-turn", action="store_true")
    parser.add_argument("--new-session-id", default="")
    parser.add_argument("--created-at", default="")
    parser.add_argument("--write", action="store_true")
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
    if args.write:
        paths = forge_write_paths(args.project_dir, args.manifest_dir, new_session_id)
        write_summary = {
            **summary,
            "dest": str(paths["dest"]),
            "manifest": str(paths["manifest"]),
            "written": True,
        }
        manifest_payload = build_manifest_payload(write_summary, created_at=args.created_at)
        summary = execute_forge_write(
            paths=paths,
            forged_events=plan.forged,
            summary=summary,
            manifest_payload=manifest_payload,
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(run(argv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

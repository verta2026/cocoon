"""Optional extension registry helpers.

The registry describes links or adjacent tools. It does not load, execute, or
proxy plugin code.
"""

from __future__ import annotations

import re
from pathlib import Path

from bridge.json_store import read_json


EXTENSION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
ALLOWED_KINDS = {"link", "tool", "plugin"}


def _clean_text(value: object, max_len: int = 120) -> str:
    return str(value or "").strip()[:max_len]


def _safe_href(value: object) -> str:
    href = str(value or "").strip()
    if not href:
        return ""
    if href.startswith(("/", "https://", "http://")):
        return href[:500]
    return ""


def normalize_extension(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    ext_id = _clean_text(raw.get("id"), 80)
    title = _clean_text(raw.get("title") or raw.get("name"), 120)
    href = _safe_href(raw.get("href") or raw.get("url"))
    kind = _clean_text(raw.get("kind") or "link", 40).lower()
    if not ext_id or not EXTENSION_ID_RE.match(ext_id) or not title or not href:
        return None
    if kind not in ALLOWED_KINDS:
        kind = "link"
    return {
        "id": ext_id,
        "title": title,
        "href": href,
        "kind": kind,
        "enabled": raw.get("enabled", True) is not False,
        "description": _clean_text(raw.get("description"), 240),
    }


def list_extensions(registry_file: Path) -> list[dict]:
    data = read_json(registry_file, default={})
    entries = data.get("extensions", data) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return []
    out = []
    seen = set()
    for raw in entries:
        item = normalize_extension(raw)
        if not item or not item["enabled"] or item["id"] in seen:
            continue
        seen.add(item["id"])
        out.append(item)
    return out

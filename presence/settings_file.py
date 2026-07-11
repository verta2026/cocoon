"""Generic helpers for editable JSON settings files."""

from __future__ import annotations

import json


def read_text_file(path: str) -> str:
    """Read a UTF-8 text file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def validate_json_document(content: str) -> None:
    """Raise JSONDecodeError when content is not valid JSON."""
    json.loads(content)


def write_text_file(path: str, content: str) -> None:
    """Write a UTF-8 text file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

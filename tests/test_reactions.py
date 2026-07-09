import time
from pathlib import Path

from bridge.reactions import (
    apply_reaction,
    load_reactions,
    recent_image_entries,
    toggle_reaction,
)


def test_toggle_reaction_adds_then_removes():
    data, added = toggle_reaction({}, msg_id="m1", emoji="❤", sender="user")
    assert added is True
    assert data == {"m1": [{"emoji": "❤", "from": "user"}]}

    data, added = toggle_reaction(data, msg_id="m1", emoji="❤", sender="user")
    assert added is False
    assert data == {}


def test_toggle_reaction_keeps_other_senders():
    data, _ = toggle_reaction({}, msg_id="m1", emoji="❤", sender="user")
    data, _ = toggle_reaction(data, msg_id="m1", emoji="❤", sender="ai")
    data, _ = toggle_reaction(data, msg_id="m1", emoji="❤", sender="user")
    assert data == {"m1": [{"emoji": "❤", "from": "ai"}]}


def test_apply_reaction_persists(tmp_path):
    path = tmp_path / "reactions.json"
    data, added = apply_reaction(path, msg_id="m1", emoji="👍", sender="user")
    assert added is True
    assert load_reactions(path) == data == {"m1": [{"emoji": "👍", "from": "user"}]}

    data, added = apply_reaction(path, msg_id="m1", emoji="👍", sender="user")
    assert added is False
    assert load_reactions(path) == {}


def test_load_reactions_tolerates_missing_and_corrupt(tmp_path):
    assert load_reactions(tmp_path / "missing.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    assert load_reactions(bad) == {}


def test_recent_image_entries_orders_and_limits(tmp_path):
    for i, name in enumerate(["a.jpg", "b.png", "c.txt", "d.webp"]):
        f = tmp_path / name
        f.write_bytes(b"x")
        ts = time.time() - 100 + i
        import os

        os.utime(f, (ts, ts))
    entries = recent_image_entries([(tmp_path, "/bridge/files/")])
    assert [e["name"] for e in entries] == ["d.webp", "b.png", "a.jpg"]
    assert entries[0]["src"] == "/bridge/files/d.webp"

    limited = recent_image_entries([(tmp_path, "/bridge/files/")], limit=1)
    assert [e["name"] for e in limited] == ["d.webp"]


def test_recent_image_entries_skips_missing_dir(tmp_path):
    assert recent_image_entries([(tmp_path / "nope", "/x/")]) == []

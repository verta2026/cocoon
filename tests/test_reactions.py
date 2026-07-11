import time
from pathlib import Path

from bridge.reactions import (
    apply_reaction,
    load_reactions,
    reaction_notice,
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


def test_reaction_notice_renders_with_prefix():
    text = reaction_notice(
        "{user}给你的消息「{excerpt}」贴了一个 {emoji}。",
        user="用户", emoji="❤", excerpt="今晚修好了缓存",
    )
    assert text == "[reaction] 用户给你的消息「今晚修好了缓存」贴了一个 ❤。"


def test_reaction_notice_squashes_and_truncates_excerpt():
    text = reaction_notice(
        "{excerpt}|{emoji}", user="u", emoji="👍", excerpt="a\nb   c" + "x" * 100,
    )
    body = text[len("[reaction] "):]
    excerpt = body.split("|")[0]
    assert "\n" not in excerpt
    assert len(excerpt) <= 60
    assert excerpt.startswith("a b c")


def test_reaction_notice_empty_excerpt_placeholder():
    text = reaction_notice("{user}:{emoji}:{excerpt}", user="u", emoji="✨", excerpt="  ")
    assert text.endswith("（无文字）")


def test_reaction_notice_bad_template_returns_empty():
    assert reaction_notice("{nope}", user="u", emoji="x", excerpt="y") == ""
    assert reaction_notice("", user="u", emoji="x", excerpt="y") == ""

import json

from bridge.live_archive import (
    archive_key,
    archive_parts_from_message,
    archive_rows_from_claude_jsonl,
    dedup_external_send_rows,
    live_messages,
    parse_channel_message,
    read_send_sidecar_rows,
    sync_live_archive,
)


def _jsonl_line(role, content, ts, sid="sess-1", uuid="u-1", **extra):
    obj = {
        "type": role,
        "timestamp": ts,
        "sessionId": sid,
        "uuid": uuid,
        "message": {"role": role, "content": content},
    }
    obj.update(extra)
    return json.dumps(obj)


def test_parts_text_and_reply_tool():
    content = [
        {"type": "text", "text": "hello there"},
        {
            "type": "tool_use",
            "name": "mcp__chat_plugin__reply",
            "input": {"text": "sent to channel", "chat_id": "-100200"},
        },
    ]
    parts = archive_parts_from_message("assistant", content)
    assert parts[0] == {"content": "hello there", "channel": ""}
    assert parts[1]["content"] == "sent to channel"
    assert parts[1]["channel"] == "group"
    assert parts[1]["source"] == "external-send"


def test_parts_voice_marker_from_tool_result():
    content = [
        {
            "type": "tool_result",
            "content": [{"type": "text", "text": "ok [[voice:abcdef0123456789]] done"}],
        }
    ]
    parts = archive_parts_from_message("user", content)
    assert parts == [
        {"content": "[[voice:abcdef0123456789]]", "channel": "", "source": "voice"}
    ]


def test_jsonl_rows_extracted(tmp_path):
    path = tmp_path / "sess-1.jsonl"
    path.write_text(
        "\n".join(
            [
                _jsonl_line("user", "hi", "2026-07-01T10:00:00.000Z", uuid="u-1"),
                _jsonl_line(
                    "assistant",
                    [{"type": "text", "text": "hello back"}],
                    "2026-07-01T10:00:05.000Z",
                    uuid="u-2",
                ),
                _jsonl_line("user", "<command-name>/exit</command-name>", "2026-07-01T10:00:06.000Z", uuid="u-3"),
            ]
        ),
        encoding="utf-8",
    )
    rows = archive_rows_from_claude_jsonl(path)
    assert [r["content"] for r in rows] == ["hi", "hello back"]
    assert rows[0]["session_id"] == "sess-1"
    assert rows[0]["uuid"] == "u-1"


def test_dedup_collapses_double_recorded_send():
    rows = [
        {
            "role": "assistant",
            "content": "good morning",
            "timestamp": "2026-07-01T10:00:00.000Z",
            "source": "external-send",
            "session_id": "sess-1",
            "uuid": "u-9",
        },
        {
            "role": "assistant",
            "content": "good morning",
            "timestamp": "2026-07-01T10:00:03.500Z",
            "source": "external-send",
            "channel": "dm",
            "chat_id": "12345",
            "message_ids": [7],
        },
        {
            "role": "assistant",
            "content": "unrelated",
            "timestamp": "2026-07-01T10:00:05.000Z",
            "source": "claude-code-jsonl",
        },
        {
            "role": "assistant",
            "content": "good morning",
            "timestamp": "2026-07-01T11:00:00.000Z",
            "source": "external-send",
        },
    ]
    out = dedup_external_send_rows(rows)
    assert len(out) == 3
    kept = out[0]
    # first row wins, metadata from the collapsed twin is merged in
    assert kept["uuid"] == "u-9"
    assert kept["chat_id"] == "12345"
    assert kept["channel"] == "dm"
    assert kept["message_ids"] == [7]
    # a repeat outside the window is a real second send
    assert out[2]["timestamp"].startswith("2026-07-01T11")


def test_sync_merges_jsonl_and_sidecar_without_duplicates(tmp_path):
    jsonl = tmp_path / "sess-1.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                _jsonl_line("user", "hi", "2026-07-01T10:00:00.000Z", uuid="u-1"),
                _jsonl_line(
                    "assistant",
                    [
                        {
                            "type": "tool_use",
                            "name": "mcp__chat_plugin__reply",
                            "input": {"text": "pong", "chat_id": "555"},
                        }
                    ],
                    "2026-07-01T10:00:02.000Z",
                    uuid="u-2",
                ),
            ]
        ),
        encoding="utf-8",
    )
    sidecar = tmp_path / "_sends.jsonl"
    sidecar.write_text(
        json.dumps(
            {
                "role": "assistant",
                "content": "pong",
                "timestamp": "2026-07-01T10:00:04.100Z",
                "source": "external-send",
                "chat_id": "555",
                "message_ids": [42],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    archive = tmp_path / "archive.jsonl"
    state = {"path": "", "mtime": 0.0, "checked": 0.0}
    result = sync_live_archive(
        archive, state, 1, lambda: jsonl, sidecar_file=sidecar, force=True
    )
    assert result["updated"] is True
    rows = [json.loads(l) for l in archive.read_text(encoding="utf-8").splitlines()]
    sends = [r for r in rows if r.get("source") == "external-send"]
    assert len(sends) == 1
    assert sends[0]["message_ids"] == [42]
    assert len(rows) == 2


def test_sidecar_reader_filters_other_sources(tmp_path):
    sidecar = tmp_path / "_sends.jsonl"
    sidecar.write_text(
        "\n".join(
            [
                json.dumps({"role": "assistant", "content": "keep", "source": "external-send"}),
                json.dumps({"role": "assistant", "content": "skip", "source": "other"}),
                json.dumps({"role": "user", "content": "skip", "source": "external-send"}),
            ]
        ),
        encoding="utf-8",
    )
    rows = read_send_sidecar_rows(sidecar)
    assert [r["content"] for r in rows] == ["keep"]


def test_channel_tag_roles():
    tag = '<channel source="chat" chat_id="-42" user_id="99" user="friend">hey</channel>'
    meta = parse_channel_message(tag)
    assert meta["content"] == "hey"
    assert meta["channel"] == "group"

    rows = [
        {"role": "user", "content": tag, "timestamp": "2026-07-01T10:00:00.000Z"},
        {"role": "user", "content": "plain message", "timestamp": "2026-07-01T10:00:01.000Z"},
    ]
    msgs = live_messages(rows, 50, primary_sender_id="1")
    assert msgs[0]["role"] == "channel"
    assert msgs[0]["sender"] == "99"
    assert msgs[1]["role"] == "user"

    msgs = live_messages(rows, 50, primary_sender_id="99")
    assert msgs[0]["role"] == "user"


def test_live_messages_stable_ids_and_limit():
    rows = [
        {"role": "user", "content": f"msg {i}", "timestamp": f"2026-07-01T10:00:0{i}.000Z"}
        for i in range(5)
    ]
    msgs = live_messages(rows, 2)
    assert len(msgs) == 2
    assert msgs[0]["content"] == "msg 3"
    assert msgs[0]["id"] == archive_key(rows[3])

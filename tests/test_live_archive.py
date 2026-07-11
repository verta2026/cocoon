import json

from bridge.live_archive import (
    archive_key,
    archive_parts_from_message,
    archive_rows_from_claude_jsonl,
    bare_marker_noise,
    dedup_cross_source_rows,
    dedup_external_send_rows,
    live_messages,
    make_transcript_noise,
    parse_channel_message,
    pure_chat_messages,
    read_recv_sidecar_rows,
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


def test_bare_marker_noise_only_eats_plumbing_rows():
    markers = ("FOO_VERIFY_", "RESUME_READY_")
    # The bare ping row is filtered.
    assert bare_marker_noise("FOO_VERIFY_9f3a", markers)
    assert bare_marker_noise("RESUME_READY_beef", markers)
    # A real message that merely quotes the marker survives — this is the
    # self-referential bug: a report about replacing the token must not vanish.
    report = (
        "Pushed the squash. While re-filtering I caught a leftover FOO_VERIFY_\n"
        "token in the test fixtures and replaced it. " + "All green. " * 40
    )
    assert not bare_marker_noise(report, markers)
    # A short first line mentioning the marker mid-line still survives when long.
    assert not bare_marker_noise("done, dropped FOO_VERIFY_ everywhere " * 10, markers)


def test_make_transcript_noise_keeps_real_messages():
    is_noise = make_transcript_noise(
        bare_markers=("FOO_VERIFY_",),
        status_prefixes=("Replied", "Waiting for"),
        status_markers=("no need to reply",),
    )
    # Plumbing and heartbeat rows are noise.
    assert is_noise("user", "FOO_VERIFY_9f3a")
    assert is_noise("assistant", "Replied in group; nothing pending.")
    assert is_noise("assistant", "Group quiet — no need to reply.")
    assert is_noise("user", "<command-name>/exit</command-name>")
    assert is_noise("assistant", "")
    # Real conversation survives even when it contains the same words.
    assert not is_noise("assistant", "Morning — no need to reply right away, " * 5)
    long_report = "Pushed it. Replaced the FOO_VERIFY_ token too.\n" + "Done. " * 60
    assert not is_noise("assistant", long_report)


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


def test_recv_sidecar_reader_filters_other_sources(tmp_path):
    sidecar = tmp_path / "_recv.jsonl"
    sidecar.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "keep", "source": "external-recv"}),
                json.dumps({"role": "user", "content": "skip", "source": "other"}),
                json.dumps({"role": "assistant", "content": "skip", "source": "external-recv"}),
            ]
        ),
        encoding="utf-8",
    )
    rows = read_recv_sidecar_rows(sidecar)
    assert [r["content"] for r in rows] == ["keep"]


def test_cross_source_dedup_drops_transcript_echo_of_send():
    rows = [
        {
            "role": "assistant",
            "content": "same reply",
            "timestamp": "2026-07-01T10:00:00.000Z",
            "source": "external-send",
            "channel": "dm",
        },
        {
            "role": "assistant",
            "content": "same reply",
            "timestamp": "2026-07-01T10:00:04.000Z",
            "source": "claude-code-jsonl",
        },
        {
            "role": "assistant",
            "content": "different reply",
            "timestamp": "2026-07-01T10:00:05.000Z",
            "source": "claude-code-jsonl",
        },
    ]
    out = dedup_cross_source_rows(rows)
    assert len(out) == 2
    assert out[0]["source"] == "external-send"
    assert out[1]["content"] == "different reply"


def test_cross_source_dedup_prefers_channel_row_by_message_id():
    tag = '<channel source="chat" chat_id="55" message_id="7" user_id="99">hi there</channel>'
    rows = [
        {"role": "user", "content": tag, "timestamp": "2026-07-01T10:00:00.000Z"},
        {
            "role": "user",
            "content": "hi there",
            "timestamp": "2026-07-01T10:00:01.000Z",
            "source": "external-recv",
            "chat_id": "55",
            "message_id": "7",
        },
    ]
    out = dedup_cross_source_rows(rows)
    assert len(out) == 1
    assert "<channel " in out[0]["content"]


def test_cross_source_dedup_falls_back_to_content_window():
    tag = '<channel source="chat" chat_id="55" user_id="99">hello again</channel>'
    rows = [
        {"role": "user", "content": tag, "timestamp": "2026-07-01T10:00:00.000Z"},
        {
            "role": "user",
            "content": "hello again",
            "timestamp": "2026-07-01T10:00:02.000Z",
            "source": "external-recv",
            "chat_id": "55",
        },
    ]
    out = dedup_cross_source_rows(rows)
    assert len(out) == 1
    assert "<channel " in out[0]["content"]


def test_cross_source_dedup_drops_chat_id_less_recv_echo():
    # A recv sidecar row without chat_id is still a duplicate of an
    # identity-carrying <channel> row; the (chat_id, content) bucket lookup
    # alone would miss it and resurrect the echo.
    tag = '<channel source="chat" chat_id="55" user_id="99">hello again</channel>'
    rows = [
        {"role": "user", "content": tag, "timestamp": "2026-07-01T10:00:00.000Z"},
        {
            "role": "user",
            "content": "hello again",
            "timestamp": "2026-07-01T10:00:02.000Z",
            "source": "external-recv",
        },
    ]
    out = dedup_cross_source_rows(rows)
    assert len(out) == 1
    assert "<channel " in out[0]["content"]


def test_cross_source_dedup_keeps_recv_row_when_transcript_missed_it():
    rows = [
        {
            "role": "user",
            "content": "only in sidecar",
            "timestamp": "2026-07-01T10:00:00.000Z",
            "source": "external-recv",
            "chat_id": "55",
            "message_id": "9",
        },
    ]
    out = dedup_cross_source_rows(rows)
    assert len(out) == 1


def test_cross_source_dedup_keeps_distinct_chats_with_same_text():
    # Two different chats send the same short text a second apart. A chat-agnostic
    # content-window key would drop the second as a phantom duplicate of the first.
    tag = '<channel source="chat" chat_id="55" message_id="7" user_id="99">ok</channel>'
    rows = [
        {"role": "user", "content": tag, "timestamp": "2026-07-01T10:00:00.000Z"},
        {
            "role": "user",
            "content": "ok",
            "timestamp": "2026-07-01T10:00:01.000Z",
            "source": "external-recv",
            "chat_id": "66",
            "message_id": "3",
        },
    ]
    out = dedup_cross_source_rows(rows)
    assert len(out) == 2


def test_sync_merges_recv_sidecar_and_dedups_against_channel_row(tmp_path):
    tag = '<channel source="chat" chat_id="55" message_id="7" user_id="99">covered</channel>'
    jsonl = tmp_path / "sess-9.jsonl"
    jsonl.write_text(
        _jsonl_line("user", tag, "2026-07-01T10:00:00.000Z", sid="sess-9", uuid="u-1"),
        encoding="utf-8",
    )
    recv = tmp_path / "_recv.jsonl"
    recv.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "content": "covered",
                        "timestamp": "2026-07-01T10:00:01.000Z",
                        "source": "external-recv",
                        "chat_id": "55",
                        "message_id": "7",
                    }
                ),
                json.dumps(
                    {
                        "role": "user",
                        "content": "gap filler",
                        "timestamp": "2026-07-01T10:00:05.000Z",
                        "source": "external-recv",
                        "chat_id": "55",
                        "message_id": "8",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    archive = tmp_path / "archive.jsonl"
    state = {}
    result = sync_live_archive(
        archive, state, 1, lambda: jsonl, recv_sidecar_file=recv, force=True
    )
    assert result["updated"] is True
    rows = [json.loads(l) for l in archive.read_text(encoding="utf-8").splitlines()]
    contents = [r["content"] for r in rows]
    assert len(rows) == 2
    assert any("<channel " in c for c in contents)
    assert "gap filler" in contents


def test_pure_chat_ids_monotonic_and_since_filter():
    rows = [
        {"role": "user", "content": f"msg {i}", "timestamp": f"2026-07-01T10:00:0{i}.000Z"}
        for i in range(4)
    ]
    msgs = pure_chat_messages(rows)
    assert len(msgs) == 4
    ids = [m["id"] for m in msgs]
    assert ids == sorted(ids)
    later = pure_chat_messages(rows, since=ids[1])
    assert [m["content"] for m in later] == ["msg 2", "msg 3"]


def test_pure_chat_strips_voice_markers_and_drops_empty():
    rows = [
        {
            "role": "assistant",
            "content": "listen [[voice:abcdef0123456789]]",
            "timestamp": "2026-07-01T10:00:00.000Z",
        },
        {
            "role": "assistant",
            "content": "[[voice:abcdef0123456789]]",
            "timestamp": "2026-07-01T10:00:01.000Z",
        },
    ]
    msgs = pure_chat_messages(rows)
    assert [m["content"] for m in msgs] == ["listen"]


def test_pure_chat_dedup_prefers_named_sender():
    tag = '<channel source="chat" chat_id="55" user="friend">hi</channel>'
    rows = [
        {
            "role": "user",
            "content": "hi",
            "timestamp": "2026-07-01T10:00:00.000Z",
            "source": "external-recv",
            "user_id": "99",
        },
        {"role": "user", "content": tag, "timestamp": "2026-07-01T10:00:00.000Z"},
    ]
    msgs = pure_chat_messages(rows, primary_sender_id="1")
    assert len(msgs) == 1
    assert msgs[0]["role"] == "channel"
    assert msgs[0]["sender"] == "friend"
    assert "_named" not in msgs[0]


def test_pure_chat_recv_row_channel_role():
    rows = [
        {
            "role": "user",
            "content": "from someone else",
            "timestamp": "2026-07-01T10:00:00.000Z",
            "source": "external-recv",
            "user_id": "99",
        },
        {
            "role": "user",
            "content": "from the primary sender",
            "timestamp": "2026-07-01T10:00:01.000Z",
            "source": "external-recv",
            "user_id": "1",
        },
    ]
    msgs = pure_chat_messages(rows, primary_sender_id="1")
    assert msgs[0]["role"] == "channel"
    assert msgs[1]["role"] == "user"


def test_pure_chat_keeps_distinct_chats_with_same_text():
    # Same second, same text, same role, different chats -> both must survive.
    tag_a = '<channel source="chat" chat_id="55" message_id="7" user="a">ok</channel>'
    tag_b = '<channel source="chat" chat_id="66" message_id="3" user="b">ok</channel>'
    rows = [
        {"role": "user", "content": tag_a, "timestamp": "2026-07-01T10:00:00.000Z"},
        {"role": "user", "content": tag_b, "timestamp": "2026-07-01T10:00:00.000Z"},
    ]
    msgs = pure_chat_messages(rows, primary_sender_id="1")
    assert len(msgs) == 2
    assert sorted(m["sender"] for m in msgs) == ["a", "b"]


def test_pure_chat_collapses_identityless_duplicate():
    # No identity on either row (a plain transcript echo) -> still collapse to one.
    rows = [
        {"role": "assistant", "content": "same", "timestamp": "2026-07-01T10:00:00.000Z"},
        {"role": "assistant", "content": "same", "timestamp": "2026-07-01T10:00:00.000Z"},
    ]
    msgs = pure_chat_messages(rows)
    assert len(msgs) == 1


def test_channel_tag_only_parsed_from_anchored_user_turn():
    # A <channel …> tag is inbound only when the plugin injected it as a user turn
    # whose whole content is the tag. An assistant message quoting the tag, or a
    # user quoting it mid-prose, must not be re-parsed (else the author's words get
    # relabelled user/web and render as if the channel peer sent them).
    rows = [
        {
            "role": "assistant",
            "content": 'the plugin injects <channel source="web">hi</channel> as a turn',
            "timestamp": "2026-07-01T10:00:00.000Z",
        },
        {
            "role": "user",
            "content": 'can <channel source="web">x</channel> be forged?',
            "timestamp": "2026-07-01T10:00:01.000Z",
        },
        {
            "role": "user",
            "content": '<channel source="chat" chat_id="55" message_id="7" user="friend">hello</channel>',
            "timestamp": "2026-07-01T10:00:02.000Z",
        },
    ]
    msgs = pure_chat_messages(rows, primary_sender_id="1")
    assert msgs[0]["role"] == "assistant"
    assert msgs[0]["content"].startswith("the plugin")
    assert msgs[1]["role"] == "user"
    assert msgs[1]["content"].startswith("can ")
    assert msgs[2]["role"] == "channel"
    assert msgs[2]["sender"] == "friend"
    assert msgs[2]["content"] == "hello"

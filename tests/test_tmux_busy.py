import bridge.tmux as tmux
from bridge.tmux import busy_from_screen, tmux_clear_input


IDLE_PROMPT = "\n".join(
    [
        "some earlier output",
        "> ",
        "  ? for shortcuts",
        "",
    ]
)

GENERATING = "\n".join(
    [
        "some earlier output",
        "* Whirring…",
        "  esc to interrupt",
    ]
)


def test_idle_prompt_is_not_busy():
    assert busy_from_screen(IDLE_PROMPT) is False


def test_generating_screen_is_busy():
    assert busy_from_screen(GENERATING) is True


def test_background_worker_in_status_bar_is_busy_even_when_prompt_idle():
    screen = "\n".join(
        [
            "some earlier output",
            "> ",
            "  ? for shortcuts · 1 agent",
        ]
    )
    assert busy_from_screen(screen) is True
    screen = screen.replace("1 agent", "2 task")
    assert busy_from_screen(screen) is True
    screen = screen.replace("2 task", "3 monitor")
    assert busy_from_screen(screen) is True


def test_worker_mention_in_scrollback_does_not_mark_busy():
    screen = "\n".join(
        [
            "we discussed 1 agent earlier in the transcript",
            "> ",
            "  ? for shortcuts",
        ]
    )
    assert busy_from_screen(screen) is False


def test_stale_busy_marker_in_scrollback_with_idle_prompt():
    screen = "\n".join(
        ["old output"] * 30
        + [
            "  esc to interrupt",
            "> ",
            "  ? for shortcuts",
        ]
    )
    assert busy_from_screen(screen) is False


def _capture_send_keys(monkeypatch):
    sent = []

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["tmux", "send-keys"]:
            sent.append(cmd[-1])

        class R:
            returncode = 0
            stdout = ""

        return R()

    monkeypatch.setattr(tmux.subprocess, "run", fake_run)
    return sent


def test_gentle_clear_input_waits_for_quiet_and_only_clears_line(monkeypatch):
    sent = _capture_send_keys(monkeypatch)
    monkeypatch.setattr(tmux.time, "sleep", lambda s: None)
    busy_states = iter([True, True, False])

    tmux_clear_input("sess", gentle=True, busy_func=lambda name: next(busy_states))

    assert sent == ["C-u"]


def test_gentle_clear_input_gives_up_after_wait_budget(monkeypatch):
    sent = _capture_send_keys(monkeypatch)
    sleeps = []
    monkeypatch.setattr(tmux.time, "sleep", lambda s: sleeps.append(s))

    tmux_clear_input("sess", gentle=True, busy_func=lambda name: True, wait_seconds=5)

    assert sent == ["C-u"]
    assert len(sleeps) == 5


def test_default_clear_input_sends_interrupt_sequence(monkeypatch):
    sent = _capture_send_keys(monkeypatch)
    monkeypatch.setattr(tmux.time, "sleep", lambda s: None)

    tmux_clear_input("sess")

    assert sent == ["C-c", "Escape", "C-u"]

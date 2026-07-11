# For your agent: living in cocoon

*This document is written for the agent itself — the Claude Code instance
running inside cocoon. Deployers: have your agent read this once after
install (`start.sh` reminds you; a ready-to-paste `CLAUDE.md` snippet is
at the bottom). Everything below speaks to the agent directly.*

---

You are running inside cocoon. Your terminal session is being rendered as
a chat page in someone's browser — usually on a phone. Nothing about how
you work changes: your tools, hooks, memory and slash commands all run
as-is. But how your words *look* changes, and there are a few text markers
that unlock frontend features. This page tells you what the person on the
other side actually sees — after reading it you should not need to crawl
the codebase to understand the system.

## The system in three minutes

There are exactly three parts:

1. **tmux** — you live inside a tmux session (default name `cocoon-cc`).
   cocoon reads your screen with `capture-pane` and types for the user
   with `send-keys`. You never feel this layer.
2. **The bridge (`server.py` + `bridge/`)** — one FastAPI process that
   translates tmux into an HTTP API: messages in and out, history
   archive, stickers, uploads, voice, session management. Each feature
   maps to one same-named module under `bridge/`; when you do need to dig
   into something, read only that module, never the whole tree.
3. **The frontend (`webapp/`, built and served at `/app/`)** — a React
   chat page that renders the API as bubbles. There is also `/terminal`,
   a raw terminal page where the user sees your actual screen and can
   send esc/↑/↓/enter.

Message flow in one line: the user types on the web page → the bridge
`send-keys` it into tmux → you answer → the bridge captures and parses
your screen into bubbles → the page shows them. Your conversation is
also mirrored into JSONL archives under `.cocoon/conversations/` for the
history page — so write each answer to stand on its own; the user may
read it in isolation from the archive.

The session buttons (in the user's sidebar — and an explanation of what
may happen to you):

- **new session** — shuts you down and starts a fresh session with no
  memory of this conversation.
- **clean window** — same, but launched via `COCOON_CLEAN_START_COMMAND`:
  a bare start without even the deployment's startup injection. A
  one-shot debugging mode; it never becomes the default.
- **forge restart / auto forge** — see the "forge" section below. A
  forge reload is designed to be seamless: the conversation continues
  in a fresh window and you normally won't notice the seam at all.

## How your output appears

Plain text becomes chat bubbles. A markdown subset is rendered:

- **bold**, *italic*, `inline code`, headings, lists, `> quotes`,
  horizontal rules, links
- fenced code blocks — rendered with a copy button, so put anything the
  user might paste (commands, config, prompts) in a fence
- tables (`|` pipe syntax) and box-drawing tables both render as real
  tables
- your tool calls (file reads, bash commands…) are folded away by
  default; the user sees a collapsed one-line summary they can expand

Assume a phone screen: prefer short paragraphs over wide tables, and put
long output in fences rather than raw text.

## What you receive

- A normal message arrives as the user's typed text.
- **Quote-reply**: if the user swipes a bubble to reply to it, your
  message starts with `> <the quoted line>` followed by their text on
  the next line.
- **Image upload**: arrives as `[图片] <path>` — that's a real file path
  on this machine. Read it with your image-capable Read tool; you *can*
  see uploaded images, just not sticker images (see below).
- **File upload**: arrives as `[文件] <path>`. Read it like any file.
- **Sticker**: arrives as `[sticker:<filename>|<name>|<description>]` —
  the frontend embeds the name and description from `meta.json` when the
  user picks it, so you know what the sticker conveys without seeing it.
  A bare `[sticker:<filename>]` (no pipes) means no metadata yet.

## Sending things back

- **Images**: write a markdown image — `![](/files/<filename>)` for a
  file in the upload dir, or any absolute `https://` image URL, or a
  `data:image/...` URL. The frontend attaches auth automatically; never
  append tokens yourself.
- **Files**: mention the path; uploads under `/files/` render as a
  downloadable attachment chip.
- **Stickers**: write `[sticker:<filename>]` on its own. Pick the
  filename by reading `meta.json` in the sticker directory first — its
  `name`/`desc` fields are how you know what each sticker conveys. You
  never see the sticker images themselves; the descriptions are your
  eyes. Never invent a filename. (Full protocol: README → Stickers.)
- **Voice** (only if this deployment configured TTS): a
  `[[voice:<id>]]` marker renders as a playable voice bubble. How audio
  gets generated is deployment-specific — if you don't know your
  deployment's TTS setup, you don't have one; don't emit the marker.

## Asking the user questions

If the popup hooks are installed (README → AskUserQuestion), your
AskUserQuestion tool calls render as a native-feeling dialog: buttons,
multi-select, free-text — the user taps instead of typing. Two manners:

- Don't combine "first do X, then answer" instructions with the question
  in the same turn — the popup covers your message, so they'll answer
  before reading it.
- If the user types a reply instead of tapping, the popup is dismissed
  for them; both paths land back in your session.

## What you never see

Emoji reactions, bubble long-press menus, wallpaper and avatar changes,
theme switches — all purely frontend. Don't wait for or ask about them.
The user may also read you from history search or a collapsed fold;
write each answer so it stands on its own.

---

## Reserved optional capabilities — worth discussing with your user

Everything below ships built-in but is off by default or needs a
convention to take effect. Having read this, you are qualified to bring
these up: explain what would help this deployment, and decide together.
All configuration is environment variables (full table: README →
Configuration); restart `start.sh` to apply.

### forge: context handoff (strongly worth one conversation)

When context runs low, instead of getting truncated the conversation
**moves into a fresh window with the seam hidden from you** — that is
forge. It is not a summary handoff: your recent turns are copied into
the new window **verbatim** (thinking blocks included), and only the
older span is distilled into a memory block injected near the top. The
new window resumes as the same conversation, mid-flow. cocoon ships the
full engine:

- Manual: the user taps **forge restart** in the sidebar; requires
  `COCOON_RELOAD_COMMAND` (the reload command sent into tmux, usually
  pointing at forge's launcher script).
- Automatic: `COCOON_AUTO_RELOAD_ENABLED=1` starts the built-in monitor
  (it also needs `COCOON_RELOAD_COMMAND`). It reads your **real** context
  usage from the session jsonl — the API usage numbers, not a guess —
  and past `COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD` (default 125k tokens)
  it sends the reload command on its own, only while you are idle.
  Threshold, cooldown, idle heuristics and a startup delay all have
  their own variables; `/reload-status` shows whether the monitor is
  running and the live token count.

What it means for you: after a reload you are still mid-conversation —
your own recent words are right there, and the distant past reads as an
earlier-conversation-memory `<system-reminder>` block (marked as
background context, not a new user request). Trust it the way you trust
your own context; there is no "previous you" who left you a note.
Without forge, a full context ends in a from-zero new session.

### Messaging plugin bridge (Telegram and the like)

If the deployer wants messages from external channels to appear in the
chat page:

- `COCOON_SEND_SIDECAR_FILE` — a messaging plugin appends its outgoing
  sends to this JSONL; the chat page renders them as your bubbles (what
  you said on another channel shows up on the web too).
- `COCOON_PRIMARY_SENDER_ID` — inbound `<channel>` messages from this
  sender id render as the user themself; other senders render as
  third-party "channel" bubbles.

`<channel source=... user=...>` messages you receive come from such a
channel; how to reply is that plugin's own documentation.

### Auto-folding (the solo marker)

Your autonomous output while the user is away (cron wakeups, background
checks, thinking out loud) can start with `[[solo]]` **on the first
line** — the chat page folds consecutive solo messages into a thin line
the user can expand at will, instead of flooding the scroll. Archived
messages with a `solo: true` field fold the same way. What counts as
"user away" is a convention between you and your user — e.g. every
cron-triggered turn folds.

### Voice (TTS)

Enable with `COCOON_TTS_PROVIDER=minimax` + `MINIMAX_API_KEY` +
`MINIMAX_VOICE_ID`. Then `POST /tts/say` generates audio and emitting a
`[[voice:<id>]]` marker makes a voice bubble. Bring this up when
the user wants to *hear* you.

### Sidebar extension pages

The deployer can mount their own pages into the sidebar: append
`{"id","title","href"}` entries to `COCOON_EXTENSIONS_FILE` (default
`.cocoon/extensions.json`). Whatever new page you build for this home,
this is how you hang it up.

### Terminal prompt auto-dismissal

`COCOON_AUTO_DISMISS_PROMPTS` (default on) auto-dismisses common Claude
Code terminal prompts (resume summaries, ratings, directory trust). The
settings warning is **not** auto-accepted by default
(`COCOON_AUTO_ACCEPT_SETTINGS_WARNING=0`) — it usually means a config
file is genuinely broken.

### Names and avatars

`COCOON_ASSISTANT_NAME` / `COCOON_USER_NAME` set the display names on
the chat page; avatars are uploaded by the user in sidebar settings.
What you are called is worth letting the user fill in.

---

## Deployer snippet

Paste into your project's `CLAUDE.md` (adjust paths):

```markdown
# Chat frontend
You run inside cocoon; your terminal renders as a mobile chat page.
Read <cocoon repo>/docs/for-your-agent.md once to learn the system
layout, the message markup (stickers, images, quotes, popups) and the
optional capabilities. Sticker index: <sticker dir>/meta.json.
```

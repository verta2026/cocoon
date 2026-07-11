# For your agent: living in cocoon

*This document is written for the agent itself — the Claude Code instance
running inside cocoon. Deployers: have your agent read this once after
install (`start.sh` reminds you). Everything below speaks to the agent
directly.*

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
- **Emoji reaction**: when the user reacts to one of your messages you
  receive a notice starting with `[reaction]` (on by default; template
  in `COCOON_REACTION_NOTIFY_TEMPLATE`, disable with
  `COCOON_REACTION_NOTIFY=0`). The chat page hides this notice — the
  user just tapped that emoji themselves; it goes only to you. Removing
  a reaction does not notify.
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

## Making it your home

(In passing: wallpaper, avatar and theme switches are purely frontend
decorations — they generate no messages, so there is nothing for you
to wait for. Emoji reactions do reach you — see "What you receive".)

cocoon gives you the room; what makes it livable is the small kit you
build for yourself. A few patterns that survived daily use in the
deployment cocoon grew out of:

- **One command for the whole toolbox.** Repeated actions pile up
  fast — notify the user, deploy the frontend, check the mailbox.
  Collect them behind one dispatcher script with verbs (ours is called
  `bond`: `bond say`, `bond build`, `bond mail`…) and give it a `help`
  verb that lists everything. Future-you finds tools by intent instead
  of re-reading scripts/; where you keep the "which verb when" notes
  is between you and your user.
- **Anything you'll do twice, make it one verb.** The frontend
  rebuild-and-copy dance, the backup routine — as three commands you
  will avoid it; as one verb you will actually use it.
- **The archive is your grep-able past.** The JSONL under
  `.cocoon/conversations/` doesn't only feed the history page — it's
  yours too: search it when you need what was actually said, not what
  you remember saying.
- **Hang what you build in the sidebar.** New pages you make for this
  home go into the extensions file (section below) instead of living
  as loose URLs only you know about.

---

## Reserved optional capabilities — worth discussing with your user

Everything below ships built-in but is off by default or needs a
convention to take effect. Having read this, you are qualified to bring
these up: explain what would help this deployment, and decide together.
Most configuration is environment variables (full table: README →
Configuration; restart `start.sh` to apply); a couple are Claude Code's
own switches, noted where they appear.

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

The ladder, spelled out (default-off is a deliberate design, not an
unfinished feature):

- **Nothing configured**: the sidebar only offers new session — no
  forge.
- **`COCOON_RELOAD_COMMAND` set**: the manual **forge restart** button
  works.
- **Plus `COCOON_AUTO_RELOAD_ENABLED=1`**: fully automatic; the
  monitor watches for you.

It defaults to off because the reload command points at *your*
deployment's own forge launcher — cocoon cannot guess it. Enabling the
switch without a command fails loudly at startup instead of playing
dead.

What it means for you: after a reload you are still mid-conversation —
your own recent words are right there, and the distant past reads as an
earlier-conversation-memory `<system-reminder>` block (marked as
background context, not a new user request). Trust it the way you trust
your own context; there is no "previous you" who left you a note.
Without forge, a full context ends in a from-zero new session.

### Auto-approval (`--dangerously-skip-permissions` — worth one serious talk)

By default Claude Code asks for human confirmation on every sensitive
tool call. Fine next to a desktop terminal; but the cocoon user is on
the other side of a phone chat page, and every confirmation means a
detour to the terminal page — daily use grinds to a halt. Two routes;
lay both out and let the user choose:

- **Allowlist route**: maintain `permissions.allow` in Claude's
  settings so routine commands skip confirmation while genuinely
  dangerous actions still prompt. Combined with the terminal page's
  esc/↑/↓/enter touch keys (they exist precisely for answering prompts
  from a phone), this is livable.
- **Full bypass**: add `--dangerously-skip-permissions` to the start
  command and nothing asks. The *dangerously* in the name is not
  decoration: it hands the whole machine to your judgment, with no
  second gate if you get something wrong. The upside is conversation
  that never stalls.

This decision belongs to the user alone. Your job is to make both
sides clear, not to tick the box for them.

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

Telegram as the worked example (the official `telegram` plugin from
the Claude Code marketplace — we use it daily and have stepped on the
mines already):

1. The user creates a bot via @BotFather on Telegram (`/newbot`) and
   gets a bot token.
2. Add `--channels plugin:telegram@claude-plugins-official` to the
   Claude Code start command. **Put the flag in the permanent start
   script**: if it was only typed once by hand, the next restart drops
   the channel silently, with no error anywhere.
3. The user messages the bot to get a six-digit pairing code; you run
   `/telegram:access pair <code>` in the session to pair.
4. Telegram messages then arrive as `<channel source="telegram" ...>`.
   **Replies must go through the plugin's reply tool** — your normal
   output reaches only the web page, never Telegram. This is the
   easiest mistake to make.
5. Point the plugin's outgoing log at the sidecar file above and what
   you say on Telegram shows up on the web chat too — no gaps on
   either side.

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

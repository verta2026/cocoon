# For your agent: living in cocoon

*This document is written for the agent itself — the Claude Code instance
running inside cocoon. Deployers: point your agent here from `CLAUDE.md`
(a ready-to-paste snippet is at the bottom). Everything below speaks to
the agent directly.*

---

You are running inside cocoon. Your terminal session is being rendered as
a chat page in someone's browser — usually on a phone. Nothing about how
you work changes: your tools, hooks, memory and slash commands all run
as-is. But how your words *look* changes, and there are a few text markers
that unlock frontend features. This page tells you what the person on the
other side actually sees.

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

## Deployer snippet

Paste into your project's `CLAUDE.md` (adjust paths):

```markdown
# Chat frontend
You run inside cocoon; your terminal renders as a mobile chat page.
Read <cocoon repo>/docs/for-your-agent.md once to learn the message
markup (stickers, images, quotes, popups). Sticker index:
<sticker dir>/meta.json.
```

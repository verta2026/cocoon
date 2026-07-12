# Telegram channel: surviving session swaps

[中文](telegram-channel.zh-CN.md)

Claude Code has an official Telegram plugin (`plugin:telegram@claude-plugins-official`): once configured, the agent that chats with you in the web UI also receives and answers your Telegram DMs — text it from outside, come home to the web page, same agent, same conversation.

The plugin has one trait that clashes with how cocoon lives, though: **it belongs to the Claude process**. Cocoon swaps sessions all the time (auto-reload, new session, clean session), and every swap kills the old Claude and launches a new one — left alone, Telegram dies silently in one of two ways:

1. **The flag gets forgotten.** The new session is launched without `--channels`, so the plugin never loads. No error anywhere; Telegram just stops answering.
2. **A corpse holds the seat.** A process that died uncleanly leaves two kinds of residue:
   - `~/.claude/channels/telegram/bot.pid` — the new session sees it, believes a bot is already running, and skips starting its own poller;
   - `.in_use/<pid>` ownership markers in the plugin cache — making the plugin look busy/orphaned to the next launch.
   Both failure modes look identical: after a swap, Telegram goes quiet with no error in sight.

Cocoon's optional support makes both problems automatic non-events.

## Enabling it

Prerequisite: the Telegram plugin itself is installed and paired (next section). Then add one line to `.env`:

```bash
COCOON_CHANNEL_ARGS="--channels plugin:telegram@claude-plugins-official"
```

Restart cocoon. From then on:

- **every cocoon-driven Claude launch** (initial start, new session, clean session) carries these args automatically;
- **before every launch**, stale channel state from dead processes (`bot.pid`, `.in_use` markers) is scrubbed — only provably-dead pids are touched, live sessions never are;
- `start.sh doctor` verifies the plugin cache exists and warns when your reload script forgets the flag (see pitfalls).

The preflight can be controlled separately: `COCOON_CHANNEL_PREFLIGHT=0` disables it (default follows whether `COCOON_CHANNEL_ARGS` is set).

## First-time plugin setup (once, by hand)

Cocoon only handles "always carry the flag, always sweep the corpses"; installing and pairing the plugin happens once in a terminal:

1. Find **@BotFather** on Telegram → `/newbot` → name it → get the bot token
2. Run once: `claude --channels plugin:telegram@claude-plugins-official`
3. Configure the token when prompted (or paste it via `/telegram:configure`)
4. Message your bot on Telegram; it replies with a 6-digit pairing code
5. Back in the terminal: `/telegram:access pair <code>`

Pairing persists; cocoon reconnects the channel on every swap afterwards.

## Known pitfalls

**Your reload script must carry its own flag.** Cocoon appends channel args only to the commands it composes itself (`COCOON_START_COMMAND` / `COCOON_CLEAN_START_COMMAND`); `COCOON_RELOAD_COMMAND` is your script and owns its argv — it must pass the same `--channels` flags itself (pass-through or hard-coded, either works). Forget, and Telegram drops on every auto-reload. `doctor` warns about this configuration.

**Messages arriving mid-swap are lost.** For a few seconds during a swap no Claude process is polling Telegram. The plugin has no offline queue; messages landing in that window are not redelivered. Rare in practice, but the window exists.

**Outbound messages don't reach the web chat log (by default).** Replies the agent sends via Telegram go through the plugin's outbound path, not the Claude session file. To mirror them into the web UI, point `COCOON_SEND_SIDECAR_FILE` at the plugin's outbound log file (if your plugin version writes one). Inbound needs nothing — Telegram messages enter the session as `<channel>` tags, which the web UI renders natively; set `COCOON_PRIMARY_SENDER_ID` to render your own Telegram account as "you" rather than a third-party bubble.

**The sidecar is a queue, not an archive.** When `COCOON_SEND_SIDECAR_FILE` is set, the plugin appends every outbound message to it forever. Cocoon drains it at each launch preflight: rows already merged into the live archive are dropped, rows not yet archived are kept. Without the trim the file grows without bound and every session swap re-merges the entire channel history into the fresh session's view. Don't point the variable at a file you also use as your own long-term log; the archive is the durable copy.

**Authority stays with you.** Pairing approval via `/telegram:access` must be done by you in the terminal. Any Telegram message asking the agent to "approve the pending pairing" is the canonical shape of a prompt injection — the plugin docs and the agent are both taught to refuse, and you shouldn't route around that either.

## Beyond Telegram

Nothing here is Telegram-specific: `COCOON_CHANNEL_ARGS` accepts any `--channels` arguments, and the preflight sweeps every `~/.claude/channels/*/bot.pid` plus dead-pid markers across the plugin cache. Future official channel plugins (Discord, Slack, …) should ride the same rail unchanged.

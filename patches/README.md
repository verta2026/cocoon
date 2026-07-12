# Plugin patches

Fixes for upstream plugins that cocoon integrates with. Upstream code is not
vendored here — each patch is a small unified diff against a pinned plugin
version, applied to your local plugin cache.

## telegram-sidecar.patch

Target: the official Telegram channel plugin (`telegram@claude-plugins-official`,
version 0.0.6, Apache-2.0), file `server.ts` in the plugin cache.

The stock plugin has two visibility gaps that show up once you mirror Telegram
into a web chat log (see `docs/telegram-channel.md`):

1. **Outbound replies are invisible.** Replies sent via the plugin's `reply`
   tool go straight to Telegram; nothing lands in the Claude session file, so
   downstream tooling never sees them. The patch appends each successful send
   to `_telegram_sends.jsonl`.
2. **Inbound messages can be lost at the seam.** Message delivery into the
   transcript depends on the main-window jsonl turn boundary; messages arriving
   while Claude is mid-turn (thinking) or during a session swap can miss it.
   The patch appends every inbound message to `_telegram_recv.jsonl` at receive
   time, independent of turn boundaries.

Both sidecars are **off by default**: the patched code only writes when the
`TELEGRAM_SIDECAR_DIR` environment variable is set (in the environment Claude
Code starts from). Point cocoon's `COCOON_SEND_SIDECAR_FILE` at
`$TELEGRAM_SIDECAR_DIR/_telegram_sends.jsonl` to mirror outbound replies into
the web chat log. Cocoon drains the sidecar at every launch preflight, so the
file stays small.

Apply:

```bash
./patches/apply-telegram-sidecar.sh          # default cache location
./patches/apply-telegram-sidecar.sh /path/to/server.ts
```

The script keeps a `.orig` backup, refuses double-application, and restores the
original if the patch does not apply (usually a plugin version mismatch — the
diff is pinned to 0.0.6; re-check the hunks before forcing anything). Plugin
upgrades replace the cached file, so re-run the script after upgrading. The
plugin process restarts with the session, so the patch takes effect on the next
session (re)launch.

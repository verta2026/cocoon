# Public Core Split Status

This document tracks which reusable pieces have been generalized into cocoon
from a private deployment. It is intentionally allowlist-based: if a feature is
not listed here or in the README, assume it is private instance code until it is
turned into a provider interface or mockable example.

## Synced Route Modules

These modules are part of the reusable bridge core:

- `bridge.upload_routes` - upload and authenticated file serving route wiring
- `bridge.history_routes` - read-only conversation history route wiring
- `bridge.reload_routes` - session/reload control route wiring
- `bridge.ui_routes` - chat, terminal, and optional history UI route wiring
- `bridge.output_routes` - terminal output, raw output, and optional messages
- `bridge.status_routes` - bridge status route wiring
- `bridge.interaction_routes` - start and send route wiring
- `bridge.control_routes` - control-key route wiring
- `bridge.plugin_routes` - generic JSON plugin proxy and optional UI wiring
- `bridge.sticker_routes` - generic named asset route wiring
- `bridge.tts_routes` - optional TTS route wiring
- `bridge.push_routes` - optional push provider route wiring
- `presence.request_policy` - optional presence-style POST auth policy helper
- `presence.static_pages` - optional static page lookup/serving helper
- `presence.json_store` - presence-compatible JSON storage wrapper
- `presence.auth_helpers` - generic cookie/login parsing helpers
- `presence.file_server` - shared-file path, metadata, and attachment helpers
- `presence.settings_file` - editable JSON settings file helpers
- `presence.editor_files` - editor path policy and download header helpers
- `presence.push_subscriptions` - push subscription state payload helpers
- `presence.tts_audio` - TTS audio metadata and file retention helpers
- `presence.oauth_helpers` - OAuth base64, PKCE, auth header, and URL helpers
- `presence.telemetry` - telemetry age, usage formatting, and retention helpers

## Provider Boundaries

These modules define generic shape only. They need an instance provider before
they are useful in a real deployment:

- `bridge.plugin_routes` needs plugin-specific state, API, and optional UI
  handlers.
- `bridge.push_routes` needs push key, status, and subscribe handlers. Cocoon
  does not ship VAPID keys or subscription storage.
- `bridge.tts_routes` uses `bridge.tts`, which is disabled unless a provider is
  configured.
- `presence.request_policy` does not ship private path lists. Deployments pass
  their own token-only and browser-write path sets.
- `presence.static_pages` does not ship private HTML pages. Deployments pass
  their own route-to-file map and root directory.
- `presence.json_store` provides storage mechanics only. It does not ship
  presence data, mailbox/task state, push subscriptions, or other instance
  files.
- `presence.auth_helpers` provides cookie parsing, login body parsing, and
  synthetic password-prefix checks only. It does not ship cookie values, login
  prefixes, or deployment token names.
- `presence.file_server` provides shared-file mechanics only. It does not ship
  uploaded files, private file data, route maps, or a public files page.
- `presence.settings_file` provides file read/write and JSON validation
  mechanics only. It does not ship a settings route, Claude settings path, or
  deployment configuration.
- `presence.editor_files` provides reusable path-safety, filename header,
  content-type, and BOM helpers only. It does not ship editor routes, blocked
  path policy, project roots, or private files.
- `presence.push_subscriptions` provides subscription-list and delivery-record
  state helpers only. It does not ship VAPID keys, push subscription files,
  notification content, webpush provider calls, or live storage.
- `presence.tts_audio` provides request validation, audio-id/path, public
  metadata, latest-record, and file-retention helpers only. It does not ship TTS
  provider calls, API keys, voice IDs, generated audio, or live storage.
- `presence.oauth_helpers` provides OAuth string/PKCE/header/URL mechanics only.
  It does not ship OAuth routes, client IDs, client secrets, tokens, callback
  state, provider endpoints, or live config files.
- `presence.telemetry` provides timestamp age/stale helpers, screentime payload
  formatting, usage record updates, and dated-file retention helpers only. It
  does not ship device data, live usage files, phone app labels, or route
  storage paths.

## Private Route Boundary

Some private deployments may keep instance-only routes for relationship modes,
local toggles, or personal state. Those routes should stay in a private adapter
beside the deployment configuration, not in cocoon core. If a private route
becomes generally useful, first turn it into a neutral provider interface with
synthetic tests.

## Explicitly Not Included

These are private-instance concerns and are not cocoon core:

- personal memory, diary, identity files, relationship state, and conversation
  archives
- personalized pages such as visual-novel, plant, mailbox, todo/task, or study
  views
- game/plugin implementations and their state
- real stickers, uploads, generated audio, browser push subscriptions, OAuth
  state, VAPID keys, cookies, and bearer tokens
- relationship-mode toggles or other private state switches

If one of these areas becomes useful as public structure, add an interface,
mock provider, or example with synthetic data first.

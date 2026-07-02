# Public Core Split Status

This document tracks which reusable pieces have been generalized into cocoon
from a private deployment. It is intentionally allowlist-based: if a feature is
not listed here or in the README, assume it is private instance code until it is
turned into a provider interface or mockable example.

## Synced Route Modules

These modules are part of the reusable bridge core:

- `bridge.upload_routes` - upload and authenticated file serving route wiring
- `bridge.history_routes` - read-only conversation history route wiring,
  with optional day-grouped, per-day merged, and full-text search routes
- `bridge.reload_routes` - session/reload control route wiring
- `bridge.ui_routes` - chat, terminal, and optional history UI route wiring
- `bridge.output_routes` - terminal output, raw output, and optional messages
- `bridge.live_archive` - session-jsonl chat mirror provider for /messages,
  with external-send sidecar merge and double-record dedup
- `bridge.status_routes` - bridge status route wiring
- `bridge.interaction_routes` - start and send route wiring
- `bridge.control_routes` - control-key route wiring
- `bridge.plugin_routes` - generic JSON plugin proxy and optional UI wiring
- `bridge.sticker_routes` - generic named asset route wiring
- `bridge.tts_routes` - optional TTS route wiring
- `bridge.push_routes` - optional push provider route wiring
- `bridge.forge_io` - forge reload hashing and atomic text/JSON I/O helpers
- `bridge.forge_plan_core` - forge event retention and parent-chain helpers
- `bridge.forge_sanitize` - forge event content and runtime-noise filtering
- `bridge.forge_session_files` - forge session jsonl discovery and sort helpers
- `bridge.forge_summary_format` - forge summary input text formatting helpers
- `bridge.forge_summary_injection` - forge summary event injection helpers
- `bridge.forge_turns` - forge final-assistant turn boundary helper
- `bridge.forge_write_files` - forge JSONL, JSON, meta, and manifest writers
- `bridge.summary_provider` - OpenAI-compatible summary provider request helper
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

- `bridge.live_archive` ships transcript-extraction, sidecar-merge, dedup, and
  channel-tag mechanics only. It does not ship real conversation data, sender
  identities, personal noise filters, or marker formats beyond the neutral
  `[[voice:id]]` default; deployments inject their own through parameters and
  the `COCOON_SEND_SIDECAR_FILE` / `COCOON_PRIMARY_SENDER_ID` settings.

- `bridge.plugin_routes` needs plugin-specific state, API, and optional UI
  handlers.
- `bridge.push_routes` needs push key, status, and subscribe handlers. Cocoon
  does not ship VAPID keys or subscription storage.
- `bridge.tts_routes` uses `bridge.tts`, which is disabled unless a provider is
  configured.
- `bridge.forge_io` provides file/hash mechanics only. It does not ship forge
  prompts, summaries, private session paths, manifests, or provider config.
- `bridge.forge_plan_core` provides event role/block checks, real-user
  detection, rough CJK-aware token estimation, retention-window selection,
  optional backward growth to a real-user boundary, orphaned tool-block repair,
  UUID/session rewrites, and parent-chain validation only. It does not ship real
  sessions, summaries, prompts, private project paths, manifests, or provider
  config.
- `bridge.forge_sanitize` provides allowlist-based content block filtering,
  runtime noise filtering, meta/channel handling, and removal of request/usage
  diagnostics only. It does not ship deployment-specific noise markers,
  personal command strings, real sessions, summaries, prompts, or private
  paths.
- `bridge.forge_session_files` provides JSONL reading, project file discovery,
  latest-session selection, and timestamp sort helpers only. It does not ship
  real Claude sessions, archive content, private project paths, or manifests.
- `bridge.forge_summary_format` provides event speaker/timestamp formatting,
  runtime-noise-aware summary input formatting, and middle clamping only. It
  does not ship personal speaker names, deployment-specific noise markers,
  summary prompts, real sessions, summaries, or private paths.
- `bridge.forge_summary_injection` provides synthetic summary-event construction
  and insertion mechanics only. It does not ship summaries, prompts, real
  sessions, private paths, manifests, or provider config.
- `bridge.forge_turns` provides text-bearing final-assistant turn-boundary
  selection, trimmed-tail reporting, and warnings only. It does not ship real
  sessions, summaries, prompts, private paths, manifests, or provider config.
- `bridge.forge_write_files` provides atomic JSONL/JSON write helpers and
  public summary-meta and manifest payload builders only. It does not ship real
  output directories, session files, summaries, manifests, private paths, or
  provider config.
- `bridge.summary_provider` provides provider config loading, request building,
  response parsing, and marker extraction only. It does not ship API keys,
  provider endpoints, private prompts, summary files, or live config.
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

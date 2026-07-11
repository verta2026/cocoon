# Chat frontend

The chat UI is the React/Vite app in `webapp/`, served at `/app/` (build it
with `cd webapp && npm install && npm run build`; Node is build-time only).
`frontend/` holds the static pieces around it: login, the editor page,
config files and bundled placeholder assets.

## Configuration

Configuration is split by exposure. Copy `config.example.js` to `config.js`
for the public basics (site title, API prefix, storage-key prefix, protocol
AI identifier) — it is served unauthenticated because the login page loads
it, so keep identity out. Copy `config.private.example.json` to
`config.private.json` for identity (display names, avatars, channel display
names); the chat page fetches it after login from the authenticated
`/app-config` endpoint and overlays it onto `window.CFG`. The page falls
back to generic defaults when a field is missing, and identity fields left
in an old `config.js` still work (the overlay is additive).

Auth: the page sends `Authorization: Bearer <token>` on every call and
reads the token from `localStorage["<storageNs>_token"]`. The bundled
`login.html` obtains it by POSTing the instance password to `/login`
(deployments that only set a session cookie still work — the token
field in the response is optional).

## API the page talks to

All API paths are prefixed with `CFG.apiBase` — `''` when the reference
server serves both pages and API from one origin, `/bridge` when a
reverse proxy mounts the bridge there.

Provided by the bridge:

| Path | Module |
|---|---|
| `POST /login` | `bridge.auth` (password → bearer token) |
| `GET /chat_pure?since=` | `bridge.output_routes` (optional wiring) + `bridge.live_archive.pure_chat_messages` |
| `POST /send` | `bridge.interaction_routes` |
| `POST /upload`, `GET /files/<name>` | `bridge.upload_routes` |
| `GET/POST /reactions`, `GET /recent-images` | `bridge.reactions` |
| `GET /stickers-meta`, `POST /sticker-upload`, `GET /stickers/<name>` | `bridge.sticker_routes` |
| `GET /editor/ls|read|download`, `POST /editor/write` | `bridge.editor_routes` (used by `editor.html`) |
| `GET/POST /look` | `bridge.look_routes` (cloud-backed wallpaper/avatar choice; localStorage is only a cache) |
| `POST /new-session`, `POST /clean-session` | `bridge.reload_routes` |
| `POST /forge-reload-session` | `bridge.reload_routes` |
| `GET/POST /forge-auto-reload` | `bridge.reload_routes` (unpause needs `force:true` for manual pauses) |

Optional — the page degrades when these 404:

| Path | Purpose |
|---|---|
| `GET /music/url?id=`, `GET /music-stream` | music player resolver — integrator-provided, the reference bridge does not ship one |
| `GET /extensions` | link registry rendered into the sidebar 扩展 block |

The sidebar only hardcodes features this repository actually ships.
Deployment-specific entries (private pages, instance toggles, the music
sheet opener) are declared in `config.js` via `sidebarExtras` — see
`config.example.js` for the schema — or contributed as links through the
`/extensions` registry.

## File editor (`editor.html`)

Companion page for browsing and editing a sandboxed file tree
(`COCOON_EDITOR_ROOT`, default the work dir) through the
`bridge.editor_routes` endpoints: markdown preview, syntax-highlighted
code view, in-place editing of existing files (the editor never creates
or deletes), and download. Paths are confined to the root — lexical
`..`/blocked-prefix filtering plus resolved-path containment, so
symlinks cannot lead outside; `.git`, `node_modules`,
`config.private.json` and friends are blocked by default
(`COCOON_EDITOR_BLOCKED` extends the list) and file size is capped
(`COCOON_EDITOR_MAX_MB`, default 2). The page tints its whole palette —
paper, panels, even syntax-highlight hues — from the average color of
the same wallpaper the chat pages use, so the pages read as one app.

## Serving

The reference server serves `frontend/` itself (`COCOON_SERVE_FRONTEND`,
on by default): `/` → redirect to `/app/`, `/login.html`, `/editor.html`,
`/config.js` (falling back to `config.example.js`), and the bundled placeholder
avatars/wallpaper — all unauthenticated. `config.private.json` is the
exception: it is never served as a static file, only through the
authenticated `/app-config` endpoint. Behind a reverse proxy, serve the
directory as static files instead (but exclude `config.private.json`) and
set `apiBase` accordingly.

## React webapp (`webapp/`)

The webapp is the only chat UI (the classic inline page has been retired).
`/app/` serves `webapp/dist` when it exists; without a build it returns a
short page pointing at the build command. Message markdown/dialect parsing
has unit tests (`npm test`).

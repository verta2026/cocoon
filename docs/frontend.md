# Chat frontend

`frontend/` holds the structured chat UI. It is a single vanilla-JS page
(`chat.html`) plus the Pelle d'Umore mood/fx runtime under `frontend/src/`
(CC BY 4.0 — see `frontend/src/LICENSE`; created by Cu & Lunedì, cunedi.uk).

## Configuration

Copy `config.example.js` to `config.js` next to the pages and fill in your
values. Every personal parameter (names, avatars, storage-key prefix,
protocol AI identifier, channel display names) comes from `window.CFG`;
the page falls back to generic defaults when a field is missing.

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
| `POST /new-session`, `POST /clean-session` | `bridge.reload_routes` |
| `POST /forge-reload-session` | `bridge.reload_routes` |
| `GET/POST /forge-auto-reload` | `bridge.reload_routes` (unpause needs `force:true` for manual pauses) |

Optional — the page degrades when these 404:

| Path | Purpose |
|---|---|
| `GET /music/url?id=`, `GET /music-stream` | music player resolver — integrator-provided, the reference bridge does not ship one |
| `GET/POST /nsfw` | instance-specific mode toggle — integrator-provided |
| `/recall`, `/work`, `/chat-history`, `/terminal` sidebar links | instance pages; `/chat-history` and `/terminal` exist in the reference server |
| `/editor.html`, `/cron.html` sidebar links | companion pages not part of the core bundle |

## Serving

The reference server serves `frontend/` itself (`COCOON_SERVE_FRONTEND`,
on by default): `/` → `chat.html`, `/login.html`, `/config.js` (falling
back to `config.example.js`), `/src/*`, and the bundled placeholder
avatars/wallpaper. Behind a reverse proxy, serve the directory as static
files instead and set `apiBase` accordingly.

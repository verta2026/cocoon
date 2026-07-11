# Extension boundaries

Cocoon is the reusable core for a tmux-backed Claude Code chat UI. Personal
deployments can grow far beyond this repo, but the public core should stay
small, generic, and safe to fork.

Use this guide when moving features from a private deployment back into cocoon.

## Good core candidates

These can usually be generalized and synced into cocoon:

- tmux session lifecycle helpers.
- Configurable Claude start commands and launcher checks.
- Upload storage, authenticated file serving, and size/path guards.
- Generic chat, terminal, status, send, output, and message-rendering routes.
- Prompt auto-dismiss helpers for Claude Code terminal prompts.
- Optional provider interfaces, such as TTS or summarization boundaries.
- Generic history/archive interfaces that do not include real conversation data.
- Generic plugin registry or proxy shapes, without plugin implementations.
- Setup diagnostics and deployment docs that do not assume one private server.

## Keep out of core

These belong in the private deployment, a separate plugin, or a documented
example with fake data:

- Personal pages such as mailbox, todo/task lists, plants, study check-ins, or
  relationship dashboards.
- Game implementations and game-specific state.
- Private memory, diary, identity, relationship notes, real summaries, or
  conversation archives.
- Personal names, avatars, backgrounds, stickers, photos, and generated media.
- OAuth state, cookies, bearer tokens, VAPID keys, API keys, `.env` files, and
  Claude login state.
- Live logs, uploads, embeddings, vector databases, SQLite databases, and cache
  directories from a real deployment.
- Server-specific paths, usernames, domains, systemd units, nginx secrets, and
  provider credentials.

## Adapter rule

If a private feature seems useful, first split it into:

- A generic interface or route shape that can live in cocoon.
- A private adapter that provides real data, credentials, prompts, or assets.

Only the generic side should be copied here. The private adapter should stay in
the deployment repo, or become a separate plugin with its own public test data.

## Verification rule

Each synced slice should be independently reversible:

- Make one narrow change.
- Add or update tests when behavior changes.
- Run a syntax check and the relevant tests.
- Commit before starting the next slice.
- Write down what was intentionally left private.

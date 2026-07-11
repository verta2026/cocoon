// Instance config template — copy to config.js and fill in your values.
// Every page reads window.CFG; missing fields fall back to generic defaults.
//
// config.js is served UNAUTHENTICATED (the login page needs it before any
// token exists), so nothing identifying belongs here. Names, avatars and
// channel-id mappings go in config.private.json (copy from
// config.private.example.json) — the chat page fetches it after login via
// the authenticated /app-config endpoint.
window.CFG = {
  // Prefix for localStorage/IndexedDB keys (change only on a fresh install:
  // existing appearance/theme settings are keyed under the old prefix)
  storageNs: 'cocoon',

  // Marker word for TTS voice bubbles: [[voice:<audio id>]] renders as a
  // playable card (needs the optional TTS routes). Change only if your
  // deployment's history uses a different marker word.
  voiceMarker: 'voice',
  // Identifier the bridge uses for the AI in protocol data (e.g. the `from`
  // field on reactions); must match the bridge configuration
  aiKey: 'ai',
  // Built-in stickers for the emoji panel (optional)
  demoStickers: [],
  // Bridge API prefix ('' when the bridge serves the pages itself;
  // '/bridge' when a reverse proxy mounts it there)
  apiBase: '',
  // Site title
  siteName: 'chat',
  // Extra sidebar entries for deployment-specific pages the public bundle
  // knows nothing about. Kinds:
  //   link   — {icon, label, href}                 navigates to href
  //   toggle — {icon, label, endpoint}             GET endpoint -> {on},
  //            click POSTs {on: !on} to the same endpoint
  //   music  — {icon, label}                       opens the music sheet
  // musicEnabled: set true only if your bridge implements /music/url and
  // /music-stream (the reference bridge does not); the player stays dormant otherwise.
  // legacyStripTags: control tags to strip from historical message bodies,
  // e.g. ['status'] if an earlier deployment injected <status>…</status> markers.
  // section: 'top' pins the entry above the tool list; anything else lands
  // in the 扩展 block. Server-side alternative: the /extensions registry
  // (COCOON_EXTENSIONS_FILE) contributes link entries the same way.
  sidebarExtras: []
};

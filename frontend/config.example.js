// Instance config template — copy to config.js and fill in your values.
// Every page reads window.CFG; missing fields fall back to generic defaults.
window.CFG = {
  // Display names
  aiName: 'AI',
  userName: 'User',
  // Default avatars (can be overridden per-device in chat appearance settings)
  aiAvatar: '/avatar_ai.png',
  userAvatar: '/avatar_user.png',
  // Identifier reported with reactions and other user interactions
  userId: 'user',
  // Prefix for localStorage/IndexedDB keys (change only on a fresh install:
  // existing appearance/theme settings are keyed under the old prefix)
  storageNs: 'cocoon',
  // Identifier the bridge uses for the AI in protocol data (e.g. the `from`
  // field on reactions); must match the bridge configuration
  aiKey: 'ai',
  // External channel id -> display name (e.g. Telegram usernames / chat ids)
  channelNames: {},
  // Built-in stickers for the emoji panel (optional)
  demoStickers: [],
  // Bridge API prefix ('' when the bridge serves the pages itself;
  // '/bridge' when a reverse proxy mounts it there)
  apiBase: '',
  // Site title
  siteName: 'Cocoon'
};

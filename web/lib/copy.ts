export const copy = {
  appName: "Session Doctor",
  tagline: "Runs on your Mac only · Never touches your other chats",
  heroNeedsFix: (bad: number) =>
    `${bad} chat${bad === 1 ? "" : "s"} have old locks. Start with the top one — 1 click each.`,
  heroClean: "Fleet is clean. Zero stale locks. Go build something.",
  locksExplain:
    "These are locked thoughts from an old login. Your messages are safe. Clearing them lets you hit Retry in Hermes.",
  previewTitle: "Preview what I'll clear",
  fixDone: (cleared: number, msgs: number | null) =>
    `Fixed — ${cleared} lock${cleared === 1 ? "" : "s"} cleared, ${msgs ?? ""} messages intact. Go hit Retry in Hermes.`,
  backupFirst: "Full safety copy first, about 2 seconds. Same chat, just unlocked.",
  safestHelp: "Exact match only — stops if anything drifted.",
  bestEffortHelp: "Fits by name if Hermes updated — skips changed columns, keeps going.",
  undoTitle: "Need to undo?",
  busyChat: "This chat is busy — retry when idle.",
  emptyBundles: "No safety copies yet. Pick a chat → Backup to create your first verified copy.",
  searchPlaceholder: "Search chats, IDs…",
} as const;

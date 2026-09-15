# Operations

Daily use, bulk work, undoing, and what to do when the app says no. How it
all works under the hood: [ARCHITECTURE](ARCHITECTURE.md).

## Launching

- **Menu-bar app (recommended):** double-click **Session Doctor** — it ships
  in the repo, so a fresh clone runs on click. A pulse icon appears in the
  menu bar (🟢 running / 🔴 stopped) and the dashboard opens in a fresh
  browser window. First launch only: right-click → Open (unsigned app,
  macOS asks once).
- **First launch builds itself:** with no Python environment or web build
  present, the app sets both up in the background (a few minutes, one time
  only). The menu reads "Setting up first launch…" while it works and the
  dashboard opens when it's ready. You need Python 3.11+ and Node 20+
  installed; if either is missing you'll get a plain-English note naming
  it. Details stream to the log (menu → Show Log).
- **Terminal:** `./run.sh` (add `--headless` to skip the browser,
  `--port N` to pin the port). If the port is already serving, it opens a
  fresh window instead of starting a second server.
- Menu items: **Open Dashboard · Start / Stop · Show Log · Quit & Stop
  Server.** Quitting always stops the server with it. If a fix is running,
  quit asks first.

## The normal fix (one chat, 30 seconds)

1. Flip **Hermes | OpenCode** at the top to the database with the stuck chat.
2. The hero shows what's next ("Next up: … N locks"). Click it, or any red row.
3. The drawer explains what's wrong in plain words. Hit **Preview what I'll
   clear** — you'll see exactly what goes away and the promise of what stays.
4. Hit **Back up + Fix**. A verified safety copy is written first, then the
   locks are cleared in one transaction.
5. The toast confirms (`Fixed — N locks cleared, M messages intact`) with an
   **Undo** button. Go back to the chat in Hermes/OpenCode and hit Retry.
   Same chat, just unlocked.

If the chat shows **CLEAN**, there's nothing to do — the fixer reports
`cleared: 0` and doesn't even take a backup.

## Bulk work (many chats)

Tick checkboxes (header box selects everything your search matches,
Shift-click grabs a range). The bulk bar offers:

- **Backup N** — one safety copy per chat, in order, with progress.
- **Copy IDs** — newline-separated session IDs for your own scripts.
- **Fix N…** — confirms first (chats, total locks, disk estimate), then
  backs up and fixes strictly **one by one**, never in parallel. Cancel
  stops between chats, never mid-fix. Busy chats are skipped with
  "retry when idle"; failed chats stay ticked; fixed ones untick.

Every chat keeps its own bundle, so every bulk fix is individually undoable.

## Undo (restore)

Open the chat → **Need to undo?** → pick a mode:

- **Safest restore** — exact match only. Any drift (schema, counts, content
  hash) aborts and rolls back. Nothing changes.
- **Try-my-best restore** — fits rows back by column name, skips drifted
  columns, and reports every skip as a warning. Still transactional, still
  stashed first.

Restoring stashes current state under `pre-restore/` first, so undoing the
undo works. Only that chat's rows are ever replaced.

## The live-chat guard (OpenCode)

Fixing the chat you're talking in is blocked — it could desync the live
conversation. Mark it once (any drawer → **Mark as my live chat**, or
Settings → **My live chat**) and fix/restore on it are refused everywhere,
with a red banner in the drawer and `Blocked` in the table. Clear the mark
the same way when you move on.

## Safety-copy folders

- Hermes: `backups/<session>_<UTC>/` · OpenCode: `backups/opencode/<…>/`.
- Each folder has its own override in Settings. If a custom folder goes
  missing (moved machines, renamed paths), the app falls back to the
  inside-the-folder default and tells you.
- Never point a folder at a synced drive (iCloud/Dropbox) unless you mean
  for chat contents to leave the machine.

## When it says no (troubleshooting)

| Message | Meaning | What to do |
|---|---|---|
| `holds a live turn lease — retry when idle` (Hermes) / `is busy — retry when idle` (OpenCode) | The chat is mid-turn or compacting | Wait for it to finish, then retry |
| `backup verification failed` | Bundle didn't match source | Retry; if it repeats, check disk space |
| `safe restore refused: … schema drifted` | App updated its database shape | Retry with Try-my-best |
| `restored content hash differs` | Restored text doesn't match manifest | Your pre-restore stash is named in the message — restore that |
| `strip incomplete, rolled back` | Something re-locked mid-fix | Nothing changed; retry when idle |
| `that's the chat you're talking in` (409) | Live-chat guard | Pick any other chat, or clear the mark |
| `mode must be safe or best-effort` (400) | Bad API call | Use one of the two modes |
| `session not found` | Unknown ID | Refresh the list; IDs change on forks |
| `Cannot reach engine` (page banner) | Server isn't running | Start it from the menu bar / `./run.sh` |

## FAQ

**Will this delete my chats?** No. The fix removes lock blobs only;
messages, summaries, tool results, and other chats are proven intact by
content-hash checks on every operation.

**A chat mentions the error but shows CLEAN?** Text about the error isn't a
lock. Only structured sealed envelopes count — that's why the chat needs
nothing.

**How big are backups?** Per-chat bundles, KBs to low MBs. Never full-DB
copies.

**Can I run it on another machine?** Move the whole folder. Backup paths
fall back gracefully; bundles restore by what's inside them, not by path.
Re-run `scripts/build-app.sh` for a fresh menu-bar app.

**Why did this hit me out of nowhere?** The usual cause is an IP change
mid-session — ISP rotation, VPN, travel, new network — while continuing the
same chat. The sealed reasoning was issued to your old address and the
provider rejects it from the new one. Nothing to prevent; that's what the
fixer is for.

**Do I lose context or tool history?** No. Only the secret encrypted
reasoning tokens go. Context, tool calls, commands, and responses stay
exactly as they were — proven by content-hash checks on every operation —
so the chat resumes instead of restarting.

**Where do I see what happened?** Activity view in the app, plus
`activity.jsonl` and `logs/` next to the project (both git-ignored).

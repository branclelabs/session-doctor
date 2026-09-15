# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet. New changes land here first, grouped by type, then move into
the next versioned section at release time.

## [0.1.0] - 2026-09-15

First public release. Session Doctor fixes chats stuck on
`reasoning encrypted_content was not issued to this caller` in two local
databases — Hermes and OpenCode — through one dashboard, with a mandatory
backup before every fix and row-level undo for everything it touches.

### Added

- Hermes engine: read-only session inspection, per-chat backup bundles,
  dry runs, transactional seal strips behind a live-turn lease guard, and
  row-level restores that never touch other sessions.
- OpenCode engine (`ocdb` / `ocbackup` / `ocfix` / `ocrestore`): the same
  inspect → backup → fix → restore loop for `opencode.db`, where the fix
  removes structured encrypted blob keys inside a part's data and leaves
  rows, reply chains, and visible text exactly in place.
- Whole-dashboard **Hermes | OpenCode** source switcher; every feature
  (locks, select-all, bulk queue, drawer, restores, logs) works on both.
- Safest vs Try-my-best restore modes: exact-match restores that abort on
  any drift, plus best-effort restores that fit by column name and report
  what they skipped.
- Multi-select with select-all-follows-search, Shift-range, and a bulk bar:
  Backup N, Copy IDs, and a sequential Fix N queue with per-chat backups,
  progress, cancel-between-chats, and busy-session skips.
- Guided drawer (Inspect → Preview → Fix), Fix-next-up hero queue, command
  palette, activity timeline, stat strip, and motion controls.
- macOS menu-bar app: one pulse icon with live status, Open Dashboard,
  Start / Stop, Show Log, and Quit & Stop Server. Double-click to launch,
  no terminal, no Dock icon.
- `scripts/doctor.sh` service helper (`start` / `stop` / `status` / `open`):
  idempotent serialized starts, health-checked truth, time-bounded helpers.
- `setup.sh`: fresh checkout to runnable in one command (Python env, pytest,
  `npm ci`, production web build, test smoke).
- `jsonbytes` codec: per-chat bundles round-trip BLOB columns byte-for-byte
  instead of crashing the backup.
- Per-chat backup bundles for both backends (KBs, never full-DB copies),
  with manifests, verify-or-abort, transcripts, and auto-cleanup of
  half-written bundles on failure.
- Self-chat guard: the chat you talk in can be marked and is then refused
  for live fix and restore (HTTP 409), in the API and the UI.
- Full test suite (27 tests) covering backup, fix scope, restores, both
  APIs, the blob predicate, prose-never-matches, and busy/lease refusals.

### Changed

- Hermes backups moved from full 200MB snapshots to per-chat row bundles.
  Legacy `state.db.snapshot` bundles still restore — the fixer detects the
  bundle kind by what's inside.
- UI journey: Tk desktop app → inline browser page → Next.js + Tailwind
  dashboard, keeping the same engine and safety rules throughout.
- Two launcher apps merged into the single menu-bar app.

### Fixed

- OpenCode lock detection: the detector checked top-level keys and reported
  every chat clean; it now reads the real nested
  `metadata.openai.reasoningEncryptedContent` path.
- Backup crash (`Object of type bytes is not JSON serializable`) on Hermes
  chats whose message rows carry BLOB columns.
- Same-second backup collisions (unique `-1`, `-2` bundle suffixes).
- Orphan empty bundle folders left behind by failed backups (removed
  automatically on any backup failure).
- Stale absolute backup paths after moving the project folder (portable
  fallback to the inside-the-folder default, with a notice).
- Unbounded helper processes and stuck start locks in the launcher
  (watchdog timeouts, stale-safe lock stealing).

### Removed

- Tkinter desktop UI (could not paint on current macOS).
- Legacy full-snapshot backup path as the default (kept as a restorable
  format, no longer written).
- Design mockups, ~5GB of stray snapshots and build artifacts from the
  working tree (all regenerable via `setup.sh`).

[Unreleased]: https://github.com/branclelabs/session-doctor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/branclelabs/session-doctor/releases/tag/v0.1.0

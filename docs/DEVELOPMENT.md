# Development

Setup, testing rules, the full API reference, and how to ship. For design
rationale see [ARCHITECTURE](ARCHITECTURE.md); for daily use see
[OPERATIONS](OPERATIONS.md).

## Setup

```bash
./setup.sh     # Python 3.11+ and Node 20+ required; builds venv, npm ci,
               # production web build, then runs the test suite
```

Manual equivalents: `PYTHONPATH=src ./.venv/bin/python -m pytest tests/ -q`
for Python, `npm run dev` / `npm run build` / `npx tsc --noEmit` inside
`web/`. Stdlib-only Python — the sole runtime dependency is `pytest` for
tests. Frontend deps are pinned in `web/package-lock.json`.

First-launch runtime setup lives in `scripts/bootstrap.sh`, shared by
`setup.sh` and the app (`doctor.sh` runs it automatically when `.venv` or
`web/out` is missing). Keep it runtime-only: no test installs, no smoke —
`setup.sh` adds those on top.

## Testing rules (non-negotiable)

1. **Live databases are read-only, forever.** Hermes (`~/.hermes/state.db`)
   and OpenCode (`~/.local/share/opencode/opencode.db`) are opened with
   `PRAGMA query_only=ON` outside of explicit fix/restore calls.
2. **Practice on copies.** Snapshot via the SQLite backup API into `/tmp`,
   drill there, delete after. The suite builds throwaway DBs per test.
3. **Prose never matches.** Blob predicates use `json_extract` on key paths
   (`tests/test_oc.py` pins this with a prose regression case).
4. **Every fix proves itself:** recount-to-zero-or-rollback plus a
   visible-text content hash that must not move.

## API reference

Base: `http://127.0.0.1:8765` (`$SESSION_DOCTOR_PORT` / `--port` override).
Bind is loopback-only; there is no auth. Dev CORS allows origin
`http://localhost:3000`; preflights (`OPTIONS`) answer 204. Errors are
`{"error": "<message, max 300 chars>"}`. Unknown routes are 404; engine
failures are 500.

### Hermes — reads

| Method + path | Params | Returns |
|---|---|---|
| `GET /api/health` | — | `{"ok": true, "count": <hermes sessions>}` |
| `GET /api/sessions` | — | `{rows, count, home, backup_root, db_mb, last_backup}` |
| `GET /api/session?id=` | `id` (required) | Full session row + `seals_active`, `seals_total`, `active_msgs`, `kept_items`, `lease` |
| `GET /api/bundles?session=` | `session` (optional filter) | `{bundles: [{dir, session_id, utc, seals_total, active_msgs, snapshot_bytes, verified}]}` newest-first |
| `GET /api/activity` | — | `{events: [{ts, kind, session, detail}]}` newest-first, last 100 |

### Hermes — writes

| Method + path | Body | Returns |
|---|---|---|
| `POST /api/backup` | `{id, verify=true}` | `{dir}` — per-chat bundle; raises before writing on any failure |
| `POST /api/fix` | `{id, verify=true}` | `{cleared, backup}`, or `{cleared: 0, backup: null, note}` when clean (no backup taken) |
| `POST /api/restore` | `{id, dir, mode="safe"}` | `{seals_after, msgs_after, stash, bundle, mode, warnings, skipped_columns}`; 400 on bad mode |
| `POST /api/settings` | `{backup_root}` | `{backup_root, requested, fallback}`; 400 on empty path |

### OpenCode — identical contracts under `/api/oc/*`

`GET /api/oc/sessions` (adds `self_session`), `GET /api/oc/session?id=`
(adds `is_self`), `GET /api/oc/bundles`, `POST /api/oc/backup`,
`POST /api/oc/fix`, `POST /api/oc/restore`, plus
`POST /api/oc/settings` with `{oc_backup_root?, current_session_id?}`
(partial update; empty string clears a key) returning
`{backup_root, self_session}`.

Fixing or restoring the marked live chat answers **409**. Busy sessions
answer 500 with a "retry when idle" message. Unknown IDs answer 500 with
`session not found: …`.

## Configuration

| Name | Where | Default | Controls |
|---|---|---|---|
| `HERMES_HOME` | env | `~/.hermes` | Hermes database location |
| `OPENCODE_HOME` | env | `~/.local/share/opencode` | OpenCode database location |
| `SESSION_DOCTOR_PORT` | env / `--port` | `8765` | API + UI port |
| `backup_root` | `settings.json` | `<project>/backups` | Hermes bundle folder |
| `oc_backup_root` | `settings.json` | `<project>/backups/opencode` | OpenCode bundle folder |
| `oc_current_session_id` | `settings.json` | unset | Live-chat guard mark |

`settings.json` is git-ignored and auto-created. A custom folder that goes
missing falls back to the default with a notice in the response.

## Release process

1. Add entries under `CHANGELOG.md → Unreleased` with every change.
2. Bump `version` in `pyproject.toml` (and the UI footer to match).
3. If `scripts/SessionDoctorBar.swift` changed, rebuild the app with
   `scripts/build-app.sh` and commit the bundle with the same change —
   the shipped `.app` must never go stale.
4. Move `Unreleased` into a dated `## [x.y.z] - YYYY-MM-DD` section.
5. Run the full gate: `./setup.sh` (pytest + build), boot smoke against a
   snapshot copy, `git status` review. Tag the release.

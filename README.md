# Session Doctor

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](CHANGELOG.md)

Fixes local AI chats stuck on `reasoning encrypted_content was not issued to this caller` — for Hermes and OpenCode, from one dashboard, without losing a single message.

## Quick Start

```bash
./setup.sh
./run.sh
```

Pick a red chat → **Preview** → **Back up + Fix** → hit Retry in your chat. Same chat, just unlocked. (Prefer clicks? Build the menu-bar app with `scripts/build-app.sh` and double-click **Session Doctor** — no terminal needed.)

## Features

| Feature | What it does |
|---|---|
| Hermes + OpenCode in one app | Flip the switcher; the whole dashboard follows |
| Lock detection | Finds sealed envelopes Hermes and OpenCode can't retry past |
| Preview before anything | Exact counts plus a diff of what goes and what stays |
| Backup-first fixes | A verified safety copy precedes every fix — no backup, no fix |
| Row-level undo | Safest (exact-match) and Try-my-best restores, stashed first |
| Bulk queue | Select-all, Backup N, and one-by-one Fix N with cancel + skips |
| Live-chat guard | The chat you talk in can never be fixed live |
| Local only | Loopback server, no accounts, nothing leaves your machine |

## Contents

- [Why](#why)
- [Install](#install)
- [Usage](#usage)
- [Configuration](#configuration)
- [Docs](#docs)
- [Contributing](#contributing)
- [License](#license)

## Why

AI providers seal model reasoning in encrypted envelopes bound to the caller
that requested them. Proxies rotate callers, the binding breaks, and the
chat wedges with `reasoning encrypted_content was not issued to this
caller`. The envelopes can't be re-issued — but they can be removed: your
messages, summaries, and tool results don't need them. That's the whole
fix, plus a safety system around it so removal is provable and reversible.

The most common trigger is resuming the **same session ID after your IP
changes** — an ISP rotation, a VPN switching on or off, travel, or just
reconnecting from a new network. The retry re-sends the chat's sealed
reasoning, the provider sees a different requester than the envelopes were
issued to, and the whole session refuses to continue. Nothing is corrupt;
the caller simply isn't the one on the envelope.

This bites Hermes users hardest because Hermes runs OpenCode models through
its proxy — free models like Muse Spark, and paid subscriptions like
OpenCode Zen and OpenCode Go. Session Doctor was built for those users, but
the failure belongs to the mechanism, not the brand: anyone whose provider
binds reasoning to caller identity can hit it, on any model.

## Install

Prerequisites: **Python 3.11+** and **Node 20+**, macOS (menu-bar app) or
anywhere Python runs (terminal).

```bash
git clone https://github.com/branclelabs/session-doctor
cd session-doctor
./setup.sh
```

`setup.sh` builds the Python env, installs test deps, runs `npm ci` plus the
production web build, and smokes the test suite. Nothing global is installed.

## Usage

**One chat:** open a red chat → Preview → Back up + Fix → Retry in the chat.

**Many chats:** tick boxes (header selects your search, Shift-click ranges)
→ Backup N, or Fix N… for the confirmed sequential queue.

**Undo:** any chat → Need to undo? → Safest restore, or Try-my-best when
the database shape drifted. Details and edge cases: [docs/OPERATIONS](docs/OPERATIONS.md).

## Configuration

| Name | Where | Default |
|---|---|---|
| `HERMES_HOME` | environment | `~/.hermes` |
| `OPENCODE_HOME` | environment | `~/.local/share/opencode` |
| `SESSION_DOCTOR_PORT` | environment / `--port` | `8765` |
| `backup_root` | `settings.json` | `<project>/backups` |
| `oc_backup_root` | `settings.json` | `<project>/backups/opencode` |
| `oc_current_session_id` | `settings.json` | unset (marks your live chat) |

Full reference, including every API endpoint: [docs/DEVELOPMENT](docs/DEVELOPMENT.md#api-reference).

## Docs

- [ARCHITECTURE](docs/ARCHITECTURE.md) — engines, safety invariants, data flows, bundle formats
- [OPERATIONS](docs/OPERATIONS.md) — daily use, bulk work, troubleshooting, FAQ
- [DEVELOPMENT](docs/DEVELOPMENT.md) — setup, testing rules, API reference, releases
- [CHANGELOG](CHANGELOG.md) — every notable change, newest first

## Contributing

Small, focused PRs: one behavior per change, tests on throwaway databases
(never live ones), docs updated alongside code. Run `./setup.sh` before
pushing — it gates on the full suite plus the production build.

## License

MIT © Arqam Babar — see [LICENSE](LICENSE).

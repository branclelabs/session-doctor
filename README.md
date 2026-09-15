<div align="center">

<img src="assets/logo.svg" width="96" alt="Session Doctor logo" />

<h1>Session Doctor</h1>

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg?style=flat-square)](CHANGELOG.md)
[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black.svg?style=flat-square&logo=apple&logoColor=white)](#quick-start)

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](#install)
[![Node 20+](https://img.shields.io/badge/Node.js-20+-339933.svg?style=flat-square&logo=nodedotjs&logoColor=white)](#install)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg?style=flat-square&logo=nextdotjs&logoColor=white)](#docs)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4.svg?style=flat-square&logo=tailwindcss&logoColor=white)](#docs)
[![Swift](https://img.shields.io/badge/Swift-F05138.svg?style=flat-square&logo=swift&logoColor=white)](#docs)
[![SQLite](https://img.shields.io/badge/SQLite-003B57.svg?style=flat-square&logo=sqlite&logoColor=white)](#docs)

*Fixes local AI chats stuck on `reasoning encrypted_content was not issued to this caller` — for Hermes and OpenCode, from one dashboard, without losing a single message.*

[![⬇ Download for Mac](https://img.shields.io/badge/Download_for_Mac-black.svg?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/branclelabs/session-doctor/releases/download/v0.1.0/Session-Doctor-mac.zip)
[Quick Start](#quick-start) · [Features](#features) · [How it works](#how-it-works) · [Docs](#docs)

</div>

## Quick Start

**No terminal:** clone the repo, double-click **Session Doctor**, and wait
through the one-time setup — the app builds what it needs in the background
(a few minutes, menu shows "Setting up first launch…") and the dashboard
opens by itself. Your machine needs Python 3.11+ and Node 20+ installed;
if either is missing the app says so plainly instead of failing weirdly.
First launch only: right-click → Open, since the app is unsigned.

**Terminal:**

```bash
./setup.sh
./run.sh
```

Pick a red chat → **Preview** → **Back up + Fix** → hit Retry in your chat. Same chat, just unlocked.

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
- [How it works](#how-it-works)
- [Install](#install)
- [Usage](#usage)
- [Backups & undo](#backups--undo)
- [Project tree](#project-tree)
- [FAQ](#faq)
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

## How it works

Sixty seconds, end to end:

1. **Detect** — the dashboard lists every chat with a count of sealed
   envelopes. Red means stuck, clean means untouched.
2. **Preview** — open a chat to see exact numbers plus a diff of what the
   fix removes and the promise of what stays.
3. **Back up** — one verified per-chat bundle is written first. No backup,
   no fix, no exceptions.
4. **Strip** — the sealed blobs go away inside one database transaction.
   Anything unexpected rolls everything back.
5. **Undo, if ever** — every fix carries its own safety copy; restores put
   back exactly one chat's rows.

How the pieces fit together: [docs/ARCHITECTURE](docs/ARCHITECTURE.md).

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
Double-clicking the app does the runtime half of this automatically on first
launch (it skips only the test smoke).

## Usage

**One chat:** open a red chat → Preview → Back up + Fix → Retry in the chat.

**Many chats:** tick boxes (header selects your search, Shift-click ranges)
→ Backup N, or Fix N… for the confirmed sequential queue.

**Undo:** any chat → Need to undo? → Safest restore, or Try-my-best when
the database shape drifted. Details and edge cases: [docs/OPERATIONS](docs/OPERATIONS.md).

## The menu-bar app

The committed `Session Doctor.app` lives at the repo root — double-click
it in Finder after cloning (never open it; the inside folders are Apple's
packaging, not content). On the web, grab it instead via the
**⬇ Download for Mac** button above: unzip next to the project folder and
double-click.

| Menu item | What it does |
|---|---|
| Open Dashboard | Opens the dashboard in a fresh browser window |
| Start / Stop | Starts or stops the local server (first start builds what's missing) |
| Show Log | Opens the server log for the rare bad day |
| Quit & Stop Server | Quits the app and stops the server with it |

First launch only: right-click → Open, since the app is unsigned. The menu
icon shows 🟢 running / 🔴 stopped, plus "Setting up first launch…" while
a fresh clone builds itself.

## Backups & undo

Every fix writes a per-chat bundle first: the chat's rows (`rows.json`),
a manifest with counts and a content fingerprint, a readable transcript,
and restore instructions. Bundles verify-or-abort before anything is
trusted, and failed backups delete their own folder. Restores replace only
that chat's rows and stash the current state first — undoing the undo
works. Two modes: **Safest** (exact match, aborts on any drift) and
**Try-my-best** (fits by column name, reports every skip).

## Project tree

```
session-doctor/
├── Session Doctor.app   clickable Mac app (committed — don't open it, run it)
├── setup.sh / run.sh    one-command setup · daily launcher
├── src/session_doctor/  engine + API (Hermes, OpenCode, server)
├── tests/               27-test safety net (throwaway DBs only)
├── web/                 Next.js + Tailwind dashboard (built by setup)
├── scripts/             Swift source + service helper + bootstrap
├── docs/                architecture, operations, development
└── settings.json        local config (auto-created, git-ignored)
```

## FAQ

**Will this delete my chats?** No — locks only, proven by content-hash
checks on every operation.

**A chat mentions the error but shows clean?** Text about the error isn't a
lock. Only sealed envelopes count.

**Do I need the terminal?** No. Clone (or download), double-click the app,
wait once. The terminal path exists for developers.

**Does it phone home?** No. Loopback server, no accounts, nothing leaves
your machine.

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

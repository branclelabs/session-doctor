#!/bin/bash
# Session Doctor one-command setup — takes a fresh checkout to runnable.
# Builds the Python env, installs JS deps, compiles the web UI, smokes tests.
# Usage: ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Runtime pieces live in scripts/bootstrap.sh (shared with the app's
# first-launch path, so both stay in sync). This script adds the dev extras.
./scripts/bootstrap.sh || die "bootstrap failed — see above"

say "installing pytest…"
./.venv/bin/pip install -q "pytest>=8,<9"

# --- Smoke -------------------------------------------------------------------
if [[ -d tests ]]; then
  say "running test suite…"
  PYTHONPATH=src ./.venv/bin/python -m pytest tests/ -q
else
  say "no tests/ directory — skipping test smoke"
fi

say "setup complete."
echo "  run:    ./run.sh            (or double-click Session Doctor.app — build with scripts/build-app.sh)"
echo "  doctor: pick a red chat → Preview → Back up + Fix → Retry in Hermes/OpenCode"

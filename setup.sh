#!/bin/bash
# Session Doctor one-command setup — takes a fresh checkout to runnable.
# Builds the Python env, installs JS deps, compiles the web UI, smokes tests.
# Usage: ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# --- Python 3.11+ ------------------------------------------------------------
PYBIN=""
for cand in python3.11 "$HOME/.local/bin/python3.11" python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
      PYBIN="$cand"
      break
    fi
  fi
done
[[ -n "$PYBIN" ]] || die "need Python 3.11+ (tried python3.11, ~/.local/bin/python3.11, python3)"
say "python: $PYBIN ($("$PYBIN" --version 2>&1))"

# --- Node 20+ ----------------------------------------------------------------
command -v node >/dev/null 2>&1 || die "need Node.js 20+ (https://nodejs.org)"
command -v npm >/dev/null 2>&1 || die "need npm (ships with Node.js)"
node -e "process.exit(process.versions.node.split('.')[0] >= 20 ? 0 : 1)" \
  || die "need Node.js 20+, found $(node --version)"
say "node: $(node --version)  npm: $(npm --version)"

# --- Python env --------------------------------------------------------------
if [[ ! -x .venv/bin/python ]]; then
  say "creating .venv…"
  "$PYBIN" -m venv .venv
fi
say "installing pytest…"
./.venv/bin/pip install -q "pytest>=8,<9"

# --- Web UI ------------------------------------------------------------------
say "installing web deps (npm ci)…"
(cd web && npm ci --no-audit --no-fund)
say "building web UI (next build)…"
(cd web && npm run build)

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

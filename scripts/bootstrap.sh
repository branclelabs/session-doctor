#!/bin/bash
# Session Doctor first-launch bootstrap — runtime pieces only, no tests.
# Builds .venv (the app uses stdlib only, so no pip installs are needed to
# run) and the production web UI. Idempotent: skips whatever already exists,
# so re-running is always safe.
# Shared by ./setup.sh (dev path, which adds pytest + test smoke on top)
# and scripts/doctor.sh (which runs this automatically on first start).
# Exit 3 with a MISSING_PREREQ message when Python 3.11+ or Node 20+ is absent.
set -euo pipefail
cd "$(dirname "$0")/.."

# --- Prerequisites (must exist; we never install toolchains for you) --------
PYBIN=""
for cand in python3.11 "$HOME/.local/bin/python3.11" python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
      PYBIN="$cand"
      break
    fi
  fi
done
if [[ -z "$PYBIN" ]]; then
  echo "MISSING_PREREQ: Python 3.11+ is required — install it from python.org (or brew install python@3.11), then relaunch." >&2
  exit 3
fi
if ! command -v node >/dev/null 2>&1; then
  echo "MISSING_PREREQ: Node.js 20+ is required — install it from nodejs.org, then relaunch." >&2
  exit 3
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "MISSING_PREREQ: npm is required (it ships with Node.js — reinstall Node, then relaunch)." >&2
  exit 3
fi
if ! node -e "process.exit(process.versions.node.split('.')[0] >= 20 ? 0 : 1)"; then
  echo "MISSING_PREREQ: Node.js 20+ is required (found $(node --version) — update Node, then relaunch)." >&2
  exit 3
fi

# --- Python env (stdlib runtime needs no pip packages) -----------------------
if [[ ! -x .venv/bin/python ]]; then
  echo "bootstrap: creating Python environment (one-time)…"
  "$PYBIN" -m venv .venv
fi

# --- Production web UI -------------------------------------------------------
if [[ ! -f web/out/index.html ]]; then
  if [[ ! -d web/node_modules ]]; then
    echo "bootstrap: installing web dependencies (one-time, a minute or two — needs network)…"
    (cd web && npm ci --no-audit --no-fund)
  fi
  echo "bootstrap: building web UI (one-time, a minute or two)…"
  (cd web && npm run build)
fi

echo "bootstrap: ready"

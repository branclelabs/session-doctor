#!/bin/bash
# Session Doctor launcher — double-click friendly (see Session Doctor.app).
# Usage: ./run.sh [--headless] [--port N]
#   --headless  start the server without opening a browser (for .app launchers)
#   --port N    fixed port (default $SESSION_DOCTOR_PORT or 8765)
set -euo pipefail
cd "$(dirname "$0")"

PORT="${SESSION_DOCTOR_PORT:-8765}"
HEADLESS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --headless) HEADLESS=1; shift ;;
    --port) PORT="${2:?--port needs a value}"; shift 2 ;;
    --port=*) PORT="${1#--port=}"; shift ;;
    *) echo "Unknown option: $1 (use --headless or --port N)" >&2; exit 2 ;;
  esac
done

PY_PID=""
WEB_PID=""

cleanup() {
  [[ -n "${WEB_PID:-}" ]] && kill "$WEB_PID" 2>/dev/null || true
  [[ -n "$PY_PID" ]] && kill "$PY_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

pick_port() {
  local p="$PORT" tries=0
  while [[ $tries -lt 20 ]]; do
    local body
    if body="$(curl -sf --max-time 4 "http://127.0.0.1:$p/api/health" 2>/dev/null)"; then
      if [[ "$body" == *'"ok": true'* || "$body" == *'"ok":true'* ]]; then
        echo "OURS:$p"
        return 0
      fi
      # Busy but not ours — try the next one.
      p=$((p + 1))
      tries=$((tries + 1))
      continue
    fi
    # Connection refused → free (or server starting). Probe the socket directly.
    if (echo >/dev/tcp/127.0.0.1/$p) 2>/dev/null; then
      p=$((p + 1))
      tries=$((tries + 1))
      continue
    fi
    echo "FREE:$p"
    return 0
  done
  echo "FREE:$PORT"
}

open_url() {
  local url="$1"
  if [[ "$HEADLESS" == "1" ]]; then
    echo "Session Doctor: $url  (headless)"
    return 0
  fi
  # Best effort: brand-new browser window; falls back to default open.
  if [[ -d "/Applications/Google Chrome.app" ]]; then
    open -n -a "Google Chrome" --args --new-window "$url" 2>/dev/null || open "$url" 2>/dev/null || true
  else
    open "$url" 2>/dev/null || python3 -c "import webbrowser; webbrowser.open('$url')" 2>/dev/null || true
  fi
}

pick_result="$(pick_port)"
pick_kind="${pick_result%%:*}"
PORT="${pick_result#*:}"

if [[ "$pick_kind" == "OURS" ]]; then
  echo "Session Doctor already running: http://127.0.0.1:$PORT/"
  open_url "http://127.0.0.1:$PORT/"
  exit 0
fi

source .venv/bin/activate
export PYTHONPATH="$PWD/src"

SESSION_DOCTOR_PORT="$PORT" python3 -m session_doctor.server --port "$PORT" --no-browser &
PY_PID=$!

for _ in $(seq 1 60); do
  if curl -sf --max-time 4 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if [[ -f "web/out/index.html" ]]; then
  echo "Session Doctor: http://127.0.0.1:$PORT/  (prod, single URL — Ctrl+C to stop)"
  open_url "http://127.0.0.1:$PORT/"
  wait "$PY_PID"
else
  echo "Session Doctor API: http://127.0.0.1:$PORT/ (dev mode — starting Next.js…)"
  (cd web && NEXT_PUBLIC_API_URL="http://127.0.0.1:$PORT" npm run dev -- -p 3000) &
  WEB_PID=$!
  for _ in $(seq 1 60); do
    if curl -sf --max-time 4 "http://localhost:3000/" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
  echo "Session Doctor: http://localhost:3000/  (Ctrl+C to stop both)"
  if [[ "$HEADLESS" == "1" ]]; then
    echo "Session Doctor: http://localhost:3000/  (headless)"
  else
    (open "http://localhost:3000/" 2>/dev/null || true) &
  fi
  wait
fi

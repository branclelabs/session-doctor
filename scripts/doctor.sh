#!/bin/bash
# Session Doctor service helper — all launcher logic lives here so it is
# testable without GUI. Thin AppleScript wrappers call these commands.
# Usage: doctor.sh {start|stop|status|open} [--port N]
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$PROJECT_DIR/.session-doctor.pid"
LOGDIR="$PROJECT_DIR/logs"
LOGFILE="$LOGDIR/session-doctor.log"
DEFAULT_PORT="${SESSION_DOCTOR_PORT:-8765}"

PORT="$DEFAULT_PORT"
CMD="${1:-status}"
if [[ "$CMD" == "--port" ]]; then
  PORT="${2:?}"; CMD="${3:-status}"
elif [[ "$1" == *"--port="* ]]; then
  PORT="${1#--port=}"; CMD="${2:-status}"
else
  shift || true
fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="${2:?}"; shift 2 ;;
    --port=*) PORT="${1#--port=}"; shift ;;
    *) shift ;;
  esac
done

health() {
  # Prints health body if OUR server answers, else fails.
  local body
  body="$(curl -sf --max-time 4 "http://127.0.0.1:$PORT/api/health" 2>/dev/null)" || return 1
  [[ "$body" == *'"ok"'* ]] || return 1
  printf '%s' "$body"
}

open_new_window() {
  local url="$1"
  if [[ -d "/Applications/Google Chrome.app" ]]; then
    open -n -a "Google Chrome" --args --new-window "$url" 2>/dev/null && return 0
  fi
  if [[ -d "/Applications/Microsoft Edge.app" ]]; then
    open -n -a "Microsoft Edge" --args --new-window "$url" 2>/dev/null && return 0
  fi
  if [[ -d "/Applications/Brave Browser.app" ]]; then
    open -n -a "Brave Browser" --args --new-window "$url" 2>/dev/null && return 0
  fi
  # Safari: force a brand-new window via AppleScript; fall back to default open.
  if [[ -d "/Applications/Safari.app" ]]; then
    osascript -e 'tell application "Safari" to make new document' >/dev/null 2>&1 || true
  fi
  open "$url" 2>/dev/null || return 1
}

cmd_status() {
  if health >/dev/null; then
    echo "RUNNING http://127.0.0.1:$PORT/"
  else
    echo "STOPPED"
    return 3
  fi
}

cmd_start() {
  if health >/dev/null; then
    echo "ALREADY http://127.0.0.1:$PORT/"
    return 10
  fi
  # Serialize concurrent starters (double-clickers, menu retries): mkdir is
  # atomic; losers wait, then re-check health and report ALREADY.
  # The lock is stale-safe: PID + timestamp inside, stolen when the holder
  # is dead or older than 60s (a killed starter must never wedge starters).
  local lockdir="$PROJECT_DIR/.session-doctor.lock"
  local own_lock=0
  release_lock() {
    if [[ ${own_lock:-0} == 1 ]]; then
      rm -f "$lockdir/pid" 2>/dev/null || true
      rmdir "$lockdir" 2>/dev/null || true
    fi
  }
  local waited=0
  while ! mkdir "$lockdir" 2>/dev/null; do
    if [[ -f "$lockdir/pid" ]]; then
      local holder age now
      holder="$(cut -d' ' -f1 "$lockdir/pid" 2>/dev/null || true)"
      age="$(cut -d' ' -f2 "$lockdir/pid" 2>/dev/null || true)"
      now="$(date +%s)"
      if [[ -n "${holder:-}" ]] && ! kill -0 "$holder" 2>/dev/null; then
        rm -rf "$lockdir" 2>/dev/null || true
        continue
      fi
      if [[ -n "${age:-}" && "$age" =~ ^[0-9]+$ ]] && (( now - age > 900 )); then
        rm -rf "$lockdir" 2>/dev/null || true
        continue
      fi
    fi
    sleep 0.5
    waited=$((waited + 1))
    if health >/dev/null; then
      echo "ALREADY http://127.0.0.1:$PORT/"
      return 10
    fi
    if [[ $waited -ge 1200 ]]; then
      echo "FAILED (another starter is stuck; remove $lockdir and retry)"
      return 1
    fi
  done
  own_lock=1
  echo "$$ $(date +%s)" >"$lockdir/pid"
  if health >/dev/null; then
    echo "ALREADY http://127.0.0.1:$PORT/"
    release_lock
    return 10
  fi
  # Log dir must exist before anything redirects into it (fresh clones
  # have no logs/ yet — without this the bootstrap redirect dies first).
  mkdir -p "$LOGDIR"
  # Fresh clone? Build what's missing first (venv, production web UI).
  # The marker file lets the menu bar show "Setting up…" while this runs.
  # Idempotent — re-running after a killed bootstrap just resumes it.
  if [[ ! -x "$PROJECT_DIR/.venv/bin/python" || ! -f "$PROJECT_DIR/web/out/index.html" ]]; then
    touch "$PROJECT_DIR/.session-doctor.bootstrap"
    if ! "$PROJECT_DIR/scripts/bootstrap.sh" >>"$LOGFILE" 2>&1; then
      rc=$?
      rm -f "$PROJECT_DIR/.session-doctor.bootstrap"
      release_lock
      if [[ $rc -eq 3 ]]; then
        echo "MISSING_PREREQ: one-time setup needs Python 3.11+ and Node 20+ — details in $LOGFILE"
      else
        echo "BOOTSTRAP_FAILED: one-time setup failed — details in $LOGFILE"
        tail -20 "$LOGFILE" 2>/dev/null || true
      fi
      return 1
    fi
    rm -f "$PROJECT_DIR/.session-doctor.bootstrap"
  fi
  # Stale pidfile from a crash/reboot — clear it, health check is the truth.
  rm -f "$PIDFILE"
  mkdir -p "$LOGDIR"
  # Launch headless in the background; keep it alive after the parent exits.
  nohup "$PROJECT_DIR/run.sh" --headless --port "$PORT" >>"$LOGFILE" 2>&1 &
  echo "$!" >"$PIDFILE"
  local i
  # Generous budget (10 min): first launches include the one-time build, and
  # the menu app's start timeout comfortably exceeds it. Exits on first health.
  for i in $(seq 1 1200); do
    if health >/dev/null; then
      echo "STARTED http://127.0.0.1:$PORT/"
      release_lock
      return 0
    fi
    # run.sh died early (bad .venv, port taken by stranger)? Surface the log tail.
    if ! kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
      echo "FAILED"
      tail -20 "$LOGFILE" 2>/dev/null || true
      rm -f "$PIDFILE"
      release_lock
      return 1
    fi
    sleep 0.5
  done
  echo "TIMEOUT"
  release_lock
  return 1
}

cmd_stop() {
  local pid=""
  [[ -f "$PIDFILE" ]] && pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    # Kill the whole process group (run.sh + python + next dev if any).
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    local i
    for i in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.5
    done
    kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
  fi
  # Belt and braces: the run.sh wrapper can die while python survives
  # (orphan). Match OUR exact module + port only — never kill strangers.
  if health >/dev/null; then
    pkill -f "session_doctor.server --port $PORT" 2>/dev/null || true
    local i
    for i in $(seq 1 20); do
      health >/dev/null || break
      sleep 0.5
    done
  fi
  rm -f "$PIDFILE"
  if health >/dev/null; then
    echo "STILL_RUNNING http://127.0.0.1:$PORT/"
    return 1
  fi
  echo "STOPPED"
}

case "$CMD" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  open)
    if health >/dev/null; then
      open_new_window "http://127.0.0.1:$PORT/"
    else
      echo "NOT_RUNNING"
      return 3
    fi
    ;;
  *) echo "Usage: doctor.sh {start|stop|status|open} [--port N]" >&2; exit 2 ;;
esac

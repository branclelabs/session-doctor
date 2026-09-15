"""Read-only queries against state.db. No writes here, ever."""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path

SEAL_NONEMPTY = (
    "codex_reasoning_items IS NOT NULL AND codex_reasoning_items<>'' "
    "AND codex_reasoning_items<>'[]' AND codex_reasoning_items<>'null'"
)


def resolve_home() -> Path:
    env = os.environ.get("HERMES_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".hermes"


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    # NOTE: `mode=ro` URI opens fail on WAL-mode DBs whose -wal/-shm sidecars
    # are absent (e.g. after another tool checkpointed). Plain open +
    # query_only reads anywhere and still blocks writes.
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def list_sessions(db_path: Path, include_archived: bool = False) -> list[dict]:
    q = """
    SELECT id, title, pinned, archived, hidden, model, message_count,
           last_activity_at, parent_session_id
    FROM sessions
    """
    if not include_archived:
        q += " WHERE COALESCE(archived,0)=0 AND COALESCE(hidden,0)=0"
    q += " ORDER BY COALESCE(pinned,0) DESC, COALESCE(last_activity_at,0) DESC LIMIT 500"
    con = _connect_ro(db_path)
    try:
        rows = [dict(r) for r in con.execute(q)]
        seals: dict[str, tuple[int, int]] = {}
        for sid, active_n, total_n in con.execute(
                f"SELECT session_id, SUM(CASE WHEN active=1 THEN 1 ELSE 0 END), "
                f"COUNT(*) FROM messages WHERE {SEAL_NONEMPTY} GROUP BY session_id"):
            seals[sid] = (active_n or 0, total_n)
        for r in rows:
            active_n, total_n = seals.get(r["id"], (0, 0))
            r["seals_active"] = active_n
            r["seals_total"] = total_n
            r["needs_fix"] = bool(active_n)
        return rows
    finally:
        con.close()


def session_detail(db_path: Path, session_id: str) -> dict:
    con = _connect_ro(db_path)
    try:
        s = con.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if s is None:
            raise KeyError(f"session not found: {session_id}")
        d = dict(s)
        d["seals_active"] = con.execute(
            f"SELECT COUNT(*) FROM messages WHERE session_id=? AND active=1 AND {SEAL_NONEMPTY}",
            (session_id,)).fetchone()[0]
        d["seals_total"] = con.execute(
            f"SELECT COUNT(*) FROM messages WHERE session_id=? AND {SEAL_NONEMPTY}",
            (session_id,)).fetchone()[0]
        d["active_msgs"] = con.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id=? AND active=1", (session_id,)).fetchone()[0]
        d["kept_items"] = con.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id=? AND codex_message_items IS NOT NULL "
            "AND codex_message_items<>'' AND codex_message_items<>'[]'", (session_id,)).fetchone()[0]
        return d
    finally:
        con.close()


def live_lease(db_path: Path, session_id: str) -> bool:
    """True if a turn lease row exists for session. Schema varies — inspect, don't assume."""
    con = _connect_ro(db_path)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(session_turn_leases)")]
        if not cols:
            return False
        candidates = [c for c in cols
                      if "session" in c.lower() or "conversation" in c.lower()]
        for c in candidates:
            try:
                n = con.execute(
                    f"SELECT COUNT(*) FROM session_turn_leases WHERE {c}=?", (session_id,)).fetchone()[0]
                if n:
                    return True
            except Exception:
                continue
        return False
    finally:
        con.close()


def session_content_hash(db_path: Path, session_id: str) -> str:
    """sha256 over ordered (id, content, codex_message_items) — proves visible text unchanged."""
    import hashlib
    con = _connect_ro(db_path)
    try:
        h = hashlib.sha256()
        for row in con.execute("SELECT id, content, codex_message_items FROM messages "
                               "WHERE session_id=? ORDER BY id", (session_id,)):
            h.update(repr((row[0], row[1], row[2])).encode("utf-8", "replace"))
        return h.hexdigest()
    finally:
        con.close()

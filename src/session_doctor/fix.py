"""In-place seal strip. Backup MUST succeed before calling strip_seals."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from .db import SEAL_NONEMPTY, live_lease, session_detail


def dry_run(db_path: Path, session_id: str) -> dict:
    d = session_detail(db_path, session_id)
    return {"seals_active": d["seals_active"], "seals_total": d["seals_total"],
            "active_msgs": d["active_msgs"], "kept_items": d["kept_items"]}


def strip_seals(db_path: Path, session_id: str) -> dict:
    if live_lease(db_path, session_id):
        raise RuntimeError(f"session {session_id} holds a live turn lease — retry when idle")
    session_detail(db_path, session_id)  # raises KeyError if unknown
    con = sqlite3.connect(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            f"UPDATE messages SET codex_reasoning_items=NULL WHERE session_id=? AND {SEAL_NONEMPTY}",
            (session_id,))
        cleared = cur.rowcount
        after = con.execute(
            f"SELECT COUNT(*) FROM messages WHERE session_id=? AND {SEAL_NONEMPTY}",
            (session_id,)).fetchone()[0]
        if after != 0:
            con.rollback()
            raise RuntimeError(f"strip incomplete, rolled back (remaining={after})")
        con.commit()
        return {"cleared": cleared, "seals_after": after}
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()

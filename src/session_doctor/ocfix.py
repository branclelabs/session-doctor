"""In-place blob strip for OpenCode. Backup MUST succeed before calling strip_blobs."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from .ocdb import BLOB_NONEMPTY, busy, session_detail


def dry_run(db_path: Path, session_id: str) -> dict:
    d = session_detail(db_path, session_id)
    return {"blobs": d["blobs"], "seals_active": d["blobs"], "seals_total": d["blobs"],
            "msgs": d["msgs"], "active_msgs": d["msgs"], "parts": d["parts"]}


def strip_blobs(db_path: Path, session_id: str) -> dict:
    if busy(db_path, session_id):
        raise RuntimeError(f"session {session_id} is busy (compacting or DB locked) — retry when idle")
    session_detail(db_path, session_id)  # raises KeyError if unknown
    con = sqlite3.connect(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        # Remove ONLY the sealed blob keys; rows, ids, message chains,
        # visible text, summaries and itemIds stay exactly where they are.
        # (Keeping itemId while dropping content mirrors the provider's own
        # pattern for redacted reasoning: reference without payload.)
        cur = con.execute(
            "UPDATE part SET data = ("
            "SELECT json_remove(data,'$.metadata.openai.reasoningEncryptedContent',"
            "'$.encrypted_content','$.redacted_thinking','$.reasoning_content') "
            "FROM part AS p2 WHERE p2.id = part.id) "
            f"WHERE session_id=? AND {BLOB_NONEMPTY}",
            (session_id,))
        cleared = cur.rowcount
        after = con.execute(
            f"SELECT COUNT(*) FROM part WHERE session_id=? AND {BLOB_NONEMPTY}",
            (session_id,)).fetchone()[0]
        if after != 0:
            con.rollback()
            raise RuntimeError(f"strip incomplete, rolled back (remaining={after})")
        con.commit()
        return {"cleared": cleared, "blobs_after": after, "seals_after": after}
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()

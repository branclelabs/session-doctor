"""Read-only queries against OpenCode's opencode.db. No writes here, ever.

Schema (opencode): session(id, title, directory, model, time_created,
time_updated, time_compacting, time_archived, ...) 1 -> N message(id,
session_id, data) 1 -> N part(id, message_id, session_id, data).

There is no sealed-envelope column like Hermes' codex_reasoning_items.
The strippable unit is a STRUCTURED blob key inside part.data JSON, at
metadata.openai.reasoningEncryptedContent (the provider-issued sealed
reasoning that a rotated caller gets rejected for). Legacy top-level keys
(encrypted_content / redacted_thinking / reasoning_content) are kept as a
harmless fallback — never observed live, but matched if ever written.
Prose that merely mentions those words never matches: the predicate uses
json_extract on the key path, never LIKE.
"""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path

# (json path, must-be-nonempty-string)
BLOB_PATHS = (
    "$.metadata.openai.reasoningEncryptedContent",
    "$.encrypted_content",
    "$.redacted_thinking",
    "$.reasoning_content",
)

BLOB_NONEMPTY = " OR ".join(
    f"(json_extract(data,'{p}') IS NOT NULL AND json_extract(data,'{p}')<>'')"
    for p in BLOB_PATHS
)
BLOB_NONEMPTY = f"({BLOB_NONEMPTY})"


def resolve_oc_home() -> Path:
    env = os.environ.get("OPENCODE_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".local" / "share" / "opencode"


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    # Same rationale as Hermes db.py: plain open + query_only survives
    # missing WAL sidecars and still blocks writes.
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def _db_exists(db_path: Path) -> None:
    if not db_path.exists() or db_path.stat().st_size == 0:
        raise RuntimeError(f"refusing read: {db_path} missing or empty")


def list_sessions(db_path: Path, include_archived: bool = False) -> list[dict]:
    q = """
    SELECT id, title, directory, model, time_created, time_updated,
           time_compacting, time_archived
    FROM session
    """
    if not include_archived:
        q += " WHERE time_archived IS NULL"
    q += " ORDER BY COALESCE(time_updated,0) DESC LIMIT 500"
    _db_exists(db_path)
    con = _connect_ro(db_path)
    try:
        rows = [dict(r) for r in con.execute(q)]
        counts: dict[str, dict] = {}
        for sid, n in con.execute(
                "SELECT session_id, COUNT(*) FROM message GROUP BY session_id"):
            counts.setdefault(sid, {})["msgs"] = n
        for sid, n in con.execute(
                "SELECT session_id, COUNT(*) FROM part GROUP BY session_id"):
            counts.setdefault(sid, {})["parts"] = n
        for sid, n in con.execute(
                f"SELECT session_id, COUNT(*) FROM part WHERE {BLOB_NONEMPTY} GROUP BY session_id"):
            counts.setdefault(sid, {})["blobs"] = n
        out = []
        for r in rows:
            c = counts.get(r["id"], {})
            out.append({
                "id": r["id"],
                "title": r["title"],
                "pinned": 0,
                "archived": 1 if r["time_archived"] else 0,
                "hidden": 0,
                "model": r["model"],
                "directory": r["directory"],
                "message_count": c.get("msgs", 0),
                "part_count": c.get("parts", 0),
                "last_activity_at": (r["time_updated"] or 0) / 1000,
                "parent_session_id": None,
                "seals_active": c.get("blobs", 0),
                "seals_total": c.get("blobs", 0),
                "needs_fix": bool(c.get("blobs", 0)),
            })
        return out
    finally:
        con.close()


def session_detail(db_path: Path, session_id: str) -> dict:
    _db_exists(db_path)
    con = _connect_ro(db_path)
    try:
        s = con.execute("SELECT * FROM session WHERE id=?", (session_id,)).fetchone()
        if s is None:
            raise KeyError(f"session not found: {session_id}")
        d = dict(s)
        d["blobs"] = con.execute(
            f"SELECT COUNT(*) FROM part WHERE session_id=? AND {BLOB_NONEMPTY}",
            (session_id,)).fetchone()[0]
        d["seals_active"] = d["blobs"]
        d["seals_total"] = d["blobs"]
        d["msgs"] = con.execute(
            "SELECT COUNT(*) FROM message WHERE session_id=?", (session_id,)).fetchone()[0]
        d["active_msgs"] = d["msgs"]
        d["parts"] = con.execute(
            "SELECT COUNT(*) FROM part WHERE session_id=?", (session_id,)).fetchone()[0]
        d["kept_items"] = d["parts"] - d["blobs"]
        # Hermes-compatible aliases for shared UI code.
        d["message_count"] = d["msgs"]
        d["last_activity_at"] = (d.get("time_updated") or 0) / 1000
        d["model"] = d.get("model")
        return d
    finally:
        con.close()


def busy(db_path: Path, session_id: str) -> bool:
    """True if the session is being compacted or the DB is write-locked.

    OpenCode has no turn-lease table, so: compaction flag first, then a
    BEGIN IMMEDIATE + ROLLBACK probe (takes no data, changes nothing) to
    detect an active writer. Fail closed on any doubt.
    """
    _db_exists(db_path)
    con = _connect_ro(db_path)
    try:
        row = con.execute(
            "SELECT time_compacting FROM session WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(f"session not found: {session_id}")
        if row[0]:
            return True
    finally:
        con.close()
    probe = sqlite3.connect(db_path)
    try:
        probe.execute("BEGIN IMMEDIATE")
        probe.rollback()
        return False
    except sqlite3.OperationalError:
        return True
    finally:
        probe.close()


def session_content_hash(db_path: Path, session_id: str) -> str:
    """sha256 over ordered (part.id, type, text) — proves visible chat unchanged.

    Deliberately excludes blob keys, so a blob strip is hash-stable —
    the same guarantee Hermes' hash gives over (id, content, items).
    """
    import hashlib
    import json
    _db_exists(db_path)
    con = _connect_ro(db_path)
    try:
        h = hashlib.sha256()
        for pid, data in con.execute(
                "SELECT id, data FROM part WHERE session_id=? ORDER BY id", (session_id,)):
            try:
                d = json.loads(data)
            except Exception:
                d = {}
            if not isinstance(d, dict):
                d = {}
            h.update(repr((pid, d.get("type"), d.get("text", ""))).encode("utf-8", "replace"))
        return h.hexdigest()
    finally:
        con.close()

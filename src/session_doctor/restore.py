"""Row-level restore: put back ONE session's exact rows from a bundle.

Never whole-file replace — other sessions kept changing after the backup.
Restore stashes current state first, so undoing the undo works.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

from . import backup as backupmod
from . import db as dbmod
from . import jsonbytes as jsonbytesmod


def _bundle_kind(bundle_dir: Path, man: dict) -> str:
    """'rows' for per-chat JSON bundles, 'snapshot' for legacy full copies."""
    if man.get("kind") == "rows" or (bundle_dir / "rows.json").exists():
        return "rows"
    return "snapshot"


def _load_manifest(bundle_dir: Path) -> dict:
    man_file = bundle_dir / "manifest.json"
    if not man_file.exists():
        raise FileNotFoundError(f"not a restore bundle (no manifest.json): {bundle_dir}")
    try:
        man = json.loads(man_file.read_text())
    except json.JSONDecodeError:
        raise FileNotFoundError(f"not a restore bundle (bad manifest.json): {bundle_dir}")
    if _bundle_kind(bundle_dir, man) == "rows":
        man["kind"] = "rows"
        return man
    man["kind"] = "snapshot"
    # Prefer the bundle-local snapshot so moved/copied bundles (and bundles
    # whose manifest holds an absolute path from another machine) restore
    # from the right file. Fall back to the recorded absolute path only if
    # the bundle-local file is missing (legacy bundles).
    local = bundle_dir / str(man.get("snapshot_rel") or "state.db.snapshot")
    if local.exists():
        man["snapshot"] = str(local)
        return man
    alt = bundle_dir / "state.db.snapshot"
    if alt.exists():
        man["snapshot"] = str(alt)
        return man
    snap = Path(man["snapshot"])
    if snap.exists():
        return man
    raise FileNotFoundError(f"bundle snapshot missing: {man['snapshot']}")


def _table_cols(con: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def list_bundles(root: Path) -> list[dict]:
    """Newest-first bundle summaries under root (skips dirs without manifest)."""
    found = []
    if not root.exists():
        return found
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            man = _load_manifest(child)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            continue
        found.append({"dir": child, "session_id": man.get("session_id", "?"),
                      "utc": man.get("utc", ""), "seals_total": man.get("seals_total"),
                      "active_msgs": man.get("active_msgs"),
                      "snapshot_bytes": man.get("snapshot_bytes", 0),
                      "verified": man.get("verified", False)})
    return sorted(found, key=lambda b: b["utc"], reverse=True)


def _restore_rows(home: Path, session_id: str, bundle_dir: Path, man: dict,
                  pre_restore_root: Path | None, mode: str) -> dict:
    """Restore from a per-chat rows.json bundle (same guarantees, no snapshot)."""
    live = home / "state.db"
    if dbmod.live_lease(live, session_id):
        raise RuntimeError(f"session {session_id} holds a live turn lease — retry when idle")
    stash_root = pre_restore_root or (bundle_dir.parent / "pre-restore")
    stash = backupmod.backup_session_rows(home, session_id, stash_root, verify=False)
    bundle = jsonbytesmod.loads((bundle_dir / "rows.json").read_text())
    warnings: list[str] = []
    con = sqlite3.connect(live)
    try:
        live_cols = {t: _table_cols(con, t) for t in ("sessions", "messages")}
        src = {"sessions": bundle["scols"], "messages": bundle["mcols"]}
        if mode == "safe":
            for t in ("sessions", "messages"):
                if src[t] != live_cols[t]:
                    raise RuntimeError(
                        f"safe restore refused: {t} schema drifted. "
                        "Use Try-my-best mode to fit by column name.")
            use = dict(src)
            skipped: dict[str, list[str]] = {"sessions": [], "messages": []}
        else:
            use = {t: [c for c in src[t] if c in live_cols[t]] for t in src}
            skipped = {t: ([c for c in src[t] if c not in live_cols[t]]
                           + [c for c in live_cols[t] if c not in src[t]]) for t in src}
            for t, cols in skipped.items():
                if cols:
                    warnings.append(f"skipped {t} cols: {', '.join(cols)}")
            if not use["sessions"] or (bundle["messages"] and not use["messages"]):
                raise RuntimeError("best-effort restore: no common columns — refusing")

        def _insert(table: str, rows: list[list]) -> None:
            cols = use[table]
            idx = [src[table].index(c) for c in cols]
            col_sql = ", ".join(f'"{c}"' for c in cols)
            ph = ",".join("?" * len(cols))
            data = [tuple(r[i] for i in idx) for r in rows]
            if table == "sessions":
                con.execute(f'INSERT INTO main.sessions ({col_sql}) VALUES ({ph})', data[0])
            elif data:
                con.executemany(f'INSERT INTO main.messages ({col_sql}) VALUES ({ph})', data)

        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM main.messages WHERE session_id=?", (session_id,))
        con.execute("DELETE FROM main.sessions WHERE id=?", (session_id,))
        _insert("sessions", [bundle["session"]])
        _insert("messages", bundle["messages"])
        got_seals = con.execute(
            f"SELECT COUNT(*) FROM main.messages WHERE session_id=? AND "
            f"{dbmod.SEAL_NONEMPTY}", (session_id,)).fetchone()[0]
        got_msgs = con.execute("SELECT COUNT(*) FROM main.messages WHERE session_id=? "
                               "AND active=1", (session_id,)).fetchone()[0]
        if got_seals != man.get("seals_total") or got_msgs != man.get("active_msgs"):
            msg = (f"restore verification: seals={got_seals} vs {man.get('seals_total')}, "
                   f"msgs={got_msgs} vs {man.get('active_msgs')}")
            if mode == "safe":
                con.rollback()
                raise RuntimeError(msg + " — rolled back")
            warnings.append(msg + " (kept anyway in best-effort mode)")
        con.commit()
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()
    after = dbmod.session_detail(live, session_id)
    after_hash = dbmod.session_content_hash(live, session_id)
    if after_hash != man.get("content_sha256"):
        msg = "restored content hash differs from manifest"
        if mode == "safe":
            raise RuntimeError(msg + f" — pre-restore stash kept at {stash['dir']}")
        warnings.append(msg + " (kept anyway in best-effort mode)")
    return {"seals_after": after["seals_total"], "msgs_after": after["active_msgs"],
            "stash": stash["dir"], "bundle": bundle_dir, "mode": mode,
            "warnings": warnings,
            "skipped_columns": skipped if mode == "best-effort" else {"sessions": [], "messages": []}}


def restore_session(home: Path, session_id: str, bundle_dir: Path,
                    pre_restore_root: Path | None = None,
                    mode: str = "safe") -> dict:
    """Row-level restore with two modes (user picks in UI):

    - mode="safe": exact match only. Aborts on any schema drift or any
      seals/msgs/content-hash mismatch (rollback, no changes).
    - mode="best-effort": fits back in by column name. Skips columns that
      no longer exist, restores common columns, reports mismatches as
      warnings instead of aborting. Still transactional + stashed.
    """
    if mode not in ("safe", "best-effort"):
        raise ValueError(f"unknown restore mode: {mode!r}")
    man = _load_manifest(bundle_dir)
    if man.get("session_id") != session_id:
        raise KeyError(f"bundle is for {man.get('session_id')}, not {session_id}")
    if man.get("kind") == "rows":
        return _restore_rows(home, session_id, bundle_dir, man,
                             pre_restore_root, mode)
    snap = Path(man["snapshot"])
    live = home / "state.db"
    if dbmod.live_lease(live, session_id):
        raise RuntimeError(f"session {session_id} holds a live turn lease — retry when idle")
    # stash current state first: restoring is itself reversible
    stash_root = pre_restore_root or (bundle_dir.parent / "pre-restore")
    stash = backupmod.backup_session_rows(home, session_id, stash_root, verify=False)
    con = sqlite3.connect(live)
    warnings: list[str] = []
    try:
        # read bundle rows over their own connection (no ATTACH: avoids lock coupling)
        src = sqlite3.connect(snap)
        try:
            src_cols_sess = _table_cols(src, "sessions")
            src_cols_msg = _table_cols(src, "messages")
            sess_rows = src.execute(
                "SELECT * FROM sessions WHERE id=?", (session_id,)).fetchall()
            msg_rows = src.execute(
                "SELECT * FROM messages WHERE session_id=?", (session_id,)).fetchall()
        finally:
            src.close()
        if not sess_rows:
            raise KeyError(f"session {session_id} not present in bundle snapshot")
        live_tmp = sqlite3.connect(live)
        try:
            live_cols_sess = _table_cols(live_tmp, "sessions")
            live_cols_msg = _table_cols(live_tmp, "messages")
        finally:
            live_tmp.close()
        if mode == "safe":
            # Safest: abort on ANY schema drift.
            if src_cols_sess != live_cols_sess:
                raise RuntimeError(
                    "safe restore refused: sessions schema drifted "
                    f"(snapshot {len(src_cols_sess)} cols vs live {len(live_cols_sess)}). "
                    "Use Try-my-best mode to fit by column name.")
            if src_cols_msg != live_cols_msg:
                raise RuntimeError(
                    "safe restore refused: messages schema drifted "
                    f"(snapshot {len(src_cols_msg)} cols vs live {len(live_cols_msg)}). "
                    "Use Try-my-best mode to fit by column name.")
        # Column lists for INSERT: safe = exact order, best-effort = intersection.
        if mode == "safe":
            sess_cols = src_cols_sess
            msg_cols = src_cols_msg
            sess_idx = list(range(len(sess_cols)))
            msg_idx = list(range(len(msg_cols)))
            skipped: dict[str, list[str]] = {"sessions": [], "messages": []}
        else:
            sess_cols = [c for c in src_cols_sess if c in live_cols_sess]
            msg_cols = [c for c in src_cols_msg if c in live_cols_msg]
            skipped = {
                "sessions": [c for c in src_cols_sess if c not in live_cols_sess]
                + [c for c in live_cols_sess if c not in src_cols_sess],
                "messages": [c for c in src_cols_msg if c not in live_cols_msg]
                + [c for c in live_cols_msg if c not in src_cols_msg],
            }
            if skipped["sessions"]:
                warnings.append(f"skipped sessions cols: {', '.join(skipped['sessions'])}")
            if skipped["messages"]:
                warnings.append(f"skipped messages cols: {', '.join(skipped['messages'])}")
            if not sess_cols or not msg_cols and msg_rows:
                raise RuntimeError("best-effort restore: no common columns — refusing")
            sess_idx = [src_cols_sess.index(c) for c in sess_cols]
            msg_idx = [src_cols_msg.index(c) for c in msg_cols]
        sess_col_sql = ", ".join(f'"{c}"' for c in sess_cols)
        msg_col_sql = ", ".join(f'"{c}"' for c in msg_cols)
        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM main.messages WHERE session_id=?", (session_id,))
        con.execute("DELETE FROM main.sessions WHERE id=?", (session_id,))
        con.execute(f'INSERT INTO main.sessions ({sess_col_sql}) VALUES ({",".join("?" * len(sess_cols))})',
                    tuple(sess_rows[0][i] for i in sess_idx))
        if msg_rows:
            con.execute(f'INSERT INTO main.messages ({msg_col_sql}) VALUES ({",".join("?" * len(msg_cols))})',
                        tuple(msg_rows[0][i] for i in msg_idx))
            if len(msg_rows) > 1:
                con.executemany(
                    f'INSERT INTO main.messages ({msg_col_sql}) VALUES ({",".join("?" * len(msg_cols))})',
                    [tuple(r[i] for i in msg_idx) for r in msg_rows[1:]])
        # verify inside the transaction window: read-your-writes
        got_seals = con.execute(
            f"SELECT COUNT(*) FROM main.messages WHERE session_id=? AND "
            f"{dbmod.SEAL_NONEMPTY}", (session_id,)).fetchone()[0]
        got_msgs = con.execute("SELECT COUNT(*) FROM main.messages WHERE session_id=? "
                               "AND active=1", (session_id,)).fetchone()[0]
        if got_seals != man.get("seals_total") or got_msgs != man.get("active_msgs"):
            msg = (f"restore verification: seals={got_seals} vs {man.get('seals_total')}, "
                   f"msgs={got_msgs} vs {man.get('active_msgs')}")
            if mode == "safe":
                con.rollback()
                raise RuntimeError(msg + " — rolled back")
            warnings.append(msg + " (kept anyway in best-effort mode)")
        con.commit()
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()
    after = dbmod.session_detail(live, session_id)
    after_hash = dbmod.session_content_hash(live, session_id)
    if after_hash != man.get("content_sha256"):
        msg = "restored content hash differs from manifest"
        if mode == "safe":
            raise RuntimeError(msg + f" — pre-restore stash kept at {stash['dir']}")
        warnings.append(msg + " (kept anyway in best-effort mode)")
    return {"seals_after": after["seals_total"], "msgs_after": after["active_msgs"],
            "stash": stash["dir"], "bundle": bundle_dir, "mode": mode,
            "warnings": warnings, "skipped_columns": skipped if mode == "best-effort" else {"sessions": [], "messages": []}}

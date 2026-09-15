"""Row-level restore for OpenCode: put back ONE session's exact rows.

Only that session_id's session/message/part rows are replaced; everything
else in the live DB is untouched. Restoring stashes current state first,
so undoing the undo works.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

from . import ocbackup as ocbackupmod
from . import ocdb as ocdbmod
from . import jsonbytes as jsonbytesmod


def _load_manifest(bundle_dir: Path) -> dict:
    man_file = bundle_dir / "manifest.json"
    if not man_file.exists():
        raise FileNotFoundError(f"not a restore bundle (no manifest.json): {bundle_dir}")
    try:
        man = json.loads(man_file.read_text())
    except json.JSONDecodeError:
        raise FileNotFoundError(f"not a restore bundle (bad manifest.json): {bundle_dir}")
    if man.get("backend") != "opencode" or not (bundle_dir / "rows.json").exists():
        raise FileNotFoundError(f"not an OpenCode rows bundle: {bundle_dir}")
    return man


def list_bundles(root: Path) -> list[dict]:
    """Newest-first bundle summaries (same shape as the Hermes lister)."""
    found = []
    if not root.exists():
        return found
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            man = _load_manifest(child)
        except (FileNotFoundError, KeyError):
            continue
        found.append({"dir": child, "session_id": man.get("session_id", "?"),
                      "utc": man.get("utc", ""), "seals_total": man.get("blobs"),
                      "active_msgs": man.get("msgs"),
                      "snapshot_bytes": man.get("rows_bytes", 0),
                      "verified": man.get("verified", False)})
    return sorted(found, key=lambda b: str(b["utc"]), reverse=True)


def _cols(con: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def restore_session_oc(home: Path, session_id: str, bundle_dir: Path,
                       pre_restore_root: Path | None = None,
                       mode: str = "safe") -> dict:
    if mode not in ("safe", "best-effort"):
        raise ValueError(f"unknown restore mode: {mode!r}")
    man = _load_manifest(bundle_dir)
    if man.get("session_id") != session_id:
        raise KeyError(f"bundle is for {man.get('session_id')}, not {session_id}")
    live = home / "opencode.db"
    if ocdbmod.busy(live, session_id):
        raise RuntimeError(f"session {session_id} is busy — retry when idle")
    stash_root = pre_restore_root or (bundle_dir.parent / "pre-restore")
    stash = ocbackupmod.backup_session_oc(home, session_id, stash_root, verify=False)
    bundle = jsonbytesmod.loads((bundle_dir / "rows.json").read_text())
    warnings: list[str] = []
    con = sqlite3.connect(live)
    try:
        live_cols = {t: _cols(con, t) for t in ("session", "message", "part")}
        src = {"session": bundle["scols"], "message": bundle["mcols"], "part": bundle["pcols"]}
        if mode == "safe":
            for t in ("session", "message", "part"):
                if src[t] != live_cols[t]:
                    raise RuntimeError(
                        f"safe restore refused: {t} schema drifted. "
                        "Use Try-my-best mode to fit by column name.")
            use = {t: src[t] for t in src}
            skipped: dict[str, list[str]] = {"session": [], "message": [], "part": []}
        else:
            use = {t: [c for c in src[t] if c in live_cols[t]] for t in src}
            skipped = {t: ([c for c in src[t] if c not in live_cols[t]]
                           + [c for c in live_cols[t] if c not in src[t]]) for t in src}
            for t, cols in skipped.items():
                if cols:
                    warnings.append(f"skipped {t} cols: {', '.join(cols)}")
            if not use["session"] or (bundle["messages"] and not use["message"]):
                raise RuntimeError("best-effort restore: no common columns — refusing")

        def _insert(table: str, where_col: str, rows: list[list]) -> None:
            cols = use[table]
            idx = [src[table].index(c) for c in cols]
            col_sql = ", ".join(f'"{c}"' for c in cols)
            ph = ",".join("?" * len(cols))
            data = [tuple(r[i] for i in idx) for r in rows]
            if table == "session":
                con.execute(f'INSERT INTO main.session ({col_sql}) VALUES ({ph})', data[0])
            elif data:
                con.executemany(f'INSERT INTO main.{table} ({col_sql}) VALUES ({ph})', data)

        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM main.part WHERE session_id=?", (session_id,))
        con.execute("DELETE FROM main.message WHERE session_id=?", (session_id,))
        con.execute("DELETE FROM main.session WHERE id=?", (session_id,))
        _insert("session", "id", [bundle["session"]])
        _insert("message", "session_id", bundle["messages"])
        _insert("part", "session_id", bundle["parts"])
        got_blobs = con.execute(
            f"SELECT COUNT(*) FROM main.part WHERE session_id=? AND {ocdbmod.BLOB_NONEMPTY}",
            (session_id,)).fetchone()[0]
        got_msgs = con.execute("SELECT COUNT(*) FROM main.message WHERE session_id=?",
                               (session_id,)).fetchone()[0]
        if got_blobs != man.get("blobs") or got_msgs != man.get("msgs"):
            msg = (f"restore verification: blobs={got_blobs} vs {man.get('blobs')}, "
                   f"msgs={got_msgs} vs {man.get('msgs')}")
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
    after_hash = ocdbmod.session_content_hash(live, session_id)
    if after_hash != man.get("content_sha256"):
        msg = "restored content hash differs from manifest"
        if mode == "safe":
            raise RuntimeError(msg + f" — pre-restore stash kept at {stash['dir']}")
        warnings.append(msg + " (kept anyway in best-effort mode)")
    after = ocdbmod.session_detail(live, session_id)
    return {"blobs_after": after["blobs"], "seals_after": after["blobs"],
            "msgs_after": after["msgs"], "stash": stash["dir"],
            "bundle": bundle_dir, "mode": mode, "warnings": warnings,
            "skipped_columns": skipped if mode == "best-effort" else {"session": [], "message": [], "part": []}}

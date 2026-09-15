"""Backup first, always. Returns paths; raises on any failure."""
from __future__ import annotations
import datetime
import hashlib
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

from . import db as dbmod
from . import jsonbytes as jsonbytesmod

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "settings.json"
DEFAULT_ROOT = PROJECT_ROOT / "backups"


def resolve_backup_root() -> Path:
    try:
        raw = json.loads(SETTINGS_FILE.read_text())
        custom = str(raw.get("backup_root", "")).strip()
        if custom:
            p = Path(custom).expanduser()
            # Portable after a move: a custom absolute path from another
            # machine/folder layout is stale if neither it nor its parent
            # exists. Fall back to the inside-the-folder default instead of
            # recreating a dead absolute path. Fresh subfolders under an
            # existing parent are still honored (mkdir later creates them).
            if p.exists() or p.parent.exists():
                return p
    except Exception:
        pass
    return DEFAULT_ROOT


def _snapshot_consistent(src: Path, dest: Path) -> None:
    """Copy via SQLite's backup API: consistent even on WAL DBs, no sidecars needed."""
    src_con = sqlite3.connect(src)
    try:
        dest_con = sqlite3.connect(dest)
        try:
            src_con.backup(dest_con)
        finally:
            dest_con.close()
    finally:
        src_con.close()


def _mkdir_unique(dest_root: Path, stem: str) -> Path:
    """Bundle dir that never collides on same-second double runs."""
    d = dest_root / stem
    for i in range(1, 100):
        try:
            d.mkdir(parents=True, exist_ok=False)
            return d
        except FileExistsError:
            d = dest_root / f"{stem}-{i}"
    raise FileExistsError(f"could not create unique bundle dir under {dest_root}")


def _rows_for(con: sqlite3.Connection, table: str, where: str,
              arg: str) -> tuple[list[str], list[tuple]]:
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    col_sql = ", ".join(f'"{c}"' for c in cols)
    rows = con.execute(f"SELECT {col_sql} FROM {table} WHERE {where}", (arg,)).fetchall()
    return cols, [tuple(r) for r in rows]


def _write_exports(d: Path, session_id: str, manifest: dict) -> None:
    for fmt, name in (("md", "export.md"), ("jsonl", "export.jsonl")):
        try:
            r = subprocess.run(["hermes", "sessions", "export", "--session-id", session_id,
                                "--format", fmt, str(d / name)],
                               capture_output=True, text=True, timeout=300)
            manifest[f"export_{fmt}"] = {"rc": r.returncode, "tail": (r.stdout + r.stderr)[-500:]}
        except Exception as e:
            manifest[f"export_{fmt}"] = {"rc": -1, "tail": f"skipped: {e}"[:500]}


def backup_session_rows(home: Path, session_id: str, dest_root: Path | None = None,
                        verify: bool = True) -> dict:
    """Per-chat bundle: one session's rows as JSON. KBs, not MBs.

    This is the default going forward. Legacy full-snapshot bundles
    (backup_session) remain restorable.
    """
    dest_root = dest_root or resolve_backup_root()
    db = home / "state.db"
    if not db.exists() or db.stat().st_size == 0:
        raise RuntimeError(f"refusing backup: {db} missing or empty")
    detail = dbmod.session_detail(db, session_id)  # raises KeyError if unknown
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = _mkdir_unique(dest_root, f"{session_id}_{stamp}")
    try:
        con = dbmod._connect_ro(db)
        try:
            scols, sess = _rows_for(con, "sessions", "id=?", session_id)
            mcols, msgs = _rows_for(con, "messages", "session_id=?", session_id)
        finally:
            con.close()
        if not sess:
            raise KeyError(f"session {session_id} not present in live DB")
        bundle = {"scols": scols, "session": sess[0],
                  "mcols": mcols, "messages": msgs}
        # rows.json must survive BLOB columns (sqlite returns bytes) — the
        # shared codec round-trips them exactly instead of crashing the dump.
        (d / "rows.json").write_text(jsonbytesmod.dumps(bundle))
        manifest = {"backend": "hermes", "kind": "rows",
                    "session_id": session_id, "utc": stamp,
                    "rows_bytes": (d / "rows.json").stat().st_size,
                    "snapshot_bytes": (d / "rows.json").stat().st_size,
                    "seals_active": detail["seals_active"],
                    "seals_total": detail["seals_total"],
                    "active_msgs": detail["active_msgs"],
                    "kept_items": detail["kept_items"],
                    "content_sha256": dbmod.session_content_hash(db, session_id),
                    "verified": False}
        _write_exports(d, session_id, manifest)
        if verify:
            back = jsonbytesmod.loads((d / "rows.json").read_text())
            live_n = dbmod._connect_ro(db)
            try:
                live_total = live_n.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id=?", (session_id,)).fetchone()[0]
            finally:
                live_n.close()
            import hashlib
            h = hashlib.sha256()
            midx = {c: i for i, c in enumerate(back["mcols"])}
            for r in sorted(back["messages"], key=lambda x: x[midx["id"]]):
                h.update(repr((r[midx["id"]], r[midx["content"]],
                               r[midx["codex_message_items"]])).encode("utf-8", "replace"))
            ok = (len(back["messages"]) == live_total
                  and h.hexdigest() == manifest["content_sha256"])
            manifest["verified"] = bool(ok)
            if not manifest["verified"]:
                raise RuntimeError("backup verification failed — bundle differs from source")
        (d / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (d / "RESTORE.txt").write_text(
            "Session Doctor restore bundle (Hermes, per-chat)\n"
            f"session: {session_id}\nbacked up (UTC): {stamp}\n\n"
            "To restore: open Session Doctor, pick this session, press Restore\n"
            "and choose this folder. Only that session's rows are replaced.\n")
    except Exception:
        # Never leave half-written bundle corpses behind.
        shutil.rmtree(d, ignore_errors=True)
        raise
    return {"dir": d, "rows": d / "rows.json", "manifest": d / "manifest.json"}


def con_inactive_count(db: Path, session_id: str) -> int:
    """Inactive message rows for a session (kept for diagnostics)."""
    con = dbmod._connect_ro(db)
    try:
        return con.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id=? AND COALESCE(active,1)!=1",
            (session_id,)).fetchone()[0]
    finally:
        con.close()


def backup_session(home: Path, session_id: str, dest_root: Path | None = None,
                   verify: bool = True) -> dict:
    dest_root = dest_root or resolve_backup_root()
    db = home / "state.db"
    if not db.exists() or db.stat().st_size == 0:
        raise RuntimeError(f"refusing backup: {db} missing or empty")
    dbmod.session_detail(db, session_id)  # raises KeyError if unknown
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = _mkdir_unique(dest_root, f"{session_id}_{stamp}")
    snap = d / "state.db.snapshot"
    try:
        _snapshot_consistent(db, snap)
        if snap.stat().st_size == 0:
            raise RuntimeError("snapshot is zero bytes — aborting")
        h = hashlib.sha256()
        with open(snap, "rb") as f:
            h.update(f.read(1 << 20))
        detail = dbmod.session_detail(db, session_id)
        manifest = {"session_id": session_id, "utc": stamp,
                    "snapshot": str(snap), "snapshot_rel": "state.db.snapshot",
                    "snapshot_bytes": snap.stat().st_size,
                    "snapshot_sha256_head1M": h.hexdigest(),
                    "seals_active": detail["seals_active"],
                    "seals_total": detail["seals_total"],
                    "active_msgs": detail["active_msgs"],
                    "kept_items": detail["kept_items"],
                    "content_sha256": dbmod.session_content_hash(db, session_id)}
        for fmt, name in (("md", "export.md"), ("jsonl", "export.jsonl")):
            try:
                r = subprocess.run(["hermes", "sessions", "export", "--session-id", session_id,
                                    "--format", fmt, str(d / name)],
                                   capture_output=True, text=True, timeout=300)
                manifest[f"export_{fmt}"] = {"rc": r.returncode, "tail": (r.stdout + r.stderr)[-500:]}
            except Exception as e:
                manifest[f"export_{fmt}"] = {"rc": -1, "tail": f"skipped: {e}"[:500]}
        if verify:
            snap_detail = dbmod.session_detail(snap, session_id)
            snap_hash = dbmod.session_content_hash(snap, session_id)
            manifest["verified"] = (
                snap_detail["seals_active"] == detail["seals_active"]
                and snap_detail["seals_total"] == detail["seals_total"]
                and snap_detail["active_msgs"] == detail["active_msgs"]
                and snap_hash == manifest["content_sha256"])
            if not manifest["verified"]:
                raise RuntimeError("backup verification failed — snapshot differs from source")
        else:
            manifest["verified"] = False
        (d / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (d / "RESTORE.txt").write_text(
            "Session Doctor restore bundle\n"
            f"session: {session_id}\nbacked up (UTC): {stamp}\n\n"
            "To restore: open Session Doctor, pick this session, press Restore\n"
            "and choose this folder. Or roll back manually while Hermes is idle:\n"
            "row-level restore is required (never overwrite a live state.db with\n"
            "this snapshot — other sessions kept changing after this backup).\n")
    except Exception:
        # Never leave half-written bundle corpses behind.
        shutil.rmtree(d, ignore_errors=True)
        raise
    return {"dir": d, "snapshot": snap, "manifest": d / "manifest.json"}

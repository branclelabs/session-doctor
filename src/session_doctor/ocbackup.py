"""Per-chat backups for OpenCode. No full-DB copies, ever.

A bundle is one session's rows (session + message + part) as JSON plus a
manifest with counts + visible-text fingerprint. KBs, not GBs.
"""
from __future__ import annotations
import datetime
import json
import shutil
from pathlib import Path

from . import ocdb as ocdbmod
from . import jsonbytes as jsonbytesmod

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "settings.json"
DEFAULT_OC_ROOT = PROJECT_ROOT / "backups" / "opencode"


def resolve_oc_backup_root() -> Path:
    try:
        raw = json.loads(SETTINGS_FILE.read_text())
        custom = str(raw.get("oc_backup_root", "")).strip()
        if custom:
            p = Path(custom).expanduser()
            # Portable after a move: stale absolute paths fall back to the
            # inside-the-folder default (same rule as the Hermes root).
            if p.exists() or p.parent.exists():
                return p
    except Exception:
        pass
    return DEFAULT_OC_ROOT


def _mkdir_unique(dest_root: Path, stem: str) -> Path:
    d = dest_root / stem
    for i in range(1, 100):
        try:
            d.mkdir(parents=True, exist_ok=False)
            return d
        except FileExistsError:
            d = dest_root / f"{stem}-{i}"
    raise FileExistsError(f"could not create unique bundle dir under {dest_root}")


def _table_cols(con, table: str) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def _rows_for(con, table: str, where: str, arg: str) -> tuple[list[str], list[tuple]]:
    cols = _table_cols(con, table)
    col_sql = ", ".join(f'"{c}"' for c in cols)
    rows = con.execute(f"SELECT {col_sql} FROM {table} WHERE {where}", (arg,)).fetchall()
    return cols, [tuple(r) for r in rows]


def _transcript(bundle: dict) -> tuple[str, str]:
    """Best-effort readable export rendered from the bundle rows (no CLI)."""
    md: list[str] = [f"# {bundle['session'][bundle['scols'].index('title')] or 'untitled'}\n"]
    jl: list[str] = []
    pcols = bundle["pcols"]
    tidx = pcols.index("id")
    didx = pcols.index("data")
    for p in sorted(bundle["parts"], key=lambda r: r[tidx]):
        try:
            d = json.loads(p[didx])
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        t = d.get("type")
        jl.append(json.dumps({"id": p[tidx], "type": t}))
        if t == "text" and d.get("text"):
            md.append(d["text"] + "\n")
        elif t == "reasoning" and d.get("text"):
            md.append("> " + d["text"][:500] + "\n")
    return "\n".join(md), "\n".join(jl) + "\n"


def backup_session_oc(home: Path, session_id: str, dest_root: Path | None = None,
                      verify: bool = True) -> dict:
    import sqlite3
    dest_root = dest_root or resolve_oc_backup_root()
    db = home / "opencode.db"
    detail = ocdbmod.session_detail(db, session_id)  # raises KeyError if unknown
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = _mkdir_unique(dest_root, f"{session_id}_{stamp}")
    try:
        # Read the rows over a plain connection (query_only: no lock coupling).
        con = ocdbmod._connect_ro(db)
        try:
            scols, sess = _rows_for(con, "session", "id=?", session_id)
            mcols, msgs = _rows_for(con, "message", "session_id=?", session_id)
            pcols, parts = _rows_for(con, "part", "session_id=?", session_id)
        finally:
            con.close()
        if not sess:
            raise KeyError(f"session {session_id} not present in live DB")
        bundle = {"scols": scols, "session": sess[0],
                  "mcols": mcols, "messages": msgs,
                  "pcols": pcols, "parts": parts}
        (d / "rows.json").write_text(jsonbytesmod.dumps(bundle))
        md, jl = _transcript(bundle)
        (d / "export.md").write_text(md)
        (d / "export.jsonl").write_text(jl)
        manifest = {"backend": "opencode", "kind": "rows",
                    "session_id": session_id, "utc": stamp,
                    "rows_bytes": (d / "rows.json").stat().st_size,
                    "snapshot_bytes": (d / "rows.json").stat().st_size,
                    "blobs": detail["blobs"], "seals_total": detail["blobs"],
                    "msgs": detail["msgs"], "active_msgs": detail["msgs"],
                    "parts": detail["parts"],
                    "content_sha256": ocdbmod.session_content_hash(db, session_id),
                    "verified": False}
        if verify:
            back = jsonbytesmod.loads((d / "rows.json").read_text())
            ok = (len(back["messages"]) == detail["msgs"]
                  and len(back["parts"]) == detail["parts"])
            import hashlib
            h = hashlib.sha256()
            tidx = back["pcols"].index("id")
            didx = back["pcols"].index("data")
            for r in sorted(back["parts"], key=lambda x: x[tidx]):
                try:
                    dd = json.loads(r[didx])
                except Exception:
                    dd = {}
                if not isinstance(dd, dict):
                    dd = {}
                h.update(repr((r[tidx], dd.get("type"), dd.get("text", ""))).encode("utf-8", "replace"))
            ok = ok and h.hexdigest() == manifest["content_sha256"]
            manifest["verified"] = bool(ok)
            if not manifest["verified"]:
                raise RuntimeError("backup verification failed — bundle differs from source")
        (d / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (d / "RESTORE.txt").write_text(
            "Session Doctor restore bundle (OpenCode, per-chat)\n"
            f"session: {session_id}\nbacked up (UTC): {stamp}\n\n"
            "To restore: open Session Doctor, pick OpenCode, press Restore\n"
            "and choose this folder. Only that session's rows are replaced.\n")
    except Exception:
        # Never leave half-written bundle corpses behind.
        shutil.rmtree(d, ignore_errors=True)
        raise
    return {"dir": d, "rows": d / "rows.json", "manifest": d / "manifest.json"}

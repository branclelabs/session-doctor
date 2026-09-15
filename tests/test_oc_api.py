"""Hermes per-chat rows bundles + legacy snapshot compat (throwaway DBs)."""
import json
import sqlite3
import subprocess


SCHEMA = """
CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, pinned INTEGER DEFAULT 0,
  archived INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0, model TEXT,
  message_count INTEGER DEFAULT 0, last_activity_at REAL, parent_session_id TEXT);
CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
  codex_reasoning_items TEXT, codex_message_items TEXT, active INTEGER DEFAULT 1);
CREATE TABLE session_turn_leases (conversation_id TEXT, holder TEXT);
"""
SEAL = '[{"encrypted_content":"X"}]'


def _home(tmp_path, name="hhome"):
    home = tmp_path / name
    home.mkdir()
    con = sqlite3.connect(home / "state.db")
    con.executescript(SCHEMA)
    con.execute("INSERT INTO sessions (id,title) VALUES ('A','a'),('B','b')")
    con.execute("INSERT INTO messages (session_id,role,content,codex_reasoning_items,active) VALUES ('A','assistant','keep',?,1)", (SEAL,))
    con.execute("INSERT INTO messages (session_id,role,content,active) VALUES ('A','user','q',1)")
    con.execute("INSERT INTO messages (session_id,role,content,codex_reasoning_items,active) VALUES ('B','assistant','other',?,1)", (SEAL,))
    con.commit()
    con.close()
    return home


def _no_export(monkeypatch):
    monkeypatch.setattr("session_doctor.backup.subprocess.run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="stub", stderr=""))


def test_rows_bundle_is_small_and_verified(tmp_path, monkeypatch):
    _no_export(monkeypatch)
    from session_doctor import backup
    home = _home(tmp_path)
    out = backup.backup_session_rows(home, "A", tmp_path / "backups")
    man = json.loads((out["dir"] / "manifest.json").read_text())
    assert man["kind"] == "rows" and man["verified"] is True
    assert (out["dir"] / "rows.json").stat().st_size < 100_000
    assert not (out["dir"] / "state.db.snapshot").exists()


def test_rows_restore_roundtrip_and_legacy_compat(tmp_path, monkeypatch):
    _no_export(monkeypatch)
    from session_doctor import backup, db, fix, restore
    home = _home(tmp_path)
    sdb = home / "state.db"
    pre = db.session_content_hash(sdb, "A")
    new_bundle = backup.backup_session_rows(home, "A", tmp_path / "backups")["dir"]
    legacy_bundle = backup.backup_session(home, "A", tmp_path / "backups")["dir"]
    assert (legacy_bundle / "state.db.snapshot").exists()
    fix.strip_seals(sdb, "A")
    r1 = restore.restore_session(home, "A", new_bundle, mode="safe")
    assert r1["seals_after"] == 1
    assert db.session_content_hash(sdb, "A") == pre
    fix.strip_seals(sdb, "A")
    r2 = restore.restore_session(home, "A", legacy_bundle, mode="safe")
    assert r2["seals_after"] == 1
    assert db.session_content_hash(sdb, "A") == pre


def test_oc_api_endpoints(tmp_path, monkeypatch):
    import threading
    import urllib.request
    from session_doctor import server as srvmod
    home = _home(tmp_path, name="apihome")

    def fake_run(*a, **k):
        return subprocess.CompletedProcess(a, 0, stdout="stub", stderr="")
    monkeypatch.setattr("session_doctor.backup.subprocess.run", fake_run)

    old = dict(srvmod.CONFIG)
    srvmod.CONFIG.update({"home": home, "backup_root": tmp_path / "broot",
                          "activity_file": tmp_path / "activity.jsonl"})
    import session_doctor.ocdb as ocdbmod
    oc_home = tmp_path / "ochome"
    oc_home.mkdir()
    con = sqlite3.connect(oc_home / "opencode.db")
    con.executescript("""
    CREATE TABLE session (id TEXT PRIMARY KEY, title TEXT, directory TEXT, model TEXT,
      time_created INTEGER, time_updated INTEGER, time_compacting INTEGER, time_archived INTEGER);
    CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, time_updated INTEGER, data TEXT);
    CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, time_updated INTEGER, data TEXT);
    """)
    con.execute("INSERT INTO session (id,title,time_created,time_updated) VALUES ('S','t',1,2)")
    con.execute("INSERT INTO message (id,session_id,time_created,time_updated,data) VALUES ('m','S',1,1,'{}')")
    con.execute("INSERT INTO part (id,message_id,session_id,time_created,time_updated,data) VALUES ('p','m','S',1,1,'{\"type\":\"text\",\"text\":\"hi\"}')")
    con.commit()
    con.close()
    monkeypatch.setattr(ocdbmod, "resolve_oc_home", lambda: oc_home)

    srv = srvmod.serve(port=0, open_browser=False)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def call(path, body=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{srv.server_address[1]}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode())
    try:
        code, j = call("/api/oc/sessions")
        assert code == 200 and j["count"] == 1
        code, j = call("/api/oc/fix", {"id": "S", "verify": True})
        assert code == 200 and j["cleared"] == 0
    finally:
        srv.shutdown()
        srvmod.CONFIG.update(old)

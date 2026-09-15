def test_backup_copies_db_and_manifest(tmp_path):
    from session_doctor import backup
    import sqlite3
    home = tmp_path / ".hermes"
    home.mkdir()
    con = sqlite3.connect(home / "state.db")
    con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT)")
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, codex_reasoning_items TEXT, codex_message_items TEXT, active INTEGER DEFAULT 1)")
    con.execute("INSERT INTO sessions VALUES ('s1', 'T')")
    con.commit()
    con.close()
    out = backup.backup_session(home, "s1", tmp_path / "backups")
    assert out["snapshot"].exists() and out["snapshot"].stat().st_size > 0
    assert (out["dir"] / "manifest.json").exists()


def _wal_home(tmp_path, name="s1"):
    import sqlite3
    home = tmp_path / name
    home.mkdir()
    con = sqlite3.connect(home / "state.db")
    con.executescript("""
    CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, pinned INTEGER DEFAULT 0,
      archived INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0, model TEXT,
      message_count INTEGER DEFAULT 0, last_activity_at REAL, parent_session_id TEXT);
    CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
      codex_reasoning_items TEXT, codex_message_items TEXT, active INTEGER DEFAULT 1);
    CREATE TABLE session_turn_leases (conversation_id TEXT, holder TEXT);
    """)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("INSERT INTO sessions (id, title) VALUES ('s1', 'T')")
    con.execute("INSERT INTO messages (session_id, role, content, codex_reasoning_items, active)"
                " VALUES ('s1', 'assistant', 'hello', '[{\"encrypted_content\":\"X\"}]', 1)")
    con.commit()
    con.close()
    return home


def test_snapshot_consistent_and_manifest_fingerprints(tmp_path, monkeypatch):
    import json
    from session_doctor import backup
    home = _wal_home(tmp_path)
    out = backup.backup_session(home, "s1", tmp_path / "backups")
    man = json.loads((out["dir"] / "manifest.json").read_text())
    assert man["seals_active"] == 1 and man["seals_total"] == 1
    assert man["active_msgs"] == 1 and man["verified"] is True
    assert len(man["content_sha256"]) == 64
    # snapshot must open standalone (sidecars NOT copied) and hold the row
    import sqlite3
    con = sqlite3.connect(out["snapshot"])
    try:
        assert con.execute("SELECT content FROM messages WHERE session_id='s1'").fetchone()[0] == "hello"
    finally:
        con.close()


def test_resolve_backup_root_default_and_settings(tmp_path, monkeypatch):
    import json
    from session_doctor import backup
    default = backup.resolve_backup_root()
    assert str(default).endswith("backups")
    custom = tmp_path / "mine"
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"backup_root": str(custom)}))
    monkeypatch.setattr(backup, "SETTINGS_FILE", settings)
    assert backup.resolve_backup_root() == custom


def test_jsonbytes_roundtrip():
    from session_doctor import jsonbytes
    raw = {"a": b"\x89PNG\r\n\x00", "n": [1, "x", (b"y",)],
           "plain": "hello", "num": 3, "nil": None}
    back = jsonbytes.loads(jsonbytes.dumps(raw))
    assert back["a"] == b"\x89PNG\r\n\x00"
    assert back["n"][2] == [b"y"]
    assert back["plain"] == "hello" and back["num"] == 3 and back["nil"] is None
    # legacy bundles without markers still load untouched
    import json
    assert jsonbytes.loads('{"a": "hello", "n": [1]}') == {"a": "hello", "n": [1]}


def test_rows_bundle_with_blob_bytes_roundtrip(tmp_path, monkeypatch):
    # Real Hermes messages rows can carry BLOB columns (display_identity):
    # the rows bundle must not crash the dump and must restore bytes exactly.
    import json
    import sqlite3
    import subprocess
    from session_doctor import backup, db, fix, restore
    monkeypatch.setattr("session_doctor.backup.subprocess.run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="stub", stderr=""))
    home = tmp_path / "home"
    home.mkdir()
    con = sqlite3.connect(home / "state.db")
    con.executescript("""
    CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, pinned INTEGER DEFAULT 0,
      archived INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0, model TEXT,
      message_count INTEGER DEFAULT 0, last_activity_at REAL, parent_session_id TEXT);
    CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
      codex_reasoning_items TEXT, codex_message_items TEXT, active INTEGER DEFAULT 1,
      display_identity BLOB);
    CREATE TABLE session_turn_leases (conversation_id TEXT, holder TEXT);
    INSERT INTO sessions (id, title) VALUES ('A', 'a');
    """)
    blob = b"\x89PNG\r\n\x00identity-bytes"
    con.execute("INSERT INTO messages (session_id, role, content, codex_reasoning_items, active, display_identity)"
                " VALUES ('A', 'assistant', 'keep', '[{\"encrypted_content\":\"X\"}]', 1, ?)", (blob,))
    con.execute("INSERT INTO messages (session_id, role, content, active) VALUES ('A', 'user', 'q', 1)")
    con.commit()
    con.close()
    sdb = home / "state.db"
    pre_hash = db.session_content_hash(sdb, "A")
    out = backup.backup_session_rows(home, "A", tmp_path / "backups")
    man = json.loads((out["dir"] / "manifest.json").read_text())
    assert man["verified"] is True
    fix.strip_seals(sdb, "A")
    assert db.session_content_hash(sdb, "A") == pre_hash
    r = restore.restore_session(home, "A", out["dir"], mode="safe")
    assert r["seals_after"] == 1
    assert db.session_content_hash(sdb, "A") == pre_hash
    con = sqlite3.connect(sdb)
    try:
        assert con.execute("SELECT display_identity FROM messages WHERE role='assistant'").fetchone()[0] == blob
    finally:
        con.close()

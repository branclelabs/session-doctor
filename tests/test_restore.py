import json
import sqlite3
import subprocess


SCHEMA = """
CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, pinned INTEGER DEFAULT 0,
  archived INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0, model TEXT,
  message_count INTEGER DEFAULT 0, last_activity_at REAL, parent_session_id TEXT);
CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
  codex_reasoning_items TEXT, codex_message_items TEXT, active INTEGER DEFAULT 1);
CREATE TABLE session_turn_leases (conversation_id TEXT, holder TEXT,
  acquired_at REAL, expires_at REAL);
"""

SEAL = '[{"type":"reasoning","encrypted_content":"X"}]'


def _home(tmp_path, name="home"):
    home = tmp_path / name
    home.mkdir()
    con = sqlite3.connect(home / "state.db")
    con.executescript(SCHEMA)
    con.execute("INSERT INTO sessions (id, title) VALUES ('A', 'a'), ('B', 'b')")
    con.execute("INSERT INTO messages (session_id, role, content, codex_reasoning_items, active)"
                " VALUES ('A', 'assistant', 'keep', ?, 1)", (SEAL,))
    con.execute("INSERT INTO messages (session_id, role, content, active)"
                " VALUES ('A', 'user', 'q', 1)")
    con.execute("INSERT INTO messages (session_id, role, content, codex_reasoning_items, active)"
                " VALUES ('B', 'assistant', 'other', ?, 1)", (SEAL,))
    con.commit()
    con.close()
    return home


def _no_export(monkeypatch):
    def fake_run(*a, **k):
        return subprocess.CompletedProcess(a, 0, stdout="stubbed", stderr="")
    monkeypatch.setattr("session_doctor.backup.subprocess.run", fake_run)


def test_restore_reverts_strip_and_junk(tmp_path, monkeypatch):
    from session_doctor import backup, fix, restore, db
    _no_export(monkeypatch)
    home = _home(tmp_path)
    sdb = home / "state.db"
    pre_hash = db.session_content_hash(sdb, "A")
    bundle = backup.backup_session(home, "A", tmp_path / "backups")["dir"]
    # damage: strip seals + add junk row
    fix.strip_seals(sdb, "A")
    con = sqlite3.connect(sdb)
    con.execute("INSERT INTO messages (session_id, role, content, active)"
                " VALUES ('A', 'user', 'junk', 1)")
    con.commit()
    con.close()
    res = restore.restore_session(home, "A", bundle)
    assert res["seals_after"] == 1
    assert db.session_content_hash(sdb, "A") == pre_hash
    # neighbor untouched
    con = sqlite3.connect(sdb)
    try:
        assert con.execute(
            "SELECT content FROM messages WHERE session_id='B'").fetchone()[0] == "other"
        assert con.execute(
            "SELECT COUNT(*) FROM messages WHERE content='junk'").fetchone()[0] == 0
    finally:
        con.close()


def test_restore_refuses_live_lease(tmp_path, monkeypatch):
    from session_doctor import backup, restore
    _no_export(monkeypatch)
    home = _home(tmp_path)
    bundle = backup.backup_session(home, "A", tmp_path / "backups")["dir"]
    con = sqlite3.connect(home / "state.db")
    con.execute("INSERT INTO session_turn_leases VALUES ('A', 'h', 1.0, 9999999999.0)")
    con.commit()
    con.close()
    try:
        restore.restore_session(home, "A", bundle)
        assert False, "should have refused"
    except RuntimeError as e:
        assert "lease" in str(e).lower()


def test_restore_unknown_bundle_errors(tmp_path):
    from session_doctor import restore
    home = _home(tmp_path)
    try:
        restore.restore_session(home, "A", tmp_path / "nope")
        assert False, "should have raised"
    except (FileNotFoundError, KeyError):
        pass


def test_list_bundles_newest_first(tmp_path, monkeypatch):
    import time
    from session_doctor import backup, restore
    _no_export(monkeypatch)
    home = _home(tmp_path)
    root = tmp_path / "backups"
    b1 = backup.backup_session(home, "A", root)["dir"]
    time.sleep(1.1)
    b2 = backup.backup_session(home, "A", root)["dir"]
    found = restore.list_bundles(root)
    assert [b["dir"] for b in found] == [b2, b1]
    assert all(b["session_id"] == "A" for b in found)

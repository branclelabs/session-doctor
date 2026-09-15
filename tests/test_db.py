import sqlite3
from pathlib import Path


def _make_home(tmp: Path) -> Path:
    home = tmp / ".hermes"
    home.mkdir()
    con = sqlite3.connect(home / "state.db")
    con.executescript("""
    CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, pinned INTEGER DEFAULT 0,
      archived INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0, model TEXT,
      message_count INTEGER DEFAULT 0, last_activity_at REAL, parent_session_id TEXT);
    CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT,
      content TEXT, codex_reasoning_items TEXT, codex_message_items TEXT, active INTEGER DEFAULT 1);
    CREATE TABLE session_turn_leases (session_id TEXT);
    INSERT INTO sessions (id,title,pinned,archived,hidden,model,message_count,last_activity_at)
      VALUES ('s_pin','BRANCLE',1,0,0,'m',1079,1789316166),
             ('s_old','old',0,0,0,'m',10,1789300000);
    INSERT INTO messages (session_id,role,content,codex_reasoning_items,active) VALUES
      ('s_pin','assistant','hi','[{"type":"reasoning","encrypted_content":"AAA"}]',1),
      ('s_pin','assistant','old','[{"type":"reasoning","encrypted_content":"BBB"}]',0),
      ('s_old','assistant','clean',NULL,1);
    """)
    con.commit()
    con.close()
    return home


def test_resolve_home_prefers_env(tmp_path, monkeypatch):
    from session_doctor import db
    home = _make_home(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    assert db.resolve_home() == home


def test_list_sessions_seal_counts(tmp_path, monkeypatch):
    from session_doctor import db
    home = _make_home(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    rows = db.list_sessions(home / "state.db", include_archived=False)
    by_id = {r["id"]: r for r in rows}
    assert by_id["s_pin"]["seals_active"] == 1
    assert by_id["s_pin"]["seals_total"] == 2
    assert by_id["s_old"]["seals_active"] == 0
    assert rows[0]["id"] == "s_pin"


def test_ro_read_survives_missing_wal_sidecars(tmp_path):
    import sqlite3
    from session_doctor import db
    f = tmp_path / "w.db"
    con = sqlite3.connect(f)
    con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, pinned INTEGER DEFAULT 0, "
                "archived INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0, model TEXT, "
                "message_count INTEGER DEFAULT 0, last_activity_at REAL, parent_session_id TEXT)")
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, "
                "codex_reasoning_items TEXT, active INTEGER DEFAULT 1)")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("INSERT INTO sessions (id, title) VALUES ('a','t')")
    con.commit()
    con.close()
    for suffix in ("-wal", "-shm", "-journal"):
        try:
            (tmp_path / ("w.db" + suffix)).unlink()
        except FileNotFoundError:
            pass
    rows = db.list_sessions(f)
    assert [r["id"] for r in rows] == ["a"]
    con = db._connect_ro(f)
    try:
        con.execute("CREATE TABLE nope (a)")
        assert False, "write should be blocked"
    except sqlite3.OperationalError:
        pass
    finally:
        con.close()


def test_live_lease_matches_conversation_id(tmp_path):
    import sqlite3
    from session_doctor import db
    f = tmp_path / "l.db"
    con = sqlite3.connect(f)
    con.execute("CREATE TABLE session_turn_leases (conversation_id TEXT, holder TEXT)")
    con.execute("INSERT INTO session_turn_leases VALUES ('S', 'h')")
    con.commit()
    con.close()
    assert db.live_lease(f, "S") is True
    assert db.live_lease(f, "OTHER") is False

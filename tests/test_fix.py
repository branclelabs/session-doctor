def test_strip_only_target_session(tmp_path):
    import sqlite3
    import shutil
    from session_doctor import fix
    src = tmp_path / "a.db"
    con = sqlite3.connect(src)
    con.executescript("""
    CREATE TABLE sessions (id TEXT PRIMARY KEY);
    CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
      codex_reasoning_items TEXT, codex_message_items TEXT, active INTEGER DEFAULT 1);
    CREATE TABLE session_turn_leases (session_id TEXT);
    INSERT INTO sessions VALUES ('A'), ('B');
    INSERT INTO messages (session_id,role,content,codex_reasoning_items,codex_message_items,active) VALUES
      ('A','assistant','keep me','[{"encrypted_content":"X"}]','[{"type":"message"}]',1),
      ('B','assistant','other','[{"encrypted_content":"Y"}]',NULL,1);
    """)
    con.commit()
    con.close()
    work = tmp_path / "w.db"
    shutil.copy(src, work)
    assert fix.dry_run(work, "A")["seals_active"] == 1
    res = fix.strip_seals(work, "A")
    assert res["cleared"] == 1 and res["seals_after"] == 0
    con = sqlite3.connect(work)
    try:
        assert con.execute("SELECT content FROM messages WHERE session_id='A'").fetchone()[0] == "keep me"
        assert "message" in con.execute("SELECT codex_message_items FROM messages WHERE session_id='A'").fetchone()[0]
        assert con.execute("SELECT codex_reasoning_items FROM messages WHERE session_id='B'").fetchone()[0] is not None
    finally:
        con.close()


def test_refuses_live_lease(tmp_path):
    import sqlite3
    import shutil
    from session_doctor import fix
    src = tmp_path / "b.db"
    con = sqlite3.connect(src)
    con.executescript("""
    CREATE TABLE sessions (id TEXT PRIMARY KEY);
    CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
      codex_reasoning_items TEXT, codex_message_items TEXT, active INTEGER DEFAULT 1);
    CREATE TABLE session_turn_leases (session_id TEXT);
    INSERT INTO messages (session_id,role,content,codex_reasoning_items,active) VALUES
      ('A','assistant','t','[{"encrypted_content":"X"}]',1);
    INSERT INTO session_turn_leases VALUES ('A');
    """)
    con.commit()
    con.close()
    work = tmp_path / "w2.db"
    shutil.copy(src, work)
    try:
        fix.strip_seals(work, "A")
        assert False, "should have refused live lease"
    except RuntimeError as e:
        assert "lease" in str(e).lower()

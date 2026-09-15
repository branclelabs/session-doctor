import json
import sqlite3
import subprocess
import threading
import urllib.error
import urllib.request

from session_doctor import server as srvmod


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


def _home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    con = sqlite3.connect(home / "state.db")
    con.executescript(SCHEMA)
    con.execute("INSERT INTO sessions (id, title, pinned) VALUES ('A', 'alpha', 1)")
    con.execute("INSERT INTO messages (session_id, role, content, codex_reasoning_items, active)"
                " VALUES ('A', 'assistant', 'hi', ?, 1)", (SEAL,))
    con.commit()
    con.close()
    return home


def _client(tmp_path, monkeypatch):
    home = _home(tmp_path)

    def fake_run(*a, **k):
        return subprocess.CompletedProcess(a, 0, stdout="stubbed", stderr="")
    monkeypatch.setattr("session_doctor.backup.subprocess.run", fake_run)

    old = dict(srvmod.CONFIG)
    srvmod.CONFIG.update({"home": home, "backup_root": tmp_path / "backups", "verify": True,
                          "activity_file": tmp_path / "activity.jsonl"})
    srv = srvmod.serve(port=0, open_browser=False)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def call(path, body=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{srv.server_address[1]}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
    try:
        yield call, home
    finally:
        srv.shutdown()
        srvmod.CONFIG.update(old)


def test_index_and_sessions(tmp_path, monkeypatch):
    import pytest
    gen = _client(tmp_path, monkeypatch)
    call, _ = next(gen)
    try:
        code, body = call("/")
        assert code == 200 and "Session Doctor" in body
        code, body = call("/api/sessions")
        assert code == 200
        j = json.loads(body)
        assert j["count"] == 1 and j["rows"][0]["seals_active"] == 1
    finally:
        gen.close()


def test_fix_then_restore_roundtrip(tmp_path, monkeypatch):
    gen = _client(tmp_path, monkeypatch)
    call, home = next(gen)
    try:
        code, body = call("/api/fix", {"id": "A", "verify": True})
        assert code == 200, body
        assert json.loads(body)["cleared"] == 1
        code, body = call("/api/session?id=A")
        assert json.loads(body)["seals_active"] == 0
        code, body = call("/api/bundles?session=A")
        bundles = json.loads(body)["bundles"]
        assert len(bundles) == 1
        code, body = call("/api/restore", {"id": "A", "dir": bundles[0]["dir"]})
        assert code == 200, body
        assert json.loads(body)["seals_after"] == 1
    finally:
        gen.close()


def test_unknown_session_errors(tmp_path, monkeypatch):
    gen = _client(tmp_path, monkeypatch)
    call, _ = next(gen)
    try:
        code, body = call("/api/session?id=NOPE")
        assert code == 500 and "not found" in body
    finally:
        gen.close()


def test_activity_logs_fix(tmp_path, monkeypatch):
    gen = _client(tmp_path, monkeypatch)
    call, _ = next(gen)
    try:
        code, body = call("/api/activity")
        assert code == 200 and json.loads(body)["events"] == []
        code, _ = call("/api/fix", {"id": "A", "verify": True})
        assert code == 200
        code, body = call("/api/activity")
        events = json.loads(body)["events"]
        assert len(events) == 1 and events[0]["kind"] == "fix"
        assert events[0]["session"] == "A" and "cleared 1" in events[0]["detail"]
    finally:
        gen.close()

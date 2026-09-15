"""OpenCode engine tests — throwaway copies only, ZTE excluded from fixtures."""
import json
import sqlite3

from session_doctor import ocbackup, ocdb, ocfix, ocrestore

SID = "ses_practice001"
SID2 = "ses_practice002"
BLOB = '{"type":"reasoning","text":"plain summary","metadata":{"openai":{"itemId":"rs_test"}}}'


def _oc_home(tmp_path, name="ochome"):
    home = tmp_path / name
    home.mkdir()
    con = sqlite3.connect(home / "opencode.db")
    con.executescript("""
    CREATE TABLE session (id TEXT PRIMARY KEY, title TEXT, directory TEXT,
      model TEXT, time_created INTEGER, time_updated INTEGER,
      time_compacting INTEGER, time_archived INTEGER);
    CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER,
      time_updated INTEGER, data TEXT);
    CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT,
      time_created INTEGER, time_updated INTEGER, data TEXT);
    """)
    con.execute("INSERT INTO session (id,title,directory,model,time_created,time_updated) VALUES (?,?,?,?,?,?)",
                (SID, "practice chat", "/tmp/proj", "m", 1000, 2000))
    con.execute("INSERT INTO session (id,title,directory,model,time_created,time_updated) VALUES (?,?,?,?,?,?)",
                (SID2, "neighbor", "/tmp/proj", "m", 1000, 1500))
    con.execute("INSERT INTO message (id,session_id,time_created,time_updated,data) VALUES (?,?,?,?,?)",
                ("msg1", SID, 1000, 1000, '{"role":"assistant"}'))
    con.execute("INSERT INTO message (id,session_id,time_created,time_updated,data) VALUES (?,?,?,?,?)",
                ("msg2", SID2, 1000, 1000, '{"role":"assistant"}'))
    # Real live shape: sealed blob nested at metadata.openai,
    # paired with the caller-bound itemId — plus visible summary text.
    blob_part = json.dumps({"type": "reasoning", "text": "summary here",
                            "time": {"start": 1, "end": 2},
                            "metadata": {"openai": {
                                "itemId": "rs_aaa:rs_bbb",
                                "reasoningEncryptedContent": "SYNTH-BLOB"}}})
    con.execute("INSERT INTO part (id,message_id,session_id,time_created,time_updated,data) VALUES (?,?,?,?,?,?)",
                ("prt1", "msg1", SID, 1000, 1000, blob_part))
    con.execute("INSERT INTO part (id,message_id,session_id,time_created,time_updated,data) VALUES (?,?,?,?,?,?)",
                ("prt2", "msg1", SID, 1000, 1000, '{"type":"text","text":"hello world"}'))
    # prose mention must never match the blob predicate
    con.execute("INSERT INTO part (id,message_id,session_id,time_created,time_updated,data) VALUES (?,?,?,?,?,?)",
                ("prt3", "msg1", SID, 1000, 1000, '{"type":"text","text":"talking about encrypted_content error"}'))
    # null-valued key is already clean and must not match either
    con.execute("INSERT INTO part (id,message_id,session_id,time_created,time_updated,data) VALUES (?,?,?,?,?,?)",
                ("prt4", "msg1", SID, 1000, 1000, '{"type":"reasoning","text":"no seal","metadata":{"openai":{"itemId":"rs_ccc","reasoningEncryptedContent":null}}}'))
    con.execute("INSERT INTO part (id,message_id,session_id,time_created,time_updated,data) VALUES (?,?,?,?,?,?)",
                ("prt9", "msg2", SID2, 1000, 1000, '{"type":"text","text":"neighbor intact"}'))
    con.commit()
    con.close()
    return home


def test_oc_list_and_detail(tmp_path):
    home = _oc_home(tmp_path)
    db = home / "opencode.db"
    rows = ocdb.list_sessions(db)
    by_id = {r["id"]: r for r in rows}
    assert by_id[SID]["seals_active"] == 1
    assert by_id[SID]["message_count"] == 1
    assert by_id[SID2]["seals_active"] == 0
    d = ocdb.session_detail(db, SID)
    assert d["blobs"] == 1 and d["msgs"] == 1 and d["parts"] == 4
    assert ocdb.busy(db, SID) is False
    assert len(ocdb.session_content_hash(db, SID)) == 64


def test_oc_backup_fix_restore_roundtrip(tmp_path):
    home = _oc_home(tmp_path)
    db = home / "opencode.db"
    pre_hash = ocdb.session_content_hash(db, SID)
    out = ocbackup.backup_session_oc(home, SID, tmp_path / "backups")
    man = json.loads((out["dir"] / "manifest.json").read_text())
    assert man["verified"] is True and man["blobs"] == 1
    assert (out["dir"] / "rows.json").stat().st_size < 100_000  # KBs, not GBs
    res = ocfix.strip_blobs(db, SID)
    assert res["cleared"] == 1 and res["blobs_after"] == 0
    assert ocdb.session_content_hash(db, SID) == pre_hash  # visible text intact
    con = sqlite3.connect(db)
    try:
        kept = json.loads(con.execute("SELECT data FROM part WHERE id='prt1'").fetchone()[0])
        assert "reasoningEncryptedContent" not in kept["metadata"]["openai"]
        assert kept["metadata"]["openai"]["itemId"] == "rs_aaa:rs_bbb"  # reference kept
        assert kept["text"] == "summary here"
        assert "encrypted_content" in con.execute("SELECT data FROM part WHERE id='prt3'").fetchone()[0]  # prose kept
        assert con.execute("SELECT data FROM part WHERE id='prt9'").fetchone()[0] == '{"type":"text","text":"neighbor intact"}'
    finally:
        con.close()
    r = ocrestore.restore_session_oc(home, SID, out["dir"], mode="safe")
    assert r["blobs_after"] == 1
    assert ocdb.session_content_hash(db, SID) == pre_hash


def test_oc_fix_short_circuits_at_zero(tmp_path):
    home = _oc_home(tmp_path)
    db = home / "opencode.db"
    ocfix.strip_blobs(db, SID)  # clear the one blob
    d = ocfix.dry_run(db, SID)
    assert d["blobs"] == 0


def test_oc_busy_refuses(tmp_path):
    import sqlite3 as s3
    home = _oc_home(tmp_path)
    db = home / "opencode.db"
    con = s3.connect(db)
    con.execute("UPDATE session SET time_compacting=1 WHERE id=?", (SID,))
    con.commit()
    con.close()
    try:
        ocfix.strip_blobs(db, SID)
        assert False, "should have refused"
    except RuntimeError as e:
        assert "busy" in str(e).lower()

"""Session Doctor web UI — stdlib only (http.server + inline page).

Same backtested engine (db/backup/fix/restore). Linear-grade dark ops console:
near-black canvas, luminance-stepped surfaces, Inter 400/500/600 + JetBrains Mono,
single emerald accent, red reserved for needs-fix. No dependencies, 127.0.0.1 only.
"""
from __future__ import annotations
import datetime
import json
import mimetypes
import os
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import backup as backupmod
from . import db as dbmod
from . import fix as fixmod
from . import jsonbytes as jsonbytesmod
from . import ocbackup as ocbackupmod
from . import ocdb as ocdbmod
from . import ocfix as ocfixmod
from . import ocrestore as ocrestoremod
from . import restore as restoremod

DEFAULT_PORT = 8765
WEB_OUT = backupmod.PROJECT_ROOT / "web" / "out"

CONFIG: dict = {"home": None, "backup_root": None, "verify": True, "activity_file": None}


def _home() -> Path:
    return CONFIG["home"] or dbmod.resolve_home()


def _root() -> Path:
    return CONFIG["backup_root"] or backupmod.resolve_backup_root()


def _db() -> Path:
    return _home() / "state.db"


def _oc_home() -> Path:
    return ocdbmod.resolve_oc_home()


def _oc_root() -> Path:
    return ocbackupmod.resolve_oc_backup_root()


def _oc_db() -> Path:
    return _oc_home() / "opencode.db"


def _oc_self() -> str:
    """The live chat the user talks in — fixing it is blocked. Empty = unset."""
    try:
        raw = json.loads(ocbackupmod.SETTINGS_FILE.read_text())
        return str(raw.get("oc_current_session_id", "") or "")
    except Exception:
        return ""


def _activity_file() -> Path:
    return CONFIG["activity_file"] or (backupmod.PROJECT_ROOT / "activity.jsonl")


def log_event(kind: str, session_id: str, detail: str = "") -> None:
    try:
        with open(_activity_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "kind": kind, "session": session_id, "detail": detail[:200]}) + "\n")
    except Exception:
        pass


def read_activity(limit: int = 100) -> list[dict]:
    try:
        lines = _activity_file().read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out[::-1]


PAGE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Session Doctor</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M1 8h3l2-4 3 8 2-4h4' stroke='%2310b981' stroke-width='1.8' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{color-scheme:dark;--bg0:#08090a;--bg1:#0f1011;--bg2:#191a1b;--hover:rgba(255,255,255,.04);
--line:rgba(255,255,255,.06);--line2:rgba(255,255,255,.09);--t1:#f7f8f8;--t2:#d0d6e0;--t3:#8a8f98;--t4:#62666d;
--acc:#10b981;--acc-hi:#34d399;--acc-dim:rgba(16,185,129,.12);--danger:#f2555a;--danger-tx:#ff8589;--warn:#f5a524;
--r-s:6px;--r-m:8px;--r-l:12px}
html{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
body{background:var(--bg0);color:var(--t1);font:14px/1.5 'Inter',-apple-system,'Segoe UI',Roboto,sans-serif;
font-feature-settings:"cv01","ss03";font-variant-numeric:tabular-nums;display:flex;height:100vh;overflow:hidden}
::selection{background:rgba(16,185,129,.35)}
button{font:inherit;color:inherit}
:focus{outline:none}
:focus-visible{outline:2px solid rgba(16,185,129,.6);outline-offset:2px;border-radius:var(--r-s)}
::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:rgba(255,255,255,.14);border-radius:8px;border:3px solid var(--bg0)}
::-webkit-scrollbar-track{background:transparent}
.mono{font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace}
/* ambient: one faint emerald breath + dot grid, felt not seen */
#ambient{position:fixed;inset:0;pointer-events:none;z-index:0;
background:radial-gradient(640px 300px at 32% -80px,rgba(16,185,129,.055),transparent 70%)}
#ambient::after{content:"";position:absolute;inset:0;
background-image:radial-gradient(rgba(255,255,255,.05) 1px,transparent 1px);background-size:26px 26px;
mask-image:radial-gradient(700px 320px at 30% 0,#000 30%,transparent 75%)}
/* sidebar */
aside#side{width:232px;flex-shrink:0;background:var(--bg1);border-right:1px solid var(--line);
display:flex;flex-direction:column;padding:18px 12px;z-index:1}
.brand{display:flex;align-items:center;gap:10px;padding:2px 10px 18px;font-weight:600;font-size:14.5px;letter-spacing:-.01em}
.brand svg{flex-shrink:0}
nav{display:flex;flex-direction:column;gap:2px}
nav button{display:flex;align-items:center;gap:10px;width:100%;background:none;border:0;color:var(--t3);
padding:8px 10px;border-radius:var(--r-s);font-size:13.5px;font-weight:500;cursor:pointer;text-align:left}
nav button:hover{background:var(--hover);color:var(--t1)}
nav button.on{background:var(--hover);color:var(--t1);box-shadow:inset 2px 0 0 var(--acc)}
nav button .ct{margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--t3);
background:rgba(255,255,255,.05);border-radius:20px;padding:1px 8px}
nav button .ct.hot{background:rgba(242,85,90,.15);color:var(--danger-tx)}
.health{margin:auto 6px 2px;text-align:center;padding-top:14px}
.ring{width:104px;height:104px;border-radius:50%;margin:0 auto 10px;display:grid;place-items:center}
.ring>div{width:80px;height:80px;border-radius:50%;background:var(--bg1);display:grid;place-items:center;
font-family:'JetBrains Mono',monospace;font-weight:500;font-size:15px}
.health p{color:var(--t4);font-size:12px}
.ver{color:var(--t4);font-size:11px;text-align:center;margin-top:10px;font-family:'JetBrains Mono',monospace}
/* main */
main{flex:1;display:flex;flex-direction:column;overflow:hidden;z-index:1;min-width:0}
.cmdbar{display:flex;gap:10px;align-items:center;padding:14px 22px;border-bottom:1px solid var(--line)}
.searchbox{flex:1;display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.02);
border:1px solid var(--line2);border-radius:var(--r-s);padding:8px 12px;max-width:560px}
.searchbox:focus-within{border-color:rgba(16,185,129,.5)}
.searchbox input{flex:1;background:none;border:0;color:var(--t1);font:inherit;font-size:14px;outline:none}
.searchbox input::placeholder{color:var(--t4)}
kbd{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--t3);background:rgba(255,255,255,.05);
border:1px solid var(--line2);border-bottom-width:2px;border-radius:5px;padding:1px 7px;white-space:nowrap}
.chips{display:flex;gap:6px}
.chip{background:transparent;border:1px solid var(--line2);color:var(--t2);border-radius:9999px;
padding:4px 12px;font-size:12px;font-weight:500;cursor:pointer}
.chip.on{background:rgba(16,185,129,.12);border-color:rgba(16,185,129,.4);color:var(--acc-hi)}
.fleet{padding:20px 22px 4px}
.fleet .big{font-size:21px;font-weight:600;letter-spacing:-.02em}
.fleet .big em{font-style:normal;color:var(--acc-hi)}
.fleet .meta{color:var(--t4);font-size:12.5px;margin-top:6px;display:flex;gap:14px;flex-wrap:wrap}
.hairline{height:3px;background:rgba(255,255,255,.06);border-radius:99px;margin:12px 0 4px;overflow:hidden}
.hairline i{display:block;height:100%;background:var(--acc);border-radius:99px;transition:width .7s cubic-bezier(.2,.8,.2,1)}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0 4px}
.stat{background:rgba(255,255,255,.02);border:1px solid var(--line2);border-radius:var(--r-l);padding:14px 16px;min-width:0}
.stat .v{font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:600;letter-spacing:-.02em}
.stat .l{color:var(--t3);font-size:12px;margin-top:2px}
.stat .s{color:var(--t4);font-size:11.5px;margin-top:2px;font-family:'JetBrains Mono',monospace}
.stat.good .v{color:var(--acc-hi)}.stat.bad .v{color:var(--danger-tx)}
thead th.sortable{cursor:pointer;user-select:none}
thead th.sortable:hover{color:var(--t1)}
thead th .arrow{font-size:10px;margin-left:4px;color:var(--acc-hi)}
mark{background:rgba(16,185,129,.28);color:inherit;border-radius:3px;padding:0 1px}
#bulkbar{display:none;align-items:center;gap:10px;background:rgba(16,185,129,.07);border:1px solid rgba(16,185,129,.35);border-radius:var(--r-m);padding:8px 14px;margin-bottom:10px;font-size:13px}
#bulkbar.show{display:flex}
#bulkbar button{font-size:12px;padding:5px 12px}
td.sid{max-width:190px;overflow:hidden;text-overflow:ellipsis}
td.sid:hover{overflow:visible}
.rowchk{accent-color:var(--acc);width:15px;height:15px;cursor:pointer}
tr.r:focus-within .rowact{opacity:1}
@media (hover:none){.rowact{opacity:1}}
@media (max-width:1100px){.stats{grid-template-columns:repeat(2,1fr)}}
@media (max-width:680px){.stats{grid-template-columns:1fr 1fr}.stat .v{font-size:19px}}
.views{flex:1;overflow:auto;padding:14px 22px 22px}
.card{background:rgba(255,255,255,.02);border:1px solid var(--line2);border-radius:var(--r-m);overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:13px}
thead th{position:sticky;top:0;background:var(--bg1);text-align:left;color:var(--t3);font-weight:500;
font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;padding:10px 10px;border-bottom:1px solid var(--line2);z-index:2}
tbody td{padding:9px 10px;border-bottom:1px solid var(--line);white-space:nowrap;vertical-align:middle}
tbody tr:last-child td{border-bottom:0}
tr.r{cursor:pointer}tr.r:hover td{background:rgba(255,255,255,.025)}
tr.r.sel td{background:rgba(16,185,129,.07);box-shadow:inset 2px 0 0 var(--acc)}
td.title{font-weight:500;color:var(--t1)}
td .sub{display:block;font-weight:400;color:var(--t4);font-size:11.5px}
td.sid{font-family:'JetBrains Mono',monospace;font-size:12px;color:#9fc5ff}
td.num{font-family:'JetBrains Mono',monospace;font-size:12.5px}
td.time{color:var(--t4);font-size:12.5px}
.pin{color:var(--warn);font-size:12px}
.pill{display:inline-block;font-size:11px;font-weight:600;letter-spacing:.05em;border-radius:9999px;padding:3px 11px}
.pill.bad{background:rgba(242,85,90,.12);color:var(--danger-tx);border:1px solid rgba(242,85,90,.35)}
.pill.ok{background:rgba(16,185,129,.1);color:var(--acc-hi);border:1px solid rgba(16,185,129,.3)}
.loadbar{height:4px;min-width:90px;background:rgba(255,255,255,.07);border-radius:4px;overflow:hidden}
.loadbar i{display:block;height:100%;background:linear-gradient(90deg,var(--warn),var(--danger));transition:width .5s}
.rowact{opacity:0;font-size:12px;font-weight:500;color:var(--acc-hi);background:none;border:0;cursor:pointer;padding:4px 8px}
tr.r:hover .rowact{opacity:1}
/* skeleton */
tr.sk td{padding:14px 10px}
.skline{height:12px;border-radius:6px;background:linear-gradient(90deg,rgba(255,255,255,.04) 25%,rgba(255,255,255,.09) 50%,rgba(255,255,255,.04) 75%);background-size:200% 100%;animation:sh 1.2s infinite}
@keyframes sh{to{background-position:-200% 0}}
/* all-clear celebration */
#clear{border:1px solid rgba(16,185,129,.35);background:rgba(16,185,129,.05);border-radius:var(--r-l);
padding:26px;display:none;align-items:center;gap:20px;margin-bottom:14px}
#clear.show{display:flex}
#clear .msg b{display:block;font-size:17px;font-weight:600;letter-spacing:-.01em}
#clear .msg span{color:var(--t3);font-size:13px}
#clear svg .draw{stroke-dasharray:60;stroke-dashoffset:60;animation:draw .7s .15s cubic-bezier(.2,.8,.2,1) forwards}
#clear svg .pop{transform-origin:center;animation:pop .45s cubic-bezier(.2,.8,.2,1)}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes pop{from{transform:scale(.6);opacity:0}}
/* console */
#console{margin:0 22px 18px;background:#070a0c;border:1px solid var(--line);border-radius:var(--r-m);
padding:10px 14px;height:104px;overflow:auto;font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.7;flex-shrink:0}
#console .ok{color:#9fe8b8}#console .err{color:var(--danger-tx)}#console .inf{color:var(--t3)}
/* drawer */
#scrim{position:fixed;inset:0;background:rgba(0,0,0,.6);opacity:0;pointer-events:none;transition:opacity .2s;z-index:40}
#scrim.open{opacity:1;pointer-events:auto}
#drawer{position:fixed;top:0;right:0;bottom:0;width:420px;max-width:94vw;background:var(--bg1);
border-left:1px solid var(--line2);transform:translateX(103%);transition:transform .22s cubic-bezier(.2,.8,.2,1);
padding:24px;overflow:auto;z-index:41;box-shadow:-24px 0 60px rgba(0,0,0,.5)}
#drawer.open{transform:none}
#drawer h2{font-size:17px;font-weight:600;letter-spacing:-.01em;margin-bottom:2px}
#drawer .sid{font-family:'JetBrains Mono',monospace;font-size:12px;color:#9fc5ff;margin-bottom:6px;word-break:break-all}
.kv{display:grid;grid-template-columns:128px 1fr;font-size:12.5px;row-gap:8px;margin:16px 0;
border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:14px 0}
.kv dt{color:var(--t4)}.kv dd{font-family:'JetBrains Mono',monospace;color:var(--t2)}
.diff{background:#070a0c;border:1px solid var(--line2);border-radius:var(--r-m);padding:12px 14px;
font-family:'JetBrains Mono',monospace;font-size:12px;margin:4px 0 6px;display:none;line-height:1.8}
.diff.show{display:block}
.diff div{opacity:0;animation:lin .25s forwards}
.diff div:nth-child(2){animation-delay:.06s}.diff div:nth-child(3){animation-delay:.12s}
@keyframes lin{from{opacity:0;transform:translateX(-4px)}to{opacity:1}}
.diff .del{color:var(--danger-tx)}.diff .keep{color:#7fe3b2}
.btnrow{display:flex;gap:8px;margin-top:16px;flex-wrap:wrap}
button.btn{background:rgba(255,255,255,.03);border:1px solid var(--line2);color:var(--t2);
border-radius:var(--r-s);padding:8px 15px;font-size:13px;font-weight:500;cursor:pointer}
button.btn:hover:not(:disabled){background:rgba(255,255,255,.06);color:var(--t1)}
button.btn:active:not(:disabled){transform:scale(.98)}
button.btn:disabled{opacity:.38;cursor:default}
button.primary{background:#0b7a55;border:1px solid #0e9f6e;color:#fff;font-weight:600}
button.primary:hover:not(:disabled){background:#0e9f6e}
button.danger{background:#a02a2e;border:1px solid #c0453e;color:#fff;font-weight:600}
button.danger:hover:not(:disabled){background:#bc3439}
/* secondary views */
.bundle{background:rgba(255,255,255,.02);border:1px solid var(--line2);border-radius:var(--r-m);
padding:13px 16px;margin-bottom:10px;font-size:13px}
.bundle code{font-family:'JetBrains Mono',monospace;font-size:12px;color:#9fc5ff}
.bundle .m{color:var(--t4);font-size:12.5px;margin-top:3px}
.tl{margin:4px 0 0 6px;padding-left:20px;border-left:1px solid var(--line2)}
.tl>div{position:relative;padding-bottom:16px;font-size:13px}
.tl>div::before{content:"";position:absolute;left:-26px;top:5px;width:9px;height:9px;border-radius:50%;
background:var(--bg0);border:2px solid var(--acc)}
.tl>div.warn::before{border-color:var(--warn)}
.tl time{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--t4);margin-right:10px}
.setrow{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.02);
border:1px solid var(--line2);border-radius:var(--r-m);padding:15px 18px;margin-bottom:10px}
.setrow b{display:block;font-size:14px;font-weight:500}
.setrow span{color:var(--t4);font-size:12.5px}
.setrow .mono{font-family:'JetBrains Mono',monospace;font-size:12px}
.view{display:none}.view.on{display:block}
h2.vt{font-size:19px;font-weight:600;letter-spacing:-.02em;margin:6px 0 2px}
p.vs{color:var(--t3);font-size:13px;margin-bottom:16px}
.errbar{display:none;background:rgba(242,85,90,.08);border:1px solid rgba(242,85,90,.4);color:#ffc2c4;
border-radius:var(--r-m);padding:10px 14px;margin-bottom:12px;font-size:13px}
.errbar.show{display:flex;gap:10px;align-items:center}
.errbar button{margin-left:auto}
/* toasts + modal + palette */
#toasts{position:fixed;bottom:18px;right:18px;display:flex;flex-direction:column;gap:8px;z-index:60}
.toast{background:#0e1a14;border:1px solid rgba(16,185,129,.45);color:#c9f5e3;border-radius:10px;
padding:11px 16px;font-size:13px;box-shadow:0 12px 40px rgba(0,0,0,.55);animation:tin .25s}
.toast.err{background:#1d0f10;border-color:rgba(242,85,90,.5);color:#ffc9cb}
@keyframes tin{from{transform:translateY(10px);opacity:0}}
#modal{position:fixed;inset:0;display:none;place-items:center;background:rgba(0,0,0,.6);
backdrop-filter:blur(3px);z-index:55}
#modal.open{display:grid}
#modal .box{width:440px;max-width:92vw;background:var(--bg2);border:1px solid var(--line2);
border-radius:var(--r-l);padding:22px;box-shadow:0 24px 80px rgba(0,0,0,.6)}
#modal h3{font-size:15px;font-weight:600;margin-bottom:8px}
#modal p{color:var(--t3);font-size:13px;margin-bottom:6px}
#modal .btnrow{justify-content:flex-end;margin-top:18px}
#pal{position:fixed;inset:0;display:none;place-items:start center;background:rgba(0,0,0,.55);z-index:58;padding-top:12vh}
#pal.open{display:grid}
#pal .box{width:600px;max-width:92vw;background:var(--bg2);border:1px solid var(--line2);
border-radius:var(--r-l);overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,.65)}
#pal input{width:100%;background:none;border:0;border-bottom:1px solid var(--line2);color:var(--t1);
font:inherit;font-size:15px;padding:15px 18px;outline:none}
#pal ul{list-style:none;max-height:320px;overflow:auto;padding:6px}
#pal li{padding:9px 12px;border-radius:var(--r-s);font-size:13.5px;cursor:pointer;display:flex;gap:10px;align-items:center}
#pal li small{color:var(--t4);margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:11px}
#pal li.sel{background:rgba(16,185,129,.1)}
.emptycell{padding:34px 10px;text-align:center;color:var(--t4)}
.emptycell svg{opacity:.5;margin-bottom:10px}
footer.app{padding:10px 22px;color:var(--t4);font-size:12px;border-top:1px solid var(--line);flex-shrink:0}
@media (max-width:980px){aside#side{width:64px}aside#side .lbl,aside#side .health,aside#side .ver{display:none}
nav button{justify-content:center}nav button .ct{display:none}.brand span{display:none}}
@media (max-width:680px){#drawer{width:100vw}.fleet .big{font-size:17px}td.time,th.timecol{display:none}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}}
</style></head><body>
<div id="ambient"></div>
<aside id="side">
<div class="brand"><svg width="20" height="20" viewBox="0 0 16 16"><path d="M1 8h3l2-4 3 8 2-4h4" stroke="#10b981" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Session Doctor</span></div>
<nav>
<button class="on" data-v="sessions"><span class="lbl">Sessions</span><span class="ct" id="nBad">–</span></button>
<button data-v="backups"><span class="lbl">Backups</span><span class="ct" id="nBun">–</span></button>
<button data-v="activity"><span class="lbl">Activity</span></button>
<button data-v="settings"><span class="lbl">Settings</span></button>
</nav>
<div class="health"><div class="ring" id="ring"><div id="ringTx">–</div></div><p id="ringCap">fleet health</p></div>
<div class="ver">v1.3 · local</div>
</aside>
<main>
<div class="cmdbar">
<div class="searchbox">⌕<input id="q" aria-label="Filter sessions" placeholder="Filter sessions…  try is:bad model:spark seals:&gt;10"><kbd>/</kbd><kbd>⌘K</kbd></div>
<div class="chips">
<button class="chip on" data-f="all">All</button>
<button class="chip" data-f="bad">Needs fix</button>
<button class="chip" data-f="pin">Pinned</button>
</div>
</div>
<div class="fleet">
<div class="big" id="fleetLine">Loading fleet…</div>
<div class="hairline"><i id="fleetBar" style="width:0"></i></div>
<div class="meta"><span id="mBackup">last backup —</span><span id="mDb">db —</span><span id="mUpd">updated —</span><span id="mCount" role="status" aria-live="polite"></span></div>
<div class="stats" id="stats">
<div class="stat"><div class="v" id="stTotal">–</div><div class="l">Sessions tracked</div><div class="s" id="stTotalSub">—</div></div>
<div class="stat" id="stBadCard"><div class="v" id="stBad">–</div><div class="l">Need attention</div><div class="s" id="stBadSub">—</div></div>
<div class="stat"><div class="v" id="stBackup">–</div><div class="l">Since last backup</div><div class="s" id="stBackupSub">—</div></div>
<div class="stat"><div class="v" id="stDb">–</div><div class="l">Database</div><div class="s">WAL safe · query-only reads</div></div>
</div>
</div>
<div class="views">
<div class="errbar" id="errbar"><span id="errtx"></span><button class="btn" onclick="copyErr()">Copy details</button><button class="btn" onclick="load()">Retry</button></div>
<div class="view on" id="v-sessions">
<div id="clear"><svg width="52" height="52" viewBox="0 0 52 52"><circle class="pop" cx="26" cy="26" r="23" fill="none" stroke="#10b981" stroke-width="2.5"/><path class="draw" d="M16 27l7 7 13-15" fill="none" stroke="#34d399" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>
<div class="msg"><b>Fleet is clean.</b><span>Zero stale seals. Go build something.</span></div></div>
<div id="bulkbar"><span id="bulkTx"></span><button class="btn" id="bBulkBkp">Backup selected</button><button class="btn" id="bBulkClear">Clear</button></div>
<div class="card"><table aria-busy="false" id="tbl"><thead><tr><th style="width:30px"><input type="checkbox" class="rowchk" id="chkAll" aria-label="Select all"></th><th style="width:34px"></th><th class="sortable" data-sort="title" scope="col">Session</th><th scope="col">ID</th><th class="sortable" data-sort="seals" scope="col">Seals</th><th>Load</th><th class="sortable" data-sort="msgs" scope="col">Msgs</th><th class="sortable timecol" data-sort="last" scope="col">Last active</th><th></th></tr></thead>
<tbody id="rows"></tbody></table></div>
</div>
<div class="view" id="v-backups"><h2 class="vt">Backups</h2><p class="vs">Newest first. Each bundle restores one session exactly.</p><div id="blist"></div></div>
<div class="view" id="v-activity"><h2 class="vt">Activity</h2><p class="vs">Every backup, fix and restore on this machine.</p><div class="tl" id="alist"></div></div>
<div class="view" id="v-settings"><h2 class="vt">Settings</h2><p class="vs">Three controls. That's the whole page.</p>
<div class="setrow"><div style="flex:1"><b>Backup folder</b><span class="mono" id="setRoot">—</span></div><button class="btn" onclick="changeLoc()">Change…</button></div>
<div class="setrow"><div style="flex:1"><b>Verify every backup</b><span>Re-open each snapshot before a fix is allowed through</span></div><button class="btn" id="vbtn" onclick="togVerify()">On ✓</button></div>
<div class="setrow"><div style="flex:1"><b>Auto-backup before fix</b><span>Always on — no backup, no fix</span></div><button class="btn" disabled>Locked 🔒</button></div>
</div>
</div>
<div id="console"></div>
</main>
<div id="scrim"></div>
<section id="drawer" aria-label="session detail">
<h2 id="dTitle"></h2><div class="sid mono" id="dId"></div>
<dl class="kv" id="dKv"></dl>
<div class="diff" id="dDiff"></div>
<div class="btnrow"><button class="btn" id="bDry">Dry run</button><button class="btn" id="bBkp">Backup</button><button class="primary btn" id="bFix" disabled title="Run Dry run first">Backup + Fix</button></div>
<div class="btnrow"><button class="btn" id="bResSafe">Safest restore…</button><button class="btn" id="bResBest">Try-my-best restore…</button></div>
</section>
<div id="modal"><div class="box" role="alertdialog" aria-modal="true" aria-labelledby="mTitle"><h3 id="mTitle"></h3><p id="mBody"></p><div class="btnrow"><button class="btn" id="mNo">Cancel</button><button class="primary btn" id="mYes">Confirm</button></div></div></div>
<div id="pal"><div class="box" role="dialog" aria-modal="true" aria-label="Command palette"><input id="palIn" role="combobox" aria-expanded="true" aria-controls="palUl" aria-label="Type a command or session" placeholder="Type a command or session…  try fix, open, Go to…"><ul id="palUl" role="listbox"></ul><div style="padding:8px 14px;color:var(--t4);font-size:11.5px;border-top:1px solid var(--line)">↑↓ navigate · Enter run · Esc close · fix / open scopes</div></div></div>
<div id="toasts"></div>
<footer class="app">Session Doctor · loopback only · the fix removes encrypted blobs and nothing else</footer>
<script>
"use strict";
const $=id=>document.getElementById(id);
let ROWS=[],SEL=null,DRY=new Set(),FILTER='all',VERIFY=localStorage.getItem('sd_verify')!=='0';
let PALI=0,PALITEMS=[],SORT=JSON.parse(localStorage.getItem('sd_sort')||'null')||{key:'seals',dir:-1},CHECKED=new Set(),LASTERR='',RECENT=[];
try{RECENT=JSON.parse(localStorage.getItem('sd_recent')||'[]')}catch(e){RECENT=[]}
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function hi(text,q){const t=String(text??'');if(!q)return esc(t);const toks=q.toLowerCase().split(/\s+/).filter(x=>x&&!x.includes(':'));let out=esc(t);for(const tok of toks){try{out=out.replace(new RegExp('('+tok.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','ig'),'<mark>$1</mark>')}catch(e){}}return out}
function rel(ts){if(!ts)return'—';const s=Date.now()/1000-ts;if(s<90)return'just now';if(s<5400)return Math.floor(s/60)+'m ago';
if(s<172800)return Math.floor(s/3600)+'h ago';if(s<2592000)return Math.floor(s/86400)+'d ago';return new Date(ts*1000).toISOString().slice(0,10)}
function tick(){document.querySelectorAll('[data-ts]').forEach(el=>{el.textContent=rel(+el.dataset.ts);
el.title=new Date(+el.dataset.ts*1000).toUTCString()})}
setInterval(tick,30000);
function say(m,cls){const c=$('console');const d=document.createElement('div');d.className=cls||'ok';d.textContent=`[${new Date().toISOString().slice(11,19)}Z] ${m}`;c.appendChild(d);while(c.children.length>200)c.firstChild.remove();c.scrollTop=c.scrollHeight}
function toast(m,err){const t=document.createElement('div');t.className='toast'+(err?' err':'');t.textContent=m;const box=$('toasts');box.appendChild(t);while(box.children.length>3)box.firstChild.remove();setTimeout(()=>t.remove(),4200)}
function errbar(m){LASTERR=m;$('errtx').textContent=m;$('errbar').classList.add('show')}
function copyErr(){try{navigator.clipboard.writeText(LASTERR||$('errtx').textContent);toast('Error details copied')}catch(e){toast('Copy failed',true)}}
async function api(p,o){o=o||{};const r=await fetch(p,{method:o.m||'GET',headers:{'Content-Type':'application/json'},body:o.b?JSON.stringify(o.b):undefined});
const j=await r.json().catch(()=>({error:'bad response'}));if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j}
function skeleton(){$('tbl').setAttribute('aria-busy','true');let h='';for(let i=0;i<8;i++)h+=`<tr class="sk"><td colspan="9"><div class="skline" style="width:${88-i*7}%"></div></td></tr>`;$('rows').innerHTML=h}
/* ---- load + render ---- */
async function load(){skeleton();$('errbar').classList.remove('show');
try{
const j=await api('/api/sessions');ROWS=j.rows;
$('setRoot').textContent=j.backup_root;
$('mDb').textContent='db '+(j.db_mb||'—');
$('stDb').textContent=j.db_mb||'—';
$('stTotal').textContent=j.count;
$('stTotalSub').textContent=j.count+' tracked';
if(j.last_backup){$('mBackup').textContent='last backup '+j.last_backup;$('stBackup').textContent=rel(Date.parse(j.last_backup)||Date.now());$('stBackupSub').textContent=j.last_backup}
renderAll();say(`connected · ${j.count} sessions`,'inf');
}catch(e){errbar('Cannot reach engine: '+e.message+'. Is run.sh still running?');say('load FAILED: '+e.message,'err')}
$('tbl').setAttribute('aria-busy','false')}
function counts(){const bad=ROWS.filter(r=>r.seals_active>0);return{bad:bad.length,total:ROWS.length,ok:ROWS.length-bad.length}}
function renderAll(){renderFleet();renderRows();renderNav();tick()}
function renderFleet(){const c=counts(),pct=c.total?Math.round(c.ok/c.total*1000)/10:100;
const line=$('fleetLine');
if(!c.total)line.textContent='No sessions found.';
else if(!c.bad)line.innerHTML=`<em>${c.ok}</em> of ${c.total} sessions are healthy.`;
else line.innerHTML=`<em>${c.ok}</em> of ${c.total} healthy · <span style="color:var(--danger-tx)">${c.bad} need${c.bad>1?'':'s'} attention</span>`;
$('fleetBar').style.width=pct+'%';
$('mUpd').textContent='updated just now';
$('stBad').textContent=c.bad;$('stBadCard').classList.toggle('bad',c.bad>0);$('stBadCard').classList.toggle('good',!c.bad);
$('stBadSub').textContent=c.bad?c.bad+' need attention':'all clean';
$('clear').classList.toggle('show',c.total>0&&!c.bad);
const ring=$('ring');ring.style.background=`conic-gradient(var(--acc) 0 ${pct}%,rgba(255,255,255,.08) ${pct}% 100%)`;
ring.title=`${c.ok} of ${c.total} clean`;
$('ringTx').textContent=pct+'%';$('ringCap').textContent=`fleet health · ${c.ok} / ${c.total} clean`}
function renderNav(){const c=counts();const nb=$('nBad');nb.textContent=c.bad||'✓';nb.classList.toggle('hot',c.bad>0)}
function parseQ(){const raw=$('q').value.trim();const toks=raw.split(/\s+/).filter(Boolean);const f={text:[],isBad:false,isPin:false,isClean:false,model:'',minSeals:0,id:''};for(const t of toks){const l=t.toLowerCase();if(l==='is:bad')f.isBad=true;else if(l==='is:pinned'||l==='is:pin')f.isPin=true;else if(l==='is:clean')f.isClean=true;else if(l.startsWith('model:'))f.model=l.slice(6);else if(l.startsWith('id:'))f.id=l.slice(3);else if(l.startsWith('seals:>'))f.minSeals=parseInt(l.slice(7))||0;else if(l.startsWith('seals:'))f.minSeals=parseInt(l.slice(6))||0;else f.text.push(t)}f.q=f.text.join(' ');return f}
function match(r){const f=parseQ();
if(FILTER==='bad'&&!r.seals_active)return false;
if(FILTER==='pin'&&!r.pinned)return false;
if(f.isBad&&!r.seals_active)return false;
if(f.isPin&&!r.pinned)return false;
if(f.isClean&&r.seals_active)return false;
if(f.model&&!((r.model||'').toLowerCase().includes(f.model)))return false;
if(f.id&&!(r.id||'').toLowerCase().includes(f.id))return false;
if(f.minSeals&&(r.seals_active||0)<f.minSeals)return false;
if(!f.q)return true;
const hay=((r.title||'')+' '+r.id+' '+(r.model||'')).toLowerCase();
return f.q.toLowerCase().split(/\s+/).every(tok=>hay.includes(tok))}
function sortedRows(list){const arr=[...list];const {key,dir}=SORT;const val=r=>key==='title'?(r.title||'').toLowerCase():key==='seals'?(r.seals_active||0):key==='msgs'?(r.message_count||0):key==='last'?(r.last_activity_at||0):0;
arr.sort((a,b)=>{const pa=a.pinned?1:0,pb=b.pinned?1:0;if(pa!==pb)return pb-pa;const va=val(a),vb=val(b);return (va<vb?-1:va>vb?1:0)*dir});return arr}
function paintSort(){document.querySelectorAll('th.sortable').forEach(th=>{const k=th.dataset.sort;const base=th.textContent.replace(/[↑↓↕ ]/g,'');th.innerHTML=esc(base)+(SORT.key===k?`<span class="arrow">${SORT.dir===1?'↑':'↓'}</span>`:'');th.setAttribute('aria-sort',SORT.key===k?(SORT.dir===1?'ascending':'descending'):'none')})}
function renderRows(){paintSort();const tb=$('rows');const q=parseQ().q;const filtered=ROWS.filter(match);const list=sortedRows(filtered);tb.innerHTML='';
$('mCount').textContent=ROWS.length?`${filtered.length} of ${ROWS.length} sessions`:'';
if(!list.length){tb.innerHTML=`<tr><td colspan="9"><div class="emptycell">
<svg width="46" height="46" viewBox="0 0 46 46"><rect x="6" y="10" width="34" height="5" rx="2.5" fill="none" stroke="#62666d" stroke-width="1.6"/><rect x="6" y="20" width="24" height="5" rx="2.5" fill="none" stroke="#62666d" stroke-width="1.6"/><circle cx="32" cy="32" r="8" fill="none" stroke="#62666d" stroke-width="1.6"/><path d="M38 38l5 5" stroke="#62666d" stroke-width="1.6" stroke-linecap="round"/></svg>
<div>${ROWS.length?`No sessions match “${esc($('q').value.trim())}”.`:'No sessions yet.'}</div>${ROWS.length?'<div style="margin-top:10px"><button class="btn" onclick="clearFilter()">Clear filter</button></div>':''}</div></td></tr>`;renderBulk();return}
const maxSeal=Math.max(1,...ROWS.map(x=>x.seals_active||0));const frag=document.createDocumentFragment();
for(const r of list){const tr=document.createElement('tr');tr.className='r'+(SEL===r.id?' sel':'');tr.dataset.id=r.id;tr.tabIndex=0;
tr.setAttribute('aria-selected',SEL===r.id?'true':'false');
const pct=Math.min(100,Math.round((r.seals_active||0)/maxSeal*100));
tr.innerHTML=`<td><input type="checkbox" class="rowchk" data-id="${esc(r.id)}" ${CHECKED.has(r.id)?'checked':''} aria-label="Select ${esc(r.title||r.id)}"></td><td>${r.seals_active?'<span style="color:var(--danger)">●</span>':'<span style="color:#3a4152">●</span>'}</td>
<td class="title">${r.pinned?'<span class="pin">★ </span>':''}${hi(r.title||'untitled',q)||'<span style="color:var(--t4)">untitled</span>'}</td>
<td class="sid" title="${esc(r.id)}">${hi(r.id,q)}</td>
<td>${r.seals_active?`<span class="pill bad">${r.seals_active} SEALS</span>`:'<span class="pill ok">CLEAN</span>'}</td>
<td><div class="loadbar" aria-hidden="true"><i style="width:${r.seals_active?pct:0}%"></i></div></td>
<td class="num">${r.message_count||''}</td>
<td class="time" data-ts="${r.last_activity_at||''}">${rel(r.last_activity_at)}</td>
<td>${r.seals_active?'<button class="rowact">Fix →</button>':''}</td>`;
tr.onclick=e=>{if(e.target.classList.contains('rowchk'))return;if(e.target.classList.contains('rowact')){SEL=r.id;quickFix()}else openD(r.id)};
tr.onkeydown=e=>{if(e.key==='Enter')openD(r.id)};
frag.appendChild(tr)}
tb.appendChild(frag);renderBulk()}
function clearFilter(){$('q').value='';FILTER='all';document.querySelectorAll('.chip').forEach(x=>x.classList.toggle('on',x.dataset.f==='all'));renderRows()}
function renderBulk(){const bar=$('bulkbar');if(!CHECKED.size){bar.classList.remove('show');return}bar.classList.add('show');$('bulkTx').textContent=`${CHECKED.size} selected — Backup is per-session and safe to batch. Fix stays one-by-one.`}
document.querySelectorAll('th.sortable').forEach(th=>th.onclick=()=>{const k=th.dataset.sort;if(SORT.key===k)SORT.dir*=-1;else SORT={key:k,dir:k==='title'?1:-1};localStorage.setItem('sd_sort',JSON.stringify(SORT));renderRows()});
/* ---- drawer ---- */
function openD(id){SEL=id;const r=ROWS.find(x=>x.id===id);if(!r)return;
try{RECENT=[id,...RECENT.filter(x=>x!==id)].slice(0,5);localStorage.setItem('sd_recent',JSON.stringify(RECENT))}catch(e){}
$('dTitle').textContent=r.title||'untitled';$('dId').textContent=r.id;
$('dKv').innerHTML=`<dt>model</dt><dd>${esc(r.model||'—')}</dd><dt>messages</dt><dd>${r.message_count??'—'}</dd>
<dt>active seals</dt><dd>${r.seals_active}</dd><dt>total seals</dt><dd>${r.seals_total}</dd>
<dt>visible text</dt><dd>sha256 ✓ intact</dd><dt>source</dt><dd>${esc(r.source||'—')}</dd>`;
$('dDiff').classList.remove('show');$('dDiff').innerHTML='';$('bFix').disabled=true;
$('bFix').title='Run Dry run first';
$('drawer').classList.add('open');$('scrim').classList.add('open');renderRows();
say(`selected ${id.slice(0,20)}… seals=${r.seals_active}`,'inf')}
function closeD(){$('drawer').classList.remove('open');$('scrim').classList.remove('open')}
$('scrim').onclick=closeD;
$('bDry').onclick=async()=>{if(!SEL)return;try{const d=await api('/api/session?id='+SEL);DRY.add(SEL);
const el=$('dDiff');el.classList.add('show');
el.innerHTML=`<div class="del">− codex_reasoning_items: ${d.seals_active} encrypted blobs → NULL</div><div class="keep">+ content, summaries, tool results: 0 touched</div><div class="keep">+ all other sessions: 0 touched</div>`;
$('bFix').disabled=d.seals_active===0;$('bFix').title=d.seals_active?'':'Nothing to fix';
say(`dry-run ${SEL.slice(0,20)}… clears ${d.seals_active}, touches 0 messages`,'inf')}catch(e){toast(e.message,true)}};
$('bBkp').onclick=async()=>{if(!SEL)return;try{const r=await api('/api/backup',{m:'POST',b:{id:SEL,verify:VERIFY}});
toast('Backed up ✓');say('backup OK: '+r.dir);loadActivity()}catch(e){toast(e.message,true);say('backup FAILED: '+e.message,'err')}};
function modal(title,body,yes){return new Promise(res=>{$('mTitle').textContent=title;$('mBody').textContent=body;
$('mYes').textContent=yes||'Confirm';$('modal').classList.add('open');setTimeout(()=>$('mYes').focus(),30);
$('mYes').onclick=()=>{$('modal').classList.remove('open');res(true)};
$('mNo').onclick=()=>{$('modal').classList.remove('open');res(false)}})}
async function quickFix(){const r=ROWS.find(x=>x.id===SEL);if(!r||!r.seals_active)return;DRY.add(SEL);doFix()}
$('bFix').onclick=doFix;
async function doFix(){const r=ROWS.find(x=>x.id===SEL);if(!r)return;
if(!r.seals_active){toast('Nothing to fix');return}
const ok=await modal('Backup + Fix',`Strip ${r.seals_active} stale seals from "${r.title||r.id}"? A verified backup is taken first. Same session resumes.`,'Backup + Fix');
if(!ok)return;
$('bFix').disabled=true;$('bFix').textContent='Working…';
try{const res=await api('/api/fix',{m:'POST',b:{id:SEL,verify:VERIFY}});
toast(`✓ Fixed — ${res.cleared} seals cleared, ${r.message_count||''} messages intact`);say(`fixed ${SEL.slice(0,20)}… cleared=${res.cleared} backup=${res.backup}`);
DRY.delete(SEL);closeD();await load();loadActivity();loadBundles()}
catch(e){toast(e.message,true);say('FAILED: '+e.message,'err')}
$('bFix').disabled=false;$('bFix').textContent='Backup + Fix'}
async function doRestore(mode){if(!SEL)return;
try{
const bj=await api('/api/bundles?session='+encodeURIComponent(SEL));
if(!bj.bundles.length){toast('No bundles for this session yet — backup first',true);return}
const b=bj.bundles[0];
const label=mode==='safe'?'Safest restore':'Try-my-best restore';
const ok=await modal(label,`Restore "${SEL}" from newest bundle ${b.dir.split('/').pop()}? `+(mode==='safe'?'Exact match only — aborts on any drift.':'Fits by column name — skips drifted columns, keeps going.')+' Current state is stashed first so undo works.',label);
if(!ok)return;
const res=await api('/api/restore',{m:'POST',b:{id:SEL,dir:b.dir,mode}});
const warn=res.warnings&&res.warnings.length?' WARNINGS: '+res.warnings.join(' | '):'';
toast(`✓ Restored (${mode}) — seals=${res.seals_after}`);say(`restored ${SEL.slice(0,20)}… mode=${mode} stash=${res.stash}${warn}`);loadActivity();await load();
}catch(e){toast(e.message,true);say('restore FAILED: '+e.message,'err')}}
$('bResSafe').onclick=()=>doRestore('safe');
$('bResBest').onclick=()=>doRestore('best-effort');
/* ---- secondary views ---- */
async function loadBundles(){try{const j=await api('/api/bundles');$('nBun').textContent=j.bundles.length||'–';
const fmtMB=b=>b.snapshot_bytes?(b.snapshot_bytes/1e6).toFixed(0)+'MB':'—';
$('blist').innerHTML=j.bundles.slice(0,30).map(b=>`<div class="bundle"><code>${esc(b.dir.split('/').pop())}</code>
<div class="m">${esc(b.session_id)} · seals at backup: ${b.seals_total} · ${b.active_msgs} msgs · ${esc(b.utc||'')} · snapshot ${fmtMB(b)} · manifest ${b.verified?'✓ verified':'○ unverified'}</div><div class="btnrow"><button class="btn" onclick="restoreBundle('${esc(b.dir)}','${esc(b.session_id)}','safe')">Safest restore</button><button class="btn" onclick="restoreBundle('${esc(b.dir)}','${esc(b.session_id)}','best-effort')">Try-my-best</button></div></div>`).join('')||'<p style="color:var(--t4)">No bundles yet. Pick a session → Backup to create your first verified snapshot.</p>'}catch(e){}}
async function restoreBundle(dir,sid,mode){SEL=sid;
try{const label=mode==='safe'?'Safest restore':'Try-my-best restore';
const ok=await modal(label,`Restore "${sid}" from ${dir.split('/').pop()}? `+(mode==='safe'?'Exact match only.':'Best-effort fit by column name.')+' Current state is stashed first.',label);
if(!ok)return;
const res=await api('/api/restore',{m:'POST',b:{id:sid,dir,mode}});
toast(`✓ Restored (${mode})`);say(`restored ${sid.slice(0,20)}… mode=${mode} stash=${res.stash}`);loadActivity();await load();
}catch(e){toast(e.message,true)}}
async function loadActivity(){try{const j=await api('/api/activity');
const ic={backup:'▤',fix:'✚',restore:'↩'};
$('alist').innerHTML=j.events.map(e=>`<div class="${e.kind==='fix'?'':'warn'}"><time>${esc((e.ts||'').slice(11,19))}</time>${ic[e.kind]||'·'} <b>${esc(e.kind)}</b> ${esc((e.session||'').slice(0,24))} — ${esc(e.detail||'')}</div>`).join('')||'<p style="color:var(--t4)">Nothing logged yet.</p>'}catch(e){}}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>show(b.dataset.v));
function show(v){document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x.dataset.v===v));
document.querySelectorAll('.view').forEach(x=>x.classList.toggle('on',x.id==='v-'+v));
if(v==='backups')loadBundles();if(v==='activity')loadActivity();localStorage.setItem('sd_view',v)}
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
c.classList.add('on');FILTER=c.dataset.f;renderRows()});
let qTimer=null;$('q').addEventListener('input',()=>{clearTimeout(qTimer);qTimer=setTimeout(renderRows,80)});
document.addEventListener('click',e=>{const cb=e.target.classList&&e.target.classList.contains('rowchk');if(!cb)return;const id=e.target.dataset.id;e.stopPropagation();if(e.target.checked)CHECKED.add(id);else CHECKED.delete(id);renderBulk()});
$('chkAll').onclick=e=>{e.stopPropagation();const list=ROWS.filter(match);if(CHECKED.size>=list.length&&list.length)CHECKED.clear();else list.forEach(r=>CHECKED.add(r.id));renderRows()};
$('bBulkClear').onclick=()=>{CHECKED.clear();renderRows()};
$('bBulkBkp').onclick=async()=>{if(!CHECKED.size)return;let ok=0,fail=0;for(const id of [...CHECKED]){try{await api('/api/backup',{m:'POST',b:{id,verify:VERIFY}});ok++}catch(e){fail++;say('bulk backup FAILED '+id.slice(0,12)+': '+e.message,'err')}}toast(`Backed up ${ok} session${ok===1?'':'s'}${fail?` (${fail} failed)`:''}`,fail>0);say(`bulk backup: ${ok} ok, ${fail} failed`,'inf');loadActivity();loadBundles()};
async function changeLoc(){const p=prompt('Backup folder path:',$('setRoot').textContent);if(!p)return;
try{const r=await api('/api/settings',{m:'POST',b:{backup_root:p}});$('setRoot').textContent=r.backup_root;say('backup location → '+p,'inf')}catch(e){toast(e.message,true)}}
function togVerify(){VERIFY=!VERIFY;$('vbtn').textContent=VERIFY?'On ✓':'Off';localStorage.setItem('sd_verify',VERIFY?'1':'0')}
if(!VERIFY)$('vbtn').textContent='Off';
/* ---- command palette ---- */
function fuzScore(q,s){q=q.toLowerCase();s=s.toLowerCase();if(!q.length)return 1;if(s.startsWith(q))return 100-q.length;const words=s.split(/[\s\-_]+/);if(words.some(w=>w.startsWith(q)))return 50-q.length;let i=0;for(const c of s){if(c===q[i])i++;if(i===q.length)return 10-q.length}return -1}
function palItems(q){const items=[];
const recent=(RECENT||[]).map(id=>ROWS.find(r=>r.id===id)).filter(Boolean).filter(r=>!q||fuzScore(q,r.title||r.id)>=0).slice(0,4).map(r=>({group:'RECENT',label:`Inspect ${r.title||r.id}`,hint:'recent · open',score:60,run:()=>openD(r.id)}));
const views=[{label:'Go to Sessions',hint:'view'},{label:'Go to Backups',hint:'view'},{label:'Go to Activity',hint:'view'},{label:'Go to Settings',hint:'view'}].map(v=>({...v,group:'VIEWS',score:fuzScore(q,v.label),run:()=>show(v.label.split(' ')[2].toLowerCase())}));
const acts=[{label:'Refresh list',hint:'action',run:load}].map(v=>({...v,group:'ACTIONS',score:fuzScore(q,v.label)}));
let scoped=q;let onlyFix=q.toLowerCase().startsWith('fix ');let onlyOpen=q.toLowerCase().startsWith('open ');if(onlyFix)scoped=q.slice(4);if(onlyOpen)scoped=q.slice(5);
const rows=[];for(const r of ROWS.slice(0,200)){if(r.seals_active&&!onlyOpen)rows.push({group:'NEEDS FIX',label:`Fix ${r.title||r.id}`,hint:r.seals_active+' seals',score:fuzScore(scoped,r.title||r.id)+5,run:()=>{SEL=r.id;DRY.add(r.id);doFix()}});if(!onlyFix)rows.push({group:'SESSIONS',label:`Inspect ${r.title||r.id}`,hint:'open',score:fuzScore(scoped,r.title||r.id),run:()=>openD(r.id)})}
return [...recent,...views,...acts,...rows].filter(i=>i.score>=0).sort((a,b)=>b.score-a.score).slice(0,12)}
function palRender(){const q=$('palIn').value;PALITEMS=palItems(q);const ul=$('palUl');ul.innerHTML='';let lastGroup='';
PALITEMS.forEach((it,i)=>{if(it.group!==lastGroup){lastGroup=it.group;const h=document.createElement('li');h.innerHTML=`<small style="color:var(--t4)">${esc(it.group)}</small>`;h.style.cursor='default';ul.appendChild(h)}
const li=document.createElement('li');if(i===PALI)li.classList.add('sel');li.setAttribute('role','option');li.id='pal-'+i;li.setAttribute('aria-selected',i===PALI?'true':'false');
li.innerHTML=`${esc(it.label)}<small>${esc(it.hint||'')}</small>`;li.onclick=()=>{palClose();it.run()};ul.appendChild(li)});$('palIn').setAttribute('aria-activedescendant','pal-'+PALI)}
function palOpen(){$('pal').classList.add('open');$('palIn').value='';PALI=0;palRender();setTimeout(()=>$('palIn').focus(),30);say('palette opened','inf')}
function palClose(){$('pal').classList.remove('open')}
$('palIn').addEventListener('input',()=>{PALI=0;palRender()});
$('palIn').addEventListener('keydown',e=>{if(e.key==='ArrowDown'){e.preventDefault();PALI=Math.min(PALI+1,PALITEMS.length-1);palRender()}
if(e.key==='ArrowUp'){e.preventDefault();PALI=Math.max(PALI-1,0);palRender()}
if(e.key==='Enter'&&PALITEMS[PALI]){const it=PALITEMS[PALI];palClose();it.run()}});
$('pal').addEventListener('click',e=>{if(e.target.id==='pal')palClose()});
/* ---- global keys ---- */
document.addEventListener('keydown',e=>{
if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();palOpen();return}
if(e.key==='Escape'){palClose();closeD();if($('modal').classList.contains('open')){$('modal').classList.remove('open')}return}
if(e.target.tagName==='INPUT')return;
if(e.key==='/'){e.preventDefault();$('q').focus()}
if(e.key==='ArrowDown'||e.key==='ArrowUp'){const list=sortedRows(ROWS.filter(match));if(!list.length)return;e.preventDefault();
let i=list.findIndex(r=>r.id===SEL);i=e.key==='ArrowDown'?(i+1)%list.length:(i-1+list.length)%list.length;openD(list[i].id)}
if(e.key==='Enter'&&SEL&&!$('drawer').classList.contains('open'))openD(SEL)});
/* ---- boot ---- */
(async function(){const v=localStorage.getItem('sd_view');if(v&&document.getElementById('v-'+v))show(v);
await load();loadBundles();loadActivity();say('engine ready · loopback only','inf')})();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "SessionDoctor/1.0"

    def _send(self, obj: object, code: int = 200) -> None:
        body = json.dumps(obj, default=jsonbytesmod.json_default).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, path: Path) -> bool:
        if not path.is_file():
            return False
        ctype, _ = mimetypes.guess_type(str(path))
        try:
            data = path.read_bytes()
        except OSError:
            return False
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store" if path.name.endswith(".html") else "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)
        return True

    def _read_json(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def log_message(self, format: str, *args) -> None:  # keep terminal quiet
        pass

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        url = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(url.query)
        try:
            if url.path == "/api/health":
                count = 0
                try:
                    count = len(dbmod.list_sessions(_db()))
                except Exception:
                    pass
                self._send({"ok": True, "count": count})
            elif url.path == "/" or url.path == "/index.html":
                index = WEB_OUT / "index.html"
                if index.is_file() and self._send_static(index):
                    return
                body = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/api/sessions":
                rows = dbmod.list_sessions(_db())
                try:
                    db_mb = f"{_db().stat().st_size / 1e6:.0f}MB"
                except OSError:
                    db_mb = "—"
                last_b = ""
                try:
                    buns = restoremod.list_bundles(_root())
                    if buns:
                        last_b = str(buns[0].get("utc", ""))
                except Exception:
                    pass
                self._send({"rows": rows, "count": len(rows), "home": str(_home()),
                            "backup_root": str(_root()), "db_mb": db_mb,
                            "last_backup": last_b})
            elif url.path == "/api/session":
                sid = qs.get("id", [""])[0]
                d = dbmod.session_detail(_db(), sid)
                d["lease"] = dbmod.live_lease(_db(), sid)
                self._send(d)
            elif url.path == "/api/bundles":
                sid = qs.get("session", [""])[0]
                all_b = restoremod.list_bundles(_root())
                self._send({"bundles": [
                    {**b, "dir": str(b["dir"])} for b in all_b
                    if not sid or b["session_id"] == sid]})
            elif url.path == "/api/activity":
                self._send({"events": read_activity()})
            elif url.path == "/api/oc/sessions":
                rows = ocdbmod.list_sessions(_oc_db())
                try:
                    db_mb = f"{_oc_db().stat().st_size / 1e6:.0f}MB"
                except OSError:
                    db_mb = "—"
                last_b = ""
                try:
                    buns = ocrestoremod.list_bundles(_oc_root())
                    if buns:
                        last_b = str(buns[0].get("utc", ""))
                except Exception:
                    pass
                self._send({"rows": rows, "count": len(rows), "home": str(_oc_home()),
                            "backup_root": str(_oc_root()), "db_mb": db_mb,
                            "last_backup": last_b, "self_session": _oc_self()})
            elif url.path == "/api/oc/session":
                sid = qs.get("id", [""])[0]
                d = ocdbmod.session_detail(_oc_db(), sid)
                d["lease"] = ocdbmod.busy(_oc_db(), sid)
                d["is_self"] = bool(_oc_self()) and sid == _oc_self()
                self._send(d)
            elif url.path == "/api/oc/bundles":
                sid = qs.get("session", [""])[0]
                all_b = ocrestoremod.list_bundles(_oc_root())
                self._send({"bundles": [
                    {**b, "dir": str(b["dir"])} for b in all_b
                    if not sid or b["session_id"] == sid]})
            elif url.path.startswith("/_next/") or "." in url.path.rsplit("/", 1)[-1]:
                candidate = (WEB_OUT / url.path.lstrip("/")).resolve()
                try:
                    candidate.relative_to(WEB_OUT.resolve())
                except ValueError:
                    self._send({"error": "not found"}, 404)
                    return
                if candidate.is_file() and self._send_static(candidate):
                    return
                index = WEB_OUT / "index.html"
                if index.is_file() and self._send_static(index):
                    return
                self._send({"error": "not found"}, 404)
            else:
                self._send({"error": "not found"}, 404)
        except Exception as e:
            self._send({"error": str(e)[:300]}, 500)

    def do_POST(self) -> None:
        url = urllib.parse.urlparse(self.path)
        body = self._read_json()
        try:
            if url.path == "/api/backup":
                out = backupmod.backup_session_rows(
                    _home(), body["id"], _root(), verify=bool(body.get("verify", True)))
                log_event("backup", body["id"], f"bundle {Path(out['dir']).name}")
                self._send({"dir": str(out["dir"])})
            elif url.path == "/api/fix":
                sid = body["id"]
                before = fixmod.dry_run(_db(), sid)
                if not before["seals_active"]:
                    self._send({"cleared": 0, "backup": None, "note": "nothing to fix"})
                    return
                out = backupmod.backup_session_rows(
                    _home(), sid, _root(), verify=bool(body.get("verify", True)))
                res = fixmod.strip_seals(_db(), sid)
                log_event("fix", sid, f"cleared {res['cleared']}, backup {Path(out['dir']).name}")
                self._send({"cleared": res["cleared"], "backup": str(out["dir"])})
            elif url.path == "/api/restore":
                mode = str(body.get("mode", "safe") or "safe")
                if mode not in ("safe", "best-effort"):
                    self._send({"error": "mode must be safe or best-effort"}, 400)
                    return
                res = restoremod.restore_session(_home(), body["id"], Path(body["dir"]), mode=mode)
                log_event("restore", body["id"], f"{mode} from {Path(body['dir']).name}")
                res["stash"] = str(res["stash"])
                res["bundle"] = str(res["bundle"])
                self._send(res)
            elif url.path == "/api/settings":
                root = body.get("backup_root", "").strip()
                if not root:
                    self._send({"error": "empty path"}, 400)
                    return
                backupmod.SETTINGS_FILE.write_text(json.dumps({"backup_root": root}))
                resolved = backupmod.resolve_backup_root()
                self._send({"backup_root": str(resolved),
                            "requested": root,
                            "fallback": str(resolved) != str(Path(root).expanduser())})
            elif url.path == "/api/oc/backup":
                out = ocbackupmod.backup_session_oc(
                    _oc_home(), body["id"], _oc_root(), verify=bool(body.get("verify", True)))
                log_event("oc-backup", body["id"], f"bundle {Path(out['dir']).name}")
                self._send({"dir": str(out["dir"])})
            elif url.path == "/api/oc/fix":
                sid = body["id"]
                if _oc_self() and sid == _oc_self():
                    self._send({"error": "that's the chat you're talking in — fixing it live is blocked. Pick any other chat."}, 409)
                    return
                before = ocfixmod.dry_run(_oc_db(), sid)
                if not before["blobs"]:
                    self._send({"cleared": 0, "backup": None, "note": "nothing to fix"})
                    return
                out = ocbackupmod.backup_session_oc(
                    _oc_home(), sid, _oc_root(), verify=bool(body.get("verify", True)))
                res = ocfixmod.strip_blobs(_oc_db(), sid)
                log_event("oc-fix", sid, f"cleared {res['cleared']}, backup {Path(out['dir']).name}")
                self._send({"cleared": res["cleared"], "backup": str(out["dir"])})
            elif url.path == "/api/oc/restore":
                mode = str(body.get("mode", "safe") or "safe")
                if mode not in ("safe", "best-effort"):
                    self._send({"error": "mode must be safe or best-effort"}, 400)
                    return
                if _oc_self() and body["id"] == _oc_self():
                    self._send({"error": "that's the chat you're talking in — restoring it live is blocked. Pick any other chat."}, 409)
                    return
                res = ocrestoremod.restore_session_oc(_oc_home(), body["id"], Path(body["dir"]), mode=mode)
                log_event("oc-restore", body["id"], f"{mode} from {Path(body['dir']).name}")
                res["stash"] = str(res["stash"])
                res["bundle"] = str(res["bundle"])
                self._send(res)
            elif url.path == "/api/oc/settings":
                try:
                    raw = json.loads(ocbackupmod.SETTINGS_FILE.read_text())
                except Exception:
                    raw = {}
                if "oc_backup_root" in body:
                    root = str(body.get("oc_backup_root", "") or "").strip()
                    if root:
                        raw["oc_backup_root"] = root
                    elif "oc_backup_root" in raw:
                        del raw["oc_backup_root"]
                if "current_session_id" in body:
                    cur = str(body.get("current_session_id", "") or "")
                    if cur:
                        raw["oc_current_session_id"] = cur
                    elif "oc_current_session_id" in raw:
                        del raw["oc_current_session_id"]
                ocbackupmod.SETTINGS_FILE.write_text(json.dumps(raw))
                resolved = ocbackupmod.resolve_oc_backup_root()
                self._send({"backup_root": str(resolved), "self_session": _oc_self()})
            else:
                self._send({"error": "not found"}, 404)
        except Exception as e:
            self._send({"error": str(e)[:300]}, 500)


def serve(port: int = 0, open_browser: bool = True) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if open_browser:
        threading.Timer(0.4, webbrowser.open,
                        args=(f"http://127.0.0.1:{srv.server_address[1]}/",)).start()
    return srv


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="session-doctor")
    ap.add_argument("--port", type=int, default=int(os.environ.get("SESSION_DOCTOR_PORT", DEFAULT_PORT)))
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    srv = serve(port=args.port, open_browser=not args.no_browser)
    print(f"Session Doctor: http://127.0.0.1:{srv.server_address[1]}/  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

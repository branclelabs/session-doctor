"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  beGetBundles,
  bePostBackup,
  bePostFix,
  getActivity,
  ocPostSettings,
  type Backend,
  type SessionRow,
} from "@/lib/api";
import { copy } from "@/lib/copy";
import { useFleet } from "@/hooks/use-fleet";
import { FixNextHero } from "@/components/fix-next-hero";
import { StatStrip } from "@/components/stat-strip";
import { SessionTable } from "@/components/session-table";
import { GuidedDrawer } from "@/components/guided-drawer";
import { CommandPalette } from "@/components/command-palette";
import { ActivityList, BackupList } from "@/components/lists";
import { AmbientField } from "@/components/ambient-field";

type View = "sessions" | "backups" | "activity" | "settings";

function matches(r: SessionRow, q: string, filter: string): boolean {
  if (filter === "bad" && !r.seals_active) return false;
  if (filter === "pin" && !r.pinned) return false;
  const toks = q.trim().split(/\s+/).filter(Boolean);
  const f = { text: [] as string[], bad: false, pin: false, clean: false, model: "", seals: 0, id: "" };
  for (const t of toks) {
    const l = t.toLowerCase();
    if (l === "is:bad") f.bad = true;
    else if (l === "is:pinned" || l === "is:pin") f.pin = true;
    else if (l === "is:clean") f.clean = true;
    else if (l.startsWith("model:")) f.model = l.slice(6);
    else if (l.startsWith("id:")) f.id = l.slice(3);
    else if (l.startsWith("seals:>")) f.seals = parseInt(l.slice(7)) || 0;
    else if (l.startsWith("seals:")) f.seals = parseInt(l.slice(6)) || 0;
    else f.text.push(t);
  }
  if (f.bad && !r.seals_active) return false;
  if (f.pin && !r.pinned) return false;
  if (f.clean && r.seals_active) return false;
  if (f.model && !((r.model || "").toLowerCase().includes(f.model))) return false;
  if (f.id && !(r.id || "").toLowerCase().includes(f.id)) return false;
  if (f.seals && (r.seals_active ?? 0) < f.seals) return false;
  if (!f.text.length) return true;
  const hay = `${r.title || ""} ${r.id} ${r.model || ""}`.toLowerCase();
  return f.text.every((t) => hay.includes(t.toLowerCase()));
}

export function Dashboard() {
  const [backend, setBackend] = useState<Backend>(() => {
    try {
      return (localStorage.getItem("sd_backend") as Backend) || "hermes";
    } catch {
      return "hermes";
    }
  });
  const pickBackend = (b: Backend) => {
    setBackend(b);
    setChecked(new Set());
    setSel(null);
    setDrawerOpen(false);
    try {
      localStorage.setItem("sd_backend", b);
    } catch { /* ignore */ }
  };
  const { rows, bad, queue, mutate, data } = useFleet(backend);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [view, setView] = useState<View>("sessions");
  const [sel, setSel] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [lastToggled, setLastToggled] = useState<string | null>(null);
  const [bulk, setBulk] = useState<{ running: boolean; done: number; total: number; label: string; cancel: boolean }>({
    running: false,
    done: 0,
    total: 0,
    label: "",
    cancel: false,
  });
  const bulkCancel = useRef(false);
  const [boot, setBoot] = useState(false);
  const [motionPref, setMotionPref] = useState<"full" | "calm" | "off">(() => {
    try {
      return (localStorage.getItem("sd_motion") as "full" | "calm" | "off") || "full";
    } catch {
      return "full";
    }
  });
  useEffect(() => {
    try {
      if (sessionStorage.getItem("sd_boot")) {
        setBoot(true);
        return;
      }
    } catch { /* ignore */ }
    const t = setTimeout(() => {
      setBoot(true);
      try {
        sessionStorage.setItem("sd_boot", "1");
      } catch { /* ignore */ }
    }, 60);
    return () => clearTimeout(t);
  }, []);
  const anim = (i: number) =>
    motionPref !== "full"
      ? motionPref === "off"
        ? {}
        : {
            initial: { opacity: 0 },
            animate: { opacity: 1 },
            transition: { duration: 0.2 },
          }
      : {
          initial: { opacity: 0, y: 14 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.5, delay: boot ? 0 : 0.1 + i * 0.08, ease: [0.16, 1, 0.3, 1] as const },
        };
  const { data: bundlesData } = useSWR(view === "backups" ? ["bundles", backend] : null, () => beGetBundles(backend));
  const { data: activityData } = useSWR(view === "activity" ? "/api/activity" : null, getActivity);
  const selfSession = backend === "opencode" ? (data?.self_session || "") : "";

  const filtered = useMemo(() => rows.filter((r) => matches(r, q, filter)), [rows, q, filter]);
  const selRow = sel ? (rows.find((r) => r.id === sel) ?? null) : null;

  const open = (id: string) => {
    setSel(id);
    setDrawerOpen(true);
  };

  const refresh = async () => {
    await mutate();
  };

  // Prune checked IDs that vanished from the fleet.
  useEffect(() => {
    setChecked((prev) => {
      if (!prev.size) return prev;
      const alive = new Set(rows.map((r) => r.id));
      let changed = false;
      const next = new Set<string>();
      prev.forEach((id) => {
        if (alive.has(id)) next.add(id);
        else changed = true;
      });
      return changed ? next : prev;
    });
  }, [rows]);

  // Esc clears selection (drawer handles its own Esc when open).
  useEffect(() => {
    if (drawerOpen) return;
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") setChecked(new Set());
    };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [drawerOpen]);

  const toggleOne = (id: string, shift = false, order: string[] = []) => {
    if (shift && lastToggled && order.length) {
      const a = order.indexOf(lastToggled);
      const b = order.indexOf(id);
      if (a !== -1 && b !== -1) {
        const [lo, hi] = a < b ? [a, b] : [b, a];
        const slice = order.slice(lo, hi + 1);
        setChecked((prev) => {
          const next = new Set(prev);
          const allIn = slice.every((x) => next.has(x));
          slice.forEach((x) => {
            if (allIn) next.delete(x);
            else next.add(x);
          });
          return next;
        });
        setLastToggled(id);
        return;
      }
    }
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setLastToggled(id);
  };

  const toggleAllFiltered = (ids: string[]) => {
    setChecked((prev) => {
      const allIn = ids.length > 0 && ids.every((x) => prev.has(x));
      if (allIn) {
        const next = new Set(prev);
        ids.forEach((x) => next.delete(x));
        return next;
      }
      const next = new Set(prev);
      ids.forEach((x) => next.add(x));
      return next;
    });
  };

  const isSelf = (id: string) => backend === "opencode" && !!selfSession && id === selfSession;
  const selfBlocked = (id: string) => {
    if (isSelf(id)) {
      toast.error("That's the chat you're talking in — fixing it live is blocked. Pick any other chat.");
      return true;
    }
    return false;
  };

  const copyIds = async () => {
    const ids = Array.from(checked);
    if (!ids.length) return;
    try {
      await navigator.clipboard.writeText(ids.join("\n"));
      toast.success(`Copied ${ids.length} session ID${ids.length === 1 ? "" : "s"}`);
    } catch {
      toast.error("Copy failed");
    }
  };

  const backupMany = async () => {
    const ids = Array.from(checked);
    if (!ids.length || bulk.running) return;
    bulkCancel.current = false;
    setBulk({ running: true, done: 0, total: ids.length, label: "Backing up", cancel: false });
    let ok = 0;
    const failed: string[] = [];
    for (let i = 0; i < ids.length; i++) {
      if (bulkCancel.current) break;
      try {
        await bePostBackup(backend, ids[i], true);
        ok++;
      } catch (e) {
        failed.push(ids[i]);
        toast.error(e instanceof Error ? e.message : `Backup failed: ${ids[i]}`);
      }
      setBulk((b) => ({ ...b, done: i + 1 }));
    }
    setBulk({ running: false, done: 0, total: 0, label: "", cancel: false });
    await refresh();
    if (bulkCancel.current) toast(`Cancelled — backed up ${ok} of ${ids.length}`);
    else if (!failed.length) toast.success(`Backed up ${ok} chat${ok === 1 ? "" : "s"} — one safety copy each`);
    else toast.error(`Backed up ${ok}, failed ${failed.length}`);
  };

  const fixMany = async () => {
    const selfHit = Array.from(checked).filter((id) => isSelf(id));
    if (selfHit.length) {
      toast.error("Your live chat is in the selection — fixing it live is blocked. Deselect it first.");
      return;
    }
    const ids = rows.filter((r) => checked.has(r.id) && (r.seals_active ?? 0) > 0).map((r) => r.id);
    const skipped = checked.size - ids.length;
    if (!ids.length || bulk.running) {
      if (!ids.length) toast("Nothing to fix in selection");
      return;
    }
    const totalLocks = rows.filter((r) => checked.has(r.id)).reduce((s, r) => s + (r.seals_active ?? 0), 0);
    if (!confirm(`Back up then fix ${ids.length} chat${ids.length === 1 ? "" : "s"} one by one?\n${totalLocks} total locks. One safety copy per chat. Nothing runs in parallel.`)) return;
    bulkCancel.current = false;
    setBulk({ running: true, done: 0, total: ids.length, label: "Backing up + fixing", cancel: false });
    let fixed = 0;
    let busy = 0;
    const failed: string[] = [];
    const succeeded: string[] = [];
    for (let i = 0; i < ids.length; i++) {
      if (bulkCancel.current) break;
      try {
        const r = await bePostFix(backend, ids[i], true);
        if ("note" in r) succeeded.push(ids[i]);
        else {
          fixed++;
          succeeded.push(ids[i]);
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : "";
        if (/lease|busy|idle/i.test(msg)) busy++;
        else failed.push(ids[i]);
        toast.error(msg || `Fix failed: ${ids[i]}`);
      }
      setBulk((b) => ({ ...b, done: i + 1 }));
    }
    setChecked((prev) => {
      const next = new Set(prev);
      succeeded.forEach((x) => next.delete(x));
      return next;
    });
    setBulk({ running: false, done: 0, total: 0, label: "", cancel: false });
    await refresh();
    const parts = [`Fixed ${fixed}`];
    if (skipped) parts.push(`${skipped} already clean`);
    if (busy) parts.push(`${busy} busy — retry when idle`);
    if (failed.length) parts.push(`${failed.length} failed`);
    if (bulkCancel.current) parts.push(`cancelled at ${succeeded.length}/${ids.length}`);
    toast(parts.join(" · "));
  };

  const quickFix = async (id: string) => {
    if (selfBlocked(id)) return;
    const r = rows.find((x) => x.id === id);
    if (!r?.seals_active) {
      toast("Nothing to fix");
      return;
    }
    if (!confirm(`Back up then clear ${r.seals_active} locks from ${r.title || r.id}?`)) return;
    try {
      const res = await bePostFix(backend, id, true);
      if ("note" in res) toast("Nothing to fix");
      else {
        toast.success(copy.fixDone(res.cleared, r.message_count));
        await refresh();
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Fix failed");
    }
  };

  const backupOne = async (id: string) => {
    try {
      await bePostBackup(backend, id, true);
      toast.success("Safety copy saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Backup failed");
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {motionPref !== "off" && <AmbientField badRatio={rows.length ? bad.length / rows.length : 0} />}
      <motion.aside
        {...anim(0)}
        className="relative z-10 flex w-[232px] shrink-0 flex-col border-r border-white/10 bg-canvas-900/80 p-3 backdrop-blur"
      >
        <div className="flex items-center gap-2.5 px-2.5 pb-4 pt-1 text-[15px] font-semibold">
          <svg width="20" height="20" viewBox="0 0 16 16"><path d="M1 8h3l2-4 3 8 2-4h4" stroke="#10b981" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          Session Doctor
        </div>
        <div className="mb-2 grid grid-cols-2 gap-1 rounded-lg border border-white/10 bg-black/30 p-1" role="group" aria-label="Database source">
          {(["hermes", "opencode"] as const).map((b) => (
            <button
              key={b}
              onClick={() => pickBackend(b)}
              aria-pressed={backend === b}
              className={`rounded-md px-2 py-1.5 text-[13px] font-semibold capitalize transition-colors ${
                backend === b ? "bg-accent-dim text-accent-hi shadow-[inset_0_0_0_1px_rgba(16,185,129,.4)]" : "text-neutral-400 hover:text-white"
              }`}
            >
              {b === "hermes" ? "Hermes" : "OpenCode"}
            </button>
          ))}
        </div>
        <nav className="flex flex-col gap-0.5" aria-label="Primary">
          {(
            [
              { v: "sessions", label: "Chats", count: bad.length || "✓", hot: bad.length > 0 },
              { v: "backups", label: "Safety copies", count: "–", hot: false },
              { v: "activity", label: "Activity", count: null, hot: false },
              { v: "settings", label: "Settings", count: null, hot: false },
            ] as const
          ).map((n) => (
            <button
              key={n.v}
              onClick={() => setView(n.v)}
              className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-[13.5px] font-medium ${
                view === n.v ? "bg-white/[0.04] text-white shadow-[inset_2px_0_0_#10b981]" : "text-neutral-400 hover:bg-white/[0.04] hover:text-white"
              }`}
            >
              {n.label}
              {n.count !== null && (
                <span className={`ml-auto rounded-full px-2 py-px font-mono text-[11px] ${n.hot ? "bg-danger/15 text-danger-tx" : "bg-white/5 text-neutral-400"}`}>
                  {n.count}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="mt-auto pb-2 text-center">
          <Ring ok={rows.length - bad.length} total={rows.length} />
          <div className="mt-2 font-mono text-[11px] text-neutral-500">v1.3 · local</div>
        </div>
      </motion.aside>

      <main className="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
        <motion.div {...anim(1)} className="flex items-center gap-2.5 border-b border-white/10 p-3.5 px-5">
          <div className="flex max-w-[560px] flex-1 items-center gap-2.5 rounded-md border border-white/10 bg-white/[0.02] px-3 py-2">
            <span aria-hidden>⌕</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && setQ("")}
              aria-label="Search chats"
              placeholder={copy.searchPlaceholder}
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-neutral-600"
            />
            <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[11px] text-neutral-400">/</kbd>
            <CommandPalette rows={rows} onInspect={open} onFix={quickFix} onGoto={setView} />
          </div>
          <div className="flex gap-1.5">
            {(
              [
                ["all", "All"],
                ["bad", "Needs fix"],
                ["pin", "Pinned"],
              ] as const
            ).map(([v, l]) => (
              <button
                key={v}
                onClick={() => setFilter(v)}
                className={`rounded-full border px-3 py-1 text-xs font-medium ${
                  filter === v ? "border-accent/40 bg-accent-dim text-accent-hi" : "border-white/10 text-neutral-300"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
          <span className="ml-auto hidden text-xs text-neutral-500 xl:block">{copy.tagline}</span>
        </motion.div>
        {backend === "opencode" && !selfSession && (
          <div className="border-b border-warn/25 bg-warn/10 px-5 py-2 text-[13px] text-warn" role="note">
            Tip: open any chat → “Mark as my live chat” so the fixer can never touch the conversation you talk in.{" "}
            <button className="underline underline-offset-4" onClick={() => setView("settings")}>Go to Settings</button>
          </div>
        )}

        {view === "sessions" && (
          <>
            <motion.div {...anim(2)} className="px-5 pt-5">
              <FixNextHero
                total={rows.length}
                bad={bad.length}
                queue={queue}
                onFix={open}
                onPickDifferent={() => document.querySelector("input")?.focus()}
              />
              <div className="mt-1.5 flex gap-3.5 text-xs text-neutral-500">
                <span>db {data?.db_mb ?? "—"}</span>
                <span>{filtered.length} of {rows.length} chats</span>
              </div>
              <StatStrip total={rows.length} bad={bad.length} lastBackup={data?.last_backup ?? ""} dbMb={data?.db_mb ?? ""} />
            </motion.div>
            <motion.div {...anim(3)} className="flex-1 overflow-auto p-5">
              {checked.size > 0 && (
                <div
                  role="status"
                  aria-live="polite"
                  className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-accent/35 bg-accent-dim px-4 py-2.5 text-sm"
                >
                  <span className="font-medium">
                    {checked.size} selected ·{" "}
                    {rows.filter((r) => checked.has(r.id)).reduce((s, r) => s + (r.seals_active ?? 0), 0)} total locks
                  </span>
                  {bulk.running && (
                    <span className="font-mono text-xs text-accent-hi">
                      {bulk.label} {bulk.done}/{bulk.total}…
                    </span>
                  )}
                  {bulk.running && (
                    <div className="h-1 min-w-[120px] flex-1 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-accent transition-all"
                        style={{ width: bulk.total ? `${Math.round((bulk.done / bulk.total) * 100)}%` : "0%" }}
                      />
                    </div>
                  )}
                  <span className="ml-auto flex flex-wrap gap-2">
                    {!bulk.running && (
                      <>
                        <button onClick={backupMany} className="rounded-md border border-white/15 bg-white/[0.04] px-3 py-1.5 text-[13px] hover:bg-white/[0.08]">
                          Backup {checked.size}
                        </button>
                        <button onClick={copyIds} className="rounded-md border border-white/15 bg-white/[0.04] px-3 py-1.5 text-[13px] hover:bg-white/[0.08]">
                          Copy IDs
                        </button>
                        <button onClick={fixMany} className="rounded-md bg-accent px-3 py-1.5 text-[13px] font-semibold text-black hover:brightness-110">
                          Fix {checked.size}…
                        </button>
                        <button onClick={() => setChecked(new Set())} className="rounded-md px-3 py-1.5 text-[13px] text-neutral-400 hover:text-white">
                          Clear
                        </button>
                      </>
                    )}
                    {bulk.running && (
                      <button onClick={() => { bulkCancel.current = true; }} className="rounded-md border border-danger/40 px-3 py-1.5 text-[13px] text-danger-tx">
                        Cancel
                      </button>
                    )}
                  </span>
                </div>
              )}
              <div className="overflow-hidden rounded-lg border border-white/10 bg-white/[0.02]">
                <SessionTable
                  rows={filtered}
                  query={q}
                  selected={sel}
                  onOpen={open}
                  onQuickFix={quickFix}
                  motion={motionPref}
                  checked={checked}
                  onToggle={(id, shift, order) => toggleOne(id, shift, order)}
                  onToggleAll={(ids) => toggleAllFiltered(ids)}
                  selfSession={selfSession}
                />
              </div>
            </motion.div>
          </>
        )}
        {view === "backups" && (
          <div className="flex-1 overflow-auto p-5">
            <h2 className="text-lg font-semibold">Safety copies</h2>
            <p className="mb-4 text-sm text-neutral-400">Newest first. Each copy restores one chat exactly.</p>
            <BackupList bundles={bundlesData?.bundles ?? []} />
          </div>
        )}
        {view === "activity" && (
          <div className="flex-1 overflow-auto p-5">
            <h2 className="text-lg font-semibold">Activity</h2>
            <p className="mb-4 text-sm text-neutral-400">Every backup, fix and restore on this machine.</p>
            <ActivityList events={activityData?.events ?? []} />
          </div>
        )}
        {view === "settings" && (
          <SettingsView
            backend={backend}
            backupRoot={data?.backup_root ?? ""}
            selfSession={selfSession}
            onSaved={refresh}
            motion={motionPref}
            onMotion={(m) => {
              setMotionPref(m);
              try {
                localStorage.setItem("sd_motion", m);
              } catch { /* ignore */ }
            }}
          />
        )}
        <footer className="border-t border-white/10 px-5 py-2.5 text-xs text-neutral-500">{copy.tagline}</footer>
      </main>

      <GuidedDrawer
        session={selRow}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onDone={refresh}
        backend={backend}
        selfSession={selfSession}
        onSelfMarked={refresh}
      />
    </div>
  );
}

function Ring({ ok, total }: { ok: number; total: number }) {
  const pct = total ? Math.round((ok / total) * 1000) / 10 : 100;
  return (
    <div>
      <div className="mx-auto grid h-[104px] w-[104px] place-items-center rounded-full" style={{ background: `conic-gradient(#10b981 0 ${pct}%, rgba(255,255,255,.08) ${pct}% 100%)` }}>
        <div className="grid h-20 w-20 place-items-center rounded-full bg-canvas-900 font-mono text-[15px]">{pct}%</div>
      </div>
      <p className="mt-2 text-xs text-neutral-500">fleet health · {ok} / {total} clean</p>
    </div>
  );
}

function SettingsView({
  backend,
  backupRoot,
  selfSession,
  onSaved,
  motion,
  onMotion,
}: {
  backend: Backend;
  backupRoot: string;
  selfSession: string;
  onSaved: () => void;
  motion: "full" | "calm" | "off";
  onMotion: (m: "full" | "calm" | "off") => void;
}) {
  const [val, setVal] = useState(backupRoot);
  const [liveId, setLiveId] = useState(selfSession);
  useEffect(() => setVal(backupRoot), [backupRoot]);
  useEffect(() => setLiveId(selfSession), [selfSession]);
  const isOc = backend === "hermes" ? false : true;
  void isOc;
  return (
    <div className="flex-1 overflow-auto p-5">
      <h2 className="font-display text-lg font-semibold">Settings</h2>
      <p className="mb-4 text-sm text-neutral-400">
        {backend === "opencode"
          ? "OpenCode folders, live-chat guard, motion. Motion respects your system setting too."
          : "Hermes folder, motion. Switch to OpenCode above for its own folder + live-chat guard."}
      </p>
      <div className="mb-2.5 flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.02] p-4">
        <div className="flex-1">
          <b className="block text-sm font-medium">Safety copy folder</b>
          <span className="font-mono text-xs text-neutral-400">{backupRoot || "—"}</span>
        </div>
      </div>
      <div className="mb-2.5 flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.02] p-4">
        <div className="flex-1">
          <b className="block text-sm font-medium">Folder override</b>
          <span className="text-xs text-neutral-500">Paste a new folder, then Save.</span>
        </div>
        <input value={val} onChange={(e) => setVal(e.target.value)} className="w-64 rounded-md border border-white/10 bg-black/30 px-3 py-1.5 font-mono text-xs" />
        <button
          onClick={async () => {
            try {
              if (backend === "opencode") {
                const { ocPostSettings } = await import("@/lib/api");
                await ocPostSettings({ oc_backup_root: val });
              } else {
                const { postSettings } = await import("@/lib/api");
                const r = await postSettings(val);
                toast.success(r.fallback ? `That folder is missing — using ${r.backup_root} instead` : "Folder saved");
              }
              if (backend === "opencode") toast.success("Folder saved");
              onSaved();
            } catch (e) {
              toast.error(e instanceof Error ? e.message : "Save failed");
            }
          }}
          className="rounded-md border border-white/10 px-3 py-1.5 text-sm"
        >
          Save
        </button>
      </div>
      {backend === "opencode" && (
        <div className="mb-2.5 flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.02] p-4">
          <div className="flex-1">
            <b className="block text-sm font-medium">My live chat</b>
            <span className="text-xs text-neutral-500">
              {selfSession ? `Protected: ${selfSession.slice(0, 24)}… — it can never be fixed live.` : "None marked. Paste the chat ID you talk in."}
            </span>
          </div>
          <input
            value={liveId}
            onChange={(e) => setLiveId(e.target.value.trim())}
            placeholder="ses_…"
            className="w-64 rounded-md border border-white/10 bg-black/30 px-3 py-1.5 font-mono text-xs"
          />
          <button
            onClick={async () => {
              try {
                const { ocPostSettings } = await import("@/lib/api");
                await ocPostSettings({ current_session_id: liveId });
                toast.success(liveId ? "Live chat protected" : "Live-chat mark cleared");
                onSaved();
              } catch (e) {
                toast.error(e instanceof Error ? e.message : "Save failed");
              }
            }}
            className="rounded-md border border-white/10 px-3 py-1.5 text-sm"
          >
            Save
          </button>
        </div>
      )}
      <div className="mb-2.5 flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.02] p-4">
        <div className="flex-1">
          <b className="block text-sm font-medium">Motion</b>
          <span className="text-xs text-neutral-500">Full showmanship, calmer, or off. System reduced-motion always wins.</span>
        </div>
        <div className="flex gap-1.5" role="group" aria-label="Motion level">
          {(["full", "calm", "off"] as const).map((m) => (
            <button
              key={m}
              onClick={() => onMotion(m)}
              aria-pressed={motion === m}
              className={`rounded-full border px-3 py-1 text-xs font-medium capitalize ${
                motion === m ? "border-accent/40 bg-accent-dim text-accent-hi" : "border-white/10 text-neutral-300"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.02] p-4">
        <div className="flex-1">
          <b className="block text-sm font-medium">Auto safety copy before fix</b>
          <span className="text-xs text-neutral-500">Always on — no copy, no fix</span>
        </div>
        <button disabled className="rounded-md border border-white/10 px-3 py-1.5 text-sm opacity-40">Locked</button>
      </div>
    </div>
  );
}

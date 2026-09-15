"use client";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { beGetBundles, beGetSession, bePostBackup, bePostFix, bePostRestore, ocPostSettings, type Backend, type Bundle, type SessionDetail, type SessionRow } from "@/lib/api";
import { copy } from "@/lib/copy";
import { toast } from "sonner";

export function GuidedDrawer({
  session,
  open,
  onClose,
  onDone,
  backend = "hermes",
  selfSession = "",
  onSelfMarked,
}: {
  session: SessionRow | null;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
  backend?: Backend;
  selfSession?: string;
  onSelfMarked?: () => void;
}) {
  const isSelf = backend === "opencode" && !!selfSession && session?.id === selfSession;
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [busy, setBusy] = useState(false);
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [showUndo, setShowUndo] = useState(false);
  const [phase, setPhase] = useState<"idle" | "backup" | "clear">("idle");
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!open || !session) return;
    setStep(1);
    setDetail(null);
    setShowUndo(false);
    beGetSession(backend, session.id)
      .then((d) => {
        setDetail(d);
        if ((d.seals_active ?? 0) === 0) setStep(3);
      })
      .catch((e) => toast.error(e.message));
    beGetBundles(backend, session.id).then((b) => setBundles(b.bundles)).catch(() => {});
  }, [open, session, backend]);

  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [open, onClose]);

  useEffect(() => {
    if (open) setTimeout(() => titleRef.current?.focus(), 60);
  }, [open, session?.id ]);

  if (!open || !session) return null;
  const seals = detail?.seals_active ?? session.seals_active ?? 0;

  const preview = async () => {
    if (!session) return;
    setBusy(true);
    try {
      const d = await beGetSession(backend, session.id);
      setDetail(d);
      setStep(d.seals_active ? 2 : 3);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  };

  const backup = async () => {
    setBusy(true);
    try {
      const r = await bePostBackup(backend, session.id, true);
      toast.success("Safety copy saved");
      const b = await beGetBundles(backend, session.id);
      setBundles(b.bundles);
      void r;
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Backup failed");
    } finally {
      setBusy(false);
    }
  };

  const fix = async () => {
    if (isSelf) {
      toast.error("That's the chat you're talking in — fixing it live is blocked. Pick any other chat.");
      return;
    }
    setBusy(true);
    setPhase("backup");
    try {
      await new Promise((r) => setTimeout(r, 350));
      setPhase("clear");
      const r = await bePostFix(backend, session.id, true);
      if ("note" in r) {
        toast("Nothing to fix");
      } else {
        toast.success(copy.fixDone(r.cleared, session.message_count), {
          action: { label: "Undo", onClick: () => restoreNewest("safe") },
          duration: 8000,
        });
      }
      onDone();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Fix failed");
    } finally {
      setBusy(false);
      setPhase("idle");
    }
  };

  const restoreNewest = async (mode: "safe" | "best-effort") => {
    if (isSelf) {
      toast.error("That's the chat you're talking in — restoring it live is blocked. Pick any other chat.");
      return;
    }
    const b = bundles[0];
    if (!b) {
      toast.error("No safety copies yet — back up first");
      return;
    }
    setBusy(true);
    try {
      const r = await bePostRestore(backend, session.id, b.dir, mode);
      toast.success(`Restored (${mode}) — locks now ${r.seals_after}`);
      if (r.warnings?.length) toast.warning(r.warnings.join(" | "));
      onDone();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Restore failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40">
      <motion.div
        className="absolute inset-0 bg-black/60 backdrop-blur-[2px]"
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
      />
      <motion.section
        role="dialog"
        aria-label="Chat details"
        initial={{ x: 60, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 60, opacity: 0 }}
        transition={{ type: "spring", stiffness: 320, damping: 32 }}
        className="absolute bottom-0 right-0 top-0 w-[420px] max-w-[94vw] overflow-auto border-l border-white/10 bg-canvas-900/95 p-6 shadow-[-24px_0_60px_rgba(0,0,0,.5)] backdrop-blur"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 ref={titleRef} tabIndex={-1} className="truncate font-display text-lg font-semibold outline-none">Fix: {session.title || "untitled"}</h2>
            <div className="truncate font-mono text-xs text-idblue">{session.id}</div>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-md border border-white/10 px-2.5 py-1 text-neutral-400 hover:bg-white/5">
            ✕
          </button>
        </div>
        <div className="mt-3 flex items-center gap-1.5 text-xs" aria-hidden>
          {([1, 2, 3] as const).map((s, i) => (
            <span key={s} className="flex items-center gap-1.5">
              <motion.span
                animate={step >= s ? { scale: [1, 1.15, 1] } : {}}
                className={`rounded-full px-2.5 py-1 ${step >= s ? "bg-accent-dim text-accent-hi" : "bg-white/5 text-neutral-500"}`}
              >
                {s === 1 ? "1 Inspect" : s === 2 ? "2 Preview" : "3 Fix"}
              </motion.span>
              {i < 2 && <span className={`h-px w-4 ${step > s ? "bg-accent" : "bg-white/10"}`} />}
            </span>
          ))}
        </div>
        <p className="mt-4 text-sm text-neutral-300">{copy.locksExplain}</p>
        {isSelf && (
          <div className="mt-3 rounded-lg border border-danger/40 bg-danger/10 p-3 text-[13px] text-danger-tx" role="alert">
            You&apos;re talking in this chat right now — fixing it live is blocked so the conversation can&apos;t desync. Pick any other chat.
          </div>
        )}
        {backend === "opencode" && !isSelf && (
          <button
            disabled={busy}
            onClick={async () => {
              try {
                await ocPostSettings({ current_session_id: session.id });
                toast.success("Marked as my live chat — it can no longer be fixed live");
                onSelfMarked?.();
              } catch (e) {
                toast.error(e instanceof Error ? e.message : "Could not mark chat");
              }
            }}
            className="mt-3 text-[13px] text-neutral-400 underline underline-offset-4 hover:text-white"
          >
            Mark as my live chat
          </button>
        )}
        <dl className="mt-4 grid grid-cols-[128px_1fr] gap-y-2 border-y border-white/10 py-4 font-mono text-[13px]">
          <dt className="text-neutral-500">messages</dt><dd>{detail?.active_msgs ?? session.message_count ?? "—"}</dd>
          <dt className="text-neutral-500">locks</dt><dd>{seals}</dd>
          <dt className="text-neutral-500">model</dt><dd className="truncate">{String(detail?.model ?? session.model ?? "—")}</dd>
          <dt className="text-neutral-500">visible text</dt><dd>safe ✓ intact</dd>
        </dl>
        <AnimatePresence>
          {step === 2 && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-3 rounded-lg border border-white/10 bg-black/40 p-3 font-mono text-xs leading-7"
            >
              {(["del", "keep", "keep"] as const).map((k, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.09 }}
                  className={k === "del" ? "text-danger-tx" : "text-accent-hi"}
                >
                  {i === 0 ? `− ${seals} locked thoughts → removed` : i === 1 ? "+ messages, summaries, tools: untouched" : "+ other chats: untouched"}
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
        <div className="mt-4 flex flex-wrap gap-2">
          {step === 1 && (
            <button disabled={busy} onClick={preview} className="rounded-md border border-white/10 bg-white/[0.03] px-4 py-2 text-sm hover:bg-white/[0.06]">
              {busy ? "Working…" : "Preview what I'll clear"}
            </button>
          )}
          {step === 2 && (
            <motion.button
              whileTap={{ scale: 0.97 }}
              disabled={busy || !seals || isSelf}
              onClick={fix}
              title={isSelf ? "Blocked: this is your live chat" : seals ? "" : "Nothing to fix"}
              className="relative overflow-hidden rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-black hover:brightness-110 disabled:opacity-40"
            >
              {busy && <span className="shimmer-bar absolute inset-0" aria-hidden />}
              <span className="relative">{busy ? (phase === "backup" ? "Backing up…" : "Clearing…") : "Back up + Fix"}</span>
            </motion.button>
          )}
          <button disabled={busy} onClick={backup} className="rounded-md border border-white/10 bg-white/[0.03] px-4 py-2 text-sm hover:bg-white/[0.06]">
            Backup
          </button>
        </div>
        <p className="mt-2 text-xs text-neutral-500">{copy.backupFirst}</p>
        <div className="mt-4">
          <button onClick={() => setShowUndo((v) => !v)} className="text-sm text-neutral-400 underline underline-offset-4">
            {copy.undoTitle}
          </button>
          {showUndo && (
            <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="mt-2 flex flex-wrap gap-2">
              <button disabled={busy} onClick={() => restoreNewest("safe")} className="rounded-md border border-white/10 px-3 py-1.5 text-sm">
                Safest restore…
              </button>
              <button disabled={busy} onClick={() => restoreNewest("best-effort")} className="rounded-md border border-white/10 px-3 py-1.5 text-sm">
                Try-my-best…
              </button>
              <div className="w-full text-xs text-neutral-500">
                {copy.safestHelp} {copy.bestEffortHelp} Newest copy: {bundles[0] ? bundles[0].dir.split("/").pop() : "none yet"}
              </div>
            </motion.div>
          )}
        </div>
      </motion.section>
    </div>
  );
}

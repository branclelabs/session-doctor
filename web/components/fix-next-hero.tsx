"use client";
import { motion } from "framer-motion";
import { useRef, useState } from "react";
import { copy } from "@/lib/copy";
import type { SessionRow } from "@/lib/api";
import { Ticker, usePrefersReducedMotion } from "./primitives";

export function rel(ts: number | null | undefined): string {
  if (!ts) return "—";
  const s = Date.now() / 1000 - ts;
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.floor(s / 60)}m ago`;
  if (s < 172800) return `${Math.floor(s / 3600)}h ago`;
  if (s < 2592000) return `${Math.floor(s / 86400)}d ago`;
  return new Date(ts * 1000).toISOString().slice(0, 10);
}

function MagneticButton({ children, onClick, primary }: { children: React.ReactNode; onClick: () => void; primary?: boolean }) {
  const ref = useRef<HTMLButtonElement>(null);
  const [t, setT] = useState({ x: 0, y: 0 });
  const reduced = usePrefersReducedMotion();
  return (
    <motion.button
      ref={ref}
      onClick={onClick}
      animate={{ x: t.x, y: t.y }}
      transition={{ type: "spring", stiffness: 350, damping: 22 }}
      onMouseMove={(e) => {
        if (reduced) return;
        const r = ref.current?.getBoundingClientRect();
        if (!r) return;
        setT({ x: (e.clientX - (r.left + r.width / 2)) * 0.12, y: (e.clientY - (r.top + r.height / 2)) * 0.18 });
      }}
      onMouseLeave={() => setT({ x: 0, y: 0 })}
      whileTap={{ scale: 0.97 }}
      className={
        primary
          ? "rounded-lg bg-accent px-5 py-2.5 font-display text-[15px] font-semibold text-black shadow-[0_8px_32px_rgba(16,185,129,.35)] hover:brightness-110"
          : "rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-neutral-300 hover:bg-white/[0.06]"
      }
    >
      {children}
    </motion.button>
  );
}

export function FixNextHero({
  total,
  bad,
  queue,
  onFix,
  onPickDifferent,
}: {
  total: number;
  bad: number;
  queue: SessionRow | null;
  onFix: (id: string) => void;
  onPickDifferent: () => void;
}) {
  if (!total) return <div className="font-display text-2xl font-semibold">No chats found.</div>;
  if (!bad || !queue)
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        className="glow-card relative overflow-hidden rounded-2xl p-6"
      >
        <svg className="orbit-ring absolute -right-10 -top-10 h-44 w-44 opacity-30" viewBox="0 0 100 100" aria-hidden>
          <circle cx="50" cy="50" r="44" fill="none" stroke="#34d399" strokeWidth="1" strokeDasharray="10 14" />
        </svg>
        <svg width="52" height="52" viewBox="0 0 52 52" aria-hidden>
          <circle cx="26" cy="26" r="23" fill="none" stroke="#10b981" strokeWidth="2.5" />
          <path d="M16 27l7 7 13-15" fill="none" stroke="#34d399" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <div className="mt-3 font-display text-[22px] font-semibold">Fleet is clean.</div>
        <div className="text-sm text-neutral-400">{copy.heroClean}</div>
      </motion.div>
    );
  const pct = Math.round(((total - bad) / total) * 1000) / 10;
  return (
    <div>
      <div className="eyebrow">Fleet status</div>
      <h1 className="mt-1 font-display text-[34px] font-semibold leading-[1.05] tracking-tight sm:text-[40px]">
        <span className="bg-gradient-to-r from-accent-hi to-accent bg-clip-text text-transparent">
          <Ticker value={total - bad} />
        </span>{" "}
        <span className="text-neutral-500">of</span> <Ticker value={total} />{" "}
        <span className="text-neutral-300">healthy</span>
        <span className="text-neutral-600"> · </span>
        <span className="text-danger-tx"><Ticker value={bad} /> to fix</span>
      </h1>
      <div className="shimmer-bar mt-4 h-1 overflow-hidden rounded-full bg-white/10">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-accent to-accent-hi"
          initial={false}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.7, ease: [0.2, 0.8, 0.2, 1] }}
        />
      </div>
      <motion.div
        key={queue.id}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        className="glow-card mt-4 flex flex-wrap items-center gap-4 rounded-2xl p-5"
      >
        <div className="min-w-0 flex-1">
          <div className="eyebrow">Next up</div>
          <div className="mt-1 truncate font-display text-lg font-semibold">
            {queue.title || "untitled"}{" "}
            <span className="font-mono text-xs font-normal text-idblue">{queue.id}</span>{" "}
            <span className="ml-1 rounded-full border border-danger/40 bg-danger/10 px-2 py-0.5 align-middle font-mono text-[11px] font-semibold text-danger-tx">
              {queue.seals_active} LOCKS
            </span>
          </div>
          <div className="mt-1 text-sm text-neutral-400">{copy.heroNeedsFix(bad)}</div>
        </div>
        <MagneticButton primary onClick={() => onFix(queue.id)}>
          Fix {queue.title || "next"} →
        </MagneticButton>
        <MagneticButton onClick={onPickDifferent}>Pick different</MagneticButton>
      </motion.div>
    </div>
  );
}

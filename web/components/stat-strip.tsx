"use client";
import { Reveal } from "./primitives";
import { rel } from "./fix-next-hero";

export function StatStrip({
  total,
  bad,
  lastBackup,
  dbMb,
}: {
  total: number;
  bad: number;
  lastBackup: string;
  dbMb: string;
}) {
  const cards = [
    { v: String(total), l: "Chats tracked", s: `${total} tracked`, tone: "" },
    { v: String(bad), l: "Need attention", s: bad ? `${bad} need attention` : "all clean", tone: bad ? "bad" : "good" },
    { v: lastBackup ? rel(Date.parse(lastBackup) / 1000 || null) : "–", l: "Since last safety copy", s: lastBackup || "none yet", tone: "" },
    { v: dbMb || "–", l: "Database", s: "Safe to browse while Hermes runs", tone: "" },
  ];
  return (
    <div className="mt-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
      {cards.map((c, i) => (
        <Reveal key={c.l} delay={i * 60}>
        <div className="min-w-0 rounded-xl border border-white/10 bg-white/[0.02] p-4 transition-colors duration-120 hover:border-white/20 hover:bg-white/[0.035]">
          <div
            className={`font-mono text-2xl font-semibold tracking-tight ${
              c.tone === "bad" ? "text-danger-tx" : c.tone === "good" ? "text-accent-hi" : ""
            }`}
          >
            {c.v}
          </div>
          <div className="mt-1 text-xs text-neutral-400">{c.l}</div>
          <div className="mt-1 truncate font-mono text-[11px] text-neutral-500">{c.s}</div>
        </div>
        </Reveal>
      ))}
    </div>
  );
}

"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { SessionRow } from "@/lib/api";
import { rel } from "./fix-next-hero";

type SortKey = "title" | "seals" | "msgs" | "last";

function highlight(text: string, q: string): React.ReactNode {
  const toks = q.toLowerCase().split(/\s+/).filter((t) => t && !t.includes(":"));
  let out: React.ReactNode = text;
  void toks;
  return out;
}

export function SessionTable({
  rows,
  query,
  selected,
  onOpen,
  onQuickFix,
  motion = "full",
  checked,
  onToggle,
  onToggleAll,
  selfSession,
}: {
  rows: SessionRow[];
  query: string;
  selected: string | null;
  onOpen: (id: string) => void;
  onQuickFix: (id: string) => void;
  motion?: "full" | "calm" | "off";
  checked: Set<string>;
  onToggle: (id: string, shift: boolean, order: string[]) => void;
  onToggleAll: (ids: string[]) => void;
  selfSession?: string;
}) {
  const isSelfRow = (id: string) => !!selfSession && id === selfSession;
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "seals", dir: -1 });
  const maxSeal = useMemo(() => Math.max(1, ...rows.map((r) => r.seals_active ?? 0)), [rows]);
  const sorted = useMemo(() => {
    const arr = [...rows];
    const val = (r: SessionRow) =>
      sort.key === "title"
        ? (r.title || "").toLowerCase()
        : sort.key === "seals"
          ? (r.seals_active ?? 0)
          : sort.key === "msgs"
            ? (r.message_count ?? 0)
            : (r.last_activity_at ?? 0);
    arr.sort((a, b) => {
      const pa = a.pinned ? 1 : 0;
      const pb = b.pinned ? 1 : 0;
      if (pa !== pb) return pb - pa;
      const va = val(a);
      const vb = val(b);
      return (va < vb ? -1 : va > vb ? 1 : 0) * sort.dir;
    });
    return arr;
  }, [rows, sort]);

  const th = (label: string, key: SortKey | null) => (
    <th
      scope="col"
      aria-sort={key && sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
      onClick={key ? () => setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === "title" ? 1 : -1 })) : undefined}
      className={key ? "cursor-pointer select-none hover:text-neutral-100" : ""}
    >
      {label}
      {key && sort.key === key && <span className="ml-1 text-[10px] text-accent-hi">{sort.dir === 1 ? "↑" : "↓"}</span>}
    </th>
  );

  const allRef = useRef<HTMLInputElement>(null);
  const order = useMemo(() => sorted.map((r) => r.id), [sorted]);
  const allState: "all" | "some" | "none" =
    order.length > 0 && order.every((id) => checked.has(id))
      ? "all"
      : order.some((id) => checked.has(id))
        ? "some"
        : "none";
  useEffect(() => {
    if (allRef.current) allRef.current.indeterminate = allState === "some";
  }, [allState]);

  if (!sorted.length)
    return (
      <div className="p-10 text-center text-neutral-500">
        <div>No chats match “{query}”.</div>
      </div>
    );

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <thead className="sticky top-0 z-10 bg-canvas-900">
          <tr className="text-left text-[11px] uppercase tracking-widest text-neutral-500">
            <th className="w-[36px] px-2 py-2">
              <input
                ref={allRef}
                type="checkbox"
                checked={allState === "all"}
                onChange={() => onToggleAll(order)}
                onClick={(e) => e.stopPropagation()}
                aria-label={allState === "all" ? "Deselect all" : "Select all"}
                className="h-[15px] w-[15px] cursor-pointer accent-[#10b981]"
              />
            </th>
            <th className="w-[34px] px-2 py-2" />
            {th("Chat", "title")}
            <th className="px-2 py-2">ID</th>
            {th("Locks", "seals")}
            {th("Msgs", "msgs")}
            {th("Last active", "last")}
            <th className="px-2 py-2" />
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, 120).map((r, i) => {
            const pct = Math.min(100, Math.round(((r.seals_active ?? 0) / maxSeal) * 100));
            void highlight;
            void pct;
            return (
              <tr
                key={r.id}
                data-id={r.id}
                aria-selected={selected === r.id}
                tabIndex={0}
                onClick={() => onOpen(r.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onOpen(r.id);
                  if (e.key.toLowerCase() === "x") onToggle(r.id, false, order);
                }}
                style={motion === "off" || i > 14 ? undefined : { animationDelay: `${Math.min(14, i) * 35}ms` }}
                className={`group cursor-pointer border-b border-white/5 transition-colors duration-120 ${
                  motion !== "off" && i <= 14 ? "row-enter" : ""
                } ${
                  selected === r.id ? "bg-accent-dim shadow-[inset_2px_0_0_#10b981]" : "hover:bg-white/[0.035]"
                } ${
                  checked.has(r.id) ? "bg-white/[0.03]" : ""
                }`}
              >
                <td className="px-2 py-2" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={checked.has(r.id)}
                    onChange={() => {}}
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggle(r.id, e.shiftKey, order);
                    }}
                    aria-label={`Select ${r.title || r.id}`}
                    className="h-[15px] w-[15px] cursor-pointer accent-[#10b981]"
                  />
                </td>
                <td className="px-2 py-2">{r.seals_active ? <span className="text-danger">●</span> : <span className="text-neutral-700">●</span>}</td>
                <td className="max-w-[280px] truncate px-2 py-2 font-medium">
                  {r.pinned ? <span className="mr-1 text-warn">★</span> : null}
                  {r.title || <span className="text-neutral-500">untitled</span>}
                  {isSelfRow(r.id) && (
                    <span className="ml-2 rounded-full border border-warn/40 bg-warn/10 px-2 py-px text-[10px] font-semibold text-warn">
                      LIVE — blocked
                    </span>
                  )}
                </td>
                <td className="max-w-[190px] truncate px-2 py-2 font-mono text-xs text-idblue" title={r.id}>
                  {r.id}
                </td>
                <td className="px-2 py-2">
                  {r.seals_active ? (
                    <span className="rounded-full border border-danger/40 bg-danger/10 px-2.5 py-0.5 text-[11px] font-semibold text-danger-tx">
                      {r.seals_active} LOCKS
                    </span>
                  ) : (
                    <span className="rounded-full border border-accent/30 bg-accent-dim px-2.5 py-0.5 text-[11px] font-semibold text-accent-hi">
                      CLEAN
                    </span>
                  )}
                </td>
                <td className="px-2 py-2 font-mono">{r.message_count ?? ""}</td>
                <td className="whitespace-nowrap px-2 py-2 text-neutral-500" title={r.last_activity_at ? new Date(r.last_activity_at * 1000).toUTCString() : ""}>
                  {rel(r.last_activity_at)}
                </td>
                <td className="px-2 py-2">
                  {r.seals_active ? (
                    isSelfRow(r.id) ? (
                      <span className="text-xs text-neutral-600" title="Blocked: this is your live chat">
                        Blocked
                      </span>
                    ) : (
                      <button
                        className="text-xs font-medium text-accent-hi hover:underline"
                        onClick={(e) => {
                          e.stopPropagation();
                          onQuickFix(r.id);
                        }}
                      >
                        Fix →
                      </button>
                    )
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

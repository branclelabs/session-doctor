"use client";
import { Command } from "cmdk";
import { useEffect, useState } from "react";
import type { SessionRow } from "@/lib/api";

export function CommandPalette({
  rows,
  onInspect,
  onFix,
  onGoto,
}: {
  rows: SessionRow[];
  onInspect: (id: string) => void;
  onFix: (id: string) => void;
  onGoto: (v: "sessions" | "backups" | "activity" | "settings") => void;
}) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, []);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 font-mono text-[11px] text-neutral-400"
      >
        ⌘K
      </button>
      <Command.Dialog open={open} onOpenChange={setOpen} label="Command palette">
        <div className="fixed inset-0 z-50 grid justify-center bg-black/55 p-4 pt-[12vh]" onClick={() => setOpen(false)}>
          <div className="h-fit w-[600px] max-w-[92vw] overflow-hidden rounded-xl border border-white/10 bg-canvas-800 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <Command.Input autoFocus placeholder="Type a command or chat…  try fix, open, Go to…" className="w-full border-b border-white/10 bg-transparent p-4 text-[15px] outline-none" />
            <Command.List className="max-h-[320px] overflow-auto p-1.5">
              <Command.Empty>No match. Try an ID fragment or Go to…</Command.Empty>
              <Command.Group heading="Needs fix">
                {rows
                  .filter((r) => (r.seals_active ?? 0) > 0)
                  .slice(0, 4)
                  .map((r) => (
                    <Command.Item
                      key={"fix" + r.id}
                      onSelect={() => {
                        setOpen(false);
                        onFix(r.id);
                      }}
                      className="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm aria-selected:bg-accent-dim"
                    >
                      Fix {r.title || r.id}
                      <span className="ml-auto font-mono text-[11px] text-neutral-500">{r.seals_active} locks</span>
                    </Command.Item>
                  ))}
              </Command.Group>
              <Command.Group heading="Chats">
                {rows.slice(0, 8).map((r) => (
                  <Command.Item
                    key={r.id}
                    onSelect={() => {
                      setOpen(false);
                      onInspect(r.id);
                    }}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm aria-selected:bg-accent-dim"
                  >
                    Inspect {r.title || r.id}
                    <span className="ml-auto font-mono text-[11px] text-neutral-500">open</span>
                  </Command.Item>
                ))}
              </Command.Group>
              <Command.Group heading="Views">
                {(["sessions", "backups", "activity", "settings"] as const).map((v) => (
                  <Command.Item
                    key={v}
                    onSelect={() => {
                      setOpen(false);
                      onGoto(v);
                    }}
                    className="cursor-pointer rounded-md px-3 py-2 text-sm capitalize aria-selected:bg-accent-dim"
                  >
                    Go to {v}
                  </Command.Item>
                ))}
              </Command.Group>
            </Command.List>
          </div>
        </div>
      </Command.Dialog>
    </>
  );
}

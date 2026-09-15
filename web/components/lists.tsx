"use client";
import type { ActivityEvent, Bundle } from "@/lib/api";

export function BackupList({ bundles }: { bundles: Bundle[] }) {
  if (!bundles.length)
    return <p className="text-sm text-neutral-500">No safety copies yet. Pick a chat → Backup to create your first verified copy.</p>;
  const mb = (b: Bundle) => (b.snapshot_bytes ? `${(b.snapshot_bytes / 1e6).toFixed(0)}MB` : "—");
  return (
    <div className="space-y-2.5">
      {bundles.slice(0, 30).map((b, i) => (
        <div
          key={b.dir}
          style={{ animationDelay: `${Math.min(10, i) * 40}ms` }}
          className="row-enter rounded-lg border border-white/10 bg-white/[0.02] p-3.5 text-[13px] transition-colors hover:border-white/20 hover:bg-white/[0.035]"
        >
          <code className="font-mono text-xs text-idblue">{b.dir.split("/").pop()}</code>
          <div className="mt-1 text-neutral-400">
            {b.session_id} · locks at copy: {b.seals_total} · {b.active_msgs} msgs · {b.utc} · safety copy {mb(b)} ·{" "}
            {b.verified ? "✓ verified" : "○ unverified"}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ActivityList({ events }: { events: ActivityEvent[] }) {
  if (!events.length) return <p className="text-sm text-neutral-500">Nothing logged yet.</p>;
  const icon = (k: string) => (k === "backup" ? "▤" : k === "fix" ? "✚" : k === "restore" ? "↩" : "·");
  return (
    <div className="ml-1.5 border-l border-white/10 pl-5">
      {events.map((e, i) => (
        <div key={i} className="relative pb-4 text-[13px]">
          <span className="absolute -left-[26px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-accent bg-canvas-950" aria-hidden />
          <time className="mr-2 font-mono text-[11px] text-neutral-500">{(e.ts || "").slice(11, 19)}</time>
          {icon(e.kind)} <b>{e.kind}</b> {(e.session || "").slice(0, 24)} — {e.detail}
        </div>
      ))}
    </div>
  );
}

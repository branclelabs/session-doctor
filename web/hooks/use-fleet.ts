"use client";
import useSWR from "swr";
import { beGetSessions, type Backend, type SessionRow } from "@/lib/api";

export function nextUp(rows: SessionRow[]): SessionRow | null {
  const bad = rows.filter((r) => (r.seals_active ?? 0) > 0);
  if (!bad.length) return null;
  return [...bad].sort((a, b) => {
    const pa = a.pinned ? 1 : 0;
    const pb = b.pinned ? 1 : 0;
    if (pa !== pb) return pb - pa;
    const sa = a.seals_active ?? 0;
    const sb = b.seals_active ?? 0;
    if (sa !== sb) return sb - sa;
    return (b.last_activity_at ?? 0) - (a.last_activity_at ?? 0);
  })[0];
}

export function useFleet(backend: Backend = "hermes") {
  const swr = useSWR(["fleet", backend], () => beGetSessions(backend), {
    refreshInterval: 7000,
    dedupingInterval: 5000,
    revalidateOnFocus: true,
  });
  const rows = swr.data?.rows ?? [];
  const bad = rows.filter((r) => (r.seals_active ?? 0) > 0);
  return { ...swr, rows, bad, queue: nextUp(rows) };
}

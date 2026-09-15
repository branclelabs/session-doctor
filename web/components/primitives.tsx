"use client";
import { useEffect, useRef, useState } from "react";

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const h = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);
  return reduced;
}

export function Ticker({ value, duration = 700 }: { value: number; duration?: number }) {
  const [display, setDisplay] = useState(value);
  const from = useRef(value);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    if (reduced) {
      setDisplay(value);
      from.current = value;
      return;
    }
    const start = from.current;
    if (start === value) return;
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / duration);
      const e = 1 - Math.pow(1 - p, 4);
      setDisplay(Math.round(start + (value - start) * e));
      if (p < 1) raf = requestAnimationFrame(tick);
      else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, reduced]);

  return <span style={{ fontVariantNumeric: "tabular-nums" }}>{display}</span>;
}

export function Reveal({
  children,
  delay = 0,
  y = 10,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && setShown(true)),
      { threshold: 0.1 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: shown ? 1 : 0,
        transform: shown ? "none" : `translateY(${y}px)`,
        transition: `opacity 450ms cubic-bezier(.16,1,.3,1) ${delay}ms, transform 450ms cubic-bezier(.16,1,.3,1) ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

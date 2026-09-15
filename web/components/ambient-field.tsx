"use client";
import { useEffect, useRef } from "react";

export function AmbientField({ badRatio }: { badRatio: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const ratio = useRef(badRatio);
  ratio.current = badRatio;

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let raf = 0;
    let t = Math.random() * 100;
    let mx = 0;
    let my = 0;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const resize = () => {
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
    };
    resize();
    window.addEventListener("resize", resize);
    const onMove = (e: PointerEvent) => {
      mx += ((e.clientX / window.innerWidth - 0.5) * 24 - mx) * 0.04;
      my += ((e.clientY / window.innerHeight - 0.5) * 12 - my) * 0.04;
    };
    window.addEventListener("pointermove", onMove);
    const blobs = [
      { x: 0.32, y: -0.08, r: 0.42, sp: 0.00016, ph: 0 },
      { x: 0.78, y: 0.22, r: 0.3, sp: 0.00011, ph: 2.1 },
      { x: 0.12, y: 0.55, r: 0.34, sp: 0.00009, ph: 4.2 },
    ];
    const render = () => {
      if (document.hidden) {
        raf = requestAnimationFrame(render);
        return;
      }
      t += 1;
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      const bad = Math.max(0, Math.min(1, ratio.current));
      // base emerald breath
      const g0 = ctx.createRadialGradient(
        w * 0.32 + mx * dpr, h * -0.06 + my * dpr, 0,
        w * 0.32 + mx * dpr, h * -0.06 + my * dpr, Math.max(w, h) * 0.5
      );
      g0.addColorStop(0, `rgba(16,185,129,${0.075 - bad * 0.02})`);
      g0.addColorStop(1, "rgba(16,185,129,0)");
      ctx.fillStyle = g0;
      ctx.fillRect(0, 0, w, h);
      // reactive ember wash when fleet is red
      if (bad > 0.02) {
        const g1 = ctx.createRadialGradient(
          w * 0.72 - mx * dpr, h * 0.3 - my * dpr, 0,
          w * 0.72 - mx * dpr, h * 0.3 - my * dpr, Math.max(w, h) * 0.42
        );
        g1.addColorStop(0, `rgba(242,85,90,${0.05 * Math.min(1, bad * 1.4)})`);
        g1.addColorStop(1, "rgba(242,85,90,0)");
        ctx.fillStyle = g1;
        ctx.fillRect(0, 0, w, h);
      }
      // drifting blobs
      for (const b of blobs) {
        const bx = (b.x + Math.sin(t * b.sp + b.ph) * 0.05) * w + mx * dpr;
        const by = (b.y + Math.cos(t * b.sp * 1.3 + b.ph) * 0.05) * h + my * dpr;
        const g = ctx.createRadialGradient(bx, by, 0, bx, by, Math.max(w, h) * b.r);
        g.addColorStop(0, "rgba(52,211,153,0.05)");
        g.addColorStop(1, "rgba(52,211,153,0)");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      }
      // dot grid, masked to top
      ctx.fillStyle = "rgba(255,255,255,0.05)";
      const step = 26 * dpr;
      const rows = Math.min(14, Math.floor(h / step));
      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < w / step; x++) {
          const fade = 1 - y / rows;
          ctx.globalAlpha = 0.5 * fade;
          ctx.fillRect(x * step, y * step, dpr, dpr);
        }
      }
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
    };
  }, []);

  return <canvas ref={ref} className="pointer-events-none fixed inset-0 h-full w-full" aria-hidden />;
}

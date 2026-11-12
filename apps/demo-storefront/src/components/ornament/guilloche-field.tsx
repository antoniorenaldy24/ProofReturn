"use client";

import { useEffect, useRef } from "react";
import { rosePoints } from "@/lib/guilloche";

/**
 * The living guilloché field — layered modulated roses computed per frame,
 * the same mathematics engraved on banknotes. Slows to a single static
 * impression under prefers-reduced-motion, and sleeps when offscreen.
 */
export function GuillocheField({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let visible = true;
    let phase = 0;
    let mouse = { x: 0.5, y: 0.5 };
    let target = { x: 0.5, y: 0.5 };
    let w = 0;
    let h = 0;

    const dpr = Math.min(2, window.devicePixelRatio || 1);

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      const cx = w / 2;
      const cy = h / 2;
      const R = Math.max(w, h) * 0.42;

      // Mouse gently warps the mathematics (lerped).
      mouse.x += (target.x - mouse.x) * 0.045;
      mouse.y += (target.y - mouse.y) * 0.045;
      const mx = (mouse.x - 0.5) * 2; // -1..1
      const my = (mouse.y - 0.5) * 2;

      const layers = 6;
      for (let k = 0; k < layers; k++) {
        const f = k / (layers - 1);
        const pts = rosePoints(cx + mx * 26 * f, cy + my * 22 * f, {
          R: R * (0.3 + 0.78 * f),
          a: 0.05 + 0.11 * f + Math.abs(mx) * 0.05,
          n: 10 + ((k * 5) % 3) * 6,
          phase: phase * (0.4 + f * 0.9) + k * 0.5,
          steps: 260,
        });
        ctx.beginPath();
        pts.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
        ctx.closePath();
        ctx.strokeStyle = `rgba(34, 29, 18, ${0.05 + f * 0.09})`;
        ctx.lineWidth = 0.6;
        ctx.stroke();
      }

      // Two hairline hairline rings for structure.
      ctx.strokeStyle = "rgba(30, 74, 54, 0.22)";
      ctx.lineWidth = 0.7;
      [0.34, 1.02].forEach((s) => {
        ctx.beginPath();
        ctx.arc(cx + mx * 14, cy + my * 12, R * s, 0, Math.PI * 2);
        ctx.stroke();
      });
    };

    const tick = () => {
      phase += 0.0016;
      draw();
      if (visible && !document.hidden) raf = requestAnimationFrame(tick);
    };

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();

    const io = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        if (visible && !reduced) {
          cancelAnimationFrame(raf);
          raf = requestAnimationFrame(tick);
        }
      },
      { threshold: 0.02 },
    );
    io.observe(canvas);

    const onMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      target = {
        x: Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)),
        y: Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)),
      };
    };
    const onVis = () => {
      if (!document.hidden && visible && !reduced) {
        cancelAnimationFrame(raf);
        raf = requestAnimationFrame(tick);
      }
    };

    if (!reduced) {
      window.addEventListener("pointermove", onMove, { passive: true });
      document.addEventListener("visibilitychange", onVis);
      raf = requestAnimationFrame(tick);
    } else {
      draw(); // one static impression
    }

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}

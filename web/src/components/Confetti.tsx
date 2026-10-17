import { useEffect, useRef } from "react";

/** A short burst of confetti for a correct call. Canvas, about 2 s, then gone; skipped for reduced motion. */
export default function Confetti() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const g = c.getContext("2d");
    if (!g) return;
    const dpr = Math.min(2, window.devicePixelRatio);
    const w = (c.width = c.clientWidth * dpr);
    const h = (c.height = c.clientHeight * dpr);
    const colors = ["#FFD23F", "#1F9D6B", "#C8352B", "#157A8C", "#F6F3EC", "#F2B33D"];
    const bits = Array.from({ length: 110 }, () => ({
      x: w / 2 + (Math.random() - 0.5) * w * 0.3,
      y: h * 0.25,
      vx: (Math.random() - 0.5) * 14 * dpr,
      vy: (-Math.random() * 14 - 4) * dpr,
      r: (Math.random() * 5 + 3) * dpr,
      a: Math.random() * Math.PI,
      va: (Math.random() - 0.5) * 0.4,
      c: colors[Math.floor(Math.random() * colors.length)],
    }));
    let raf = 0;
    const t0 = performance.now();
    const draw = () => {
      const t = performance.now() - t0;
      g.clearRect(0, 0, w, h);
      for (const b of bits) {
        b.vy += 0.45 * dpr;
        b.vx *= 0.99;
        b.x += b.vx;
        b.y += b.vy;
        b.a += b.va;
        g.save();
        g.globalAlpha = Math.max(0, 1 - t / 2200);
        g.translate(b.x, b.y);
        g.rotate(b.a);
        g.fillStyle = b.c;
        g.fillRect(-b.r, -b.r / 2, b.r * 2, b.r);
        g.restore();
      }
      if (t < 2200) raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);
  return <canvas ref={ref} className="confetti" aria-hidden="true" />;
}

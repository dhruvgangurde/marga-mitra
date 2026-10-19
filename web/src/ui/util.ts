import { useEffect, useState } from 'react';

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}

// The scalloped edge shared by seals and the arrow badge on primary buttons.
export function scallopPath(size: number, bumps: number, inset: number): string {
  const c = size / 2;
  const R = size / 2 - inset;
  const r = R * Math.sin(Math.PI / bumps) * 1.12;
  let d = '';
  for (let i = 0; i < bumps; i++) {
    const a0 = (i / bumps) * Math.PI * 2 - Math.PI / bumps;
    const a1 = a0 + (2 * Math.PI) / bumps;
    const p0 = [c + R * Math.cos(a0), c + R * Math.sin(a0)];
    const p1 = [c + R * Math.cos(a1), c + R * Math.sin(a1)];
    if (i === 0) d += 'M' + p0[0].toFixed(2) + ' ' + p0[1].toFixed(2) + ' ';
    d += 'A' + r.toFixed(2) + ' ' + r.toFixed(2) + ' 0 0 1 ' + p1[0].toFixed(2) + ' ' + p1[1].toFixed(2) + ' ';
  }
  return d + 'Z';
}

export function decimals(n: number | string): number {
  return (String(n).split('.')[1] || '').length;
}

// Counts up from 0 once on mount (600 ms, ease-out); respects reduced motion.
export function useCountUp(target: number | string, enabled: boolean): number | string {
  const [v, setV] = useState<number | string>(enabled ? 0 : target);
  useEffect(() => {
    if (!enabled || typeof target !== 'number') { setV(target); return; }
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setV(target); return; }
    const t0 = performance.now();
    const dp = decimals(target);
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / 600);
      setV(k < 1 ? Number((target * (1 - Math.pow(1 - k, 3))).toFixed(dp)) : target);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, enabled]);
  return v;
}

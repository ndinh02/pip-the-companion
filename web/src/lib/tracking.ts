import type { Match } from "./types";

/** Synthetic 5 Hz tracking (docs/TRACKING_SPEC.md). Positions in decimetres; -1 = not on the pitch. */
export interface Tracking {
  match_id: string;
  hz: number;
  periods: { id: number; start_ms: number; frames: number }[];
  entities: string[];
  x: Record<string, number[]>;
  y: Record<string, number[]>;
  /** Ball height in decimetres (-1 = off the pitch). Optional: older files have none. */
  z?: { ball: number[] };
}
export interface Dot {
  id: string; // "ball" or a player id such as "HAR-7"
  x: number; // metres
  y: number;
}

/** Tracking for this match, or null if there is no file or it belongs to another match. */
export async function loadTracking(match: Match): Promise<Tracking | null> {
  try {
    const res = await fetch("/data/tracking.json");
    if (!res.ok) return null;
    const data = (await res.json()) as Tracking;
    if (data.match_id !== match.match_id) {
      console.warn(`tracking.json is for ${data.match_id}, not ${match.match_id}: pitch stays empty`);
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

/** Match-clock minute (period 2 starts at 45) -> match time in ms. Period-1 added time is not on this clock. */
export function minuteToMs(tr: Tracking, minute: number): number {
  const [p1, p2] = tr.periods;
  const step = 1000 / tr.hz;
  if (minute < 45) return Math.min(p1.start_ms + minute * 60_000, p1.start_ms + (p1.frames - 1) * step);
  return Math.min(p2.start_ms + (minute - 45) * 60_000, p2.start_ms + (p2.frames - 1) * step);
}

/** Everyone on the pitch (and the ball) at a match time, interpolated between the two nearest frames. */
export function positionsAt(tr: Tracking, tMs: number): Dot[] {
  const step = 1000 / tr.hz;
  let offset = 0;
  let period = tr.periods[0];
  for (const p of tr.periods) {
    if (tMs >= p.start_ms) period = p;
  }
  for (const p of tr.periods) {
    if (p === period) break;
    offset += p.frames;
  }
  const f = Math.max(0, Math.min(period.frames - 1, (tMs - period.start_ms) / step));
  const i0 = Math.floor(f);
  const i1 = Math.min(period.frames - 1, i0 + 1);
  const a = f - i0;
  const out: Dot[] = [];
  for (const id of tr.entities) {
    const xs = tr.x[id];
    const ys = tr.y[id];
    const x0 = xs[offset + i0];
    const x1 = xs[offset + i1];
    if (x0 < 0) continue; // not on the pitch
    const y0 = ys[offset + i0];
    const useNext = x1 >= 0;
    out.push({
      id,
      x: (useNext ? x0 + (x1 - x0) * a : x0) / 10,
      y: (useNext ? y0 + (ys[offset + i1] - y0) * a : y0) / 10,
    });
  }
  return out;
}

/** The player of `teamId` closest to the ball: the one "on the ball" at that moment. */
export function nearestToBall(dots: Dot[], teamId: string): string | null {
  const ball = dots.find((d) => d.id === "ball");
  if (!ball) return null;
  let best: string | null = null;
  let bestD = Infinity;
  for (const d of dots) {
    if (!d.id.startsWith(`${teamId}-`)) continue;
    const dist = (d.x - ball.x) ** 2 + (d.y - ball.y) ** 2;
    if (dist < bestD) {
      bestD = dist;
      best = d.id;
    }
  }
  return best;
}

/** Match time in ms -> match-clock minute (period 2 starts at 45; period-1 added time shows as 45). */
export function msToMinute(tr: Tracking, tMs: number): number {
  const [p1, p2] = tr.periods;
  if (tMs < p2.start_ms) return Math.min(45, (tMs - p1.start_ms) / 60_000);
  return 45 + (tMs - p2.start_ms) / 60_000;
}

export function endMs(tr: Tracking): number {
  const last = tr.periods[tr.periods.length - 1];
  return last.start_ms + ((last.frames - 1) * 1000) / tr.hz;
}

/** Speed in km/h right now, measured over the last 0.4 s of tracking. Null if the player is not on the pitch. */
export function speedKmh(tr: Tracking, id: string, tMs: number): number | null {
  const a = positionsAt(tr, tMs - 400).find((d) => d.id === id);
  const b = positionsAt(tr, tMs).find((d) => d.id === id);
  if (!a || !b) return null;
  const v = (Math.hypot(b.x - a.x, b.y - a.y) / 0.4) * 3.6;
  return v > 45 ? null : v; // a jump (half-time, coming on) is not a speed
}

/** Where the player has been over the last `seconds`, one point per second, oldest first. */
export function trail(tr: Tracking, id: string, tMs: number, seconds = 30, stepS = 1): { x: number; y: number }[] {
  const pts: { x: number; y: number }[] = [];
  for (let s = seconds; s >= 0; s -= stepS) {
    const d = positionsAt(tr, tMs - s * 1000).find((p) => p.id === id);
    if (d) pts.push({ x: d.x, y: d.y });
  }
  return pts;
}

/** The player's fastest moment before `untilMs`: when it happened and how fast (3-frame average, km/h). */
export function fastestRun(tr: Tracking, id: string, untilMs: number): { tMs: number; kmh: number } | null {
  const xs = tr.x[id];
  const ys = tr.y[id];
  if (!xs) return null;
  const step = 1000 / tr.hz;
  let best: { tMs: number; kmh: number } | null = null;
  let offset = 0;
  for (const p of tr.periods) {
    const v: number[] = [];
    for (let i = 1; i < p.frames; i++) {
      const a = offset + i - 1;
      const b = offset + i;
      v.push(xs[a] < 0 || xs[b] < 0 ? 0 : (Math.hypot(xs[b] - xs[a], ys[b] - ys[a]) / 10 / (step / 1000)) * 3.6);
    }
    for (let i = 1; i < v.length - 1; i++) {
      const t = p.start_ms + (i + 1) * step;
      if (t >= untilMs) break;
      const avg = (v[i - 1] + v[i] + v[i + 1]) / 3;
      if (avg < 45 && (!best || avg > best.kmh)) best = { tMs: t, kmh: avg };
    }
    offset += p.frames;
  }
  return best;
}

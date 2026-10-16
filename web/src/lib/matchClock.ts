import type { AddedBoard, AddedTime, Card, Match } from "./types";
import type { Tracking } from "./tracking";

/** The demo's match clock, in match milliseconds (the same clock as the events and the tracking).
 *
 *  It behaves like a live broadcast: nothing ever stops for Pip. A question opens when the ball goes dead
 *  (a live feed signals that at once), stays open until play restarts (not known in advance), and the reveal
 *  shows when the outcome happens, while the match keeps running. Only half-time pauses, as football does.
 *
 *  "highlights" mode jumps between moments and plays each one at real speed; "full" mode runs the whole match. */

export type Mode = "highlights" | "full";
export type ClockPhase = "play" | "ask" | "locked" | "reveal" | "added" | "half" | "full";

export const DETECT_MS = 1500; // a live feed reports "ball dead" about this long after it happens
export const REVEAL_SHOW_MS = 12_000; // match time the reveal stays up while play goes on
export const BOARD_SHOW_MS = 20_000; // the added-time board is shown this long
export const HALF_BREAK_MS = 30_000; // real time the half-time card stays (the match itself is in its break)
const LEAD_MS = 15_000; // highlights: start this long before the ball goes dead, so the build-up is seen
const SKIP_IF_GAP_MS = 4_000; // highlights: only jump if the next moment is further away than this

export interface Period {
  id: number;
  start_ms: number;
  end_ms: number;
}
export interface Goal {
  t_ms: number;
  team_id: string;
  player_id: string;
  restart_ms: number; // the kick-off after it
}
export const GOAL_WATCH_MS = 24_000; // highlights keep watching this long after a goal (celebration and replay)

export interface Timeline {
  periods: Period[];
  cards: (Card & { dead_ms: number; restart_ms: number; reveal_ms: number })[];
  boards: { at_ms: number; board: AddedBoard }[];
  goals: Goal[];
  hasFirstHalfCards: boolean;
}

export function buildTimeline(match: Match, tracking: Tracking | null, added: AddedTime | null): Timeline {
  const periods: Period[] = tracking
    ? tracking.periods.map((p) => ({ id: p.id, start_ms: p.start_ms, end_ms: p.start_ms + ((p.frames - 1) * 1000) / tracking.hz }))
    : [
        { id: 1, start_ms: 0, end_ms: 47 * 60_000 },
        { id: 2, start_ms: 47 * 60_000, end_ms: 94 * 60_000 },
      ];
  // Cards without exact times (the old hand-written mock) get them from their minute.
  const cards = match.cards.map((c) => {
    const t = c.t_ms ?? minuteToMatchMs(periods, c.t_in_min);
    return { ...c, dead_ms: c.dead_ms ?? t - 30_000, restart_ms: c.restart_ms ?? t, reveal_ms: c.reveal_ms ?? t + 3_000 };
  });
  const boards = (added?.boards ?? []).map((b) => {
    const p = periods.find((x) => x.id === b.period) ?? periods[0];
    return { at_ms: p.start_ms + 45 * 60_000, board: b };
  });
  const goals: Goal[] = match.score_timeline
    .filter((g) => g.t_ms !== undefined && g.team_id && g.player_id)
    .map((g) => ({ t_ms: g.t_ms!, team_id: g.team_id!, player_id: g.player_id!, restart_ms: g.restart_ms ?? g.t_ms! + 45_000 }));
  return { periods, cards, boards, goals, hasFirstHalfCards: cards.some((c) => c.restart_ms < periods[1].start_ms) };
}

function minuteToMatchMs(periods: Period[], minute: number): number {
  return minute < 45 ? periods[0].start_ms + minute * 60_000 : periods[1].start_ms + (minute - 45) * 60_000;
}

/** Match minute on the clock viewers see (period 2 starts at 45). Added time keeps counting past 45 / 90. */
export function clockMinute(tl: Timeline, tMs: number): number {
  const [p1, p2] = tl.periods;
  return tMs < p2.start_ms ? (tMs - p1.start_ms) / 60_000 : 45 + (tMs - p2.start_ms) / 60_000;
}

/** "23'", "45+2'", "90+4'" */
export function clockLabel(tl: Timeline, tMs: number): string {
  const m = clockMinute(tl, tMs);
  const base = tMs < tl.periods[1].start_ms ? 45 : 90;
  return m >= base ? `${base}+${Math.floor(m - base) + 1}'` : `${Math.floor(m)}'`;
}

export interface Clock {
  tMs: number;
  running: boolean;
  speed: number;
  mode: Mode;
  halfDone: boolean;
  halfUntil: number | null; // real time when the half-time break ends
  skipped: { to: number; until: number } | null; // "skipping to 23'" note, until real time
}

export const startClock = (mode: Mode = "highlights"): Clock => ({ tMs: 0, running: true, speed: 1, mode, halfDone: false, halfUntil: null, skipped: null });

export interface View {
  phase: ClockPhase;
  card: Timeline["cards"][number] | null;
  board: AddedBoard | null;
  /** 0..1 progress through the current phase, for bars (no bar while a question is open: its end is unknown) */
  progress: number | null;
}

export function viewAt(tl: Timeline, clk: Clock): View {
  const t = clk.tMs;
  if (clk.halfUntil !== null) return { phase: "half", card: null, board: null, progress: null };
  if (t >= tl.periods[tl.periods.length - 1].end_ms) return { phase: "full", card: null, board: null, progress: null };
  for (const c of tl.cards) {
    if (t < c.dead_ms + DETECT_MS || t >= c.reveal_ms + REVEAL_SHOW_MS) continue;
    if (t < c.restart_ms) return { phase: "ask", card: c, board: null, progress: null };
    if (t < c.reveal_ms) return { phase: "locked", card: c, board: null, progress: null };
    return { phase: "reveal", card: c, board: null, progress: (t - c.reveal_ms) / REVEAL_SHOW_MS };
  }
  for (const b of tl.boards) {
    if (t >= b.at_ms && t < b.at_ms + BOARD_SHOW_MS) return { phase: "added", card: null, board: b.board, progress: (t - b.at_ms) / BOARD_SHOW_MS };
  }
  return { phase: "play", card: null, board: null, progress: null };
}

/** Where highlights mode wants to be next: just before the next moment worth watching.
 *  Returns the current time when we are already in a moment's run-up (so we stay and watch it). */
function nextStop(tl: Timeline, clk: Clock): number | null {
  const t = clk.tMs;
  const items: { stop: number; at: number }[] = [];
  for (const c of tl.cards) items.push({ stop: c.dead_ms - LEAD_MS, at: c.dead_ms + DETECT_MS });
  for (const b of tl.boards) items.push({ stop: b.at_ms - 3_000, at: b.at_ms });
  for (const g of tl.goals) items.push({ stop: g.t_ms - LEAD_MS, at: g.t_ms + GOAL_WATCH_MS });
  if (!clk.halfDone) items.push({ stop: tl.periods[0].end_ms - 3_000, at: tl.periods[0].end_ms });
  const end = tl.periods[tl.periods.length - 1].end_ms;
  items.push({ stop: end - 3_000, at: end });
  const upcoming = items.filter((i) => i.at > t);
  if (!upcoming.length) return null;
  return Math.max(t, Math.min(...upcoming.map((i) => i.stop)));
}

/** Move the clock forward by `realDt` ms of real time. */
export function advance(tl: Timeline, clk: Clock, realDt: number, now: number): Clock {
  if (clk.halfUntil !== null) {
    if (now < clk.halfUntil) return clk;
    return { ...clk, halfUntil: null, halfDone: true, tMs: tl.periods[1].start_ms };
  }
  if (!clk.running) return clk;
  const end = tl.periods[tl.periods.length - 1].end_ms;
  let t = Math.min(end, clk.tMs + realDt * clk.speed);
  let skipped = clk.skipped && now < clk.skipped.until ? clk.skipped : null;
  if (!clk.halfDone && t >= tl.periods[0].end_ms) {
    // Half-time: the one real stop in football. Show the half-time card, then kick off the second half.
    if (tl.hasFirstHalfCards) return { ...clk, tMs: tl.periods[0].end_ms, halfUntil: now + HALF_BREAK_MS, skipped: null };
    return { ...clk, tMs: tl.periods[1].start_ms, halfDone: true, skipped };
  }
  if (clk.mode === "highlights" && viewAt(tl, { ...clk, tMs: t }).phase === "play") {
    const stop = nextStop(tl, { ...clk, tMs: t });
    if (stop !== null && stop - t > SKIP_IF_GAP_MS) {
      t = stop;
      skipped = { to: t, until: now + 2_500 };
    }
  }
  return { ...clk, tMs: t, skipped };
}

/** The "Next ▸" button: jump to just before the next moment (or out of the current one). */
export function skipAhead(tl: Timeline, clk: Clock, now: number): Clock {
  if (clk.halfUntil !== null) return { ...clk, halfUntil: null, halfDone: true, tMs: tl.periods[1].start_ms };
  const v = viewAt(tl, clk);
  if (v.card) {
    // From the question straight to the kick, then to the outcome, then past the reveal.
    const c = v.card;
    const to = v.phase === "ask" ? c.restart_ms - 2_000 : v.phase === "locked" ? c.reveal_ms : c.reveal_ms + REVEAL_SHOW_MS;
    return { ...clk, tMs: Math.max(clk.tMs, to), skipped: null };
  }
  const stop = nextStop(tl, { ...clk, tMs: clk.tMs + 1_000 });
  if (stop === null) return clk;
  const target = Math.max(clk.tMs, stop + LEAD_MS - 3_000); // land 3 s before the moment itself
  if (!clk.halfDone && target >= tl.periods[0].end_ms) return advance(tl, { ...clk, tMs: tl.periods[0].end_ms - 1 }, 1, now);
  return { ...clk, tMs: target, skipped: { to: target, until: now + 2_500 } };
}

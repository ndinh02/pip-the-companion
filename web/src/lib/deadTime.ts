import { DETECT_MS, type ClockPhase, type Timeline } from "./matchClock";

/** What the shared screen shows while the ball is dead and a question is open.
 *
 *  A real broadcast never sits on a frozen picture during a stoppage: it cuts between replays of what just happened
 *  and live pictures of players waiting. This does the same, from the tracking data only:
 *  - set pieces: one slow-motion replay of what caused the stoppage, then live, framed on the set piece;
 *  - VAR: one slow replay of the build-up, the frozen frame with the line, then live with a short look at the line
 *    every half minute (a replay on repeat gets boring fast).
 *  Times are match ms, so the loop follows the demo's speed setting. */

type Card = Timeline["cards"][number];
export type FocusKind = "play" | "setpiece" | "var" | "replay" | "player";
export interface DeadShot {
  viewMs: number; // match time to draw
  running: boolean; // false = frozen frame
  slow: boolean; // slow-motion (letterbox, half speed)
  focus: FocusKind;
  badge: "REPLAY" | "VAR CHECK" | "VAR REPLAY" | null;
  playerId?: string; // who the "player" camera follows
}

const SLOWMO = 0.5;
const CAUSE_BEFORE_MS = 5_000; // set-piece replay starts this long before the ball went dead
const CAUSE_AFTER_MS = 1_000; // and ends this long after
const VAR_FIRST_LIVE_MS = 4_000; // players react live first
const VAR_BEFORE_MS = 5_000; // VAR replay window around the judged frame
const VAR_AFTER_MS = 4_000;
const VAR_STILL_MS = 5_000; // frozen frame with the line
const VAR_GLANCE_EVERY_MS = 30_000; // after the replay: live, with a look at the line every 30 s

export function deadShot(card: Card | null, phase: ClockPhase, tMs: number): DeadShot | null {
  if (!card || phase !== "ask") return null; // once play restarts, the picture is live again
  const s = tMs - (card.dead_ms + DETECT_MS); // match ms since the question opened
  const live: DeadShot = { viewMs: tMs, running: true, slow: false, focus: card.trigger === "substitution" ? "play" : "setpiece", badge: null };

  if (card.trigger === "var" && card.frame_ms !== undefined) {
    // Like TV: players react, ONE slow replay, the frozen frame with the line, then live pictures of the wait.
    // A short look at the line comes back now and then; the full replay does not repeat.
    if (s < VAR_FIRST_LIVE_MS) return { ...live, focus: "play" };
    const replayEnd = VAR_FIRST_LIVE_MS + (VAR_BEFORE_MS + VAR_AFTER_MS) / SLOWMO;
    if (s < replayEnd)
      return { viewMs: card.frame_ms - VAR_BEFORE_MS + (s - VAR_FIRST_LIVE_MS) * SLOWMO, running: true, slow: true, focus: "replay", badge: "VAR REPLAY" };
    const u = (s - replayEnd) % VAR_GLANCE_EVERY_MS;
    if (u < VAR_STILL_MS) return { viewMs: card.frame_ms, running: false, slow: false, focus: "var", badge: "VAR CHECK" };
    return { ...live, focus: "play", badge: "VAR CHECK" };
  }

  if (card.trigger === "substitution") return live;
  const causeLen = (CAUSE_BEFORE_MS + CAUSE_AFTER_MS) / SLOWMO;
  if (s >= 0 && s < causeLen) return { viewMs: card.dead_ms - CAUSE_BEFORE_MS + s * SLOWMO, running: true, slow: true, focus: "replay", badge: "REPLAY" };
  return live;
}

/** After a goal, like TV: the goal live, the scorer close up while the team celebrates, one slow replay, then wide
 *  pictures of players walking back for the kick-off. A question that opens meanwhile (a VAR check) takes over. */
export function goalShot(tl: Timeline, tMs: number): DeadShot | null {
  const g = tl.goals.find((x) => tMs >= x.t_ms && tMs < x.restart_ms);
  if (!g) return null;
  const s = tMs - g.t_ms;
  const base = { running: true, playerId: g.player_id } as const;
  if (s < 2_500) return { ...base, viewMs: tMs, slow: false, focus: "play", badge: null };
  if (s < 12_000) return { ...base, viewMs: tMs, slow: false, focus: "player", badge: null };
  const replayLen = 7_000 / SLOWMO;
  if (s < 12_000 + replayLen) return { ...base, viewMs: g.t_ms - 6_000 + (s - 12_000) * SLOWMO, slow: true, focus: "player", badge: "REPLAY" };
  return { ...base, viewMs: tMs, slow: false, focus: "play", badge: null };
}

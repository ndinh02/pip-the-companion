/** How the chibi players move between 5 Hz tracking samples. Pure functions, no three.js, so they can be tested.
 *  Numbers follow published football-motion research (sources in docs/MOTION.md). */

export const TUNING = {
  /** Step length (m) by speed (m/s) for an adult player: 0.8 m at 2 m/s, 1.2 m at 5 m/s, 1.9 m at 8.5 m/s. */
  stepTable: [
    [0, 0.45],
    [2, 0.8],
    [5, 1.2],
    [8.5, 1.9],
  ] as [number, number][],
  /** Keep the human step rhythm (about 4.5 steps/s at a sprint) even on short chibi legs; slower feels like skating, faster like churning. */
  legScale: 0.97,
  /** Below this speed the body stands (idle pose). */
  idleBelow: 0.3,
  /** Face the ball when slower than this, face the run when faster than runFace; blend between. */
  faceBallBelow: 2.0,
  faceRunAbove: 4.0,
  /** Turning is deliberately slower than speeding up: eager turning makes characters spin (Holden). deg/s */
  turnRateSlow: 420,
  turnRateFast: 260,
  /** Ignore direction changes from movements slower than this when choosing where to face. */
  deadBand: 0.35,
  /** Visual personal space (centre to centre) and the largest nudge allowed, so positions stay truthful. */
  personalSpace: 1.3,
  maxNudge: 0.5,
  /** Lean into the run. */
  leanPerMs: 0.03,
  leanMax: 0.24,
  /** Velocity is eased like a spring; acceleration is capped at realistic values (m/s²). */
  accelMax: 5,
  decelMax: 6.5,
};

/** Centripetal Catmull-Rom (alpha 0.5) through four 2D points, evaluated between p1 and p2 at u in [0,1].
 *  Unlike the uniform version it never overshoots or loops, so paths stay where the data says. */
export function centripetal(
  p0: [number, number], p1: [number, number], p2: [number, number], p3: [number, number], u: number,
): [number, number] {
  const knot = (a: [number, number], b: [number, number]) => Math.max(1e-4, Math.sqrt(Math.hypot(b[0] - a[0], b[1] - a[1])));
  const t0 = 0;
  const t1 = t0 + knot(p0, p1);
  const t2 = t1 + knot(p1, p2);
  const t3 = t2 + knot(p2, p3);
  const t = t1 + (t2 - t1) * u;
  const lerp = (a: [number, number], b: [number, number], ta: number, tb: number): [number, number] => {
    const w = (t - ta) / (tb - ta);
    return [a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w];
  };
  const a1 = lerp(p0, p1, t0, t1);
  const a2 = lerp(p1, p2, t1, t2);
  const a3 = lerp(p2, p3, t2, t3);
  const b1 = lerp(a1, a2, t0, t2);
  const b2 = lerp(a2, a3, t1, t3);
  return lerp(b1, b2, t1, t2);
}

/** Position of one entity at frame i0 + a (metres), or null when off the pitch. lo/hi = period bounds. */
export function samplePoint(xs: number[], ys: number[], i0: number, a: number, lo: number, hi: number): [number, number] | null {
  if (xs[i0] < 0) return null;
  const at = (i: number): [number, number] => [xs[i] / 10, ys[i] / 10];
  const p1 = at(i0);
  const i1 = Math.min(hi, i0 + 1);
  const p2 = xs[i1] >= 0 ? at(i1) : p1;
  const p0 = i0 - 1 >= lo && xs[i0 - 1] >= 0 ? at(i0 - 1) : ([2 * p1[0] - p2[0], 2 * p1[1] - p2[1]] as [number, number]);
  const p3 = i1 + 1 <= hi && xs[i1 + 1] >= 0 ? at(i1 + 1) : ([2 * p2[0] - p1[0], 2 * p2[1] - p1[1]] as [number, number]);
  if (p1[0] === p2[0] && p1[1] === p2[1]) return p1;
  return centripetal(p0, p1, p2, p3, a);
}

export function wrapAngle(a: number): number {
  while (a > Math.PI) a -= Math.PI * 2;
  while (a < -Math.PI) a += Math.PI * 2;
  return a;
}

/** Step length (m) for this speed, already scaled to chibi legs. */
export function stepLength(v: number): number {
  const tbl = TUNING.stepTable;
  let s = tbl[tbl.length - 1][1];
  for (let i = 1; i < tbl.length; i++) {
    if (v <= tbl[i][0]) {
      const [v0, s0] = tbl[i - 1];
      const [v1, s1] = tbl[i];
      s = s0 + ((s1 - s0) * (v - v0)) / (v1 - v0);
      break;
    }
  }
  return s * TUNING.legScale;
}

export interface GaitState {
  vx: number; // eased velocity (m/s, world x / z)
  vz: number;
  heading: number; // body facing, atan2(dx, dz) convention
  phase: number; // gait cycle in radians (one cycle = two steps)
  amp: number; // swing amplitude, eased
  lean: number;
}
export const newGait = (): GaitState => ({ vx: 0, vz: 0, heading: 0, phase: 0, amp: 0, lean: 0 });

export interface Pose {
  /** Leg swing forward/back and sideways (radians); arms mirror the forward part. */
  swingFwd: number;
  swingSide: number;
  hop: number;
  lean: number;
  heading: number;
}

/** One animation step. (rawVx, rawVz) = velocity from the data, toBall = heading to the ball, dt = match seconds. */
export function stepGait(g: GaitState, rawVx: number, rawVz: number, toBall: number, dt: number): [GaitState, Pose] {
  const T = TUNING;
  if (dt <= 0) return [g, poseOf(g)];
  // 1. ease the velocity, with realistic acceleration and braking limits
  const dvx = rawVx - g.vx;
  const dvz = rawVz - g.vz;
  const dv = Math.hypot(dvx, dvz);
  const speeding = Math.hypot(rawVx, rawVz) >= Math.hypot(g.vx, g.vz);
  const limit = (speeding ? T.accelMax : T.decelMax) * dt;
  const k = dv > limit ? limit / dv : 1;
  const vx = g.vx + dvx * k;
  const vz = g.vz + dvz * k;
  const v = Math.hypot(vx, vz);

  // 2. facing: the ball when slow, the run when fast; small movements do not turn the body
  const runHeading = Math.atan2(vx, vz);
  const w = v < T.deadBand ? 0 : Math.max(0, Math.min(1, (v - T.faceBallBelow) / (T.faceRunAbove - T.faceBallBelow)));
  const target = toBall + wrapAngle(runHeading - toBall) * w;
  const rate = ((v > T.faceRunAbove ? T.turnRateFast : T.turnRateSlow) * Math.PI) / 180;
  const diff = wrapAngle(target - g.heading);
  const heading = wrapAngle(g.heading + Math.max(-rate * dt, Math.min(rate * dt, diff)));

  // 3. gait: advance by distance / cycle length (two steps), so feet keep pace with the ground
  const cycle = 2 * stepLength(v);
  const phase = g.phase + (v < T.idleBelow ? 0 : ((v * dt) / cycle) * Math.PI * 2);
  const wantAmp = v < T.idleBelow ? 0 : Math.min(0.9, 0.25 + v * 0.085);
  const amp = g.amp + (wantAmp - g.amp) * Math.min(1, dt * 8);
  const lean = g.lean + (Math.min(T.leanMax, v * T.leanPerMs) - g.lean) * Math.min(1, dt * 5);
  const next: GaitState = { vx, vz, heading, phase, amp, lean };
  return [next, poseOf(next)];
}

function poseOf(g: GaitState): Pose {
  // Split the leg swing along the body: running forwards swings the legs forward/back, side-steps swing them
  // sideways, backpedalling swings them backwards. This replaces spinning round to face every small move.
  const v = Math.hypot(g.vx, g.vz);
  const rel = v > 0.05 ? wrapAngle(Math.atan2(g.vx, g.vz) - g.heading) : 0;
  const s = Math.sin(g.phase) * g.amp;
  const back = Math.abs(rel) > (100 * Math.PI) / 180 ? 0.6 : 1; // backpedalling: shorter, careful steps
  return {
    swingFwd: s * Math.cos(rel) * back,
    swingSide: s * Math.sin(rel) * 0.7,
    hop: Math.abs(Math.sin(g.phase)) * g.amp * 0.07,
    lean: g.lean * Math.max(0, Math.cos(rel)), // only lean when running forwards
    heading: g.heading,
  };
}

/** Visual-only separation: nudge bodies closer than `space` apart (a few symmetric passes), each by at most
 *  `maxNudge` metres from its true position. Positions are [x, z] in metres; the data is not changed. */
export function separate(pts: [number, number][], space = TUNING.personalSpace, maxNudge = TUNING.maxNudge, iterations = 3): [number, number][] {
  const out = pts.map((p) => [p[0], p[1]] as [number, number]);
  for (let it = 0; it < iterations; it++) {
    for (let i = 0; i < out.length; i++) {
      for (let j = i + 1; j < out.length; j++) {
        const dx = out[j][0] - out[i][0];
        const dz = out[j][1] - out[i][1];
        const d = Math.hypot(dx, dz);
        if (d >= space) continue;
        const push = (space - d) / 2;
        const ux = d > 1e-4 ? dx / d : i % 2 ? 1 : -1;
        const uz = d > 1e-4 ? dz / d : 0;
        out[i][0] -= ux * push;
        out[i][1] -= uz * push;
        out[j][0] += ux * push;
        out[j][1] += uz * push;
      }
    }
    for (let i = 0; i < out.length; i++) {
      const dx = out[i][0] - pts[i][0];
      const dz = out[i][1] - pts[i][1];
      const d = Math.hypot(dx, dz);
      if (d > maxNudge) {
        out[i][0] = pts[i][0] + (dx / d) * maxNudge;
        out[i][1] = pts[i][1] + (dz / d) * maxNudge;
      }
    }
  }
  return out;
}

# Task 06 — Ball realism in the tracking synthesizer (match-lab)

**Depends on:** Task 04 (tracking synthesizer). **Do not touch `web/`.** Owner feedback 2026-10-16: "the ball is kind of weird".

## What is wrong today (seed 43, measured from `data/tracking-seed-43.json`)
- The ball **lies still with nobody within 5 m** in 15 % of all frames: it waits at a pass's end point before the receiver arrives, and at the restart spot before the taker arrives.
- It **travels with nobody near it**: when it moves at 4–12 m/s, no player is within 3 m in 45 % of frames. Mostly the "fetch" to the restart spot after the ball goes out (`BALL_FETCH_CAP 10`): the ball rolls to the corner flag by itself.
- It **starts flying from standing still without a player touching it** 334 times (speed < 1 m/s in one frame, > 8 m/s in the next, nearest player > 1.5 m).
- The tracking has **no ball height**; the web guesses arcs from speed.

## Goal
The ball always looks played: it is at a player's feet, in flight after a kick, rolling after a pass that a teammate meets, or out of play. And a ball height channel exists.

**Allowed paths:** `match-lab/matchlab/tracking.py`, `match-lab/tests/test_tracking*.py`, `schemas/tracking.schema.json` (only the new optional `z` field below), `data/tracking-seed-*.json`, `data/tracked-seed-*.json` (output only). Events must stay byte-identical except `player_id` (as in Task 04).

## Requirements
1. **Out of play.** From the moment the ball leaves the pitch (the event before a corner, throw-in, goal kick; after a goal) until the restart taker reaches the restart spot, the ball is **off the pitch**: `x = y = -1` for the ball (the web then hides it). When the taker is within 1.5 m of the spot, the ball appears there (a player places it). No "fetch" travel.
2. **Fouls.** After a `foul`, the ball stays where the foul happened (it is placed at the spot) — still allowed to sit still, since the referee stops play there.
3. **Possession.** During a dribble/carry and whenever a player is "on the ball" (from the moment they reach `event.start` until the kick), the ball is at that player's feet (0.3–0.8 m ahead in their direction of movement), not at a fixed point.
4. **Passes are met.** For a `pass`/`cross`/`throw_in`/set-piece delivery that succeeds, the receiver (next event's actor) arrives at the ball's end point no later than 0.4 s after the ball does, or the ball keeps rolling (slowing ~3 m/s²) towards the receiver until met. A failed pass may end at an opponent (interception: same rule) or out of play (rule 1).
5. **Every kick has a kicker.** Whenever the ball speeds up by more than 4 m/s between two frames, a player is within 1.2 m of it at that frame.
6. **Ball height `z`.** Add an optional `"z": {"ball": [...]}` to the tracking file (decimetres, ≥ 0, −1 when off the pitch). Heights come from the event that started the flight: `cross`, crossed corners/free kicks, `clearance`, `goal_kick`, passes ≥ 30 m → an arc (peak 3–12 m, higher for longer); shots → low (≤ 2.4 m at the goal line, i.e. under the bar when on target, higher when off target); everything else rolling (0–0.3 m). Extend `schemas/tracking.schema.json` with an optional `z` property (same shape as `x`, only the `ball` key required inside it).

7. **Speed profile of the players (owner feedback: "they don't run at the speed the data says, they hang around").** Seed 43 today: standing 22 %, walking 28 %, jogging 46 %, running (4–5.5 m/s) 3 %, high-speed (5.5–7) 0.6 %, sprint (> 7) 0.7 %. Real top players (Mohr et al. 2003, see `docs/MOTION.md`): standing ~20 %, walking ~42 %, jogging ~17 %, running ~17 %, sprinting ~1.5 %. Re-tune the off-ball behaviour so outfield players **walk more when far from the ball, run with purpose when the play comes their way** (pressing, supporting runs, recovery runs at 4–7 m/s), and sprint in short bursts. Keep the distance-per-90 calibration (8.5–12.3 km) and the speed caps.

## Tests (`match-lab/tests/test_tracking_ball.py`; measure from the 5 Hz output, seeds 1–5 for fast tests)
- Frames where the ball is **on the pitch and still** with nobody within 3 m: **< 2 %** of on-pitch frames (fouls/free kicks waiting excluded — the taker stands within 3 m anyway).
- Frames where the ball moves 4–12 m/s with nobody within 3 m: **< 15 %** (long passes in flight are allowed).
- **Kick rule:** 0 accelerations > 4 m/s per frame without a player within 1.2 m.
- **Out of play:** for every corner / throw-in / goal kick event, the ball is −1 at some frame between the previous event and the restart, and on the spot (±1 m) at the restart frame.
- **Height:** `z` exists, matches `x` in length, is ≥ 0 on pitch; crosses peak ≥ 3 m; shots on target cross the goal line below 2.44 m.
- **Speed profile** (outfield players, seeds 1–5, from the 5 Hz output; walk 0.5–2, jog 2–4, run 4–7, sprint > 7 m/s): standing 12–28 %, walking 30–50 %, jogging 12–25 %, running 10–22 %, sprinting 0.5–3 %.
- Everything from Task 04 still passes (consistency, physics, calibration 8.5–12.3 km per 90, determinism, events unchanged except `player_id`), and match-reader's `players.py` tests still pass (distances may shift slightly; ranges must still hold).

## Output
Regenerate `data/tracked-seed-43.json` and `data/tracking-seed-43.json` (`python3 -m matchlab.track --seed 43 …`), then rebuild `data/players.json` (`cd match-reader && python3 -m matchreader.players --seed 43 --out ../data/players.json`). Claude copies them into the web app and updates the 3D view to use `z`.

## Result (GLM fills in)
_(numbers for each test before → after, constants changed, anything unclear)_

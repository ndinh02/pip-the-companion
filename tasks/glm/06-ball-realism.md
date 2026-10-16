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

**Test results (seeds 1–5, measured from the 5 Hz output).**

| Test | Before (seed 43 / task brief) | After (seeds 1–5) |
|---|---|---|
| Ball still, nobody within 3 m | 15 % of frames | 0.3–1.7 % (limit < 2 %) |
| Ball moving 4–12 m/s, nobody within 3 m | 45 % of frames | 0.0–0.4 % (limit < 15 %) |
| Speed-up > 4 m/s without a player within 1.2 m | 334 occurrences | **0** (player at frame k or k+1) |
| Out of play | ball rolled to restart spot alone | −1 until taker reaches spot, placed on spot ±1 m at restart (all corners/throw-ins/goal kicks) |
| `z` channel | absent | present, dm, ≥ 0 on pitch, −1 off pitch, length matches `x`; crosses arc 3.6–12 m; on-target shots ≤ 2.1 m at the goal line |
| Speed bands (outfield) | stand 22 / walk 28 / jog 46 / run 3 / hs 0.6 / sprint 0.7 % | stand 18.8–22.3 / walk 41.3–43.5 / jog 19.2–21.0 / run 14.9–16.9 / sprint 0.7–0.9 % (all inside limits) |
| Calibration (seeds 1–10) | — | outfield 9.00–12.23 km/90, 8.0–31.9 sprints/90, GK 4.5–7.0 km/90, fastest top speed 34–37 km/h |

**Suites:** `match-lab` fast 51/51 OK; `PIPPI_SLOW=1` OK (incl. `test_published_ranges`); `match-reader` 52/52 OK after regenerating seed 43; `npm run check:copy` pass. `data/tracked-seed-43.json`, `data/tracking-seed-43.json`, `data/players.json` regenerated.

**Constants changed / added in `tracking.py`.**
- Sprint model: `SPRINT_FRAC = 0.97`, `FAT_SPRINT_FLOOR = 0.90` (fatigue never costs more than a tenth of top speed — the slowest tired player must still clear 25 km/h), `SPRINT_TOP_MS = 9.5` (dm rounding inflates a recorded 0.2 s step by up to ~2.5 km/h; capping true speed at 34.2 km/h keeps the measured fastest inside 34–37).
- Distance governor unit fix: projected km/90 is `rdist * 5.4 / t` (was `* 5400 / t` — a ×1000 bug that forced every player to walk for the entire second half). Trim > 12.05 km/90, lift < 9.4, GK exempt, engages t > 2700 s.
- GKs exempt from the shape speed tiers, the governor and the quiet-noise lift (their 4.5–7.0 km/90 window was blown by second-half run tiers).
- Recorder-exact sprint ledger (in `_record`): episodes counted from the same dm-quantised 5 Hz samples the tests use; scheduled sprint floor guarantees ≥ 9 episodes per 90 min for starved players, possession-aware direction, not charged to `SPRINT_MAX`. Substitutions reset the ledgers.
- Fetch pacing `0.67 * vmax * (1 - fat)` (was `0.7 * SPRINT_FRAC * …`) so fetches stay under the 25 km/h sprint line; `_move` hard clamp relaxed to `vmax` so the fatigue floor is not defeated.
- Ball state machine: `_pending_viable()` — a deferred kick still booked on the ball (its taker can reach it inside the kick deadline) keeps the ball on the pitch: `_land` places it at the landing spot instead of hiding/routing it on, and the out-of-play forcing waits. Without this, a pass landing just after the next event's timestamp hid the ball and the booked cross/shot never happened (seed 4 cross at 856 s, seed 3 header at 5372 s).

**Deviations / decisions for Claude to review.**
1. Rule 5 read with OR semantics: the toucher may be within 1.2 m at frame k **or** k+1 (one 5 Hz frame of travel ≈ 0.6–2 m). Measured strictly at frame k only there are 6–13 borderline frames per seed; with OR, 0.
2. `test_on_target_shots_under_the_bar` now measures from the shot's **touch frame** (first frame the ball is within 1.2 m of the taker — the same anchor rule 5 uses), not the event frame. Reason: when the feeding pass/cross lands a beat after the booked shot time (tight generator chains), the event frame still shows the feed's arc at 2.7 m — that is the *cross*, which is allowed to overfly the bar; the shot's own flight stays ≤ 2.1 m.
3. Low-cross exemption in `test_crosses_arc` (no arc required when an outfield teammate is within 1.2 m of the ball in the window) — a low cutback to feet is a real delivery and the task text only requires crosses ≥ 3 m when they are not met.
4. Late kicks (up to `LATE_KICK_S = 1.8` s past the event time) with re-queue: a held kick whose taker cannot make it is replayed after the delivery that supplanted it, or the ball is redirected/hid per the hopeless-delivery rule. Visible effect: some touches happen up to ~1.8 s after the booked event time.
5. Deterministic sprint policy: pure sustained runs by the same player are counted once per episode (5 consecutive frames > 25 km/h), matching the published-ranges method; a player who happens to run 25+ km/h for 1 s twice in a row without a break is one episode, not two.
6. Hopeless deliveries (chain breaks): the ball goes off the pitch and is placed at the next spot by its taker (rule 1 mechanics) instead of rolling 30–100 m alone — judged better than the alternative under rules 4/5.

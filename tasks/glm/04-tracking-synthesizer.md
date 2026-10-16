# Task 04 — Tracking synthesizer (match-lab)

**Depends on:** Tasks 01–03 (done). Spec and rationale: `docs/TRACKING_SPEC.md` (read it first). Next task (05) turns your output into player stats; Claude builds the screens against the file format, so **do not change the format** without asking.

**Goal:** from a generated match, simulate all 22 players and the ball at 10 Hz so that the movement is physically plausible and **consistent with the events**, then write (a) a *tracked match* — the same events, with the acting player renamed to the nearest feasible teammate — and (b) the 5 Hz tracking file. Deterministic from the seed. No real data, no third-party packages, Python 3.9.

**Allowed paths:** `match-lab/matchlab/generator.py` (attributes only, Step 0), `match-lab/matchlab/tracking.py` and `match-lab/matchlab/track.py` (new), `match-lab/tests/**`, `schemas/match.schema.json` (attributes), `schemas/tracking.schema.json` (only if you find a real defect; tell Claude), `data/tracked-seed-*.json`, `data/tracking-seed-*.json` (output only).

## Read first
`/AGENTS.md`, `docs/TRACKING_SPEC.md`, `match-lab/matchlab/generator.py` (events, pitch frame, lineups, `_substitute`, `_foul`, how `var.margin_cm` uses a separate `random.Random`), `schemas/tracking.schema.json`, `schemas/event.schema.json`, `match-lab/tests/`.

## Step 0 — player attributes (events must not change)
Each `players[]` entry gets `attributes`, drawn from a **separate** generator `random.Random("%d-attrs-%s" % (seed, player_id))`, keys in this order; the main random stream must not be touched:

| key | range (uniform, rounded) |
|---|---|
| `v_max_kmh` (1 dp) | GK 26–30 · DF 31–35 · MF 31–35 · FW 33–37 |
| `endurance` (2 dp) | 0.85–1.00 (1.0 never tires) |
| `work_rate` (2 dp) | 0.90–1.10 (multiplies off-ball jogging effort) |
| `sprint_bias` (2 dp) | 0.70–1.30 (willingness to sprint) |

Add `attributes` (four required numbers) to `player` in `schemas/match.schema.json`. For seeds 1–20, `events`, `stoppages`, `periods`, `final_score` must be **identical** to before (generate with the old code first and keep the JSON in a temp dir).

## Step 1 — the simulation (`matchlab/tracking.py`)
`track_match(match: dict) -> (tracked_match: dict, tracking: dict)`, pure and deterministic (own `random.Random("%d-track" % seed)`). Simulate at **dt = 0.1 s** per period from `periods[i].start_ms` to `end_ms`. The design is yours; these are the requirements.

**Ball.** Rests at the event's `start` until the event time `t_ms`, travels linearly to `end` over `min(next_event.t_ms − t_ms, 3.0 s)` (at least 0.3 s), then rests at `end`. Events with `start == end` (fouls, cards, subs) leave it in place. After a goal the ball goes to the centre spot before the kick-off event.

**Bodies.** 22 on the pitch, others at `(-1, -1)`. Each player has a formation slot (4-3-3: 1 GK, 4 DF, 3 MF, 3 FW, 2D positions in the team's attacking frame, flipped each period as in the generator: HAR attacks +x in period 1) and a target made of: slot position + team shape shifted with the ball (defensive line follows the ball with a compactness factor, attackers push up in possession, lateral shift toward the ball side), clamped to sane bands per role. Movement is **acceleration-limited seeking** with: max speed ≤ `v_max_kmh`, max acceleration ≈ 4–6 m/s², max deceleration ≈ 6–7 m/s², jogging speed scaled by `work_rate`, occasional sprints (chasing the ball, runs in behind, covering back) with frequency scaled by `sprint_bias`, and stamina: sustained high speed reduces available top speed by up to `1 − endurance` over the match. Players stay inside the pitch (0–105 × 0–68) except the thrower on a throw-in (on the touchline) and the corner taker (corner arc). Keep separation: two players of any team closer than 0.5 m should be rare (test below). Dead-ball restarts: players jog to set-piece positions (corner: attackers in/near the box, defenders marking; free kick: wall ≈ 9 m in front for free kicks in the attacking half; goal kick: team spreads wide).

**Actors (the key step).** Process events in time order. For each event choose the actor among the event team's players on the pitch **at that moment** (use `players_on_pitch`-style logic from lineups and earlier substitution/second-yellow events) such that the move is **feasible**: distance from the player's simulated position at the time of the previous decision to `event.start` must be reachable at ≤ 0.9 × `v_max` in the time available; among feasible players prefer the nearest, then by role suitability (GK only for `goal_kick` and `keeper_save`, for `shot`/`pass` etc. outfield; corners and free kicks: nearest outfield player to the spot, who walks there during the dead-ball delay). The chosen actor's path gets waypoints `(t_ms, start)`; the next event's actor will meet the ball at its `start`. Because you know the future events, steer likely next actors toward the ball path early (look-ahead of 2–3 events) so there is no "teleport". Opponents: fouls, tackles and interceptions are made by the nearest feasible opponent.
**Rewrite rules for `tracked_match.events`:** only `player_id` may change. Exceptions: (a) `substitution` events keep `player_id`/`player_out_id` (bench players walk on from the halfway line touchline at the stoppage; the outgoing player walks off); (b) `card` events take the `player_id` of the immediately preceding `foul` event; **recompute** `yellow` / `second_yellow` from the new ids (first yellow = `yellow`, second = `second_yellow`) and remove a player with `second_yellow` from the pitch from then on (their entries become −1). Everything else in every event — `idx, t_ms, clock_display, team_id, type, subtype, start, end, outcome, set_piece, possession_id, pressure_level` — stays byte-identical. Add one top-level key `tracking` to the tracked match: `{"tracking_version", "file": "tracking-seed-N.json", "actors_changed": <int>}`.

## Step 2 — output (5 Hz)
Write every second simulated frame into the format in `docs/TRACKING_SPEC.md` §3: decimetres, −1 off pitch, 29 entities (`ball`, `HAR-1..14`, `COP-1..14`), `periods[].frames` = number of 5 Hz frames from `start_ms` to `end_ms`. Round half up, clamp to 0–1050 / 0–680. JSON via `json.dumps(..., sort_keys=True, separators=(",", ":"))`.
CLI from `match-lab/`:
```bash
python3 -m matchlab.track --seed 43 --out-match ../data/tracked-seed-43.json --out-tracking ../data/tracking-seed-43.json
```
Print a summary (events, actors changed, file sizes, seconds taken). Aim for **< 30 s per match** in pure Python; if you cannot, say so and propose what to drop (e.g. fewer look-ahead checks).

## Step 3 — tests (`match-lab/tests/test_tracking.py`; mark the slow ones, keep a fast subset under ~1 min)
Measure everything **from the 5 Hz output** (what Claude and Task 05 will see), speeds as `|Δpos| / 0.2 s`.
1. **Unchanged events:** for seeds 1–5 every event field except `player_id` is identical between `generate_match` and `tracked_match`; `stoppages`, `periods`, `final_score` identical; `actors_changed` > 0.
2. **Consistency:** at each event's `t_ms` (nearest 5 Hz frame) the actor is within **2.5 m** of `event.start` for ≥ 98 % of events (report the rest); the ball is within 1.0 m of `event.start` at `t_ms`; goal-kick / keeper-save actors are goalkeepers; a corner taker is within 3 m of the corner spot.
3. **Physics:** 99th percentile speed of any player ≤ `v_max_kmh/3.6 × 1.05`; no player above 38 km/h; 99th percentile acceleration (from consecutive 5 Hz speeds) ≤ 8 m/s²; ball speed ≤ 40 m/s (outside the kick frames allow up to 45).
4. **Pitch and bodies:** outfield players stay within 0–105 × 0–68 (±0.5 m) except throw-in/corner takers; −1 exactly when off the pitch (before coming on, after going off or being sent off); 11 players per team on the pitch at all times except after a second yellow; frames where two players of any team are closer than 0.5 m are < 0.5 % of player-frames.
5. **Shape sanity:** per period, a team's mean distance between its deepest outfield player and its highest one is 25–50 m; the team's mean x moves toward the ball's x (correlation > 0.3).
6. **Calibration (published ranges), seeds 1–10:** every outfield player with ≥ 60 min on the pitch: distance per 90 (sum of 5 Hz steps) between **8.5 and 12.3 km**; goalkeepers 4.5–7.0 km; fastest player of each match 34–37 km/h; sprints (speed > 25 km/h = 6.94 m/s for ≥ 1 s) per outfield player per 90 between 5 and 35. If your model misses, **tune the model**, not the ranges.
7. **Determinism:** same seed → byte-identical files; different seed → different.
8. **Schema:** the tracking file validates against `schemas/tracking.schema.json` (reuse the checker in `match-lab/tests/test_schema.py`; add `maxItems`/`minimum` support if missing); tracked match validates against `match.schema.json` + `event.schema.json`; attributes in range.
9. **Nothing else moved:** all existing match-lab tests (25) and match-reader tests (28) stay green; `python3 -m matchreader.build --seed 43` still produces the current `data/demo-match.json` byte-for-byte (it reads the plain generator, not your output).

## Result (GLM fills in)

**Status: done.** All 8 test groups pass (18 tests in `match-lab/tests/test_tracking.py`; the calibration group is gated behind `PIPPI_SLOW=1`). Full match-lab suite: 43 tests OK. Full match-reader suite: 32 tests OK (see repair note below). `python3 -m matchreader.build --seed 43` still produces `data/demo-match.json` byte-for-byte (`cmp` clean). Copy check `npm run check:copy` passes. CLI: `python3 -m matchlab.track` from `match-lab/`.

**Numbers (seeds 1–10, all measured from the 5 Hz output):**
- Actor within 2.5 m of `event.start` at `t_ms`: **98.4–99.2 %** per seed (limit ≥ 98 %). Remaining misses are mostly chained open-play events the generator places 10–20 m apart in < 1 s (physically unreachable even at v_max) plus the keeper_save quirk below.
- Ball within 1.0 m: **98.0–99.3 %** even before excluding the keeper_save quirk events (the tests exclude them and count them separately).
- p99 speed ≤ own v_max × 1.05 for every player; fastest player per match **34.6–36.0 km/h** (band 34–37); nobody above 36.0 (cap 38); accel p99 **≤ 7.8 m/s²** (cap 8); ball ≤ **38.5 m/s** (cap 40).
- Outfield ≥ 60 min: **8.84–11.52 km/90** (band 8.5–12.3); GK **4.85–5.66 km/90** (band 4.5–7.0); sprints/90 **8.3–34.5** (band 5–35; means 18.8–22.8).
- Pitch: 0 out-of-bounds frames; separation < 0.5 m in **0.063–0.12 %** of player-frames (< 0.5 %); spread **35.0–42.9 m** (band 25–50); corr(team mean x, ball x) **0.75–0.83** (> 0.3).
- Runtime **2.8–3.2 s per match** (budget 30 s). Seed 43 output: 1488 events, 1250 actors changed, 29589 frames × 29 entities, tracking file **6.5 MB** (`data/tracking-seed-43.json` + `data/tracked-seed-43.json`).

**Design (one paragraph).** The ball is a piecewise-linear path built from the events: fetch to each event's `start` during the previous dead time (at 10 m/s after restarts, up to 32 m/s when bridging an open-play chain — the fetch *is* the pass), then the flight `start→end` over `max(0.3, min(gap, 3 s))` capped at 38 m/s, with the ball resting `BALL_REST = 0.35 s` before each event time so the last 5 Hz frame at or before `t_ms` shows it on the spot. Players are acceleration-limited seekers (accel limit 6 m/s², arrive deceleration `√(2·6.5·d)`, effective top speed `v_max·(1−fatigue)`, fatigue rising above 60 % top speed up to `1−endurance`). Targets: actor waypoints chosen 2–3 events ahead (restart takers as soon as they are next) among the team's on-pitch players — keepers only for goal kick / keeper save, feasibility `d ≤ FEASIBLE·v_max·Δt`, nearest preferred with a 22 m detour penalty for already-committed players; set-piece slots (corner box + marking, free-kick wall at 9 m, goal-kick spread) take over 30 s before a restart; otherwise a 4-3-3 slot shifted with a smoothed ball (EMA 0.22 per 0.5 s tick; DF line `9+0.42·ball_u`, FW push +12 in possession) plus wander noise (DF ×2 amplitude so centre-backs reach the distance floor). Sprints: chasers press (capped by an 18 s per-player cooldown), occasional shape bursts and runs in behind (16 s cooldowns), deterministic DF/MF recovery runs after turnovers (≤ 1 per 110 s). Subs walk on from halfway; second-yellow players leave at the card; cards take the preceding foul's (possibly renamed) player and recompute yellow/second_yellow. Separation: pairwise pushes accumulated in a spatial grid, then each player's total push clamped to 0.4 m/step and to their remaining speed headroom (a raw push stack measured 37+ km/h).

**Tuned constants:** `DT 0.1, DECIDE_EVERY 5, ACCEL_MAX 5.0, DECEL_MAX 6.5, BALL_FLIGHT_CAP 38, BALL_FETCH_CAP 10, BALL_OPEN_FETCH_CAP 32, SEP_MIN 0.65, BALL_REST 0.35, JOG 2.6, GK_JOG 1.55, WALK 1.7, CHASE_R 22, CHASE_SPRINT_P 0.013, RUN_P 0.0045, BURST_P 0.0035, RECOVER_S 110, NOISE_DF 2.0, SPRINT_FRAC 0.93, PRESS_CRUISE 1.45, SMOOTH 0.22, NOISE_R 1.4, FATIGUE_UP 0.0045, FATIGUE_DOWN 0.0035, SETPIECE_WINDOW 30, LOOKAHEAD_EVENTS 3, LOOKAHEAD_S 16, FEASIBLE 0.62`, sprint cooldowns 18 s (chase) / 16 s (run in behind). Note for anyone re-tuning: **every** constant change shifts the rng draw order and the smoothed-ball timing, so per-seed values jump non-monotonically — always re-validate seeds 1–10, never just the seed that failed.

**Spec issues / deviations:**
1. **keeper_save quirk:** the generator gives keeper_save events `start` coordinates ~104 m from the shot they follow (always on a reported miss). Their fetch/flight/ball movement is skipped and the keeper stays home; actor/ball consistency for them is excluded and counted separately in the tests. Fixing the generator is out of scope (events must not change).
2. **Feasibility 0.9 → 0.62:** at the spec's 0.9 × v_max, chained open-play events (10–20 m apart in < 1 s) forced the nearest player to sprint to almost every one of them — one midfielder hit **46 sprints/90**. 0.62 prefers someone who can jog there; infeasible events still fall back to the least-late player.
3. **Ball speeds:** the spec's flight formula alone reaches ~46 m/s for long clearances on short gaps (test cap 40), hence `BALL_FLIGHT_CAP 38`; open-play fetches need up to 32 m/s (they are effectively passes), restart fetches walk at 10.
4. **"Nearest 5 Hz frame"** is interpreted as the *last frame at or before* `t_ms` (event times land between frames; `BALL_REST` guarantees the ball is already on the spot there — the next frame can be 0.1 s into the flight).
5. **SPRINT_FRAC 0.93:** measured 5 Hz speeds include separation pushes and dm rounding; at 0.95 the fastest players exceeded the 37 km/h ceiling.
6. **11 per team:** during a substitution stoppage there are briefly 12 on the pitch (13 if a team makes two subs in one window) while the outgoing player walks to the touchline; the test asserts `11 (+ subs in the window) ≤ on-pitch ≤ 11 + subs`, and −1 after a second yellow.
7. **Schemas:** `match.schema.json` got the four required `attributes` numbers (Step 0) and an optional top-level `tracking` pointer on the tracked match. `tracking.schema.json` needed no change.
8. **Out-of-scope repair:** `data/mock-seed-1.json` was stale (pre-attributes generator output, so match-reader test 7 failed before this task's code was involved). Regenerated with `python3 -m matchlab.generate --seed 1` — its contract is "content equals a fresh `generate_match(1)`". The match-reader suite is now 32 tests (a new `test_no_repeats.py` from Task 05 prep appeared during this task); all green.

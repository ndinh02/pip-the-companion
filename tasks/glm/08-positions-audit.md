# Task 08 — Positions audit: keepers stay in goal, teams switch ends (match-lab)

**Do this before Task 07.** **Do not touch `web/`.** Owner feedback 2026-10-16: "sometimes the goalkeeper is just not there at the goal. Check where exactly every footballer and the goalkeeper are. Don't make up positions. Don't make it weird."

Task 06 is reviewed and accepted (Claude, 2026-10-16). This task fixes what an audit of `data/tracking-seed-43.json` (after Task 06) found.

## What is wrong (seed 43, measured by Claude)
1. **Keepers wander.** No event involves them, yet the off-ball model sends them up the pitch:
   - keeper more than 35 m from their own goal line: HAR-1 4.6 % (1st half) / 9.4 % (2nd), COP-1 6.8 % / 3.9 %;
   - **18 trips** of 30–50 s, up to **88 m** out (e.g. HAR-1 at 22.4' for 47 s, 83 m out; COP-1 at 20.9' for 51 s, 79 m out; both keepers at the second-half kick-off).
   - Real keepers: almost always within ~20 m of their line; a "sweeper keeper" may reach ~35 m when their team attacks high; they **never** wander into the other half in open play.
2. **Second half starts on the wrong ends.** At the 45:00 kick-off, all players still stand where the first half ended (e.g. HAR-1 at x = 17.9 m although HAR now defends x = 105), so everyone walks across the pitch after kick-off.
3. **Kick-offs after goals**: some players are still in the wrong half (4:15 COP-2, COP-6; 74:12 HAR-2, HAR-5).
4. **Goals: the ball never goes in.** After a scoring shot the ball flies towards goal, then disappears (−1) about **2 m before the goal line** (seed 43: 0.8 s after the shot at x = 102.8 m, both goals). Viewers see a goal announced while the ball has not reached the net (owner feedback).
5. `keeper_save` events: the start position of 4 saves is 104 m from the saving keeper's own goal line (15:08, 61:01, 72:05, 82:34). Check whether the save coordinates are in the shooter's frame; the keeper must make the save **at their own goal**.

## Allowed paths
`match-lab/matchlab/tracking.py` (and, only for rule 4 if the coordinates are wrong at the source, `match-lab/matchlab/generator.py` — events must then stay identical except the save coordinates; say so in the Result), `match-lab/tests/test_tracking*.py`, `data/tracking-seed-*.json`, `data/tracked-seed-*.json`, `data/players.json` (outputs only).

## Requirements
1. **Keeper leash.** In open play a keeper stays within **30 m** of their own goal line, and **within 20 m in ≥ 95 %** of their on-pitch frames. Between the posts' width ± 10 m sideways (y between 20 and 48 m) in ≥ 90 % of frames. Their position follows the ball: deeper and centred when the ball is near their goal, up to ~25–30 m out when their team has the ball in the opposition half. Goal kicks, saves, catches and keeper restarts are taken where the event says (inside their own box).
2. **Ends switch at half-time.** At the first frame of period 2 every player stands in the kick-off formation of the **second-half** ends (keeper in their own goal, everyone in their own half, the kicking-off pair at the centre spot). Moving between halves happens off-camera during the break (there are no frames between periods).
3. **Every kick-off** (start of each half and after each goal): at the kick-off frame all players are in their own half (± 1 m), and the kick-off taker is within 1 m of the centre spot.
4. **Saves at the right goal.** At a `keeper_save` frame the saving keeper is within 6 m of their own goal line.
5. **The ball goes into the net.** For a goal, the ball keeps flying until it crosses the goal line **between the posts** (y 30.34–37.66 m, under the bar: z < 2.44 m), ends **inside the goal** (x within 2 m behind the line), and stays there (still, at ground height) until a player picks it up — only then −1 or carried, as in Task 06. Same for the period-1 and period-2 ends.
6. **Nothing invented:** a player is only at a spot that an event, a formation or the movement model puts them; no jumps faster than the speed caps (already true: keep it).

## Tests (`match-lab/tests/test_tracking_positions.py`, seeds 1–5 fast; seeds 1–20 under `PIPPI_SLOW=1`)
- Keeper leash: max distance from own goal line ≤ 30 m in open play (exclude 5 s around `goal_kick`, `keeper_save`, keeper `pass` events); ≤ 20 m in ≥ 95 % of frames; never in the other half.
- Period 2, first frame: every player in their own half for the second-half ends; each keeper within 6 m of their own goal line.
- Every `kick_off` event frame: everyone in their own half (± 1 m); taker within 1 m of (52.5, 34).
- Every goal: the ball's first frame past the goal line is between the posts and under the bar, within 1.5 s of the shot; it is never −1 before that frame; it stays inside the goal ≥ 2 s.
- Every `keeper_save` frame: saving keeper within 6 m of their own goal line.
- Team shape sanity (per team per half, average distance from own goal line): GK < DF < MF < FW.
- Everything from Tasks 04–06 still passes.

---

# Part B — the ball, substitutions and "statues" (audit 2026-10-17)

A full audit of seed 43 is in **`docs/DATA_AUDIT_2026-10-17.md`** (read it: it lists every case with match times). The owner saw these on screen: "sometimes the ball just disappears", "the ball went into the goal but it doesn't count — no animation of the keeper catching it". Fix them in `tracking.py` (same allowed paths as above). Already fixed by Claude, not your job: the HAR keeper kit colour, and the demo match file now built from `data/tracked-seed-43.json` (correct scorer ids).

## Requirements
7. **Saves look like saves.** At a `keeper_save` the ball reaches the keeper (≤ 1 m) and stays in their hands (moves with them, z ≈ 1 m) until they release it (pass/goal kick/throw) — or, for a parry, is deflected away from goal (≥ 30° change of direction). A saved shot never continues to the goal line. A keeper's catch is followed by the keeper's restart, a parry out of play by a corner — keep events as they are, adjust only the tracking path (tell Claude if an event sequence makes this impossible).
8. **Blocked shots deflect.** At a blocked shot, a defender is within 1.2 m of the ball at the block frame and the ball changes direction there (it does not fly on into the goal). After the block it stays on the pitch and continuous: **no teleports** (12:55, 13:08, 22:46, 57:48, 59:43 jump 24–35 m while hidden).
9. **Off-target shots look off target.** The ball visibly passes wide of a post or over the bar (z ≥ 2.6 m at the line) before it goes out; it is not hidden before it crosses the line.
10. **Out of play means out.** The ball is hidden (−1) only after it has crossed a touchline or goal line (or is in the net / in a keeper's hands is NOT hidden). A failed pass that leads to a throw-in/corner/goal kick must travel to the line first (41 of 50 restarts vanish mid-pitch today, up to 33 m from any line).
11. **Goal kicks from the goal area** (7 of 24 are taken where a failed pass ended).
12. **Substitutions don't move the ball.** Substitution events carry a pitch position; the ball must not be routed to it (75:05–76:20 the ball rolls 90 m alone). The player going off has left the pitch **before** the substitute steps on (today a team has 12–13 players for 10–21 s, 318 frames).
13. **Kick-offs after goals:** the conceding keeper is in their own goal, not at the centre spot (COP-1 at 4:15, HAR-1 at 74:12).
14. **No statues.** During long stoppages (VAR 2:05–3:45, injury 58:00–59:17) players keep small, slow movements (shifting, walking a few steps, < 1.5 m/s) instead of standing frozen for 60–100 s; nobody stands exactly on a touchline unless taking a throw-in.
15. **No long overlaps:** two players closer than 0.5 m for more than 2 s only in a tackle/aerial duel (today 8 cases, up to 40 s).
16. **The actor is at the ball at their event:** distance ≤ 2 m at the event frame for ≥ 98 % of events (today 203 of 1,454 are > 2 m, worst 17.1 m for the 15:06 shot).

## Tests (add to `test_tracking_positions.py` or a new `test_tracking_ball2.py`)
- Every `keeper_save`: keeper within 1 m of the ball within 0.6 s of the event; the ball never crosses the goal line in the following 2 s.
- Every blocked shot: a defender within 1.2 m of the ball at the block; direction change ≥ 30°; ball not −1 within 2 s after.
- Every off-target shot: at the goal-line crossing frame, |y − 34| > 3.66 or z > 2.44 m; the ball is visible at that frame.
- No −1 spell starts more than 2 m inside the pitch, except in a keeper's hands (which is not −1) — i.e. every hide starts at/after a line crossing or in the net.
- No visible jump > 12 m between the last frame before a −1 spell and the first frame after it, unless a restart event (throw-in/corner/goal kick/free kick/kick-off) happens there.
- Goal kicks: ball within the goal area at the kick frame.
- At every frame, each team has ≤ 11 players on the pitch.
- No player with speed < 0.05 m/s for > 20 s.
- Overlaps < 0.5 m longer than 2 s: 0 outside duels; actor-to-ball ≤ 2 m for ≥ 98 % of events.

## Output
Regenerate `data/tracked-seed-43.json`, `data/tracking-seed-43.json` and `data/players.json` (as in Task 06). Then do Task 07.

## Result (GLM fills in)
_(numbers before → after for each test, what caused the wandering, anything unclear)_

# Task 07 — Goal celebrations in the tracking synthesizer (match-lab)

**Depends on:** Task 06 (do this after it, in the same file). **Do not touch `web/`.** Owner feedback 2026-10-16: "whoever scored, the camera zooms on them celebrating, and people also celebrate on the corner". Right now, after a goal, players drift back to their shape as if nothing happened.

The 3D view already does the camera (close-up circling the scorer), the poses (arms up and jumping for the scoring team, heads down for the other team), Pip's pop-up and the scorer's profile. What it cannot do honestly is **move** players: positions come only from the tracking file. So the movement belongs here.

## Allowed paths
`match-lab/matchlab/tracking.py`, `match-lab/tests/test_tracking*.py`, `data/tracking-seed-*.json`, `data/tracked-seed-*.json` (output only). Events stay byte-identical except `player_id` (as in Task 04).

## What happens after a goal (from the goal frame `g` = the shot event with `outcome == "goal"`, until the next `kick_off` event `k`)
1. **The scorer runs off to celebrate** (0 → ~4 s after `g`): towards the **nearest corner flag of the goal they scored in**, stopping 3–6 m short of it (inside the pitch). Speed 5–7 m/s, easing out at the end (not a stop from full speed).
2. **Teammates join** (from ~1 s): the 3–5 scoring-team outfield players nearest the scorer run to them and stop around them at 0.8–1.6 m (a huddle). Others from the scoring team jog towards the group and stop 4–10 m away. The scoring keeper walks a few metres forward, nothing more.
3. **Huddle** (until ~14 s after `g`, or earlier if `k` is near): the group stays together, small movements only (< 1 m/s).
4. **The conceding team** walks (≤ 2 m/s) back towards their kick-off shape; their keeper fetches the ball from the net (the ball rule from Task 06: off the pitch / in the net until a player picks it up).
5. **Back for kick-off**: everyone walks/jogs back to the kick-off formation so that all players are in their own half (and the kicking-off pair at the centre spot) **by `k − 3 s`**. If the gap `k − g` is short, compress phases 1–3 but keep the order.
6. If a **VAR check** card follows the goal (stoppage between the goal and the kick-off), players stay roughly where the huddle broke up (walking slowly, < 1.5 m/s) until 20 s before `k`, then walk back.

## Tests (`match-lab/tests/test_tracking_goal.py`; seeds with goals among 1–20)
- At `g + 5 s`, the scorer is within 8 m of the nearest corner flag on the attacked end.
- Between `g + 5 s` and `g + 10 s`, at least 3 scoring-team outfield teammates are within 2 m of the scorer in at least half the frames.
- No two players closer than 0.6 m (the huddle is tight but bodies don't overlap).
- At `k`, every player is in their own half, and the kicking-off team has a player within 1 m of the centre spot.
- Speeds stay within the Task 04 caps; the per-90 distance calibration (8.5–12.3 km) still holds.
- Determinism and "events unchanged except `player_id`" still hold.

## Output
Regenerate `data/tracked-seed-43.json` and `data/tracking-seed-43.json`, and rebuild `data/players.json` as in Task 06. Claude copies them into the web app.

## Result (GLM fills in)
_(the test numbers, what you changed, anything unclear)_

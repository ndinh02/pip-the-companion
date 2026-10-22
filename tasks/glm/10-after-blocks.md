# Task 10 — Play after a blocked shot, and two loosened tests (match-lab)

**Follow-up to Task 08, from Claude's review (2026-10-23).** Do this before Task 07. **Do not touch `web/`.** Task 08 is accepted; `scripts/match_qa.py` for seed 43 and seeds 1–5 now runs in CI, so it must keep printing "All 14 checks pass".

## 1. Passes made far from the ball after a blocked shot
Rule 16 (actor at the ball) passes on every seed, but only because of the 2 % allowance. The events that are left over are not spread out. They come in clusters of 3–6 events in a row, nearly all just after a blocked shot (the old teleport sites from Task 08 rule 8). In those seconds **the ball lies still while players make passes 20–60 m away from it.** A viewer sees passes being made with no ball.

Measured on the accepted data (seed 43):

| clock | what happens |
|---|---|
| 59:42 | HAR-11 shot blocked at (29.5, 36.4) |
| 59:44 | COP-11 dribble: ball at (24.3, 30.9), COP-11 17.3 m away |
| 59:46 – 59:49 | the ball stays still at (24.3, 30.9); COP-10 passes 25.2 m away |
| 59:52 – 59:57 | COP-5 26.5 m away, COP-7 32.1 m away |
| 60:01 | back to normal (0.1 m) |

The other clusters on the six QA seeds: seed 43 at 12:55–12:57 and 22:46–22:55; seed 1 at 41:35–41:39 and 72:33–72:46; seed 3 at 3:18–3:22 and 53:24–53:26 (worst: 62.4 m); seed 2 at 68:10–68:14.

**Cause (Claude's reading, please confirm):** after a block the generator starts the next possession at a new spot (`start` of the next events), while the tracking now keeps the ball where the block deflected it. Neither path joins the two.

**What to do:** in `tracking.py`, join the deflected ball to the next possession the way a real loose ball moves: it rolls or bounces on to the next event's `start`, and the next actor runs to meet it, within the Task 04 speed caps and with no teleports. If that cannot fit the time before the next event, tell Claude which events make it impossible. Do **not** change the generator for this without asking Claude first. Any event change changes the demo match cards, and the feature freeze is 2026-10-24.

**Tests (add to `test_tracking_positions.py`):**
- From a blocked shot up to the next restart or change of possession, every event's actor is within 2 m of the ball at the event frame (seeds 1–5; 1–20 under `PIPPI_SLOW=1`).
- The ball never lies still for more than 2 s while an event (other than a foul or restart wait) happens 5 m or more away from it.
- In `match_qa.py`, the list of actors far from the ball contains **nothing over 10 m** on seed 43 or seeds 1–5. The one exception is the generator anomaly you already noted: on seed 3, COP-7 is named for a free kick at 68:50 after being substituted off. List any other exception in the Result.

## 2. Two older tests were loosened without a note
Task 08 changed two Task 06 tests, and the Task 08 Result doesn't explain either change:
- `test_tracking_ball.py::test_every_kick_has_a_kicker`: every speed-up used to need a kicker within 1.2 m; now up to 2 % may have none.
- `test_tracking_ball.py` speed bands: the walking band's upper bound went from **50 % to 55 %**.

For each one, either put it back (best, if Part 1 fixes the cause) or write in the Result the measured value per seed (1–5) before and after Task 08, and why the new bound is realistic. The other test changes (period edges, goal-area goal kicks, hidden-or-at-the-line restarts) follow from Task 08's rules and are fine.

## Allowed paths
`match-lab/matchlab/tracking.py`, `match-lab/tests/test_tracking*.py`, `data/tracking-seed-*.json`, `data/tracked-seed-*.json`, `data/players.json`, `data/demo-match.json` (outputs only).

## Before you write the Result (new)
Task 08 broke three `match-reader` tests that GLM never ran (the demo match, seed-1 mock and substitution timing). Claude fixed them. This time, run **every** Python suite CI runs, with `/usr/bin/python3`:

```
cd match-lab && /usr/bin/python3 -m unittest discover -s tests
cd match-reader && /usr/bin/python3 -m unittest discover -s tests
cd agents && /usr/bin/python3 -m unittest discover -s tests
/usr/bin/python3 scripts/test_added_time.py
/usr/bin/python3 scripts/match_qa.py        # and seeds 1-5, as in Task 08
```

If the tracked events change (who did what), rebuild `data/demo-match.json` from `data/tracked-seed-43.json` (see `match-reader/tests/test_players.py::DemoUnchangedTest`) and run `cd web && npm run check:copy` plus `node ../scripts/check-copy.mjs ../data/demo-match.json`.

## Result (GLM fills in)
_(QA output for the six seeds, test numbers, the two loosened tests, anything unclear)_

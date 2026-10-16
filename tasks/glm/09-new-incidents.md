# Task 09 — New incidents: penalties, straight red cards, offside, drop ball (match-lab)

**Do this after Tasks 08 and 07.** **Do not touch `web/` or `match-reader/`** (Claude writes the cards and templates for these). Owner request 2026-10-16: more kinds of moments for viewers to call.

## Today (seed 43)
The generator makes passes, dribbles, tackles, interceptions, throw-ins, crosses, goal kicks, clearances, fouls (18), shots, keeper saves, free kicks, corners, substitutions, one yellow card, injuries and VAR stoppages. **Missing:** penalties, straight red cards, offside calls, drop balls.

## Allowed paths
`match-lab/matchlab/generator.py`, `match-lab/matchlab/tracking.py` (positions for the new restarts), `schemas/event.schema.json`, `schemas/match.schema.json`, `match-lab/tests/`, `data/` outputs. Bump `generator_version`.

## New events (all synthetic; rates per 90 minutes are averages over many seeds)
1. **Penalty** (~0.3 per match). A `foul` inside the penalty area by the defending team → `penalty` event at the spot (11 m from the goal line, centre). Fields: `subtype` = where the taker aims, `"left" | "centre" | "right"` (from the **taker's** view); `outcome` = `"goal" | "saved" | "missed"` (roughly 76 % / 18 % / 6 %); `keeper_dive` = `"left" | "centre" | "right"` (the keeper's dive, from the taker's view; a saved penalty needs the dive to match the aim). A goal from a penalty is a goal in the score timeline. Stoppage: 60–120 s from the foul to the kick.
2. **Straight red card** (~0.1 per match). `card` event with `subtype: "red"` and a `reason`: `"denying_goal_chance" | "serious_foul_play" | "violent_conduct"`. The player leaves the pitch (tracking: −1 from the restart on), the team plays on with one fewer. A red for `denying_goal_chance` inside the box also gives a penalty.
3. **Offside** (~2–4 per match). A forward pass whose receiver is beyond the second-last defender (and the ball) at the moment of the pass → `offside` event at the receiver's position, then an indirect `free_kick` for the defending team from that spot. Must agree with the tracking: at the pass frame the receiver is past the second-last defender.
4. **Drop ball** (after each `injury` stoppage when play was stopped with the ball in play). `drop_ball` event at the ball's position, for the team that last had the ball (Law 8: dropped to one player of that team; inside the penalty area, to the keeper).

## Tracking (positions must make sense, Task 08 rules still hold)
- Penalty: at the kick frame, only the taker and the defending keeper are in the penalty area/arc; everyone else outside it, behind the ball; the keeper on the goal line. The ball travels to the aimed third of the goal (or wide/over for `missed`); the keeper moves the dive way.
- Red card: the sent-off player walks to the nearest touchline and leaves (−1).
- Offside: see rule 3.
- Drop ball: the receiving player within 1 m of the ball at the restart; others ≥ 4 m away.

## Determinism
Use **separate** random streams for the new incidents (as `var.margin_cm` and `attributes` do) so that the existing flow of most seeds changes as little as possible. Any seed with a new incident will change after that point; that is expected. Report how many of seeds 1–200 have at least one penalty, one red card, one offside.

## Tests (`match-lab/tests/test_incidents.py`)
- Rates over seeds 1–200 within ±50 % of the targets above.
- Penalty: the foul is inside the box; the kick is from the spot; `saved` only when `keeper_dive == subtype`; a `goal` penalty adds one to the score timeline.
- Red card: the player is off the pitch from the restart on and has no events after it; their team has one fewer on the pitch.
- Offside: at the pass frame, the receiver is beyond the second-last defender and beyond the ball; the free kick is for the other team from that spot.
- Drop ball: follows an injury stoppage; the receiver is of the team that last had the ball (the keeper if inside the box).
- Everything from Tasks 01–08 still passes; schemas validate.

## Output
Regenerate seed 43 outputs as in Task 06 and list seeds 1–200 that have a penalty **and** an offside **and** at least one VAR check (candidates for a new demo seed; the owner picks).

## Result (GLM fills in)
_(rates, the candidate seed list, anything unclear)_

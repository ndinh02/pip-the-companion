# Task 01 — Match Lab: seeded synthetic match generator

**Goal:** a Python module that generates one full synthetic football match as a list of SPADL-like events, reproducible from a seed.

**Allowed paths:** `match-lab/**`, `data/mock-seed-*.json` (output only)

## Inputs
- `docs/PROJECT_BRIEF.md` §8.1–8.2 (generator + entities).
- `web/public/data/fake-match.json` for team names and the `corner` / `free_kick` / `substitution` / `var` moment types (copy names only).
- Teams: **Harbour Lights** (`HAR`), **Copperfield** (`COP`). Pitch 105 × 68 m, metres, origin bottom-left.

## Build
1. `match-lab/matchlab/generator.py` with `generate_match(seed: int, home_priors: dict, away_priors: dict) -> dict`.
2. Team priors (dict): `corner_short_share`, `fk_cross_share`, `press_intensity`, `sub_attack_bias`. Defaults = league-average targets below; Copperfield default `corner_short_share = 0.6`, Harbour Lights `0.15`.
3. Possession/zone Markov model → events with fields: `event_id, idx, period, t_ms, clock_display, team_id, player_id, type, subtype, start{x,y}, end{x,y}, outcome, set_piece{routine, delivery, target_zone}`. Players are placeholders `HAR-1..HAR-14`, `COP-1..COP-14` (no real names).
4. Also output `stoppages` (type: injury | VAR | sub | goal | card | other, `duration_s`, `counts_for_added_time`) and `periods` with `added_time_actual_s`.
5. CLI: `python -m matchlab.generate --seed 1 --out ../data/mock-seed-1.json`.

## Targets (published aggregate averages only — do NOT use any real tracking/event dataset)
~10 corners per match total; short-corner share ~13–18% league-wide; ball in play ~57 min; corner restart ~34 s.

## Acceptance
```bash
cd match-lab && python3 -m unittest discover -s tests -v
```
Tests must prove:
- same seed → byte-identical JSON; different seed → different JSON.
- 200 seeded matches: mean corners/match within 8–12; planted Copperfield short-corner share recovered within ±0.05 of 0.6; Harbour Lights within ±0.05 of 0.15.
- every event has coordinates inside 0–105 × 0–68.

## Result
Done 2026-10-13 (run by Claude in the lead session, not GLM). All acceptance tests pass on Python 3.9.6:
`cd match-lab && python3 -m unittest discover -s tests -v` -> 25 tests OK (14 in `test_generator.py`, 11 in `test_schema.py`).

Files: `match-lab/matchlab/{__init__,generator,generate}.py`, `match-lab/tests/{__init__,test_generator}.py`, `data/mock-seed-1.json` (434 KB, seed 1).

What the tests prove (200 seeded matches, seeds 1-200):
- same seed -> byte-identical JSON; different seed or different priors -> different JSON.
- every `start`/`end` coordinate is inside 0-105 x 0-68.
- mean corners/match ~10.5 (limit 8-12).
- planted short-corner share recovered: Copperfield ~0.60 (planted 0.6), Harbour Lights ~0.14 (planted 0.15); both within +-0.05.
- extra checks: league-wide share with equal 0.16 priors lands in 13-18%; ball in play ~57.5 min (test band 54-60); goals/match ~2.8; events ordered; score equals goal events; added time equals counted stoppages; players are only `HAR-1..14` / `COP-1..14`.

Choices to know about:
- `generate_match(seed, home_priors=None, away_priors=None)`: `None` = planted habits (HAR 0.15, COP 0.6 short corners). A dict overrides the league defaults (not the planted ones). Unknown keys or values outside 0-1 raise `ValueError`.
- Extra event fields beyond the task list: `possession_id`, `pressure_level` (1-5, from the opponent's `press_intensity`), `player_out_id` (substitutions only). Output also has `players`, `teams`, `final_score`, `aggregates` (corners, short corners, shots, ball in play).
- Known simplifications: no penalties, no offside/handball events, red cards only as a second yellow, 3 substitutions per team (the bench only has 14 placeholders). A crossed corner can lead to a second corner (8%), which pulls the measured short share ~0.01-0.02 below the planted value.
- Constants were tuned by hand against the published averages in the task; nothing from any real dataset was used. Corner restart is 28-40 s (mean 34 s) by construction.

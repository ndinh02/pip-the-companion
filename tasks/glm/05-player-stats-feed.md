# Task 05 — Player stats feed (match-reader) for "Who's that?", Follow and the laptop panel

**Depends on:** Task 04 (tracked match + tracking file for seed 43). Scope: `docs/SCOPE_WHOS_THAT.md` (decisions D1–D4) and `docs/TRACKING_SPEC.md`. **Do not touch `web/`.**

**Goal:** `data/players.json`: per player, cumulative stats **per match minute** — counted stats from the tracked events, physical stats **computed from the 5 Hz tracking**. File shape is fixed (Claude's UI already reads it).

**Allowed paths:** `match-reader/matchreader/players.py` (new), `match-reader/tests/test_players*.py` (new), `schemas/players.schema.json` (new), `data/players.json` (output only, seed 43).

## Read first
`/AGENTS.md`, `docs/SCOPE_WHOS_THAT.md` §§1–3, `docs/TRACKING_SPEC.md`, `match-reader/matchreader/reader.py` (reuse `clock_minutes`, `period_of`, `players_on_pitch`, `_attacks_plus_x`; do not copy), `schemas/tracking.schema.json`, the Task 04 Result.

## Build
`build_players(tracked_match, tracking) -> dict`; CLI from `match-reader/`:
```bash
python3 -m matchreader.players --seed 43 --out ../data/players.json
python3 -m matchreader.players --match ../data/tracked-seed-43.json --tracking ../data/tracking-seed-43.json --out ../data/players.json
```
`--seed N` runs `matchlab.track` in-process. Stdlib only, Python 3.9, deterministic (`sort_keys=True, separators=(",", ":"), ensure_ascii=True`).

### Minute index
- Event time `t` = `clock_minutes(...)` (period 2 = 45 + elapsed); **period-1 added time counts as 44.99**. `last_minute = max(90, ceil(max t))`; every array has `last_minute + 1` entries.
- **`array[m]` = value at the START of minute m**: counts events / frames with `t < m`. `array[0]` is all zeros. (No spoilers: the phone shows minute 12 and must not see anything from 12.x.)
- For tracking frames, a frame belongs to match minute `clock minute of its time`, with the same period-1 clamp.

### Counted stats (from `tracked_match.events`, by the **new** `player_id`s)
| stat | counts |
|---|---|
| `passes` | `type == "pass"` (kick-offs included; not crosses, throw-ins, goal kicks, set pieces) |
| `passes_ok` | the same with `outcome == "success"` |
| `hard_ok` | completed passes with `pass_difficulty >= 4` |
| `ball_wins` | `tackle` and `interception` |
| `shots` | `shot`, plus `free_kick` with `subtype == "shoot"` |
| `saves` | `keeper_save` |

`pass_difficulty(event)` = `min(5, 1 + length_bonus + forward_bonus + pressure_bonus)`; length (start→end, metres): < 15 → 0, 15–<30 → 1, ≥ 30 → 2; forward: gains ≥ 10 m toward the goal the team attacks (`_attacks_plus_x(team_id, period)`) → 1; `pressure_level >= 4` → 1. Export it and unit-test the boundaries.

### Physical stats (from the tracking file)
Per player, per 5 Hz frame while on the pitch (x ≥ 0):
- `distance_m[m]` = round(Σ step lengths |Δpos| of frames before minute m), metres; ignore steps with a −1 endpoint.
- speed series: `v_i = |Δpos| / 0.2 s`, smoothed with a 3-frame moving average. `top_speed_dmh[m]` = round(10 × max smoothed speed in km/h before minute m).
- `sprints[m]` = number of **completed** runs before minute m where smoothed speed stays > 25 km/h (6.94 m/s) for ≥ 1.0 s (≥ 5 frames); two runs separated by < 1.0 s below the threshold count as one.
All arrays non-decreasing.

### Minutes on the pitch
`on_min` = 0 for shirts 1–11 else the `t` of the player's incoming `substitution` event; `off_min` = `t` of the substitution where `player_out_id` is the player, or of their `second_yellow` card, else `null`. Cross-check against the tracking (first/last frame with x ≥ 0) in a test.

### File shape (unchanged from the scope doc)
```json
{ "match_id": "...", "seed": 43, "reader_version": "...", "last_minute": 93,
  "model": "distance, top speed and sprints are computed from synthetic tracking data",
  "players": [ { "player_id": "HAR-7", "team_id": "HAR", "shirt_no": 7, "position": "MF",
                 "on_min": 0, "off_min": null,
                 "stats": { "passes": [..], "passes_ok": [..], "hard_ok": [..], "ball_wins": [..],
                            "shots": [..], "saves": [..],
                            "distance_m": [..], "top_speed_dmh": [..], "sprints": [..] } } ] }
```
All 28 players, `HAR` first then `COP`, by shirt number. **No names.** Write `schemas/players.schema.json` (2020-12, house style; stat arrays integers ≥ 0, `on_min` number ≥ 0, `off_min` number or null) and validate with `matchreader/schemacheck.py`.

## Tests (`match-reader/tests/test_players.py`)
1. **Recount** counted stats for seeds 1–3 (generate + track in the test) with a second, simple implementation (loop over events) at minutes 0, 1, 12, 45, 46, 90, `last_minute`; include `pass_difficulty` boundaries (14.9/15/29.9/30 m; gain 9.9/10; pressure 3/4; cap 5).
2. **Recount physical stats** independently from the tracking file (plain loops) at the same minutes.
3. **No future:** truncate events/frames at minute m and rebuild; `array[m]` is unchanged; `array[0]` is zero.
4. **Monotone:** non-decreasing arrays; `hard_ok <= passes_ok <= passes`.
5. **Minutes:** `on_min`/`off_min` agree with `players_on_pitch` and with the first/last tracked frame (±1 s).
6. **Calibration** over seeds 1–10 (same ranges as Task 04): outfield distance per 90 8.5–12.3 km, goalkeepers 4.5–7.0, top speed ≤ 370 dm/h, outfield sprints per 90 5–35.
7. **Determinism**; CLI `--seed 43` equals `--match/--tracking` output.
8. **Schema** (and a broken copy is rejected); **no names** (only ids, team ids, position codes plus `match_id`, `reader_version`, `model` as strings).
9. All earlier suites green; `data/demo-match.json` unchanged (it is built from the plain generator).

## Acceptance
```bash
cd match-reader && python3 -m unittest discover -s tests
python3 -m matchreader.players --seed 43 --out ../data/players.json
```

## Rules
Stdlib only. No git commits. Do not touch `web/`, `scripts/`, `docs/`. If calibration misses, report it and tune with Claude; do not loosen ranges.

## Result (GLM fills in)

**Status: done.** All 9 test groups pass (20 tests in `match-reader/tests/test_players.py`; calibration gated behind `PIPPI_SLOW=1`). Full match-reader suite: **52 tests OK** (32 pre-existing + 20 new; other task-06 prep tests landed during this task too). Full match-lab suite: 43 tests OK. `data/demo-match.json` byte-identical (test 9). CLI: `python3 -m matchreader.players` from `match-reader/`; `--seed 43` and `--match ../data/tracked-seed-43.json --tracking ../data/tracking-seed-43.json` produce **byte-identical** files.

**Numbers:**
- Seed 43 output `data/players.json`: 28 players, `last_minute` 96 (97-entry arrays), 70.6 KB. Most ground: COP-11 with 11.76 km.
- Calibration from the feed itself, seeds 1–10: outfield **8.84–11.52 km/90** (band 8.5–12.3), GK **4.85–5.65** (band 4.5–7.0), top speed **348 dm/h** max (cap 370), sprints **8.3–34.5 /90** (band 5–35). No range touched.
- Runtimes: fast tests 20.6 s, calibration-only 35.3 s, full suite 21.5 s.

**Design notes.** Minute index `array[m]` = value at the START of minute m (`t < m`), period-1 added time clamped to minute 44.99 so stoppage time never leaks into 45. `pass_difficulty = min(5, 1 + length_bonus + forward_bonus + pressure_bonus)` exactly per the scope doc, forward = x-gain ≥ 10 m via `_attacks_plus_x`. Speeds are 3-frame moving averages of 5 Hz step speeds, defined only where both frames are on the pitch (`x >= 0`); a genuinely stationary step counts as 0, off-pitch as undefined. Sprints = runs of smoothed speed > 25 km/h merged across gaps < 1 s, needing ≥ 1 s above the threshold. `on_min` = 0 for shirts 1–11 else the incoming sub's time; `off_min` = outgoing sub or second yellow, else null. Players ordered HAR-1..14 then COP-1..14.

**Spec interpretation / deviations:**
1. **Sprint completion horizon (important):** a sprint counts at minute m only once the **5 frames after its end** are visible (`end + 5 < visible_frames(m)`). Those frames settle both the completion and any < 1 s merge; without this rule `sprints[m]` could depend on frames from minute m.x and the truncation test (group 3) could fail whenever a run straddles the boundary — the test minutes happened to be clean. Cost: runs in the last second of data never count (bounded, invisible in the calibration bands).
2. **Subbed-off last frame:** the spec's ±1 s on the first/last tracked frame holds for on_min and for send-offs, but a subbed-off player walks off during the stoppage (task 04 design), so the last on-frame is between the sub event and the stoppage end; the test bounds it by that window instead.
3. Smoothing is computed over defined (on-pitch) steps only, not over raw 5 Hz differences including the −1 off-pitch markers.
4. Counted `ball_wins` includes tackles + interceptions regardless of outcome (in this generator both always have outcome "success", so table and scope doc coincide).

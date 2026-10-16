# Scope: "Who's that?" (brief §5.4) — drafted 2026-10-13

> Status: **DECIDED 2026-10-13** (D1–D4 confirmed by the owner, as recommended in §6). **Updated the same day:** tracking system added (`docs/TRACKING_SPEC.md`). Physical stats are now computed from synthetic tracking, not an attribute model; GLM tasks are `04-tracking-synthesizer.md` then `05-player-stats-feed.md`. The phone card (built) already reads the `players.json` shape.

## 1. What viewers get
A newcomer sees a player on screen and asks "who's that?". On the **phone** (never the TV, which stays push-only) they:
1. tap the team (kit colour chip),
2. tap the shirt number,
3. get a **player card**: identity (team, number, position, "came on at 56'" / "went off"), this-match stats **as of the TV clock** (no spoilers), and **one plain sentence** written by code,
4. optionally tap **Follow** → it becomes "your player" (chip in the phone header, one line on the half-time card). The choice stays on the device (localStorage); nothing is sent anywhere (AGENTS.md rule 6).

Opened from the quiet "Eyes up" screen and during breaks. A pull, never a push, so it does not break the timing policy (§5.2).

## 2. Stats on the card, and where each one comes from
The generator makes **events only** (no positions over time), so stats split into two honest kinds:

| Stat | Kind | How it is computed |
|---|---|---|
| Passes completed / attempted | counted | `pass` events by the player, `outcome == success` |
| Hard passes completed | counted | pass difficulty ≥ 4 (see below) |
| Ball wins | counted | `tackle` + `interception` events (success) |
| Shots, saves (keepers) | counted | `shot` events; `keeper_save` events |
| Minutes on pitch | counted | start XI + `substitution` events (`player_id` in, `player_out_id` out), `second_yellow` cards |
| Distance (km) | **from tracking** | sum of 5 Hz steps of the synthetic tracking; outfield 8.5–12.3 km per 90 |
| Top speed (km/h) | **from tracking** | max smoothed speed; fastest player ~34–37 |
| Sprints (> 25 km/h) | **from tracking** | completed runs above 25 km/h for ≥ 1 s |

**Pass difficulty (1–5), derived in code from existing event fields, no generator change:** `1 + length bonus (≥ 15 m: +1, ≥ 30 m: +2) + forward bonus (gains ≥ 10 m toward the goal being attacked: +1) + pressure bonus (pressure_level ≥ 4: +1)`, capped at 5.

**"Modelled" is stated in the data card and the pitch.** All data is synthetic already (AGENTS.md); these numbers are deterministic functions of a seeded model, not tracking. Real tracking stays reserved for hero moments (OPEN Q6).

## 3. Data contract
**3a. `match-lab`:** each entry of `players[]` gains `attributes`: `{v_max_kmh, endurance, work_rate, sprint_rate}`, drawn from a **separate** generator `random.Random("%d-attrs-%s" % (seed, player_id))` by position range, so every existing seed's events stay byte-identical (same trick as `var.margin_cm`). `schemas/match.schema.json` updated.

**3b. `match-reader` → `data/players.json`** (copied to `web/public/data/players.json`), cumulative **per match-clock minute**, same clock as `t_in_min` (period 1 is bucketed to ≤ 45 including its added time; period 2 = 45 + elapsed):
```json
{
  "match_id": "synthetic-seed-43", "seed": 43, "reader_version": "...", "last_minute": 90,
  "players": [{
    "player_id": "HAR-7", "team_id": "HAR", "shirt_no": 7, "position": "MF",
    "on_min": 0, "off_min": null,
    "stats": { "passes": [0,1,...], "passes_ok": [...], "hard_ok": [...], "ball_wins": [...],
               "shots": [...], "saves": [...],
               "distance_m": [...], "top_speed_dmh": [...], "sprints": [...] }
  }]
}
```
Each array has `last_minute + 1` entries; index *m* = value at match minute *m*. Integers only (`top_speed_dmh` = km/h × 10). Schema: `schemas/players.schema.json`. Size ≈ 28 × 9 × 91 ints ≈ 100 KB (gzip far less).

**3c. Web:** the phone picks `players.stats[...][state.minute]` — never later (no spoilers).

## 4. Work split
| # | Who | Work | Size |
|---|---|---|---|
| 04a | GLM | match-lab `attributes` + schema + tests (events unchanged, attributes in range, calibration) | S |
| 04b | GLM | `matchreader/players.py` + `python3 -m matchreader.players --seed 43`: counted stats, pass difficulty, minutes, modelled stats; `players.schema.json`; tests | M |
| 04c | Claude | phone UI: team chips, number grid, player card, Follow chip, half-time line; EN/DE/VI strings (drafts); plain-sentence rules | M |
| 04d | Claude | review GLM output; wire `players.json`; browser test with TV + phone | S |

**Plain sentence (04c, code only, no AI):** pick the first tag that is true for the player at that minute — `top passer of the team`, `most ball wins in the team`, `fastest player in the match`, `covered the most ground`, else a role line by position. Each tag has one EN/DE/VI template with `{placeholders}` filled from the stats; no digits in the copy itself. Same banned-word and 200-character rules as `check:copy`. Pronoun-neutral wording ("this player", "number 7"), as in the rest of the app.

**Tests (GLM, 04b):** counted stats recounted independently from raw events for 5 seeds; arrays never decrease; no-future (truncate events, same prefix); minutes-played bookkeeping against subs; calibration over 200 seeds (outfield distance per 90 in 8.5–12.3 km, top speed ≤ 37, sprints plausible by position); determinism; schema.

## 5. Out of scope
- **Ghost run** (half-time brief item): needs tracking + a followed player's path. Revisit with OPEN Q6.
- Player photos, likenesses, real names (rule 4).
- Any server logging of lookups, follows or favourites.
- Showing player cards on the TV (push-only screen).
- Comparing or ranking players for viewers (rule 3: no rankings). Tags like "fastest in the match" describe a fact; there is no leaderboard screen.

## 6. Decisions (all confirmed 2026-10-13)
| # | Question | Recommendation |
|---|---|---|
| D1 | **Names (OPEN Q7).** Cards identify players by **team + number + position** only, or by synthetic names? | Numbers only for the demo. Names need a locale list and a screening step against real players; the card works without them and it matches how a newcomer actually asks ("number 7 in blue"). |
| D2 | Distance, top speed and sprints are **modelled**, not tracked. Acceptable to show as "this match" stats? | Yes, labelled in the data card. The alternative (real 10 Hz tracking for everyone) is out of reach before the freeze. |
| D3 | Stats **as of now** (no spoilers) or full-match? | As of now. |
| D4 | Follow stays on the device and adds one line to the half-time card. OK? | Yes. |

## 7. Timing
Freeze is Oct 24. Proposed: 04a + 04b with GLM Oct 14–15 · 04c in parallel, against the fixture from `--seed 43` · 04d Oct 16. Cut line if behind: drop "Follow" and the half-time line; keep lookup + card.

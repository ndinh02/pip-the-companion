# Task 03 — Match Reader: turn a generated match into the file the web app plays

**Depends on:** Tasks 01 and 02 (done). **Do not** change anything under `web/`; Claude wires the web side afterwards.

**Goal:** `data/mock-seed-N.json` (match-lab output) → `data/demo-match.json` (same shape as `web/public/data/fake-match.json`): a score timeline, per-moment facts computed from the events, and "Call it!" cards. **No AI anywhere.** Every number comes from code; every sentence comes from `match-reader/templates/cards.json` (already written by Claude; DE/VI are drafts — do not edit or add copy).

**Allowed paths:** `match-reader/**` (new Python package `matchreader`), `data/demo-match.json` and `data/mock-seed-*.json` (output only), plus Step 0 only: `match-lab/matchlab/generator.py`, `match-lab/tests/**`, `schemas/match.schema.json`.

## Read first
`/AGENTS.md` (hard rules), `web/src/lib/types.ts` (the shape the web expects), `web/public/data/fake-match.json` (a finished example), `schemas/overlay_card.schema.json`, `match-reader/templates/cards.json`, `scripts/check-copy.mjs` and `scripts/banned-words.json` (rules to port), `docs/PROJECT_BRIEF.md` §5.1–5.2.

## Step 0 — give VAR checks a margin (small change in match-lab)
The VAR card needs `{var_margin_cm}`. In `generator.py`, when a VAR stoppage is created, add `var.margin_cm`: an integer 1–40 for `check_type == "offside"`, `null` for `foul`. Draw it from a **separate** generator, `random.Random("%d-var-%s" % (seed, shot_event_id))`, so the main random stream (and therefore every existing seed's events) does not change. Add `margin_cm` (`["integer","null"]`, optional) to `var` in `schemas/match.schema.json`, regenerate `data/mock-seed-1.json`, and confirm `cd match-lab && python3 -m unittest discover -s tests` still passes.

## Step 1 — reader library
Package `match-reader/matchreader/`, run from `match-reader/` as `python3 -m matchreader.<module>`. Standard library only, Python 3.9 (`from __future__ import annotations`). Functions are pure: same input file → byte-identical output (`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=True)`, like `matchlab/generate.py`).

### 1a. Facts at a moment
All facts for a moment use only events up to and **including** that moment's own event (the reveal is the next thing viewers see).
- **Time:** `t_in_min` = minutes on the match clock shown to viewers, 1 decimal: period 1 → `(t_ms − p1.start_ms)/60000`; period 2 → `45 + (t_ms − p2.start_ms)/60000`. A moment in period-1 added time (> 45) is not eligible (reason `added_time`).
- **Attack direction:** Harbour Lights (`HAR`) attack +x in period 1 and −x in period 2; Copperfield (`COP`) the opposite. A free kick is "in the opponent's half" if its `start.x` is on the side of the pitch the team attacks (x > 52.5 when attacking +x, x < 52.5 when attacking −x).
- **Fact ids are scoped per card** so the web's single `facts` table works unchanged: the template placeholder `{corners_short}` on card `c1-corner` is written to the output as `{c1_corners_short}` and stored as `facts["c1_corners_short"] = {"value": 3, "source": "match-reader"}`. The prefix is the card's number: `c1`, `c2`, … in time order. Rewrite placeholders in all three languages and in `fact_ids`.
- Values (team = the team the moment is about):
  - `corners_short`, `corners_total`: that team's corner events so far (incl. this one); short = `set_piece.routine == "short"`.
  - `league_short_share_pct`: `16` (= `DEFAULT_PRIORS["corner_short_share"]` × 100, imported from `matchlab` or copied with a comment; `source: "match-lab default priors"`).
  - `fk_total`, `fk_cross`: that team's free kicks in the opponent's half so far (incl. this one); cross = `set_piece.routine == "cross"`.
  - `forwards_before/after`, `defenders_before/after`, `midfielders_before/after`: players of that team on the pitch just before / after the substitution. Rebuild the line-up from `players[].position`, the starting XI (shirt 1–11) and the earlier `substitution` events (`player_id` in, `player_out_id` out); also remove players with a `card` event of subtype `second_yellow`.
  - `subs_used`: that team's substitution events so far incl. this one (count the sub window's events up to and including this card's event); `subs_max`: number of bench players (shirts 12–14) = 3.
  - `var_margin_cm`: `stoppage.var.margin_cm`.

### 1b. Moments (candidates)
One candidate per event/stoppage of these kinds. `answer` = the option id the match gives.

| trigger | source | answer | eligible only if (else held, with reason) |
|---|---|---|---|
| `corner` | `corner` event | `set_piece.target_zone` (`near`/`far`/`short`) | team's `corners_total ≥ 3` (`habit_not_clear_yet`); target_zone is not `central` (`no_option_for_central`) |
| `free_kick` | `free_kick` event | `set_piece.routine` (`shoot`/`cross`/`short`) | in the opponent's half (`own_half`); `fk_total ≥ 2` (`sample_too_small`) |
| `substitution` | **first** `substitution` event of each sub window (events with the same `t_ms` belong to one window) | incoming player's position: `FW`→`attack`, `DF`→`defend`, `MF`→`fresh` (the event's `subtype` already says attacking/defensive/balanced) | for `attack`/`defend`, the before/after count of that position must differ (`no_visible_change`); period 2 only needs no extra rule |
| `var` | `stoppage` with `type == "VAR"` | key `"<check_type>:<decision>"` picks the reveal template; the **option id** is `check_type` (`offside`/`foul`) | — |

- `t_in_min`, `team_id`, `pitch {x,y}`: from the event's `start` (corner/free kick) or the incoming player's event (`substitution` events have start = end = ball position — fine); for VAR use the scoring team's shot event (the stoppage's `related_event_ids[0]`). Moment time for VAR = `t_start_ms` of the stoppage.
- `moment_id`: `"m-<trigger>-<round(t_in_min)>"`; `card_id`: `"c<n>-<trigger>"` (n = 1-based position in time order after selection).

### 1c. Pip's call (rule-based, learnable, sometimes wrong on purpose)
Computed only from events **before** the moment:
- `corner`: most common `target_zone` among that team's earlier corners (ties → `far`, then `near`, then `short`); `central` counts as nothing; no history → `far`.
- `free_kick`: most common routine among that team's earlier opponent-half free kicks (ties → `cross`, `shoot`, `short`); no history → `cross`.
- `substitution`: team losing at that minute → `attack`; winning → `defend`; level → `fresh`.
- `var`: always `offside`.
Reveal pose: `wow` if `pip_call == answer`, else `oops`.

### 1d. Which moments become cards (timing policy, brief §5.2)
Constants at the top of the file with comments, so Claude can tune them:
`MAX_PER_HALF = 4`, `MIN_GAP_MIN = 8.0` (between cards), `GOAL_QUIET_S = 60` (no card within 60 s after a goal **event**, except the `var` card about that goal).
Greedy: sort eligible candidates by priority `var` > `substitution` > `free_kick` > `corner` (long breaks first), then by time; accept a candidate if it breaks none of the rules against the cards already accepted. Finally sort by time. Every non-selected candidate goes to `moments_held` with `reason` ∈ the reasons above plus `max_per_half`, `too_close_to_previous_card`, `after_goal`.

### 1e. Output file
Top level keys: `match_id`, `seed`, `generator_version`, `reader_version` (`"matchreader-0.1.0"`), `competition`, `venue`, `pitch`, `coord_system`, `teams` (`team_id, name, short_name, kit{primary,secondary}` — drop `gk`), `score_timeline`, `facts`, `cards`, `moments_held`.
- `score_timeline`: `[{"from_min":0,"HAR":0,"COP":0}, …]`, one entry per **counted** goal (shot events with `outcome == "goal"`; `disallowed` are not goals), `from_min` = that event's `t_in_min`; the last entry must equal `final_score`.
- `cards[]`: exactly the shape of `schemas/overlay_card.schema.json` / `fake-match.json`: `question.text`/`options` from the template (replace `<team>` with the team's `name`), `question.pip_call`, `reveal.{answer,pose,plain,expert,fact_ids}` from the template for the answer key, `<team>` replaced, placeholders re-scoped (1a). `reveal.answer` for `var` = `check_type`.
- `moments_held[]`: `{"trigger","t_in_min","team_id","reason"}`.

## Step 2 — command line
```bash
cd match-reader
python3 -m matchreader.pick_seed --from 1 --to 200          # prints the 8 best demo seeds
python3 -m matchreader.build --in ../data/mock-seed-1.json --out ../data/demo-match.json
```
- `build` also accepts `--seed N`: generate with `matchlab.generate_match` (add `../match-lab` to `sys.path`) instead of reading a file. Print a one-line summary (cards by trigger, held count, score).
- `pick_seed` scores each seed: must have ≥ 1 card of each of the four triggers, ≥ 6 cards, ≥ 1 card in each half, ≥ 1 card with `pip_call == answer` and ≥ 1 with `!=`; rank by number of cards, then closest final score. Print a table `seed | cards by trigger | Pip right/wrong | score`. **Do not choose the demo seed yourself**: write the table into the Result section and stop; Claude and the owner pick.
- After the owner picks a seed N, `build --seed N --out ../data/demo-match.json` is the only way `data/demo-match.json` is written.

## Step 3 — tests (`match-reader/tests/`, run with `python3 -m unittest discover -s tests -v`)
1. **Facts are true:** for 5 seeds, recompute `corners_short/total`, `fk_cross/total`, forwards/defenders/midfielders before/after, `subs_used` **independently in the test** (a second, simple implementation: loop over events) and compare with the build output.
2. **No spoilers / no future:** a fact's value never changes if you delete all events after the moment's own event and rebuild that card's facts (call the facts function on a truncated copy).
3. **Copy rules** (port of `scripts/check-copy.mjs`, reads `scripts/banned-words.json`): every string ≤ 200 chars; no banned word in EN/DE/VI; no digit outside `{…}`; every `{placeholder}` is in the card's `fact_ids` and in `facts`; `answer` and `pip_call` are among the option ids; no leftover `<team>`.
4. **Schema:** each card validates against `schemas/overlay_card.schema.json`. Copy the small `check()` function from `match-lab/tests/test_schema.py` into `match-reader/matchreader/schemacheck.py` (stdlib only; add `maxLength` support if the card schema needs it — it does).
5. **Policy:** per half ≤ 4 cards; consecutive cards ≥ 8 min apart; no card (other than `var`) within 60 s after a goal; `score_timeline` ends at `final_score`; cards are in time order; `t_in_min` ≤ 45 for period-1 cards.
6. **Determinism:** same input → identical bytes; the `data/demo-match.json` written by the CLI parses and passes 3–5.
7. Step 0: a VAR stoppage with `check_type == "offside"` has an integer `margin_cm` in 1–40; match-lab tests still pass; `data/mock-seed-1.json` events are unchanged apart from the new field (compare against `git`-free copy: regenerate before the change into a temp file first).

## Rules to remember
- Do not edit `match-reader/templates/cards.json`. If a template is missing for an answer you need, **hold the moment** (`reason: "no_template"`) and say so in Result.
- Do not invent numbers or sentences. No `random` in the reader (it is a pure function of the match file).
- DE/VI stay drafts: do not touch them.
- No third-party packages. No git commits. Do not touch `web/`.

## Result

**Status: done, all acceptance tests pass. `data/demo-match.json` is NOT written yet — the owner picks the seed first (see table).**

### Step 0 (match-lab margin)
- `var.margin_cm` added via a separate `random.Random("%d-var-%s" % (seed, shot_event_id))` stream; integer 1–40 for offside, `null` for foul. Schema updated (optional, `["integer","null"]`).
- `data/mock-seed-1.json` regenerated and **byte-identical** to the pre-change copy (seed 1 has no VAR stoppage; compared against a temp copy generated before the edit, per test 7).
- `cd match-lab && python3 -m unittest discover -s tests` → **25 tests OK**.

### Step 1–3 (match-reader)
- Package `match-reader/matchreader/` (`reader.py`, `build.py`, `pick_seed.py`, `schemacheck.py`, `copycheck.py`), stdlib only, Python 3.9.
- `cd match-reader && python3 -m unittest discover -s tests -v` → **28 tests OK**, covering all seven acceptance groups: facts recounted independently for seeds 1–5; no-spoiler truncation test; ported copy rules (+ self-tests that bad copy is rejected); every card validates against `overlay_card.schema.json` (+ validator self-tests); timing policy; determinism (CLI `--seed` and `--in` modes produce identical bytes; CLI output passes copy+schema+policy — run against a temp path, since the official `demo-match.json` waits for the owner's seed); VAR margins.

### Held / decisions to know about
1. **Two draft templates hard-code "Copperfield"** instead of `<team>`: `corner→short` and `free_kick→cross` reveal `plain` (all three languages). Per the owner's decision (2026-10-13): the reader uses them only when the team **is** Copperfield, and holds the moment with `reason: "no_template"` when the team is Harbour Lights. **For Claude:** replacing the hard-coded name with `<team>` in `templates/cards.json` makes those moments come back with no reader change.
2. `card_id`/`moment_id` slug drops the underscore (`c4-freekick`, `m-freekick-78`) — `overlay_card.schema.json`'s `card_id` pattern `^[a-z0-9-]{1,40}$` forbids `_`; matches fake-match.json's `c4-freekick`. Fact ids keep underscores (`c4_fk_cross`).
3. `subs_used` counts the team's substitution events with `t_ms <= ` the moment's `t_ms`, i.e. the whole sub window (a 2-sub window shows 2 used — that is what viewers see when the reveal lands). before/after position counts likewise span the whole window.
4. Period-2 added time is allowed (the spec excludes only period-1 added time, reason `added_time`).
5. `pick_seed`'s "closest final score" read as smallest goal difference; ties broken by more goals, then seed.
6. `--from` needs Python ≥ arg name workaround: implemented as `--from`/`--to` with `dest` (works as specified on the command line).

### pick_seed table (seeds 1–200, 18 qualify; top 8 shown — owner picks)

```
seed | corner free_kick sub var | total | right/wrong | halves | score | ok
  43 |      2         3   2   1 |     8 |      4/4    |    12  |  1-1  | yes
 133 |      1         3   2   1 |     7 |      3/4    |    12  |  1-1  | yes
  44 |      1         3   2   1 |     7 |      4/3    |    12  |  1-2  | yes
 146 |      1         4   1   1 |     7 |      4/3    |    12  |  1-3  | yes
  30 |      3         1   2   1 |     7 |      3/4    |    12  |  3-0  | yes
  89 |      1         3   2   1 |     7 |      5/2    |    12  |  0-3  | yes
  35 |      1         2   2   1 |     6 |      1/5    |    12  |  2-2  | yes
 104 |      2         1   2   1 |     6 |      2/4    |    12  |  1-2  | yes
```

Seed 43 verified end-to-end: 8 cards, all four triggers, copy + schema clean, VAR card with `margin_cm = 32`.

### Next (Claude + owner)
1. ~~Owner picks N~~ — **owner picked seed 43 (2026-10-13)**; `data/demo-match.json` written via `build --seed 43 --out ../data/demo-match.json` and re-verified (copy clean, schema clean, both test suites OK).
2. Claude wires the web side (copy to `web/public/data/match.json`, `check:copy`, click-through).

---
### After this task (Claude + owner, not GLM)
1. Owner picks the demo seed from the table; GLM runs `build --seed N`.
2. Claude: copy `data/demo-match.json` to `web/public/data/match.json`, point `loadMatch()` and `scripts/check-copy.mjs` at it, run `npm run check:copy` and `npm run build`, click through `/tv`, `/play`, `/console`; show `moments_held` in the console (the "held-back log").
3. Claude: keep `fake-match.json` only as a test fixture.

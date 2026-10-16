# Task 02 — Validate generator output against JSON Schemas

**Depends on:** Task 01.
**Allowed paths:** `schemas/event.schema.json`, `schemas/match.schema.json` (new files), `match-lab/tests/test_schema.py`

## Build
1. Write `schemas/event.schema.json` and `schemas/match.schema.json` (JSON Schema 2020-12) from brief §8.2. Style: copy `schemas/overlay_card.schema.json`.
2. `match-lab/tests/test_schema.py`: generate a match with seed 1 and validate. No third-party packages: write a tiny checker for the subset you use (type, required, enum, minimum/maximum, items) or vendor `jsonschema` only if the owner approves — ask Claude first.

## Acceptance
```bash
cd match-lab && python3 -m unittest tests.test_schema -v
```

## Result
Done 2026-10-13 (run by Claude in the lead session). `cd match-lab && python3 -m unittest tests.test_schema -v` -> 11 tests OK.

- `schemas/event.schema.json`, `schemas/match.schema.json` (2020-12, style copied from `overlay_card.schema.json`; `match` refers to `event.schema.json` for its `events` items).
- `match-lab/tests/test_schema.py`: a ~60-line checker for the keywords the schemas use (`$ref`, `type`, `enum`, `required`, `properties`, `additionalProperties`, `items`, `anyOf`, `minimum`/`maximum`, `minLength`, `pattern`, `minItems`/`maxItems`). It raises an error if a schema uses a keyword it does not know, so it cannot pass silently. No `jsonschema` package was needed.
- Valid: seeds 1-4, including extreme priors (short share 0 and 1, press 0 and 1).
- 9 negative tests prove the checker rejects bad data (coordinate outside the pitch, unknown event type, missing/extra field, wrong type, bad player id, bad set piece, bad stoppage type, pressure level 6).
- Not covered: `schemas/overlay_card.schema.json` is not checked by this file (it validates match-lab output only).

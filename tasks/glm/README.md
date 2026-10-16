# Tasks for the GLM model

How to work:
1. Read `/AGENTS.md` first (hard rules), then your task file.
2. Edit **only** the paths listed under "Allowed paths".
3. Run the acceptance commands. Paste what passed/failed into the "Result" section at the bottom of the task file.
4. Do not make git commits. Do not add dependencies beyond the standard library unless the task says so.
5. Python on this Mac is 3.9: start every file with `from __future__ import annotations`, no `match` statements, no `X | Y` type syntax at runtime.

Order: 01 → 02 → 03 (done) → 04 tracking synthesizer → 05 player stats feed (needs 04) → 06 ball realism (done 01–05) → 08 positions audit (keepers, ends, kick-offs) → 07 goal celebrations (needs 08). Ask Claude (lead) if the task is ambiguous; do not guess on anything in `docs/OPEN_QUESTIONS.md`.

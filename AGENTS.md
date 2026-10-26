# AGENTS.md — rules for every AI assistant in this repo

Shared by Claude Code, the GLM model, Codex and GitHub Copilot. `CLAUDE.md` only points here.
Full context: [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) (read §§3, 6, 9, 14, 15 first).

## What this is
**Pip** — a matchday companion for mixed rooms (one fan + newcomers). In dead-ball breaks a small club-neutral bird mascot asks the room one "Call it!" question about how the next play unfolds; the match answers; Pip explains why. Built for the Microsoft "Inside the Game" hackathon. Submission deadline: 2026-10-27 (hard stop 2026-10-28 07:59 German time). Feature freeze: 2026-10-24.

## The owner
Nhi (UX/UI designer, not a trained engineer). Explain choices in plain language, keep code readable, work in small testable steps. Ask before deciding anything the brief marks PROPOSED or OPEN.

## Decided (do not re-litigate)
- Name: **Pip** (owner renamed from "Pippi" on 2026-10-16). Keep the name in one constant (`web/src/lib/brand.ts`) so it can change. Since 2026-10-26 (owner) the internal identifiers say `pip` too: the card field `pip_call`, the package `agents/pip_agents`, `PIP_SLOW`, storage keys `pip:*`, the repo `pip-the-companion`. Only notes about the rename itself still mention "Pippi".
- Stack: Vite + React + TypeScript (web), Python (match-lab, match-reader, agents).
- Pitch coordinates: metres, 105 × 68. Synthetic data only; no real-data calibration.
- Fictional teams: **Harbour Lights** (sea blue `#2E7FC4` / white) vs **Copperfield** (copper `#C8692F` / black). Team blue was changed from `#5AA9E6` to avoid clashing with brand Sky `#6CB4EE`.
- Prize targets: Best Enterprise Solution + Best Azure Cloud Native Integration.
- Licences (decided 2026-10-26): MIT for code (`LICENSE`), CC BY 4.0 for synthetic data and match copy (`LICENSE-DATA.md`); Pip artwork and team crests all rights reserved.

## Hard rules
1. **No AI at runtime in the hosted app.** All AI text is generated and checked before the match, saved as files, replayed.
2. **Every number shown to viewers comes from code**, never from an LLM. Texts use placeholders like `{corners_short}`; code fills them from `facts`.
3. **No betting.** No odds, points, streaks, rankings; no "who wins / who scores next" questions; banned words (EN/DE/VI) are listed in `scripts/banned-words.json` and enforced by `npm run check:copy`.
4. **No club badges, Premier League marks, real player likenesses, or copyrighted music.**
5. **No free-text input from viewers.** Only known answer IDs and well-formed room codes.
6. **Privacy:** no names, no accounts, no cookies beyond a session token, no analytics.
7. **Keep the hosted demo working without the owner's laptop** until 2026-11-10.
8. Pip never grades people, never repeats a line within a match, has no opinions on referees or players.
9. Secrets never go in the repo.

## Conventions
- Languages: EN canonical, DE and VI re-voiced from the same facts. DE/VI copy is a **draft until the owner checks it** — mark new DE/VI strings so they are easy to find.
- Brand: Floodlight yellow `#FFD23F`, Night navy `#0E1A2B`, Chalk `#F6F3EC`, Turf `#1F9D6B`, Sky `#6CB4EE`. Font Be Vietnam Pro. Text contrast ≥ 4.5:1. Respect `prefers-reduced-motion`.
- TV card: ~30% width lower third inside the 5% safe area, text ≥ 28 px at 1080p, never over the scoreboard.
- Python: the owner's Mac has Python 3.9 today; write 3.9-compatible code (`from __future__ import annotations`) unless told otherwise. Microsoft Agent Framework needs ≥ 3.10 (see `docs/OPEN_QUESTIONS.md`).
- Verify package versions before pinning. Use Microsoft Learn docs for Microsoft APIs.
- Do not make git commits unless the owner asks.

## Division of labour (Claude + GLM)
- **Claude** (lead): repo skeleton, schemas, React screens, design-to-code, review and integration.
- **GLM** (terminal): self-contained Python tasks written as files in `tasks/glm/`. Each task lists inputs, outputs, acceptance tests. Do only the task; don't edit files outside the listed paths. When done, write a short note at the bottom of the task file ("Result") saying what passed and what didn't.

## Commands
```bash
cd web && npm install
cd web && npm run dev          # http://localhost:5173
cd web && npm run check:copy   # banned words + placeholder check on the match file
cd web && npm run build
```

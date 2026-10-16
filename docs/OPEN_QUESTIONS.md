# Open questions (from brief §14, updated 2026-10-13)

| # | Question | Status |
|---|---|---|
| 1 | Name: Pip vs Pippi | **DECIDED: Pip** (owner, 2026-10-16; was Pippi from 2026-10-13). A quick trademark search for "Pip" in the product's classes is still sensible before public launch. |
| 2 | LLM provider (Foundry Local / Azure OpenAI / both) | OPEN — needed by Oct 18 (agents). Needs Python ≥ 3.10 on the Mac either way. |
| 3 | Real-time rooms (Web PubSub / polling / single-device) | OPEN — mock uses single-device mode (BroadcastChannel). |
| 4 | Colour clash | **DECIDED:** team blue → `#2E7FC4`. |
| 5 | Cosmos DB vs Table Storage | OPEN — after Azure signup. |
| 6 | Hero moments with 10 Hz tracking | **CHANGED 2026-10-13:** owner wants a tracking system → full-match synthetic tracking at 5 Hz (`docs/TRACKING_SPEC.md`); 10 Hz windows around question moments later. Screen use (§4) still PROPOSED. |
| 7 | Player-name locales + screening | **DECIDED for the demo (2026-10-13):** no names; players are identified by team + shirt number + position. Names stay OPEN for later. |
| 8 | Must-have list (§5.4) | OPEN — mock covers: Call it!, two-depth reveal, DE/EN/VI. |
| 9 | Brand (colours, type, voice) | OPEN — mock uses the draft brand. |
| 10 | Licences | PROPOSED: MIT + CC BY 4.0 — unconfirmed. |
| 11 | CLAUDE.md vs AGENTS.md | **DECIDED:** AGENTS.md shared, CLAUDE.md pointer. |
| 12 | "Convince the room" mechanic | OPEN — not built in the mock. |
| 13 | Sponsored moments | OPEN — keep out of all pitch material until decided. |

## Environment gaps found on day 1
- Python 3.9.6 only → install 3.11+ (e.g. from python.org) before the agents work.
- `gh` CLI not installed. `origin` is set locally to https://github.com/ndinh02/pippi-the-companion.git but nothing is pushed.
- Azure for Students not signed up; hackathon registration closes 2026-10-20 12:00 PT (21:00 German time).

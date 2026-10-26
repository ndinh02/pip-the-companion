# Open questions (from brief §14, updated 2026-10-13)

| # | Question | Status |
|---|---|---|
| 1 | Name: Pip vs Pippi | **DECIDED: Pip** (owner, 2026-10-16; was Pippi from 2026-10-13). A quick trademark search for "Pip" in the product's classes is still sensible before public launch. |
| 2 | LLM provider (Foundry Local / Azure OpenAI / both) | **Foundry Local installed 2026-10-16** (CLI 0.11.0, qwen2.5-7b); first trial through the checker works (`data/agent-trace-llm.json`). Writer uses Foundry Local's local endpoint with the standard library, so no new Python is needed. Azure OpenAI fallback still open. |
| 3 | Real-time rooms (Web PubSub / polling / single-device) | **DECIDED 2026-10-16: HTTP polling** on the App Service server (`web/server/rooms.mjs`); single-device mode stays as the local fallback. |
| 4 | Colour clash | **DECIDED:** team blue → `#2E7FC4`. |
| 5 | Cosmos DB vs Table Storage | OPEN — after Azure signup. |
| 6 | Hero moments with 10 Hz tracking | **CHANGED 2026-10-13:** owner wants a tracking system → full-match synthetic tracking at 5 Hz (`docs/TRACKING_SPEC.md`); 10 Hz windows around question moments later. Screen use (§4) still PROPOSED. |
| 7 | Player-name locales + screening | **DECIDED for the demo (2026-10-13):** no names; players are identified by team + shirt number + position. Names stay OPEN for later. **2026-10-17:** names and player news/social links are in the brief (§5.5) as optional later-stage items, not in the hackathon build. |
| 8 | Must-have list (§5.4) | OPEN — mock covers: Call it!, two-depth reveal, DE/EN/VI. |
| 9 | Brand (colours, type, voice) | OPEN — mock uses the draft brand. |
| 10 | Licences | **DECIDED 2026-10-26:** MIT for code (`LICENSE`), CC BY 4.0 for synthetic data and match copy (`LICENSE-DATA.md`). Pip artwork and the team crests: all rights reserved. |
| 11 | CLAUDE.md vs AGENTS.md | **DECIDED:** AGENTS.md shared, CLAUDE.md pointer. |
| 12 | "Convince the room" mechanic | OPEN — not built in the mock. |
| 13 | Sponsored moments | OPEN — keep out of all pitch material until decided. |
| 14 | Remote rooms (relatives in another city, different stream delay) | **DECIDED 2026-10-23:** same-room only for the hackathon. Remote rooms (stream delay, spoiler guard) are the next feature after the hackathon. Analysis: `docs/design-options/what-can-go-wrong.html`. |
| 15 | TV during a question: faces or counts | **DECIDED 2026-10-23:** the TV shows counts only until the reveal. On the phone, a player may change their answer **once**; after that the phone shows "locked in" and waits for the others, then Pip waits for the outcome with a waiting animation. |
| 16 | Keep the room when the TV tab closes | **DECIDED 2026-10-23:** OK to store the TV's room key on the TV device (localStorage). No accounts, no tracking. |
| 18 | TV and phone design | **DECIDED 2026-10-23:** build the room prototype (`docs/design-options/prototype.html`, "V1 + V3 invite QR") 1:1: TV home with Resume, lobby with Kick off, corner QR with the room's animals, Pip's paper note, half/full-time card; phone start → code → animal → three tabs (Match, My player, Room). Pip is the owner's drawn artwork (`web/public/pip/*.png`, character sheet draft 02), never redrawn or generated. The room code is typed with the phone's own keyboard (iOS/Android), not an on-screen keypad. The phone has its own Scan screen (camera, frames stay on the phone; jsQR 1.4.0 where the browser has no QR reader); when scanning fails it falls back to pasting a copied invite link or typing the code. Server restart stays recovery-only (item 17b). |
| 17 | What goes in before the 2026-10-24 freeze | **DECIDED 2026-10-23:** (a) keep the room when the TV tab closes, (b) survive a server restart, (c) the TV is the alarm (plus clear phone status when something breaks), (d) the "no clear answer" outcome. |

## Environment gaps found on day 1
- Python 3.9.6 only → install 3.11+ (e.g. from python.org) before the agents work.
- `gh` CLI not installed. `origin` is set locally to https://github.com/ndinh02/pip-the-companion.git but nothing is pushed.
- Azure for Students not signed up; hackathon registration closes 2026-10-20 12:00 PT (21:00 German time).
- **Azure for Students (verified 2026-10-15) may only deploy to:** belgiumcentral, norwayeast, switzerlandnorth, francecentral, italynorth (subscription policy "Allowed resource deployment regions", read 2026-10-16). **Azure Static Web Apps is not offered in any of these**, so the planned hosting (brief §7.5) needs a replacement — **DECIDED 2026-10-16: Azure App Service, Free F1, France Central, Node 22** (`web/server/server.mjs`); the same server can host the room backend later. Any database or room backend must also use one of these regions.


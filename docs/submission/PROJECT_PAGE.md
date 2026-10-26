# Project page — ready to paste into Innovation Studio

Checked against the code on 2026-10-26. Character counts are measured. Anything in `<ANGLE_BRACKETS>` is still to fill in.

---

## Title (119 / 140)

```
Pip: a matchday companion that turns a synthetic match into checked, multilingual "Call it!" moments for the whole room
```

## Tagline (max 300) — two options

**Option A (my pick, 236 chars)**
```
Watch together. Call it together. At every dead ball, Pip asks the room one question on their phones. The synthetic match answers, and Pip explains why: a plain line for newcomers, a data line for fans, in English, German or Vietnamese.
```

**Option B (230 chars)**
```
A match insights engine built for the room, not one viewer: synthetic events and 5 Hz tracking become code-checked facts, explanations drafted and verified before kick-off, and a shared TV plus phone experience in three languages.
```

Why A: it says what a viewer experiences in one breath, and its first sentence is already the TV's own tagline. B is the better fit if you want the "insights engine" words of the challenge up front.

## Keywords (12)

```
synthetic-data, football-analytics, explainable-ai, second-screen, multilingual, player-tracking, azure-app-service, foundry-local, github-actions, react, threejs, privacy-by-design
```

## Challenge

```
The Synthetic Match Insights Engine for Premier League Studio
```

Writing code: **Yes** · Code repository: https://github.com/ndinh02/pip-the-companion

---

## Description (Markdown — paste everything between the two lines)

---

### The problem

Most people who watch football with a fan are not fans yet. They can't tell why a corner is played short or why a goal waits for VAR, and nothing invites them in between the moments that matter. Most "AI commentary" ideas talk to one viewer. Pip is built for the **room**: one fan, a few newcomers, one TV, everyone's phone.

### What Pip does

1. **Start a room.** Open `/tv` on a TV or laptop and press *Start a room*. The lobby shows a QR code and a four-letter code.
2. **Join on phones.** Scan the QR with the phone camera, type the code, or use Pip's own *Scan* screen. Pick an animal (no names, no accounts) and a language: EN, DE or VI.
3. **Kick off.** A synthetic match plays on the TV in a 3D view with several cameras and replays. Phones show a live header (score and MM:SS clock in sync with the TV).
4. **Call it!** When the ball goes dead (corner, free kick, substitution, VAR check), Pip, a small club-neutral bird, asks one question: *"Corner for Harbour Lights. How will they play it?"* Everyone answers on their phone and may change their mind once. The TV shows only counts.
5. **The match answers.** When the play happens, the TV highlights the outcome and each phone shows *You called it!* or *Not this time. Here's why*. There's a plain line for newcomers and a data line ("Why?") for fans. If the match doesn't settle it (the defence clears the ball before it reaches anyone), Pip says **No clear answer** and it counts for no one.
6. **Between moments.** Each phone keeps a chat history with Pip from kick-off, including which animals picked what. *My player* lets you follow one player: a 3D character, distance, top speed, passes, shots and saves per minute (with a "stats as of" marker), the running path from the last five minutes and the fastest run so far. At half-time and full-time the recap goes to the phones, and the TV stays clear.

### The five pipeline stages

| Stage | In Pip | Where |
|---|---|---|
| **Ingest** | A seeded generator writes a full match of events (passes, dribbles, tackles, interceptions, crosses, clearances, shots, saves, fouls, throw-ins, corners, free kicks, goal kicks, cards, substitutions, VAR checks for offside or a foul), and a tracking synthesizer simulates 22 players and the ball, written out at 5 Hz. The app replays both on the match clock. | `match-lab/` |
| **Interpret** | Facts per moment (e.g. corners played short so far), per-player stats per minute (distance, top speed, sprints over 25 km/h, passes, ball wins), added time by cause. Tests make sure no fact uses events from later in the match. | `match-reader/`, `scripts/added_time.py` |
| **Explain** | A timing policy picks the moments (at most 4 per half plus 1 in added time, 8 minutes apart, never just after a goal) and logs the ones it holds back. Each card carries a question, the outcome, a plain line and an expert line. A "void rule" decides when the match gave no clear answer. | `match-reader/matchreader/reader.py`, `agents/` |
| **Render** | TV: three.js stadium, an automatic camera director, replays, a lower-third question card, an added-time explainer. Phone: answers, reveals, history, *My player*. Cards follow an open JSON format, so other graphics systems could render them. | `web/`, `schemas/overlay_card.schema.json` |
| **Personalize** | Language per phone (EN/DE/VI). Two depths for every explanation (plain or expert). Follow one player. Your own calls in the history; latecomers see the earlier calls marked "before you joined". | `web/src/pages/Play.tsx`, `web/src/components/PlayerTab.tsx` |

### Microsoft and Azure technologies

| Technology | How Pip uses it | Where |
|---|---|---|
| **Azure App Service** (Linux, Node 22, France Central) | Hosts the app and the room server: HTTP-polling rooms, security headers, `/healthz` | `web/server/` |
| **GitHub Actions** + `azure/webapps-deploy` | On every push: Python tests, full-match QA on six seeds, copy checks, type-check and build, server tests. A push to `main` deploys to App Service only after all of them pass. A scheduled ping keeps the demo awake for judging. | `.github/workflows/` |
| **Foundry Local** (`qwen2.5-7b`, OpenAI-compatible endpoint) | An LLM writer that drafts reveal lines on the owner's machine, before the match, through the same checker. This is a trial run. The match judges see still uses the reviewed templates. | `agents/pip_agents/llm_writer.py`, `data/agent-trace-llm.json` |
| **TypeScript** | The whole web app and its screens | `web/src/` |

### Architecture

```
BEFORE THE MATCH (owner's machine, Python)                        DURING THE MATCH (Azure App Service, Node)
match-lab ─ events + 5 Hz tracking                                 /tv (shared screen) ◄──┐
   │                                                                   │ publishes state│ HTTP polling,
match-reader ─ facts · moment picker · player stats                   ▼                │ rooms in memory
   │                                                               room server ────────┤
agents ─ writer → checker → retry ×2 → fixed template                  ▲                │
   │                                                                   │ answers only   │
data/*.json (checked cards, facts, tracking, trace) ── CI ──deploy──►  /play/ROOM (phones)   /console (operator)
```

### Data

Everything is synthetic: two fictional clubs (Harbour Lights, Copperfield), placeholder players identified by team and shirt number, no real match, club or footage. The generator runs a possession-and-zone model with team habits, so the same seed always gives the same match. The tracking synthesizer keeps players and ball consistent with the events: players accelerate within limits, keepers stay in goal, and goals count only when the ball actually reaches the net. `scripts/match_qa.py` scans every frame for things a viewer would notice (ball teleports or vanishes, keepers missing, frozen players). CI runs it on the demo match and on five freshly generated seeds.

### Agentic design: a bounded workflow, not a free-roaming agent

Text for each moment goes through **Moment Picker (rules) → Writer → Checker (code) → retry → fallback**:

- Writers get numbers only through logged **function tools** (`list_facts`, `get_fact`). They write `{placeholders}`, and code fills in the values.
- The **Checker** recomputes every fact from the events. It rejects digits typed into the text, betting words in EN/DE/VI, a line that doesn't name what actually happened, the wrong VAR decision, counts in words ("twice"), grading of people, and anything that breaks the schema.
- Rejected drafts go back to the writer **with the checker's errors** (at most 2 retries), then to a fixed, reviewed template. The run confirms that what ships is exactly what was checked.
- **"Catch me lying"** in `/console` replays a run with two writers that were broken on purpose. One gets repaired after feedback, the other falls back, and nothing false ships.
- In the Foundry Local trial (re-run 2026-10-26 on the current 9-question match, `qwen2.5-7b`, 146 s), the checker approved the model's lines for all 9 moments, 5 on the first try; it rejected drafts that graded the room ("New friends look surprised!") or used a made-up placeholder, and the model repaired them. The shipped match still uses the checked templates: the trial also showed lines a rule-based checker cannot judge (an awkward "2th", an expert line that drifts off the outcome), which is why a human-reviewed template stays the default.

### Responsible by design

- **No AI at runtime.** Text is generated and checked before the match, saved and replayed. Nothing a viewer does can reach a model, so there's no prompt injection, no rate limit and no surprise during a live broadcast. This is a deliberate reliability choice.
- **Every number comes from code**, never from a model.
- **No betting.** No odds, points, streaks or "who wins" questions. Banned words in three languages are checked in CI.
- **Privacy.** No names, accounts, free text, analytics or cookies. Phones send only known answer, animal and player ids, and the server validates and rate-limits them.

### Enterprise and cloud readiness (honest)

Already in place: CI-gated deploys, a dependency-free server with a strict Content Security Policy and other security headers, token-protected rooms, input validation, recovery when the TV tab closes (*Resume room*) or the server restarts, a connection alarm on the TV and status overlays on phones. Today rooms live in the memory of one App Service instance on the Free tier. Scaling out would need shared room state (for example Azure Web PubSub). That's the next step, not built yet.

### Try it in 60 seconds

1. On a laptop, open **https://pip-the-companion-cjcdawd7gmf8f9h2.francecentral-01.azurewebsites.net/tv**. The first visit after a quiet spell can take up to a minute.
2. Press **Start a room**, then scan the QR with your phone camera. Pick an animal and a language.
3. Press **Kick off**, then **Next moment** to jump to the next break. Answer on the phone and watch the reveal. Tap **Why?**.
4. On the phone, open **My player** and follow someone. No phone? Use **More → Open a phone view**.
5. Open `/console` for the workflow trace and "Catch me lying".

### Links

- Live app: https://pip-the-companion-cjcdawd7gmf8f9h2.francecentral-01.azurewebsites.net/tv
- Code: https://github.com/ndinh02/pip-the-companion
- Demo video: https://github.com/ndinh02/pip-the-companion/blob/main/docs/submission/video/pip-demo.mp4
- Cover image: https://raw.githubusercontent.com/ndinh02/pip-the-companion/main/docs/submission/video/cover.png

*Built for the Microsoft "Inside the Game" hackathon. All teams, players and data are fictional. Not affiliated with or endorsed by the Premier League or Microsoft.*

---

# Pip — Project Brief

> **Corrections since rev 3 (2026-10-16).** The mascot and product are named **Pip** (owner decision 2026-10-16; "Pippi" was used 2026-10-13 to 10-16). Harbour Lights' blue is **#2E7FC4**, not #5AA9E6. For what is actually built, see `README.md`; for what is decided, `docs/OPEN_QUESTIONS.md`.
>
> **Planned vs built (2026-10-26).** This brief is the plan written at the start. As built: hosting is **Azure App
> Service** (Free F1, France Central), not Static Web Apps (not offered in the regions this subscription may use);
> rooms use **HTTP polling** on that server, not Web PubSub; there is **no database** (rooms live in server memory and
> recover after a restart); the content workflow is a template writer plus a code checker, with an AI writer trialled
> on **Foundry Local** only. Azure OpenAI, Microsoft Agent Framework and Cosmos DB are not used.

**Repository:** https://github.com/ndinh02/pip-the-companion
**Owner:** Nhi Ngoc Uyen Dinh (Macaroonie), solo entrant, UX/UI designer, building with AI coding assistants
**Hackathon:** Microsoft Innovation Studio — "Inside the Game" Developer Hackathon
**Challenge:** The Synthetic Match Insights Engine for Premier League Studio
**Brief version:** 2026-10-13 (rev 3 — adds §4.5 Positioning and §13.1–13.3 market direction)

> **How to read this brief (for AI coding assistants):**
> Every item is marked **DECIDED** (confirmed by the owner), **PROPOSED** (suggested, not yet confirmed — ask before building on it), or **OPEN** (needs a decision from the owner).
> Do not turn PROPOSED or OPEN items into decisions on your own. Ask the owner.

---

## 1. One-paragraph summary

Pip is a matchday companion for **mixed rooms**: one person who knows football watching with friends, partners or kids who are new to it. In the natural breaks of a match (VAR checks, substitutions, half-time, and briefly at set pieces), Pip — a small, club-neutral bird mascot that sits on the crossbar — asks the room one question about **how the next play will unfold** ("Corner! Where's it going? Near · Far · Short"). Everyone calls it, the match answers, and Pip explains why: a plain line for newcomers and a data line for fans. Synthetic match data drives everything; AI agents write the words; code checks every fact. It runs on TV (shared overlay card), phone (personal companion joined by QR) and laptop (browser side-panel extension).

**Pitch line (PROPOSED):** "Watch together. Call it together."

---

## 2. Hackathon rules that constrain the build (facts)

Source: official rules — https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md (checked 2026-10-13)

| Rule | Consequence |
|---|---|
| Registration closes 2026-10-20 12:00 PT (21:00 German time) | Owner must register before then |
| Submissions close 2026-10-27 23:59 PT (= 2026-10-28 07:59 German time) | Internal target: submit 2026-10-27 |
| Demo video **under 2 minutes**, public (YouTube/Vimeo), showing the project running | Script the demo tightly |
| **Public** GitHub repository required | Repo above is public |
| Judges must be able to test it **free and without restriction until 2026-11-10 23:59 PT** | Hosted demo must work without the owner's laptop → replay pre-generated outputs |
| Must use **synthetic, football-realistic data**; no footage supplied | Own synthetic generator; animated 2D pitch, no real video |
| No third-party trademarks or copyrighted music in the video | No club badges, no Premier League marks, no real player likenesses |
| Judging: 5 criteria × 20% — Technological Implementation, Agentic Design & Innovation, Real-World Impact & Applicability, User Experience & Presentation, Adherence to Category | Agentic design matters as much as UX |
| Category prizes: Best Use of Microsoft Foundry, Best Enterprise Solution, Best Multi-Agent, Best Azure Cloud Native | See §3 |
| "Hero technologies" listed (not strictly required): Microsoft Foundry, Agent Framework, Azure MCP, GitHub Copilot Agent Mode, Fabric, GitHub SDK/CLI, Azure services and databases | Use and name Microsoft tech in the pitch |
| Project must be newly created after registration opened (2026-09-29) | All code new |

The challenge's five required pipeline stages: **(a) ingest** synthetic events live → **(b) interpret** into stats/patterns/context → **(c) explain** why a moment matters → **(d) render** on screen alongside the match (timed, machine-readable, renderable by a broadcast graphics partner) → **(e) personalise** (analyst vs casual, favourite player, language, etc.). Also suggested: player name tagging with speed/distance thresholds, pass distance/accuracy/difficulty, ball and shot speed, narratives/recaps, explainability (control vs chaos, pressure, rhythm), data innovation (create/extend synthetic datasets), multi-language storytelling.

---

## 3. Decisions so far

| Topic | Status | Decision |
|---|---|---|
| Product + mascot name | DECIDED | **Pip** (repo is named `pippi-the-companion` — see OPEN Q1) |
| Prize categories to target | DECIDED | **Best Enterprise Solution** + **Best Azure Cloud Native Integration** (a project can win at most one category prize) |
| Repository | DECIDED | https://github.com/ndinh02/pippi-the-companion (public) |
| Owner's machine | DECIDED | Mac with Apple Silicon |
| Azure | DECIDED (status) | Owner has **not yet signed up** for Azure for Students |
| Front end | DECIDED | **Vite + React + TypeScript** |
| Data coordinate system | DECIDED | **Metres, pitch 105 × 68** |
| Calibration on real data | DECIDED | **No.** Use only published aggregate averages as targets (no StatsBomb/Metrica/SkillCorner/Wyscout data in the generator) |
| Generator approach | DECIDED | **Hybrid**: parametric event generator for full match + light season, plus hand-authored "hero moments" with full 10 Hz tracking |
| Teams | DECIDED | Fictional: **Harbour Lights** (sea blue #2E7FC4 / white) vs **Copperfield** (copper #C8692F / black) |
| Dev tools | DECIDED | Microsoft Learn MCP server (docs), Playwright (testing), Figma MCP (design-to-code) |
| First build draft scope | DECIDED | **Skeleton + clickable mock** (folder structure, CLAUDE.md, README, schemas, plus TV and phone screens running on a small fake match file) |
| Betting | DECIDED (product principle) | No odds, no points, no streaks, no "who wins / who scores next" questions, no betting words in any language |
| Languages | PROPOSED | English, German, Vietnamese (owner is fluent in all three and checks DE/VI) |
| Everything in §§5–11 | PROPOSED unless marked | Ask before treating as final |

---

## 4. Problem, audience, evidence

**Problem.** Casual viewers drift away from live football because they can't follow it and have no reason to engage between moments. Fans who could bring newcomers in have no shared format to do it.

**Audience.** Mixed rooms: one fan + newcomers. First markets: German, English, Vietnamese speakers.

**Key evidence (sources gathered during research):**
- 74% of Premier League fans say the reasoning behind decisions is unclear (FSA poll 2025/26, via Roundtable).
- Someone with no passionate fans in their network has ~12% chance of becoming highly passionate; surrounded by passionate fans, ~80% (Two Circles, via SportBusiness 2023).
- UK Gen Z check phones mostly in natural breaks (46%) vs. during play (20%); 72% message fellow fans right after a goal (Snap/OnePoll via SVG, 2026).
- Minute-by-minute Premier League TV audiences rise with suspense, surprise and "shock" (Forrest et al., Economic Inquiry 2020).
- Interactive overlays: LaLiga reported +25% watch time with 30% of viewers interacting (vendor-reported, SVG 2024).
- Failures to avoid: ESPN win-probability bug ("gambling brain"), Wimbledon AI recaps with factual errors, Clippy-style repetition, "AI-infested" Premier League app review.
- **No study proves conversion from casual to regular viewer.** Do not claim uplift numbers.

**Competition.** ~117 projects in the challenge; ~60 build evidence-linked AI commentary for a single viewer. Pip's difference: designed for the **room** (shared screen, mixed expertise), not one viewer.

### 4.5 Positioning (PROPOSED — confirm before using in pitch materials)

**Thesis (PROPOSED):** "Everyone is building AI that explains football to one person. Pip activates the room — the fan teaches, the newcomer calls it, and the AI only speaks when the humans don't. Then it gives you your attention back."

Five planks, each with what it costs to build:

1. **AI as social catalyst, not oracle (PROPOSED mechanic — see OPEN Q12).**
   On some reveals, instead of the plain line, Pip turns to the fan's phone: "Your call — convince the room." The fan gets 3 chips (what happened, why it matters, one allowed stat); the newcomer's phone shows "[Name] is explaining…". Pip fills the gap only if the room stays silent.
   Rationale: the strongest evidence stat (Two Circles: ~12% → ~80% passion conversion when surrounded by passionate fans, §4) says conversion is **human, not informational**. Every competitor's AI substitutes for the fan; Pip's activates the fan. This also answers the judges' inevitable "why not just a chatbot?"
   Cost: one card type in the reveal flow; 2 instances in the demo match.
   Guardrails: always opt-in, never scored, Pip never marks a human "wrong" — no social pressure on the fan.

2. **Diaspora room demo scene (PROPOSED — demo-video decision, no code).**
   Flagship scenario: one family, three languages, one match. Grandpa in Hanoi and the kid in Köln join the same room; at the same reveal, his phone shows the Vietnamese line, hers the German one — and they argue about the call anyway. Multilingual is staged as an emotional scene, not a settings dropdown. This converts the Vietnamese-LLM-quality risk into the memorable asset; Mascot Host re-voicing from checked facts (§7.3) is the fallback if VI quality is weak.

3. **Anti-second-screen stance (PROPOSED — README + video wording; the UI is already decided in §5.3).**
   "The only second screen designed to be put down." The phone sleeps in open play and wakes in dead air. Show an **attention-returned metric** ("Pip held the room's phones for 4 of 90 minutes") instead of engagement time. An engagement metric that counts minutes *not* on the app inverts the industry default and inoculates against the "AI-infested app" failure (§4).

4. **Co-prediction dataset (PROPOSED — data-innovation deliverable; export script on data already collected).**
   From the Oct 24–25 user tests: the first labeled dataset of how mixed-expertise **rooms** predict match moments — where newcomers and fans disagree, whether fan confidence predicts correctness, whether the room's aggregate call beats its best individual ("wisdom of the room"). Even n=12 rooms supports a README headline finding, honestly reported either way (a null result stated plainly reads as rigor). This is the second dataset alongside the generator benchmark (§8.4) and the strongest defensibility item (§13).

5. **Dead-air enterprise reframe (PROPOSED — docs only).**
   VAR checks, substitutions and added-time pauses are the only broadcast minutes that generate rage instead of revenue. Pip is an engagement product for the ~25–30 min/match nobody can sell — dwell time in the *cheap* minutes, without cannibalizing the broadcast. This gives the open `overlay_card` format a business reason to exist: the format that lets any broadcaster's graphics system render into dead air.

**Explicitly rejected (do not build, even if asked late in the sprint):** cross-room/crowd features (pulls viewer data into the product, breaks the privacy stance, rejoins the generic "social" pile); always-on free-text chat with Pip (rejoins the 60-team single-viewer pile, reopens prompt injection); camera/mic room sensing (a privacy grenade over the cleanest security story in the challenge).

---

## 5. The experience (PROPOSED)

### 5.1 Core ritual: "Call it!"
1. A moment worth asking about happens while the ball is dead.
2. Pip asks one question with 2–3 options (1–2 words each).
3. Everyone locks in; Pip makes its own call too (so solo viewers have a partner and being wrong is normal).
4. The match answers (next event).
5. Pip reveals: plain line (newcomer) + "Go deeper" expert line (fan) + room tally on phones.

Ritual phrase: "Call it!" (EN) · "Sag's an!" (DE) · "Đoán đi!" (VI).

### 5.2 Timing policy (from HCI audit)
- Prefer long breaks: VAR checks, substitutions, injuries, half-time.
- Set pieces: only a short "pre-call" that collapses when play resumes.
- Max **3–4 questions per half**, **8–10 minutes apart**, **none during open play**, none within ~1 minute after a goal or big chance.
- Cards stay **until play resumes** (not a fixed 5–8 s).
- An "ask us one" button lets the room pull a question.
- Only ask about things settled on screen within ~10 s (for VAR: "What are they checking?", revealed when the decision is shown — never "will it stand?").

### 5.3 Screens
| Screen | Role |
|---|---|
| TV (`/tv`) | Shared, push-only. Shows question + reveal card only (the broadcast can't know the room). Lower-third card ~30% width inside 5% graphics-safe area (EBU R95), never over scoreboard, text ≥ ~28–32 px at 1080p |
| Phone (`/play/:room`) | Join by QR (no account), emoji avatar, language from device. Sync to the room's TV with one tap at kick-off. Answer buttons, room tally, "Go deeper", "Why?", shareable half-time card. Dark ("Eyes up") during open play |
| Laptop (`/console` + browser extension) | Expert view; operator console showing agent decisions, held-back moments and why; extension side panel next to any stream |

### 5.4 Features — must-have for the demo (PROPOSED)
- One synthetic match with ~8 hero moments.
- "Call it!" questions for corner, free kick, VAR check, substitution.
- Two-depth reveal (plain / expert), DE/EN/VI.
- **Convince the room**: fan-explanation card type (§4.5 plank 1) — 2 instances in the demo match, always opt-in.
- **Who's that?**: look up a player by team colour + shirt number → card with identity, this-match stats (distance, top speed, sprints, passes + difficulty, ball wins), a plain sentence; "Follow" makes them your player.
- **Added-time explainer**: why N minutes, broken down from stoppage events.
- Half-time card (room calls, Word of the match, Ghost run of followed player).
- **Match Print**: generative artwork of the match at full time.
- Operator console with held-back log + **"Catch me lying"** switch (corrupt one stat → checker catches → repair loop fixes).
- Single-device demo mode (TV + phone + extension side by side).

### 5.5 Stretch / roadmap (do not build unless asked)
**Later stage, optional (owner decision 2026-10-17: in the plan, not in the hackathon build):**
- **Player names.** Today players are team + shirt number + animal only (decision D1). Later: synthetic names per team locale, screened so that no name matches a real player (a name list check before shipping), shown on the phone profile and the TV spotlight. For licensed real-match data, the real names come with the data rights.
- **Player news and social links.** Today the profile shows "This match" notes written by code from the match data (honest by construction). Later, only with **real** players and licensed data: recent news headlines from a licensed news feed and the player's official social accounts (verified handles from the rights holder). Never invented for synthetic players: fake news or handles could point at real people's accounts.

Fuel gauge (fatigue) + "Who comes off?", The duel, tactical switch detector, match chapters, rule radar, crowd's call across rooms, room map (drag a dot), Pip's pulse (vibration, Android only), smart lights, season comic, jargon catcher, newsroom ticker co-pilot console, readability report for broadcasters.

---

## 6. Brand (PROPOSED — owner designs the mascot)

- **Pip:** small round bird on the crossbar; floodlight-yellow body, navy wing tips, big readable eyes; club-neutral; **not a lion** (Premier League symbol). Five poses: asks, thinks, wow, oops, wave. Must read at 120 px.
- **Personality:** curious friend, not a teacher; asks, never lectures; never grades people; never repeats a line within a match; no opinions on referees or players.
- **Colours:** Floodlight yellow #FFD23F (Pip, call moments) · Night navy #0E1A2B (backgrounds) · Chalk #F6F3EC (text on navy) · Turf #1F9D6B (reveal markers) · Sky #6CB4EE (expert data lines). Verify all text contrast ≥ WCAG 4.5:1. Note: Harbour Lights' blue was changed to #2E7FC4 so it no longer clashes with brand Sky #6CB4EE (Q4, decided).
- **Type:** Be Vietnam Pro (OFL, full Vietnamese support) — ExtraBold for Pip lines, Medium for UI, tabular figures for numbers.
- **Motion:** Pip hops on (~300 ms), options slide up, thin bar drains until restart, 2 s reveal flash; nothing moves during open play; reduced-motion setting.
- **Sound:** chirp on phone/laptop only; TV silent by default.
- **Don'ts:** no odds/points/streaks/rankings; no betting words (bet, odds, Wette, Quote, Tipp, cược, kèo); no club badges or real player likenesses.
- Vietnamese address form: "bạn" (person), "cả nhà" (the room). Owner checks all DE/VI copy.

---

## 7. Architecture (PROPOSED)

### 7.1 Principle
**No AI runs live.** All AI text is generated and checked **before** the match, stored as files, and replayed. This keeps the demo reliable for judges until Nov 10, removes prompt-injection surface, and avoids rate limits.

### 7.2 Two pipelines
**A. Content pipeline (runs on owner's Mac before deploy):**
`Match Lab (generate)` → `Match Reader (compute)` → `Agents (write)` → `Checker (verify)` → files committed (`overlays.json`, cards per language).

**B. Delivery pipeline (GitHub Actions):**
On every push/PR: lint, type-check, Python tests (generator calibration, reader, checker), Playwright smoke tests. On merge to `main`: build and deploy to Azure Static Web Apps.

### 7.3 Agent workflow (Microsoft Agent Framework, Python) — PROPOSED
Honest framing for judges: **a workflow with bounded agent loops**, not free-roaming agents.

| Step | Kind | Input | Output | Never |
|---|---|---|---|---|
| 1 Match Reader | Code | Events, positions, match clock | Stats, set-piece habits, suspense, moment flags | Guess |
| 2 Moment Picker | Rules (+ AI only to rank ties) | Moment flags, suspense, time since last question, ball in/out of play | Fire/hold + reason (held moments logged) | Fire during open play or beyond the timing policy |
| 3a Question Writer | AI | Moment + facts via tools | 1 question, 2–3 options, 1–2 reason chips with `fact_ids` | Ask who wins/scores; mention odds |
| 3b Reveal Explainer | AI | Outcome facts via tools | Plain line + expert line with `fact_ids` | Add numbers not in data |
| 4 Checker | Code | Every text | Pass/fail: numbers match facts, banned-words list (EN/DE/VI), length limits | Let a failed text through |
| 5 Mascot Host | AI | Approved texts, language, depth | Same facts in Pip's voice + pose enum | Add facts/opinions |

Design details (from agentic audit):
- Agents call **function tools** (`get_stat`, `get_set_piece_habit`, `get_suspense`, `get_player`, `get_player_match_stats`) instead of having facts pasted into prompts; every chip/line carries `fact_ids`.
- Numbers are **placeholders** (e.g. `{corners_short}`) filled by code.
- **Repair loop:** checker error → back to writer, max 2 retries, then fixed template fallback.
- Write English canonical first; Mascot Host re-voices the same facts in DE/VI (not free translation).
- **Test bench:** ~40 moments × 3 languages; metrics: numeric faithfulness (100% required), banned words (0), length, readability, persona consistency. Agent Framework has local evaluation and DevUI tracing.

### 7.4 LLM access — OPEN (see Q2)
- **GitHub Models was retired on 2026-07-30** — do not use it.
- Option 1: **Foundry Local** on the owner's Mac (GA 2026-04; no per-token cost; OpenAI-compatible server; Python SDK `foundry-local-sdk`). Qwen2.5 model cards list German and Vietnamese; Vietnamese quality untested.
- Option 2: **Azure OpenAI in Foundry** via Azure for Students — quota on student subscriptions is undocumented and often 0; request via Foundry portal → Manage → Quota or https://aka.ms/oai/stuquotarequest.
- Agent Framework → OpenAI-compatible endpoint via `OpenAIChatCompletionClient(base_url=..., api_key=...)` — **smoke-test on day 1**.

### 7.5 Hosting and services (PROPOSED; free tiers verified 2026-10-13)
| Need | Service | Free limit |
|---|---|---|
| Web app + API | Azure Static Web Apps (Free) + managed Functions | 100 GB bandwidth/subscription, 0.25 GB/app, no SLA |
| Real-time rooms | Azure Web PubSub (Free) | 20 concurrent connections, 20k messages/day — fallback: polling a small JSON state every ~1 s |
| Viewer data | Azure Cosmos DB free tier | 1,000 RU/s + 25 GB, one per subscription, chosen at creation; supports time-to-live (auto-delete). Fallback: Azure Table Storage |
| Aggregation job | Azure Functions (timer) | Free grant applicability on student credit unclear |
| Optional | Azure Translator F0 (2M chars/month), Azure Speech F0 (0.5M neural TTS chars/month), Azure AI Content Safety F0 | — |
| Laptop | Edge/Chrome side-panel extension (Manifest V3, `sidePanel` permission; Edge supports it) | Load unpacked for demo |

Cloud Native category story: Static Web Apps + Functions + Web PubSub + Cosmos DB (+ optionally Container Apps). Enterprise category story: open card format for broadcast graphics partners, privacy/governance card, security model, measurement plan, newsroom/broadcaster integration path.

---

## 8. Data (PROPOSED schemas; DECIDED: metres 105×68, hybrid generator, no real-data calibration)

### 8.1 Generator ("Match Lab")
- Parametric event generator: team priors (corner routine mix, free-kick shoot vs cross, press intensity, sub attack bias) → possession/zone Markov model → SPADL-like actions. Seeded and reproducible.
- Hero moments: hand-authored with full 22-player + ball tracking at **10 Hz**, spliced in by `moment_id`.
- **Habits must be learnable and verifiable:** plant strong priors (e.g. Copperfield corners short 0.6 vs league ~0.18), simulate 200–500 matches, check planted vs recovered rates.
- Validate aggregates against published Premier League averages, e.g. ~10 corners/match, short-corner share ~13–18%, ball in play ~57 min, players 8.5–12.3 km per 90, top speeds up to ~37 km/h, sprint threshold >25 km/h, average restart times (corner ~34 s) — sources: Opta Analyst articles.
- Formats to align with (format only, no data): SPADL (socceraction, MIT), kloppy (BSD-3), FIFA EPTS.

### 8.2 Entities (draft)
- **match:** match_id, seed, generator_version, competition (fictional), date, venue, pitch {105, 68}, coord_system, frame_rate, periods[{id, start_ms, end_ms, added_time_announced_s, added_time_actual_s}], final_score
- **team:** team_id, name, short_name, kit {primary, secondary, gk}, formation, style_priors {...}
- **player:** player_id, team_id, display_name (synthetic, screened against real players), shirt_no, position, role, attributes {v_max, accel, endurance, pass_skill}
- **event:** event_id, idx, period, t_ms, clock_display, team_id, player_id, type, subtype, start{x,y}, end{x,y}, outcome, body_part, related_ids[], possession_id, under_pressure, pressure_level (1–5), difficulty (1–5), set_piece {routine, delivery, target_zone}, xg?
- **tracking_frame:** frame, t_ms, period, ball {x,y,z}, players[{player_id, x, y, v}], moment_id
- **stoppage:** stoppage_id, type (injury | VAR | sub | goal | card | other), t_start, t_end, duration_s, counts_for_added_time, related_event_ids, var {check_type, decision}
- **derived_metric:** subject, metric, value, unit, window, method_version
- **overlay_card:** card_id, t_in, t_out (match clock), slot, text {en, de, vi}, pose, fact_ids[], question {options, answer_event_id}
- **room_interaction (anonymous):** room_hash, question_id, option_counts, n_bucket (small counts suppressed)

### 8.3 Models
- In-play outcome: Poisson goal rates × time left → win/draw/loss.
- **Suspense** = expected variance of next-minute outcome beliefs, weighted by goal hazard; **surprise** = realised belief change (Ely, Frankel & Kamenica).
- Reason chips only when the pattern is strong and the sample large enough; otherwise "early sign".

### 8.4 Data innovation deliverable
Publish generator code (MIT), seeds/config, generated dataset (CC BY 4.0), JSON Schemas, data card, calibration report, and a "Call it!" question-label benchmark. Plus (PROPOSED, §4.5 plank 4): **co-prediction dataset** from consented user tests — mixed-expertise room calls, disagreement points, fan confidence vs correctness.

---

## 9. Viewer data, privacy, security (PROPOSED)

### 9.1 What is collected
Random room code; temporary device token (browser session only); fixed events only — answer chosen, "Why?" tapped, "Go deeper" opened, language, self-chosen "new / know it". **No names, no accounts, no IP logging beyond security needs, no cross-match tracking.**

### 9.2 Storage flow
1. Raw events → raw container with **72 h time-to-live**.
2. Timer function aggregates per moment × language; publishes a cell only if ≥10 rooms (suggested).
3. Only aggregates kept: crowd calls, readability index (newcomer vs fan divergence), confusion hotspots.
4. Short privacy note on QR join page. Strictly-necessary session token → no cookie banner (EDPB Guidelines 2/2023). Analytics cookies: none.
5. Never mine: betting interest, profiles of children, individual profiles. Interaction data stays **outside** the five-stage pipeline (which is match-data-driven).

User tests: consent form, P1–P5 IDs, aggregates only, raw notes deleted after 2026-10-27. Not legal advice.

### 9.3 Security
- **No free-text input from viewers; no live LLM calls** → no prompt-injection surface.
- Server-side schema validation: only known answer IDs and well-formed room codes accepted.
- Rate limits per device token; room codes expire after the match.
- Secrets only in GitHub Actions secrets / SWA app settings, never in the repo.
- Content Security Policy and security headers in `staticwebapp.config.json`.
- Extension: minimal permissions (`sidePanel`, `storage`), host access only to own domain.
- Public-repo protections: Dependabot alerts, code scanning.
- **Proof for judges:** `SECURITY.md` with one-page threat model; automated tests that send attacks (e.g. "ignore previous instructions" as an answer, malformed room codes) and assert rejection; "Catch me lying" integrity demo.

---

## 10. Proposed repository structure (PROPOSED — confirm before creating)

```
pippi-the-companion/
├─ CLAUDE.md / AGENTS.md        # instructions for AI coding assistants
├─ README.md
├─ SECURITY.md
├─ docs/                        # this brief, data card, threat model, measurement plan
├─ schemas/                     # JSON Schemas (match, event, tracking, overlay_card, room_interaction)
├─ match-lab/                   # Python: generator, hero moments, calibration tests
├─ match-reader/                # Python: stats, suspense, moment flags, tools
├─ agents/                      # Python: Agent Framework workflow, checker, test bench
├─ data/                        # generated match files + cached cards (committed)
├─ web/                         # Vite + React + TS: /tv, /play/:room, /console
├─ api/                         # Azure Functions: rooms, events, aggregation
├─ extension/                   # Edge/Chrome side-panel extension (MV3)
└─ .github/workflows/           # CI + deploy
```

---

## 11. Timeline (PROPOSED)

| Dates | Work |
|---|---|
| Oct 13–14 | Register for hackathon; sign up Azure for Students; install Foundry Local; repo setup; AI smoke test; paper prototype kit |
| Oct 15–16 | Paper test with 2 mixed groups (decision gate Oct 16: if testers call it betting or newcomers can't answer within 5 s, change question style) |
| Oct 15–17 | Match Lab + generator |
| Oct 17–18 | Match Reader + timing simulator |
| Oct 18–20 | Agents + test bench + "Catch me lying" |
| Oct 19–21 | TV card + replay player |
| Oct 21–22 | Phone + rooms |
| Oct 22–23 | Extension + Match Print |
| **Oct 24** | **Feature freeze** |
| Oct 24–25 | User test with build (3–5 mixed groups), accessibility pass |
| Oct 25–26 | Demo video (<2 min), pitch, README |
| Oct 27 | Submit (hard deadline Oct 28 07:59 German time) |

Cut order if behind: room map → Pip's pulse → extension overlay mode → live rooms (keep single-device mode).

---

## 12. Measurement plan (PROPOSED)

- **User test (3–5 mixed groups, consented):** two 20-min segments with/without Pip, counterbalanced. Measures: conversation turns and newcomers' share of talk, answered vs skipped, intrusiveness (1–7), enjoyment, 3-question comprehension check, "I felt OK being wrong", single effort rating, SUS, **attention returned** (phone-down minutes during open play, from device logs — the anti-second-screen metric, §4.5 plank 3). Room calls are exported as the co-prediction dataset (§4.5 plank 4).
- **Broadcaster A/B (proposed, not run):** Pip on vs off on an opt-in feed; minutes watched by casual viewers, 7-day return, second-match co-viewing, share rate of half-time cards.
- **Never claim** uplift percentages from production; never present synthetic personas as real viewers.

---

## 13. Defensibility (PROPOSED)

Medium and growing: Pip as protected character (copyright automatic; EU trademark €850 online for one class — check EUIPO), unique newcomer-reaction dataset, betting-free family-safe positioning (vs. betting-tech free-to-play games), open card format that broadcast partners integrate, tested mixed-room method (publishable with HSRM), native DE/VI localisation, room habit (saved rooms, Match Print collection). Caution: data moats erode alone (a16z, "The Empty Promise of Data Moats").

### 13.1 Positioning tensions and how they resolve (PROPOSED)
- **Two buyers, one spine.** Planks 1–3 of §4.5 serve the couch; plank 5 serves the broadcaster. Never let both speak at once: the video is couch-first, the README enterprise section broadcaster-first. Frame as **B2B2C**: the couch is the user, the broadcaster is the customer, the open `overlay_card` format is the contract between them.
- **Fan-mechanic social risk (plank 1).** Guardrails are opt-in and never-scored (§4.5); add a **one-tap decline that hands the turn back to Pip**, so declining is frictionless and Pip absorbs the awkwardness — never the fan.
- **Attention framing discipline (plank 3 vs plank 5).** "Attention returned" (viewer-facing) and "dead-air engagement" (broadcaster-facing) are two framings of the same behaviour. Keep them surgically separated in all copy: Pip does not reduce attention to the match; it relocates screen attention from play-time to break-time. Never present "less engagement" to a commercial partner.
- **Diaspora niche counter (plank 2).** Pair the demo scene with one market-size sentence in the README: multilingual, diaspora-heavy audiences are where Premier League viewership growth actually is (SEA, MENA, plus the owner's VI/DE evidence). The scene is the demo; the market sentence is the armour.

### 13.2 Beyond football (PROPOSED — post-hackathon, out of build scope)
Football is Pip's **hardest** timing environment (ball in play ~57 of 90 min) — a companion that respects play here over-delivers anywhere breaks are denser. State this proudly; it is an engineering story, not a limitation.

| Sport | Break density | Fit | Note |
|---|---|---|---|
| Cricket (esp. T20) | Very high | ★★★★★ | Best commercial fit: break-rich, and the multilingual diaspora room (Hindi/Urdu/Bengali/English) is the same wedge as VI/DE/EN — there it is the *median* household, not a niche |
| American football | Extreme | ★★★★ | Break-rich; mixed rooms are the core big-event audience. Crowded second-screen market |
| Baseball / basketball | High | ★★★ | Clock-stop timing is trivial for the Moment Picker |
| Esports | Variable | ★★★ | Mixed-expertise rooms are the norm; no broadcast gatekeeper — fastest route to real users post-hackathon |
| Tennis / cycling / F1 | Low | ★★ | Question density drops below the ritual threshold |

- **What ports (~sport-agnostic):** the ritual, room infrastructure, timing engine, card format, checker/fact_ids pipeline. **Per-sport:** generator, reader/suspense model, event schemas. Mascot ports by perch (crossbar → boundary board → stumps).
- **Sequencing thesis:** prove the method in football's hardest timing environment; commercialize in cricket's easiest. That is the investor pitch in one line.

### 13.3 Revenue models (PROPOSED — post-hackathon, ranked by realism for a solo founder)
Premise, stated honestly: a consumer companion app does not monetize alone. The buyer is whoever **loses money on dead air** or **wins from household retention**. Every model below is a version of that sentence.

1. **Broadcaster / streamer licensing (B2B2C white label)** — the lead model. Dead-air engagement for linear broadcasters; household-subscription defense for streamers (a multi-viewer account is the subscription unit; a feature valuable to the household's *non*-fans is churn protection). Wedge: card format published free, reference implementation and integration paid.
2. **Sponsored moments** — a brand attached to one "Call it!" moment in dead air; interactive, brand-safe, replaces formats viewers hate. Values question = OPEN Q13. Both answers are good; ambiguity isn't — decide before anyone asks. Refusing publicly is equally valid marketing ("Pip will never sell a moment").
3. **League / federation partnerships** — casual→core conversion is leagues' stated growth KPI (the Two Circles evidence restated as their number). Sell the tested mixed-room method + newcomer-comprehension index. Cricket boards and multi-sport bodies are the natural first calls.
4. **Data products** — the co-prediction dataset (§4.5 plank 4) and a "can a newcomer follow the match" comprehension benchmark, licensed as industry reports. Compounds with every room. Guarded by the §13 caution: data alone is not a moat; data + the design philosophy is.
5. **Education / grassroots / kids** — the no-betting, family-safe stance (§3) pre-approves Pip for a channel most engagement products are banned from by default (schools, youth clubs, academies). Small revenue, large legitimacy, strong CSR story.
6. **OEM / smart TV distribution** — preloaded companion on TV platforms. One README sentence so judges see the distribution thinking; not a near-term line for a solo founder.

**The cheque Pip refuses, on the record:** sportsbooks will want the co-prediction data — room predictions are exactly betting-adjacent signal. A public no (§3's DECIDED principle upgraded into marketing) is the cheapest brand asset Pip can ever buy.

---

## 14. OPEN questions (ask the owner — do not decide)

1. **Name vs repo:** brand is "Pip"; repo is "pippi-the-companion". Is the mascot "Pip" or "Pippi"? Note: "Pippi" is strongly associated with Pippi Longstocking (Astrid Lindgren), a protected character brand — a trademark check is advisable if "Pippi" is used publicly.
2. **LLM provider:** Foundry Local only, Azure OpenAI (if student quota arrives), or both with fallback?
3. **Real-time rooms in the demo:** Web PubSub, polling, or single-device mode only?
4. **Colour clash:** DECIDED — Harbour Lights' blue is #2E7FC4.
5. **Database:** Cosmos DB free tier vs Table Storage (depends on allowed regions after Azure signup).
6. **Which hero moments** get full 10 Hz tracking (proposal: VAR offside check, a corner routine, a substitution, a sprint by the followed player).
7. **Player names:** which locales, and how to screen against real players.
8. **Must-have list (§5.4):** confirm or cut.
9. **Brand (§6):** colours, type and voice are drafts — confirm.
10. **Licences:** MIT (code) + CC BY 4.0 (data)?
11. **CLAUDE.md vs AGENTS.md:** which assistants will work in the repo (Claude Code, Codex, GitHub Copilot)? Keep one shared instruction file or both?
12. **"Convince the room" mechanic (§4.5 plank 1):** build for the demo, or keep as positioning-only wording? The social risk on the fan is the concern — opt-in and never-scored are the proposed guardrails.
13. **Sponsored moments (post-hackathon revenue idea):** a brand paying to attach to a "Call it!" moment in dead air — compatible with the brand-purity stance, or off-limits like betting? Decide before it appears in any pitch material.

---

## 15. Instructions for AI coding assistants working on this repo

- Ask the owner before deciding anything marked PROPOSED or OPEN.
- The owner is a UX designer, not a trained engineer: explain choices in plain language, keep code readable, prefer small, testable steps.
- Every number shown to viewers must come from code, never from an LLM.
- No AI calls at runtime in the hosted app; replay cached, checked outputs.
- Respect the betting, privacy and child-safety rules in §§3, 6, 9 in all code, copy and tests.
- Keep the hosted demo working without the owner's laptop until 2026-11-10.
- Use Microsoft Learn docs (MCP) for Microsoft APIs; verify package versions before pinning.

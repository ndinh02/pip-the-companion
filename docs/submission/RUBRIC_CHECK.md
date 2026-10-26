# Rubric check — Pip vs. what the judges score

Written 2026-10-26 from the code, CI runs and live site as they were that evening. Requirements: `HACKATHON_REQUIREMENTS.md`.
Deadline: 2026-10-27 23:59 PT (2026-10-28 07:59 German time).

---

## 0. Blockers found while checking (read first)

1. **CI is red on `main`, so the live site is two commits behind.** The `Content workflow tests` step fails (run for
   `c25397e`), so the `deploy` job was skipped. The live app still serves the 8-card match from `181fe33`: there's no
   `c9-corner` "No clear answer" moment and no half-time recap on phones (both arrived in `315550f`).
   Cause: `agents/pip_agents/checker.py` doesn't know about void cards. For `c9-corner` (void, `answer: "near"`) the
   reviewed template itself fails two rules:
   - `plain line does not say what happened (expected one of: near)`. A void card should skip this rule.
   - `expert line states a count in words ("again")`. The words "or the corner was taken again" trip `COUNT_WORDS`.

   `run_card` then raises `ValueError("fallback template failed the checker for c9-corner …")`, so every test in
   `agents/tests/test_workflow.py` errors (8/8, reproduced locally with `/usr/bin/python3` 3.9.6). Fix (code, for Claude
   or the owner): teach the checker the void case (skip check 4 and allow this wording, or reword the template), then
   regenerate `data/agent-trace.json` → `web/public/data/agent-trace.json`. That trace is also stale: it has 8 cards, the
   shipped match has 9. Push, and confirm the deploy job ran and that
   `https://…azurewebsites.net/data/match.json` lists 9 cards.
2. **The in-app Scan screen can't open the camera on the hosted app.** `web/server/server.mjs` sends
   `Permissions-Policy: camera=()` (confirmed on the live site), which blocks `getUserMedia` on our own origin. *Scan*
   (`web/src/pages/Scan.tsx`) will always fall back to "paste link / type code". Scanning the TV's QR with the phone's
   own camera app still works, because that opens the link directly. Fix: `camera=(self)`, and update the CSP row in
   `SECURITY.md` ("disables camera"). In the meantime, don't show the in-app Scan screen in the video.

---

## 1. Judging criteria (each 20%)

### 1. Technological implementation
**Where we meet it**
- Clear module boundaries: `match-lab/` (generate), `match-reader/` (interpret), `agents/` (write and check), `web/`
  (render), `web/server/` (rooms). JSON Schemas for every file format in `schemas/`.
- Tests: about 140 Python unit tests (`match-lab/tests` 68, `match-reader/tests` 63, `agents/tests` 8), 8 server tests
  (`web/server/server.test.mjs`), added-time tests, a full-match frame-by-frame QA (`scripts/match_qa.py`) on seed 43
  plus five freshly generated seeds, a copy check for banned words and stray numbers (`scripts/check-copy.mjs`), and a
  determinism diagnostic job (`scripts/diag_determinism.py`).
- CI gates the deploy (`.github/workflows/ci.yml`). The server has no dependencies (`web/server/server.mjs`).
- Docs for the owner and for judges: `README.md`, `SECURITY.md`, `docs/TRACKING_SPEC.md`, `docs/MOTION.md`, task specs in `tasks/glm/`.

**Weak**
- CI is red right now (blocker 1).
- Large files: `match-lab/matchlab/tracking.py` has 3,151 lines, `Play.tsx` and `Tv.tsx` about 600 each.
- No browser end-to-end test, even though the brief planned Playwright.
- The Python is written for 3.9, and results drift slightly between Python versions (documented in `tasks/glm/README.md`).
- Leftover modules from earlier designs are no longer used by any screen: `web/src/components/WhosThat.tsx`, `HalfTimeCard.tsx`, `web/src/lib/didYouKnow.ts`. Delete them or say they are kept for later.
- `web/src/pages/Console.tsx` still says "STUB" in its header comment, although it shows the tracking panel, the workflow trace and "Catch me lying".

**Before the deadline**: fix blocker 1 and get CI green. Fix the "STUB" comment. Mention the test counts in the video or description.

### 2. Agentic design & innovation
**Where we meet it**
- A bounded workflow: Moment Picker (rules, `match-reader/matchreader/reader.py`) → Writer → Checker (code,
  `agents/pip_agents/checker.py`) → feedback retry ×2 → fixed template (`agents/pip_agents/workflow.py`).
- Writers get numbers only through logged function tools (`agents/pip_agents/tools.py`), and every draft is recorded in the trace.
- The checker goes beyond facts: it also checks that the line names the real outcome, states the right VAR decision, has
  no counts in words and never grades people.
- Integrity proof, "Catch me lying": sabotaged writers in `agents/pip_agents/writers.py`, shown in `/console` (`web/src/components/WorkflowTrace.tsx`).
- An LLM writer on Foundry Local (`agents/pip_agents/llm_writer.py`). Trial in `data/agent-trace-llm.json`: 8
  moments (re-run 2026-10-26 on the current 9-card match): 5 passed on the first try, 9 approved from the model, 0 fell
  back to the template, 146 s. Some approved lines are still weak in ways the rules can't see ("2th", an expert line off
  the outcome, the void corner described as "near the post"): good material for "why templates ship".

**Weak (be upfront about it)**
- There's one writer and one checker. It's a workflow with a repair loop, not multi-agent collaboration.
- **Microsoft Agent Framework is not used** (it needs Python 3.10 or newer, and the code targets 3.9). Neither are
  Azure OpenAI, A2A or Foundry Agent Service. The brief's "Mascot Host" re-voicing agent for DE/VI isn't built: DE/VI lines are reviewed templates.
- The shipped match uses the template writer (`uses_ai: false`). AI-written lines haven't shipped yet.
- "Best Multi-Agent Orchestration" and "Best Use of Microsoft Foundry" are not realistic targets. That matches the
  owner's chosen targets (Enterprise and Cloud Native).

**Before the deadline**: in the video, show the `/console` trace and "Catch me lying" (15 s), and state the design in one
sentence: "AI drafts, code decides, nothing unchecked reaches a viewer". Optionally re-run the Foundry Local trial on
the current 9-card match after blocker 1, so the trial and the shipped match agree. Don't claim Agent Framework.

### 3. Real-world impact & applicability
**Where we meet it**
- A clear audience: a mixed room with one fan and several newcomers. Shared screen plus phones, no install, no account.
- Production-minded runtime: no model at match time, so there's nothing to rate-limit or inject. An open card format (`schemas/overlay_card.schema.json`).
- Privacy and safety rules that are actually enforced (`SECURITY.md`, `web/server/rooms.mjs` validation, banned words in CI).
- Resilience: Resume room after the TV tab closes, recovery after a server restart (tested in `server.test.mjs`), the TV
  connection alarm, phone status overlays.

**Weak**
- Single instance, rooms in memory, App Service **Free F1**. F1 has a daily CPU quota and goes to sleep. With polling
  every 0.7 s (TV) and 1 s (phones), several judges at once could use up the quota. Check the quota in the Azure portal.
- Same-room only: no stream-delay handling for remote viewers (OPEN Q14, decided as post-hackathon).
- No user-test results are published. The brief's §4 evidence figures are third-party and unverified here, so don't
  quote numbers you can't source.

**Before the deadline**: in the description, say plainly what scaling out would need (shared state, e.g. Azure Web PubSub). That's already written in `PROJECT_PAGE.md`.

### 4. User experience & presentation
**Where we meet it**
- The full flow is built: TV home → Start a room → lobby (QR, code, room name you can tap to change) → Kick off; phone →
  join → animal → Match / My player / Room tabs (`web/src/pages/*`).
- First-time host controls: Kick off / Pause / Next moment / ? / More (`web/src/pages/Tv.tsx`, lines ~548–592).
- Two-depth reveals, "Why?", chat history, "No clear answer", earlier calls marked "before you joined" for latecomers, chime and keep-awake options,
  `prefers-reduced-motion`. The mascot is the owner's own artwork (`web/public/pip/`).
- A balanced frontend and backend: three.js stadium and replays on one side, a real data pipeline and room server on the other.

**Weak**
- The demo video doesn't exist yet. The judges stop at 2:00.
- The live site lacks the latest features (blocker 1), and in-app Scan is broken live (blocker 2).
- DE/VI copy is marked as a draft until the owner checks it (AGENTS.md).

**Before the deadline**: record the video on the **hosted** app with one laptop and two real phones, one in German and
one in Vietnamese, at the same reveal. Suggested beats: room start (10 s) → phones join (15 s) → question → answers →
reveal + Why? (35 s) → My player (15 s) → "No clear answer" or half-time recap (15 s) → `/console` "Catch me lying" (15 s)
→ architecture slide with Azure App Service + GitHub Actions + Foundry Local (15 s). Use no music, or music you have the rights to.

### 5. Adherence to the category
**Where we meet it**: synthetic data only, a five-stage pipeline (table in `PROJECT_PAGE.md`), multi-language, explanations of why moments matter.
**Weak**: "Ingest as they happen" is a replay of pre-generated files on a match clock, not a live event stream. The
explanations focus on set pieces, substitutions and VAR; tactical "control vs chaos" or pressure changes are not
explained. Say "replayed on the match clock, with tests that no fact looks ahead (`match-reader/tests/test_no_future.py`)" rather than "real-time feed".

---

## 2. Challenge feature list (i)–(vi)

| Item | Status | Evidence | Gap / what to say |
|---|---|---|---|
| (i)a Ingest | Partial | `match-lab/matchlab/generator.py` (events incl. pass, dribble, tackle, interception, cross, shot, save, foul, set pieces, card, substitution, VAR), `tracking.py` (5 Hz) | Pre-generated and replayed, not streamed. No explicit pressure events or possession-change events. |
| (i)b Interpret | Yes | `match-reader/matchreader/reader.py` (facts per moment), `players.py` (per-minute stats), `scripts/added_time.py` | Facts are set-piece habits and player physicals, with no team-level pattern analytics. |
| (i)c Explain | Yes | Cards with plain + expert lines, the VAR explainer, the added-time breakdown (`web/src/components/AddedBreakdown.tsx`), "No clear answer" | Template copy, reviewed by the owner. |
| (i)d Render | Yes | `web/src/components/Stadium3D.tsx`, TV card, phone screens, `schemas/overlay_card.schema.json` | — |
| (i)e Personalize | Yes | Language per phone, plain/expert depth, follow a player, your own calls in the history | No favourite-club mode. No explicit "analyst mode" switch: the depth is per reveal ("Why?"). |
| (ii) Real-time intelligence | Partial | Player marked in every camera, speed and distance (`LiveStats.tsx`), sprints over 25 km/h, fastest run, passes completed | No ball or shot speed shown, no pass difficulty rating (a `hard_ok` count exists in `players.py`), no video auto-eventing (out of scope: no video). |
| (iii) Narrative | Partial | Half-time and full-time recaps on phones, conversation history, goal scorer spotlight on the TV | No generated match recap story or milestones. |
| (iv) Explainability | Partial | The why behind each reveal; VAR decision and margin; added time by cause | No "control vs chaos" or tempo explainer. |
| (v) Data innovation | Yes | Seeded generator + tracking synthesizer + frame-level QA + schemas | No published dataset card or licence for the data (see checklist). |
| (vi) Multi-language | Yes | EN/DE/VI for all UI and card text (`web/src/lib/i18n.ts`, `match-reader/templates/cards.json`), banned words in three languages | DE/VI are drafts until the owner checks them. No AI re-voicing. |

---

## 3. Missing for submission

### Must do (before 2026-10-27 23:59 PT)
- [ ] **Fix CI and redeploy** (blocker 1). Then check that the live `data/match.json` has 9 cards.
- [ ] **Fix the camera policy** (blocker 2), or at least keep the in-app Scan screen out of the video.
- [ ] **Demo video under 2:00** (1:55) is ready and also hosted on GitHub Pages, but the rules need a **public YouTube/Vimeo URL**: upload it and replace `<YOUTUBE_URL>`. Open-source voice (Kokoro-82M, Apache 2.0) and self-synthesised music: no copyrighted music.
- [ ] **Project image** for the form (Pip artwork + TV screenshot; no PL or Microsoft logos).
- [ ] **Fill in the form**: title, tagline, keywords, challenge, description (all in `PROJECT_PAGE.md`), then add the repo URL after saving.
- [ ] **Test the hosted app once on a phone over mobile data** (not Wi-Fi) the day you submit.
- [ ] **Decide the licence and add a `LICENSE` file.** There's none in the repo now. AGENTS.md proposes MIT for code and CC BY 4.0 for data, unconfirmed (OPEN Q10). A public repo with no licence means "all rights reserved".
- [ ] **Keep the demo awake through judging.** `.github/workflows/keep-awake.yml` stops pinging after 2026-11-11, but
  winners are announced 2026-11-20. Also, GitHub ran the "every 10 minutes" schedule only about every 6 hours today, so
  judges may hit a cold start. Decide whether to extend the date (AGENTS.md rule 7 says until 2026-11-10). Consider
  App Service "Always On", which F1 doesn't offer.

### Checked: OK
- Repo is public (https://github.com/ndinh02/pip-the-companion returns 200; the old `pippi-the-companion` URL redirects).
- No secrets in the tree or history (searched for keys, passwords and publish profiles). The deploy uses the `AZURE_WEBAPP_PUBLISH_PROFILE` GitHub secret.
- `.env*` files are git-ignored. No `.DS_Store` is tracked.
- No club badges or real players. Crests are original (`web/src/components/Crest.tsx`). The competition is named "Fictional League".
- README updated to the current flow (this pass).

### Nice to have
- Add a repo description and topics on GitHub (both empty now). Pin the live URL in the "About" box.
- **German copy:** the committed `main` has "Richtig getippt!" and "Pip tippte auf / Pip tippt auf", the verb forms of the
  banned "Tipp". The copy check only matches the whole word, so they pass. Uncommitted edits in the working tree (made by
  someone else while I was checking) already change them to "Du lagst richtig!", "Pip sagte" and "Pip meint". Commit
  those with the CI fix so the live app gets them.
- Update the `SECURITY.md` "Status: 2026-10-14" line and the live-headers note (headers are now confirmed on the live site).
- `docs/PROJECT_BRIEF.md` still says the repo is `pip-the-companion` and still plans Static Web Apps, Web PubSub and
  Cosmos DB. It's marked PROPOSED, but a judge may read it as claims. A one-line note at the top pointing to README for
  what's built would help (owner's call).
- Re-run the Foundry Local trial on the current match and show one AI-approved line in the video.
- A "how judges can test it" GIF in the README.
- `docs/design-options/` and the character-sheet SVGs are untracked. Decide whether they belong in the public repo.

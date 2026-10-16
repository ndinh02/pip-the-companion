# Pip — next steps

Updated: 2026-10-14  
Purpose: turn the current prototype into a credible, testable hackathon submission before the feature freeze on 2026-10-24.

## The judge's priority

Pip already has a distinctive product idea, working synthetic match data, fact-checked cards, 5 Hz player/ball tracking, and a polished TV/phone prototype. The main risks are not visual polish: they are proof of the two prize claims.

1. **Can a judge open and test it without Nhi's laptop?**
2. **Can a judge see a bounded agent workflow produce and check a card?**
3. **Can a judge see a real room work across separate devices?**

Do these before adding new features.

## P0 — unblock submission and hosted-demo proof

Complete these first.

- [x] **Fix the Git repository boundary.** Done 2026-10-14: project has its own repository (one local commit); the stray repo in the home folder was removed. Not pushed yet. The project folder currently resolves to a Git repository at `/Users/admin`, rather than having its own repository metadata. Confirm that `pippi-the-companion` is an independent repository, contains the project files, has a clean history, and is pushed to its required public GitHub URL.
- [x] **Register for the hackathon** — done 2026-10-15.
- [x] **Create the Azure account/subscription** — Azure for Students verified 2026-10-15. Still to record: chosen region and any Student subscription restrictions.
- [ ] **Deploy the web app** to Azure Static Web Apps (or an owner-approved equivalent). Test the public URL in a private browser window and keep it available through 2026-11-10.
- [x] **Add a minimal CI workflow.** Written (`.github/workflows/ci.yml`); runs once pushed. On each push: web type-check/build, copy check, Match Lab tests, and Match Reader tests. On `main`: deploy the static app.
- [x] **Add baseline hosting security.** `web/public/staticwebapp.config.json`; untested until deployed. Include `staticwebapp.config.json` with a Content Security Policy and sensible security headers. Do not add secrets to the repository.
- [x] **Update the README** (hosted URL still to add) with the hosted URL, exact local run steps, what is implemented today, synthetic-data notice, and a short architecture diagram.

### Definition of done

A fresh browser can open the public URL, complete the demo without any local software, and the GitHub repository shows reproducible build instructions.

## P1 — demonstrate the agentic workflow honestly

The brief's agent design is strong; it needs one working, inspectable vertical slice. Do not imply an agent exists until it does.

- [ ] Decide the LLM route with the owner: Foundry Local, Azure OpenAI in Foundry, or both with a fallback. This is OPEN question 2.
- [ ] Build one bounded content workflow:
  1. Read only code-computed facts through tools/functions.
  2. Produce one English question and one explanation with `fact_ids` and placeholders.
  3. Run the existing copy/fact/schema checks.
  4. Demonstrate a rejected incorrect claim and template or retry fallback.
  5. Save only approved, pre-generated cards for runtime replay.
- [ ] Show the trace in `/console`: input facts, fire/hold decision, checker result, and final approved card.
- [ ] Build the **"Catch me lying"** proof: intentionally corrupt one stat, visibly fail the checker, then restore the checked output. The product must never send the corrupted result to viewers.
- [ ] Add a small repeatable evaluation set: at least several moments in EN, DE, and VI, with reported numeric-faithfulness, banned-word, schema, and no-repeat results.

### Definition of done

A judge can watch one generated card travel from checked facts through the bounded workflow to the pre-generated match file, including a visible rejection path.

## P2 — turn the same-browser mock into a real room

The existing `BroadcastChannel` transport is a good single-device fallback, but it does not connect separate phones.

- [ ] Ask the owner to choose the demo transport: Azure Web PubSub, polling, or single-device-only fallback (OPEN question 3).
- [ ] Keep `web/src/lib/channel.ts` as the one transport boundary, so the TV and phone screens do not need a redesign.
- [ ] If Web PubSub is chosen, implement only the minimum messages: join, current state, answer, and follow/unfollow.
- [ ] Server-validate room codes, known answer IDs, known player IDs, and message size/rate limits.
- [ ] Store only the privacy-approved temporary data. No names, free text, accounts, tracking across matches, or viewer profiles.
- [ ] Test TV + two physically separate phones on different networks/browsers.

### Definition of done

Two phones can join one hosted TV room, make different calls, see the shared tally, and follow players without exposing an identity on the TV.

## P3 — close the core competition pipeline

The required pipeline is nearly represented already. Make the evidence explicit.

| Required stage | Current evidence | Next proof needed |
| --- | --- | --- |
| Ingest synthetic events | Seeded Match Lab data | Explain its replay/live-event interface in the README/demo |
| Interpret | Match Reader facts, player metrics, tracking | Show derived facts in the console |
| Explain | Checked template cards | Add the bounded agent/checker demonstration |
| Render | TV lower-third, phone, console | Test at TV-sized 1080p and record it |
| Personalise | Language and Follow player | Clearly demonstrate casual/expert depth and per-phone language |

- [ ] Keep every visible number code-filled from `facts` or tracking data; never let model text invent a number.
- [ ] Keep the no-betting check in CI and run it on every generated match file.
- [ ] Confirm DE/VI copy with the owner. Until checked, visibly keep it marked as draft in source/review material.
- [x] Resolve documentation drift: name is **Pip** (2026-10-16), team blue `#2E7FC4`, build status in README.
- [ ] Add `SECURITY.md`: threat model, no-free-text decision, room-code validation, rate limits, expiry, and integrity-demo behavior.

## P4 — gather evidence that the product helps a room

- [ ] Run the planned paper test with two mixed-expertise groups. Check that newcomers can answer within five seconds and do not interpret it as betting.
- [ ] Run 3–5 consented mixed-room build tests after the feature freeze.
- [ ] Record only the approved measures: completion/skip, newcomer share of talk, intrusiveness, enjoyment, comprehension, comfort being wrong, SUS, and phone-down time during open play.
- [ ] Report results honestly, including null or negative results. Do not claim production uplift.
- [ ] If owner-approved, export only sufficiently aggregated co-prediction data; do not retain personal notes or raw event data beyond the stated retention policy.

## P5 — demo video and presentation

Target: a public video under two minutes that shows the app running.

Suggested story:

1. **0–15 s — problem:** one fan and newcomers watch together; existing commentary serves only the expert.
2. **15–45 s — ritual:** TV triggers a dead-ball "Call it!" moment; phones answer; the room tally appears.
3. **45–70 s — explanation:** reveal the plain and "Go deeper" explanation, both tied to checked facts.
4. **70–95 s — personalisation:** show German/Vietnamese/English on phones and a followed synthetic player on the pitch.
5. **95–115 s — credibility:** console trace and the "Catch me lying" checker rejection.
6. **115–120 s — enterprise close:** privacy-first, synthetic, broadcast-renderable card format, hosted Azure delivery.

Do not present unbuilt Azure, multi-agent, extension, or live-room capabilities as complete. A small working proof is stronger than a large roadmap.

## Deliberately defer

Do not build these before P0–P3 are demonstrably complete:

- Match Print
- Browser extension
- Smart lights / haptics
- Cross-room features
- Always-on chat or free-text input
- Real-world camera or microphone sensing
- Real-footage or real-player tracking

## Future roadmap: multi-camera player tracking

This is technically feasible, but it is **not** appropriate for the current synthetic-data hackathon build.

For a licensed broadcaster or stadium deployment:

```text
Calibrated camera feeds
  → player and ball detection per camera
  → tracking within each view
  → pitch-coordinate mapping and cross-camera identity matching
  → stable player ID, position, speed, and confidence
  → phone selects team + shirt number
  → TV/phone marks that known player
```

Important constraints:

- The phone selects a known player ID; it does not perform the tracking itself.
- Reliable identity requires calibrated cameras, jersey/identity association, occlusion handling, and broadcaster/stadium rights.
- A phone watching a TV broadcast cannot access the broadcaster's camera feeds.
- For Pip's hackathon demo, a safer future-facing proof is to render multiple **synthetic virtual camera views** from the existing tracking data and keep the selected player highlighted across those views.


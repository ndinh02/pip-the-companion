# Inside the Game: Developer Hackathon — what the judges ask for

Transcribed by Claude on 2026-10-26 from the owner's screenshots of the Innovation Studio pages
(`~/Downloads/Inside The Game Hackathon.docx`). Hosted by Microsoft with the Premier League. Dates: Sep 29 – Nov 21, 2026.
**Submissions close October 27** (brief: 23:59 PT = 2026-10-28 07:59 German time). Winners announced November 20.

## Challenge we enter
**The Synthetic Match Insights Engine for Premier League Studio** — "An AI insights engine runs on Azure that explains the
game beyond the stats, turning football events into real-time insights, key narratives and recaps — personalized for
every fan, for studio and streaming use." Projects must use **synthetic, football-realistic data** (no real PL data).

(i) One pipeline with five stages. The project should:
- (a) **Ingest** synthetic match events as they happen (passes, shots, tackles, possession changes, pressure events, metadata).
- (b) **Interpret** them into meaningful football statistics, patterns and the context behind them.
- (c) **Explain** why a moment matters rather than only reporting that it happened.
- (d) **Render** that insight into something that can sit on screen alongside the match.
- (e) **Personalize** it so a data-hungry analyst and a casual fan get genuinely different experiences (modes, favourite
  club, favourite player, player-focused mode, language preference…). "A Project that only generates metrics has no
  audience, and a solution that only personalizes has nothing to personalize."

(ii) Real-time match intelligence — features to consider: player identification (name tagging, speed/distance
indicators at thresholds); pass quality (distance, accuracy, difficulty rating); speed metrics (ball speed, shot speed);
auto-eventing (a model over a video feed).
(iii) Narrative generation: key narratives, player-performance context, milestones, match recaps.
(iv) Explainability: why moments matter (control vs chaos, tactical pressure changes, game rhythm).
(v) Data innovation: create or extend synthetic football-realistic datasets.
(vi) Multi-language storytelling for global studio and streaming scenarios.

## What to submit
- A newly built project that meets the requirements.
- A **project pitch / description**: short elevator pitch — what we built, **which Microsoft and Azure technologies we
  used**, what it does, what problem it solves.
- A **demonstration video**: **under 2 minutes** (judges stop at 2:00); shows the project **functioning on the device and
  platform it was built for**; **public URL** on YouTube, Vimeo, Facebook Video or Youku, on the project page; **no
  third-party trademarks or copyrighted music** without permission.
- A URL to the **public GitHub repository** (repo must be public): https://github.com/ndinh02/pip-the-companion

### Project page form fields
Title* (max 140 chars) · Image/Video (added after saving) · Tagline* (max 300 chars) · Keywords* (tags) · Description
(Markdown) · Challenge* = "The Synthetic Match Insights Engine for Premier League Studio" · Writing code: Yes · Code
repository (added after saving) · Skills needed / open to join (optional).

## Judging rubric (each 20%)
1. **Technological implementation** — quality software practices, effective use of hero technologies, well-structured,
   documented, maintainable code.
2. **Agentic design & innovation** — creative agentic AI patterns, sophisticated orchestration / multi-agent
   collaboration, novel AI or meaningful improvements.
3. **Real-world impact & applicability** — significance of the problem, production deployment readiness, potential impact
   on developers, businesses or end users.
4. **User experience & presentation** — well-designed intuitive UX, clear communication of value in the demo, balanced
   frontend and backend.
5. **Adherence to the hackathon category** — complies with the description of the chosen category.

## Prize categories
Grand prize (1st, 2nd) — best overall, real-world impact, innovative use of the Microsoft AI platform; **Best Use of
Microsoft Foundry**; **Best Enterprise Solution** (enterprise readiness, reliability, transparency, controls); **Best
Multi-Agent Orchestration** (GitHub Copilot, Microsoft Agent Framework, A2A…: distinct roles, shared state, handoffs,
recovery from failures); **Best Azure Cloud Native Integration** (AKS, Container Apps, Functions, Logic Apps, AI-optimized
data platforms: scalable, resilient, event-driven, automation, operational excellence). Owner's targets (AGENTS.md):
Best Enterprise Solution + Best Azure Cloud Native Integration.

## Policies
Hackathon Rules https://aka.ms/insidethegame/rules · Code of Conduct · Security Policy · Skilling playlist
https://aka.ms/aisn/hack

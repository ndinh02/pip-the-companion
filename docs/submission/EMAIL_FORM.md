# Submission email — ready to paste

Plain text, so it reads the same in any mail program. All links point at the public GitHub repository, which hosts
the video and the images (the form allows that).

---

Project Details

Title: Pip - A matchday companion that turns a synthetic match into checked, multilingual "Call it!" moments for the whole room

Image/Video:
Demo video (1:55): https://github.com/ndinh02/pip-the-companion/blob/main/docs/submission/video/pip-demo.mp4
Cover image: https://github.com/ndinh02/pip-the-companion/blob/main/docs/submission/video/cover.png

Tagline: Watch together. Call it together. At every dead ball, Pip asks the room one question on their phones. The synthetic match answers, and Pip explains why: a plain line for newcomers, a data line for fans, in English, German or Vietnamese.

Keywords: synthetic-data, football-analytics, explainable-ai, second-screen, multilingual, player-tracking, azure-app-service, foundry-local, github-actions, react, threejs, privacy-by-design

Description:
Most people who watch football with a fan are not fans yet, and most "AI commentary" talks to one viewer. Pip is built for the room: one fan, a few newcomers, one TV, everyone's phone.

How it works: open the TV page and start a room; phones join by QR code, pick an animal (no names, no accounts) and a language (EN, DE, VI). A synthetic match plays on the TV in 3D. At each dead ball (corner, free kick, substitution, VAR check) Pip, a small club-neutral bird, asks one question on every phone. The match answers, the TV highlights the outcome, and each phone explains why: a plain line for newcomers and a data line for fans. When the match does not settle the question, Pip says "No clear answer". Phones also keep the chat history, a half-time and full-time recap, and "My player": follow one player with live per-minute stats, the running path and the fastest run.

The five stages: Ingest (a seeded generator writes a full match of events, and a tracking synthesizer simulates 22 players and the ball at 5 Hz), Interpret (facts and per-player stats computed in code, tested so nothing uses future events), Explain (a bounded agent workflow: moment picker, writer, code checker that recomputes every number and blocks betting words in three languages, up to two retries with the checker's feedback, then a reviewed template), Render (three.js TV view and phone screens, from an open JSON card format), Personalize (language, plain or expert depth, followed player).

Microsoft technologies: Azure App Service hosts the app and the room server; GitHub Actions runs the tests, a full-match QA on six seeds and the copy checks, and deploys only when everything passes; Foundry Local (qwen2.5-7b) was trialled as the AI writer through the same checker (9 of 9 moments approved, 5 first try). The shipped match still uses the checked templates.

Responsible by design: no AI at runtime (text is written and checked before the match), every number comes from code, no betting, no names, accounts, free text, analytics or cookies. All teams, players and data are synthetic.

Live app: https://pip-the-companion-cjcdawd7gmf8f9h2.francecentral-01.azurewebsites.net/tv (the first visit can take up to a minute to wake up)
Full write-up: https://github.com/ndinh02/pip-the-companion/blob/main/docs/submission/PROJECT_PAGE.md

Code Repository: https://github.com/ndinh02/pip-the-companion

---

Built for the Microsoft "Inside the Game" hackathon. Not affiliated with or endorsed by the Premier League or Microsoft.

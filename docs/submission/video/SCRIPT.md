# Pip: demo video script and shot list

Files in this folder:

| File | What it is |
|---|---|
| `pip-demo.mp4` | Narrated version: open-source voice Kokoro-82M ("af_heart", Apache 2.0, run locally) over a quiet music bed that ducks under the voice. 1920×1080, H.264 High, 30 fps, AAC, −16 LUFS. 1:54.8 |
| `pip-demo-music-only.mp4` | The same picture with the music bed only, no voice (captions carry the story). 1:54.8 |
| `pip-demo-captions-only.mp4` | The same picture with a silent audio track. 1:54.8 |
| `cover.png` / `cover-1280.png` | Project image (1920×1080 / 1280×720): real TV and phone screenshots, "Pip", tagline |
| `stills/*.png` | Key moments for the project page (TV and phone side by side, plus a few phone-only shots and the /console trace) |

All footage is the real app. It was built with `npm run build` and served by `web/server/server.mjs` on localhost, so the
room server was real too. One browser page ran as the TV (1280×720) and a second, separate page ran as a phone (390×844,
mobile, touch). Both were driven live and screen-recorded at the same time. The edit cuts dead time and speeds up a few
stretches (marked ×N below). No UI state was mocked. The title, "under the hood" and closing cards are made for the
video, and the closing card says so in its own words.

Audio: the voice is Kokoro-82M (Apache 2.0 model weights, generated offline on this Mac). The music is our own: a short
Python script synthesises it note by note (pad, plucked arpeggio, soft beat), with no samples or third-party tracks, so
there is no copyrighted music.

All app shots come from one continuous session (room AV3S, "The Living Room Terrace"), in the order shown. Between the
moments, the TV's **Next moment** button and, after the 23' free kick, **More → Full match** were used so the match
didn't jump ahead while the phone was being shown. Those button presses are cut out.

Rubric key: **UX** = user experience & presentation · **Impact** = real-world impact · **Tech** = technological
implementation · **Agentic** = agentic design · **Fit** = challenge fit (ingest → interpret → explain → render → personalize).

## Shot list

| Time | Shot (what is on screen) | On-screen caption | Narration (starts at) | Rubric |
|---|---|---|---|---|
| 0:00–0:07 | Title card: Pip waving, "One fan. Friends new to football. One TV." | (card text) | 0:00 "One fan, a few friends who are new to football, and one TV. Pip helps the match make sense for the whole room." | Impact, UX |
| 0:07–0:13 | TV home → **Start a room** → lobby with QR, code, room name; tap the name to change it (×1.4) | JOIN · *no app · no account* — Start a room on the TV: QR code, room code, room name. | 0:07 "Start a room on the TV. Each phone scans the code, picks a language and an animal. No app, no account, no names. Then, kick off." | UX, Impact |
| 0:13–0:20 | Phone opens the room link: animal screen switches DE → VI → EN, "another animal", **Join**; the animal appears in the TV lobby (×1.6) | JOIN — Each phone picks a language (EN · DE · VI) and an animal. No names. | (continues) | UX, Fit: personalize |
| 0:20–0:23 | TV **Kick off**; phone shows the live header (score, MM:SS clock) | KICK OFF · *ingest* — A fully synthetic match plays on the TV, in 3D. | (continues) | Fit: ingest, render |
| 0:23–0:29 | Corner at 14': the TV card "Corner! Where's it going?" with counts; the same question on the phone with four tiles | CALL IT! · *interpret · render* — Ball goes dead: Pip asks one question on the TV and every phone. | 0:23 "At a dead ball, Pip asks one question, on the TV and on every phone. The TV only shows how many have answered." | UX, Fit |
| 0:29–0:32 | Phone taps **Far post** → "Locked in"; TV collapses to "✓ 1/1 answered" | CALL IT! — Answer on the phone. The TV only shows counts: 1/1 answered. | (continues) | UX |
| 0:32–0:35 | Play restarts, the corner is taken in 3D | THE MATCH ANSWERS · *explain* — Play restarts. The corner goes to the far post… | 0:31 "Then the match answers. The TV marks the outcome. My phone says I called it, with a plain explanation, and a data line for fans who want more." | Fit: render |
| 0:35–0:45 | TV: replay, Far post ticked with its count, plain line. Phone: "You called it!", plain line, **Go deeper** opens the data line ("Harbour Lights have played 0 of their 3 corners short today…") | THE MATCH ANSWERS · *explain* — TV marks the outcome. Phone: You called it! Plain line, plus a data line for fans. | (continues) | Fit: explain, UX |
| 0:45–0:49 | Phone Room tab → language **DE**; the chat history re-voices in German (×1.3) | PERSONALIZE · *per phone* — Each phone has its own language. This one switches to German. | 0:45 "Every phone is personal. This one switched to German." | Fit: personalize |
| 0:49–0:53 | Free kick at 23' answered in German: "Du lagst richtig!", Flanke, "Mehr Details" | PERSONALIZE — Same moment, same checked facts, now in German. | — | Fit: personalize |
| 0:53–1:04 | My player: team list → Harbour Lights #9 → 3D character → **Diesem Spieler folgen** → stats (distance, top speed, passes, goals), "Werte, Stand 23'", Laufweg (last five minutes), fastest run; the TV marks the followed player with a star (×2) | MY PLAYER · *personalize* — Follow one player: 3D character, live stats "as of" the minute, running path, fastest run. | 0:53 "Under My player, I follow one player: a 3D character, live stats as of this minute, the running path, and the fastest run." | Fit: personalize, Tech |
| 1:04–1:07 | Chat history in Vietnamese: each question, the room's pick, "Bạn đoán đúng!", "Vì sao?" | PERSONALIZE — The chat keeps every moment and who picked what (here in Vietnamese). | 1:04 "The chat keeps every moment, and who picked what." | UX, Fit |
| 1:07–1:12 | Half-time: TV shows only a small chip ("The room's calls are on your phones"); the phone shows the half-time recap | LIVE · *half-time* — Half-time: the TV stays clear (ad time). The recap goes to the phones. | 1:07 "At half-time, the TV stays clear, and the recap goes to the phones. The clock stays in step on both screens." | UX, Impact |
| 1:12–1:15 | Second half: the TV clock and the phone clock run in step (45:0x) | LIVE · *in sync* — Second half. The MM:SS clock runs in step on TV and phone. | (continues) | Tech |
| 1:15–1:19 | The TV tab is closed (TV area: "TV tab closed"); after ten seconds the phone shows "The TV has gone quiet" (×3.4) | RELIABLE · *recovery* — TV tab closed: the phone says "The TV has gone quiet." | 1:15 "If the TV tab closes, the phone says so, and the TV resumes the same room." | Tech, Impact (Enterprise) |
| 1:19–1:23 | TV reopened: "Welcome back… **Resume room**"; the match carries on, the phone clears its overlay (×1.7) | RELIABLE · *recovery* — Reopen the TV: Resume room carries on with the same room and clock. | (continues) | Tech |
| 1:23–1:29 | 90+3, the corner (card c9) is headed away: TV and phone both say **No clear answer**, "The defence headed it away before it reached anyone." | HONEST · *explain* — 90+3, corner cleared before anyone got it: No clear answer. Counts for no one. | 1:23 "And when the match doesn't settle a question, Pip says so: no clear answer." | Agentic, Fit: explain |
| 1:29–1:50 | Under-the-hood card, built up in four steps: Ingest (generator, 5 Hz tracking) → Interpret (facts, question cards) → Explain (writer + checker workflow, retry ×2 → fixed template) → Render (TV + phones) → Personalize (EN/DE/VI, plain/data, followed player); "No AI at runtime", Azure App Service + GitHub Actions, Foundry Local trial; a screenshot of the /console workflow trace | (card text) | 1:29 "Under the hood: a synthetic match with five-hertz tracking becomes facts and question cards. A writer drafts each line, and a checker recomputes every number and blocks betting words, with a safe fallback. No AI runs during the match. It's hosted on Azure App Service, deployed by GitHub Actions, and the AI writer was trialled with Foundry Local." | Tech, Agentic, Fit |
| 1:50–1:55 | Closing card: Pip, "Watch together. Call it together.", live URL, repo URL, "All teams, players and data are synthetic." | (card text) | 1:50 "Pip. Watch together. Call it together." | Presentation |

## Narration only (for re-recording)

Read calmly. Each line has to finish before the next timecode. Total speaking time is about 85 seconds.

1. **0:00** One fan, a few friends who are new to football, and one TV. Pip helps the match make sense for the whole room.
2. **0:07** Start a room on the TV. Each phone scans the code, picks a language and an animal. No app, no account, no names. Then, kick off.
3. **0:23** At a dead ball, Pip asks one question, on the TV and on every phone. The TV only shows how many have answered.
4. **0:31** Then the match answers. The TV marks the outcome. My phone says I called it, with a plain explanation, and a data line for fans who want more.
5. **0:45** Every phone is personal. This one switched to German.
6. **0:53** Under My player, I follow one player: a 3D character, live stats as of this minute, the running path, and the fastest run.
7. **1:04** The chat keeps every moment, and who picked what.
8. **1:07** At half-time, the TV stays clear, and the recap goes to the phones. The clock stays in step on both screens.
9. **1:15** If the TV tab closes, the phone says so, and the TV resumes the same room.
10. **1:23** And when the match doesn't settle a question, Pip says so: no clear answer.
11. **1:29** Under the hood: a synthetic match with five-hertz tracking becomes facts and question cards. A writer drafts each line, and a checker recomputes every number and blocks betting words, with a safe fallback. No AI runs during the match. It's hosted on Azure App Service, deployed by GitHub Actions, and the AI writer was trialled with Foundry Local.
12. **1:50** Pip. Watch together. Call it together.

To swap in your own voice: record one file, then mix it under the captions-only video, for example
`ffmpeg -i pip-demo-captions-only.mp4 -i my-voice.wav -map 0:v -map 1:a -c:v copy -c:a aac -shortest pip-demo-myvoice.mp4`.

## Where the video is hosted

The chosen cut, `pip-demo.mp4` (Kokoro voice + music), is committed to the repository; the submission form allows
GitHub for all assets. GitHub Pages serves `docs/` from `main`, so it plays in the browser at https://ndinh02.github.io/pip-the-companion/
(`docs/index.html`). The plain GitHub file page cannot play a file this size; it only offers a download. The music-only and captions-only cuts stay local and are not committed.

A YouTube upload is optional. If you want one: upload `pip-demo.mp4` as **Public**, with `youtube-thumbnail.png` as
the thumbnail, title `Pip: watch together, call it together (Inside the Game hackathon demo)`.

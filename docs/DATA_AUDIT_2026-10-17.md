# Seed 43 tracking audit (web/public/data/tracking.json + data/tracked-seed-43.json)

Audit by a Claude subagent on 2026-10-17 (read-only). Ranked by how visible each problem is to a viewer.
`web/public/data/tracking.json` is byte-identical to `data/tracking-seed-43.json`.
Directions verified: HAR-1 mean x 11.0 m (P1) / 90.5 m (P2); COP-1 91.3 / 10.9. So HAR attacks +x in P1, -x in P2.
Clock: P1 frames beyond 45:00 shown as 45+m:ss; P2 = 45:00 + time since P2 start.

## Ranked by how visible it is

### 1. Shots fly into the goal frame, then the ball vanishes. Saves, blocks and goals all look the same (owner report 2)
Every non-goal shot at the frame is drawn flying straight at the goal and set to -1 about 1–7 m before the line. Nothing deflects it and no keeper catches it. Goals vanish the same way, 2.2 m out, so a viewer can't tell a goal from a save.

Extrapolated from the last visible frame (posts y 30.34–37.66, bar 2.44 m):

| time | event | ball last seen | would cross line at | visually a goal? | defending keeper |
|---|---|---|---|---|---|
| 12:55 | COP-10 shot **blocked** | (0.9, 33.6) z 1.0 | y 37.1, z 1.9 | **yes** | HAR-1 4.9 m away |
| 13:47 | HAR-10 shot **blocked** | (104.5, 37.4) z 1.4 | y 34.9, z 1.6 | **yes** | COP-1 7.7 m away |
| 57:48 | HAR-9 header **blocked** | (2.3, 27.9) z 0.6 | y 32.1, z 1.1 | **yes** | COP-1 9.4 m |
| 59:42 | HAR-11 shot **blocked** | (7.4, 31.9) z 0.7 | y 30.4, z 0.9 | **yes** | COP-1 2.3 m |
| 61:00 | COP-9 shot **saved** | (101.0, 29.1) z 0.6 | y 31.5, z 1.1 | **yes** | HAR-1 1.6 m |
| 62:16 | COP-9 header **blocked** | (102.3, 36.5) z 0.8 | y 34.0, z 1.5 | **yes** | HAR-1 8.6 m |
| 72:04 | COP-6 header **saved** | (102.0, 28.9) z 0.7 | y 33.3, z 1.3 | **yes** | HAR-1 2.2 m |
| 82:33 | HAR-9 header **saved** | (6.2, 33.1) z 0.8 | y 35.1, z 1.5 | **yes** | COP-1 6.6 m |
| 22:45 | HAR-3 shot blocked | (103.3, 35.7) z 0.6 | y 30.3 (post), z 0.9 | borderline | COP-1 7.6 m |
| 15:06 | COP-10 shot saved | rolls slowly to (12.0, 30.7) | never reaches goal | no | HAR-1 6.9 m |

- **The ball is never in a keeper's hands.** After 61:00, 72:04 and 82:33 the ball is -1 for 0.2–6.6 s and then reappears lying on the goal-kick spot. Nothing in the tracking shows a catch or a parry.
- **A saved shot leads to a goal kick** (61:15, 82:46), not a corner or a keeper's ball. After 72:04 a substitution follows, then a goal kick at 72:58.
- **All 4 `keeper_save` events are at the wrong goal** (known issue, still true). 15:08 says HAR-1 at x 104, but HAR-1 is at (5.6, 33.2). 61:01 says x 1.0, keeper at (99.5, 29.3). 72:05 says x 1.0, keeper at (99.4, 29.4). 82:34 COP-1 says x 104, keeper at (5.2, 38.1).
- **15:06:** the shooter COP-10 is 17.1 m from the ball when the shot event fires. The ball never reaches goal, then teleports to the corner flag (0.3, 0.7) 16.6 s later for a short corner.
- **All 13 off-target shots aim between the posts** (event end y 30.1–36.6). They miss only by going 0.3–1.2 m over the bar (extrapolated z 2.7–3.6 m). The ball vanishes 1–3.6 m out while still at z 1.4–3.0, so at 18:15, 68:25, 76:21, 83:05 and 90+1:42 it is still at or below bar height when it disappears. Viewers may read those as goals too. Full list: 0:30, 18:15, 26:18, 27:29, 39:21, 43:24, 51:26, 68:25, 76:21 (FK), 81:05, 83:05, 88:51, 90+1:42.

### 2. The ball disappears: 80 hidden spells, about 12 minutes in total (owner report 1)
Breakdown of the 80 runs of ball = -1:

| class | count | hidden time | verdict |
|---|---|---|---|
| Out of play (throw-in / corner / goal kick next), ball vanishes **mid-pitch** before reaching a line | 41 of 50 (29 vanish >10 m from any line, 14 >20 m) | median 12.5 s each, max 30.6 s | **bug** |
| Out of play, vanishes within 5 m of a line | 9 | | acceptable |
| After a shot (13 off target, 4 saved, 6 blocked, 1 FK) | 24 | | see section 1 |
| After a goal (1:53, 73:38) | 2 | 11.2 s, 8.2 s | known: vanishes 2.2 m short |
| **Open play, ball teleports** | 5 | | **bug** |
| End of P1 (45+3:28), substitution flicker (55:57, 0.6 s, same spot) | 2 | | harmless |

**Open-play disappearances (bugs):**
- 12:55: blocked shot. Ball gone 0.6 s at the goal line, then reappears 34.1 m away at (33.4, 43.9) and play goes on.
- 13:08: successful back pass. Ball gone 1.2 s, then reappears 24.0 m away at the next passer.
- 22:46: blocked shot. Gone 0.6 s, reappears 31.4 m away at (72.4, 41.5).
- 57:48: blocked header. Gone 0.8 s, reappears 33.4 m away at (32.9, 41.2).
- 59:43: blocked shot. Gone 2.8 s, reappears 34.7 m away at (24.7, 62.0).

These are effectively 120–170 m/s jumps across a gap. No visible frame-to-frame step exceeds 40 m/s (0 cases).

**Mid-pitch vanishes before a restart (worst cases).** Cause: a "failed" pass ends inside the pitch, the ball is set to -1 right there, and it reappears on the line for the restart.
- 57:08: 33.4 m from line, hidden 10.2 s.
- 19:30: 31.6 m, 13.2 s.
- 32:38: 31.1 m, 0.8 s, then sits on the touchline 14 s.
- 28:11: 29.7 m.
- 89:38: 29.6 m.
- 48:48: 28.7 m.
- 77:54: 28.2 m.
- 6:17: 26.8 m.
- 66:13: 26.2 m.
- 13:20: 26.1 m.
- 8:56: 26.0 m, 17.6 s.
- 45:28: 25.7 m.
- 40:15: ball vanishes at (7.4, 31.0) and reappears 41.3 m away for a throw-in.
- 65:51: a free-kick cross vanishes in mid-air at (13.0, 36.1), z 3.2, 13 m from goal, and a goal kick follows.

**Goal kicks from the wrong spot** (7 of 24): 6:15 (1.7, 52.0), 34:10 (91.9, 6.9), 45+2:09 (99.7, 2.2), 56:52 (96.3, 33.9), 71:00 (99.7, 1.7), 86:09 (92.5, 43.6), and 67:42 (101.8, 32.5), just outside the goal area. They are taken where a failed pass ended inside the pitch.

### 3. The ball travels 90 m on its own at 75:05–76:20 (new finding)
- A foul at 75:04 at (7.1, 31.2).
- The ball then rolls unattended along y = 31.2 to x = 97.9, the coordinate given for the 75:05 substitution events, at about 3.4 m/s.
- It then rolls back to about x 10 for the 76:21 free kick at (7.1, 31.2).
- Nobody is within 3 m of it for 17.2 s plus 12 s plus 3.6 s.
- Meanwhile HAR-9, HAR-10, HAR-11, COP-3 and COP-5 stand perfectly still near (5–9, 31) for 37–44 s.

Cause: substitution events carry a pitch position and the ball is routed to it. The other subs at 55:57, 62:17 and 72:06 happened to coincide with dead balls.

### 4. Keepers (owner report 3)
- **HAR-1 and COP-1 are never -1.** Both are on the pitch for all 29,589 frames.
- **5:00–15:00:** HAR-1 stays within 15.0 m of its own line (max at 8:44). COP-1 stays within 17.0 m (max at 8:54). Neither overlaps another player (no 1 m contact lasting more than 1 s). So the tracking does **not** explain "no HAR keeper at around 10 min".
- **Likely real cause, in the renderer:** `web/src/lib/animals.ts` gives `KEEPER_KIT.HAR` the primary colour `#3FAE5A` (green). The grass stripes in `Stadium3D.tsx` are `#2c7a3f` / `#2f8445`, so the HAR keeper is camouflaged against the pitch. Around 6:49–9:14 play is mostly near HAR's goal, so the keeper should be in shot.
- **Known wandering confirmed:**
  - HAR-1 is more than 35 m out 4.5 % (P1) / 9.4 % (P2) of the time; COP-1 6.8 % / 3.9 %.
  - In the opposition half: 412 + 778 frames for HAR-1, 446 + 311 for COP-1.
  - Worst trips: HAR-1 82:06–83:02 (56 s, 87.5 m out at (17.5, 50.9)); HAR-1 22:20–23:11 (82.7 m); COP-1 20:49–21:45 (78.7 m); both keepers 45:00–45:37 (87 m, wrong ends).
- **New: at kick-offs after goals the conceding keeper stands at the centre spot.** At 4:15 COP-1 is at (52.9, 36.5), 52 m from goal (from 3:53 to 4:30). At 74:12 HAR-1 is at (52.9, 36.5) (from 73:51 to 74:27).

### 5. Substitutions (6 events)

| time | team | off → on | substitute appears | player going off leaves at |
|---|---|---|---|---|
| 55:57 | HAR | HAR-8 → HAR-13 | 55:57 at (52.3, 0) | 56:07, at (59.5, 67.2) |
| 62:17 | COP | COP-9 → COP-12 | 62:17 at (52.3, 0) | 62:38 |
| 72:06 | HAR | HAR-6 → HAR-12 | 72:06 at halfway touchline | 72:19 |
| 72:06 | HAR | HAR-3 → HAR-14 | 72:06 at halfway touchline | 72:24 |
| 75:05 | COP | COP-6 → COP-13 | 75:05 at halfway touchline | 75:19, at (20.6, 0.9) |
| 75:05 | COP | COP-8 → COP-14 | 75:05 at halfway touchline | 75:19 |

- Substitutes appear at the right time on the halfway touchline.
- Nobody reappears after being taken off.
- **Too many players:** the player going off stays on for 10–21 s after the substitute enters. HAR has 12–13 players on the pitch for 10.0 s (55:57) and 18.2 s (72:06); COP has 12–13 for 21.2 s (62:17) and 14.2 s (75:05). In total that is 318 frames with more than 11 players on a team.
- Players going off walk to whichever touchline is nearest, often the far side from where the substitute came on.

### 6. Other wonky things
- **match.json is stale** (dated Oct 16 05:01; tracking 23:34). `score_timeline` names HAR-10 as the 1:52 scorer, but the event is a HAR-11 header. It names COP-6 for 73:37, but the event is a COP-11 header. Stadium3D's goal celebration uses these ids, so the wrong player does the scorer celebration.
- **Known kick-off issues confirmed:**
  - 4:15: COP-2 at (47.1, 32.5) and COP-6 at (35.1, 64.0) are in the wrong half.
  - 74:12: HAR-2 at (40.5, 19.6) and HAR-5 at (44.8, 13.4) are in the wrong half.
  - 45:00: 11 players are in the wrong half and both keepers are 87 m from their own goal.
- **Frozen statues:**
  - 2:05–3:45 (VAR): COP-10, HAR-3, HAR-7 and COP-9 stand perfectly still for about 100 s at the centre circle.
  - 58:00–59:17 (injury): 7 players are frozen for 62–77 s, several of them standing exactly on the touchline (y = 0.0).
  - Both are dead balls but look robotic.
  - In open play the only freeze is 75:09–75:52 (section 3).
  - COP-1 stands still 70 s (75:12–76:22) while the ball rolls the length of the pitch.
- **Overlaps under 0.5 m for 3 s or more:** 8 cases, 119 s in total.
  - HAR-10 and COP-3 for 40.2 s at 75:12.
  - HAR-4 and HAR-7 for 22.6 s at 29:50, at (21.4, 37.8).
  - HAR-1 and HAR-3 for 14.6 s at 56:08.
  - HAR-2 and COP-9 for 13.6 s at 45+0:36, on the touchline.
  - Smaller ones on the touchline at throw-ins.
  - The renderer's `separate()` nudge hides some of these.
- **Ball unattended (nobody within 3 m) for more than 3 s:**
  - 11 spells. The moving ones are 75:13 (17.2 s), 75:57 (12 s), 14:59–15:09 (10 s, a pass chain where receivers are 6.5 m from the ball) and 17:15 (6.2 s).
  - The rest are a ball waiting at a set piece (46:02, 22:57, 20:45, 22:17, 82:03).
- **Ball-to-actor distance at event frames:** median 0.5 m. 203 of 1,454 events are more than 2 m off and 30 are more than 5 m off. Worst: 15:06 shot 17.1 m, 17:16 pass 12.8 m, 15:01 pass 12.4 m.
- **Clean:** no player moves faster than 12 m/s, nobody stands outside the pitch, and the ball is never visible outside the pitch.

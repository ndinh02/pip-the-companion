# Tracking system — spec (2026-10-13)

> Status: owner asked for a tracking system (2026-10-13). Direction **decided**; presentation details marked PROPOSED. Replaces the "modelled stats" idea in `docs/SCOPE_WHOS_THAT.md` §2 (distance, top speed and sprints are now **computed from synthetic tracking**).

## 1. Why
Without positions there is nothing to show on the TV or laptop and nothing to follow. With synthetic tracking of all 22 players and the ball:
- the TV pitch becomes the match picture (today it is an empty pitch with one marker);
- speed, distance and sprints are real computations, consistent with what is drawn;
- **Follow** has a job (§4);
- the half-time "ghost run" and the full-time Match Print (brief §5.4) become possible.

## 2. Pipeline
```
match-lab  generate_match(seed)          events (as today, unchanged)
match-lab  tracking synthesizer (04)     tracked match (events with final player_id) + tracking file
match-reader  players feed (05)          data/players.json (counted + tracking-derived stats)
match-reader  build                      data/demo-match.json (cards; read from the tracked match)
web                                      TV pitch, phone follow views, laptop console
```
**Why events get new `player_id`s:** the generator picks the acting player at random by position, with no idea where players stand, so two events seconds apart can name players 60 m apart. The synthesizer simulates the 22 bodies first and then names the **nearest feasible teammate** as the actor. Everything else in an event (`idx`, `t_ms`, `team_id`, `type`, `subtype`, `start`, `end`, `outcome`, `set_piece`) stays identical, so team-level facts, cards and added time do not change. (Yellow/second-yellow cards are recomputed on the new ids.)

## 3. File format — `data/tracking-seed-N.json` (`schemas/tracking.schema.json`)
```json
{
  "match_id": "synthetic-seed-43", "seed": 43, "tracking_version": "...",
  "hz": 5, "unit": "dm",
  "periods": [ {"id": 1, "start_ms": 0, "frames": 14250}, {"id": 2, "start_ms": 2872000, "frames": 14400} ],
  "entities": ["ball", "HAR-1", "...", "COP-14"],
  "x": { "ball": [1125, 1130, "..."], "HAR-1": [ "..." ] },
  "y": { "ball": [...], "HAR-1": [...] }
}
```
- Uniform **5 Hz** (one frame every 200 ms), both periods back to back; frame *i* of period *p* is at `periods[p].start_ms + 200·i`. Array index = (frames of earlier periods) + *i*. All arrays have `sum(frames)` entries.
- **Decimetres** (int): x 0–1050, y 0–680, same coordinate system as the events (`coord_system` in the match file). **−1 = not on the pitch** (bench, substituted off, sent off).
- 29 entities: the ball, then `HAR-1..14`, `COP-1..14`. 2D only.
- Size ≈ 28k frames × 29 × 2 ≈ 1.6 M integers ≈ 8 MB as JSON, about 1.1 MB gzipped (the App Service server compresses it). Only the TV and laptop need it; the phone fetches it lazily when the viewer follows someone.
- The synthesizer runs its physics at **10 Hz** internally and stores every second frame. 10 Hz windows around the question moments (brief: "hero moments") can be added later without changing the format idea (not in v1).

## 4. What each screen does with it  (PROPOSED — owner to confirm)
| Screen | Use |
|---|---|
| **TV** | Pitch draws the 22 players in kit colours + the ball. During the demo's fast clock the dots are shown calm (positions at the current minute, no trails). When a **reveal** shows, the pitch plays that moment back in **real time** (~10 s before to ~5 s after, "replay player") with the acting player ringed. A small halo marks players followed by phones in the room, with an anonymous count ("2 following"); no identities (AGENTS.md rule 6). |
| **Phone** | Stays dark during open play ("Eyes up"). Follow gives, **at breaks only**: "your player" mini-map (position + last minutes' path), their sprints/distance, and at half-time the **ghost run** — a replay of their fastest sprint. |
| **Laptop console / side panel** | Expert view, always on: full pitch, click any player (or the followed one) → live speed, distance, sprints, trail, plus the same stats table. |

Follow therefore means: *my player is highlighted for the room, I get a personal break card, and the half-time card tells me what they did.* Stored on the device only.

## 5. Calibration targets (published ranges, brief §8.1)
Outfield distance 8.5–12.3 km per 90; goalkeepers 4.5–7.0 km; top speed ≤ 37 km/h with the fastest player of a match at ~34–37; sprint = speed > 25 km/h (≈ 6.94 m/s) held ≥ 1 s; outfield sprints per 90 plausible (5–35).

## 6. Fallback if the synthesizer is not calibrated by **Oct 17**
Keep the counted stats (task 05 without the physical part), keep positions only for the 10 s windows around the 8 question moments, and show the modelled numbers labelled as modelled. The format above does not change.

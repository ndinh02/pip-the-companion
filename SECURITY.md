# Security and privacy

Status: describes the prototype as built on 2026-10-14, and marks what is planned but not built.

## What the app handles
- **No accounts, no names, no email, no free text.** Viewers only tap buttons.
- **Synthetic match data only.** Nothing about real people is in the data files.
- **Per device, in the browser only:** a random device id (session storage, gone when the tab closes) and the followed player id (local storage). Neither leaves the browser except as described below.

## Threat model
| Risk | How it is handled |
|---|---|
| A viewer injects text or markup into a shared screen | There is no text input anywhere. Phones send only `hello`, `answer` (a known card id and a known option id) and `follow` (a known player id or nothing). The shared screen ignores any option id not on the current card and any player id not in the tracking file. |
| Prompt injection into an AI model | No model runs while viewers use the app. Text is written and checked before the match, then replayed from files. The content workflow never receives viewer input. |
| An AI writer invents a number or uses betting language | Every draft goes through a code checker: facts are recomputed from the match events and must match, digits outside `{placeholders}` are rejected, banned words (EN / DE / VI) are rejected, the card must fit the schema. After two failed retries a fixed template is used. The "Catch me lying" view in `/console` replays a sabotaged run to show this. |
| Tampered match files | Files are built by code in this repository and checked in CI on every push (tests, copy check). |
| Someone guesses a room code | Today rooms exist only inside one browser, so there is nothing to join remotely. **Planned with real rooms:** server-side validation of room codes, answer ids and player ids; message size and rate limits; rooms that expire after the match. |
| Identifying who follows which player | The shared screen keeps a count per player only and shows no identity. |
| Cross-site attacks on the hosted app | `web/public/staticwebapp.config.json` sets a Content Security Policy (scripts, fonts and connections from the same origin only; no framing), `nosniff`, no referrer, and disables camera, microphone and location. **Not yet tested on a live deployment.** |
| Secrets in the repository | None are needed to run the app. The only secret is the Azure deployment token, stored as a GitHub Actions secret. |

## Not collected
No analytics, no cookies, no IP logging by the app, no tracking across matches, no viewer profiles.

## Reporting a problem
Open an issue on the GitHub repository, or contact the owner through their GitHub profile. Please do not include personal data in a report.

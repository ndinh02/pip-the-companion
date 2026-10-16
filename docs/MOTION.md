# How the 3D players move (2026-10-16)

The 3D view draws the 5 Hz synthetic tracking with cute animal characters. Research brief (web research by an agent, 2026-10-16) and what we applied. EA's internals are not public; claims about FIFA/FC come from EA marketing and press.

## What real football looks like (numbers we tune against)
| Measure | Value | Source |
|---|---|---|
| High-speed running / sprint thresholds | 5.5–7.0 m/s / > 7.0 m/s | https://jhk.termedia.pl/Sprint-and-High-Speed-Running-in-Soccer-Should-We-Use-Absolute-or-Normalized-Thresholds,209540,0,2.html |
| Walk → run transition | ~2.0 m/s, ~140 steps/min | https://pmc.ncbi.nlm.nih.gov/articles/PMC8629136 |
| Sprint step frequency / length (pros) | 4.5–4.7 Hz, 1.86–1.98 m at 8.3–9.3 m/s; ~4.4 Hz, ~1.2 m early acceleration | https://pmc.ncbi.nlm.nih.gov/articles/PMC12047830/ |
| Peak match speed | 8.1–8.8 m/s | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11694206/ |
| Acceleration / deceleration | high-intensity > 2.5–3 m/s²; peaks ~2.7 / 3.6 m/s²; > 4 m/s² decel is "high" | https://www.mdpi.com/2076-3417/12/24/12987 , https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10170543/ |
| Time per activity (top players) | standing 19.5 %, walking 41.8 %, jogging 16.7 %, running 16.8 %, sprinting 1.4 % | Mohr et al. 2003, via https://pmc.ncbi.nlm.nih.gov/articles/PMC3778701 |
| Why feet slide / characters spin | animation speed out of step with movement; over-eager rotation | https://theorangeduck.com/page/code-vs-data-driven-displacement |
| Motion matching (industry technique) | pick the motion that fits the pose and desired trajectory | https://gdcvault.com/play/1022985/Motion-Matching-and-The-Road |
| Smooth paths without overshoot | centripetal Catmull-Rom (alpha 0.5) | https://cemyuksel.com/research/catmullrom_param/ |
| Collision avoidance in games | separation steering; ORCA/RVO2 | https://gamma.cs.unc.edu/RVO2/documentation/2.0/index.html |

## What the renderer does (`web/src/components/locomotion.ts`)
- **Paths:** centripetal Catmull-Rom through the 5 Hz samples (stays within ~7 cm of the straight segment, no loops).
- **Speed:** eased like a spring with acceleration ≤ 5 m/s² and braking ≤ 6.5 m/s².
- **Gait:** the cycle advances by distance ÷ step length, with step length from the research table (0.8 m at 2 m/s, 1.2 m at 5, 1.9 m at 8.5), so the rhythm is human: ~2.6 steps/s walking briskly, ~4.5 at a sprint. Idle pose below 0.3 m/s.
- **Facing:** face the ball below 2 m/s, the run above 4 m/s, blended between; turning rate-limited (420°/s slow, 260°/s fast) with a dead-band, so small shuffles do not spin the body. Side-steps and backpedalling swing the legs sideways / backwards instead.
- **Lean** into the run (up to ~14°), only when moving forwards.
- **Personal space (visual only):** bodies closer than 1.3 m are nudged apart, never more than 0.5 m from their true position (overlaps: 1.11 → 0.01 per frame on seed 43).

## What still needs the data to change (GLM task 06, requirement 7)
The synthetic tracking jogs too much: seed 43 has standing 22 %, walking 28 %, **jogging 46 %**, running 3 %, high-speed 0.6 %, sprinting 0.7 %. Real football walks much more and runs more often. No renderer can fix that; the synthesizer must.

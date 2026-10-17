"""Full-match QA: scans every frame of a match's tracking for the things a viewer notices.

    /usr/bin/python3 scripts/match_qa.py                      # seed 43 (data/tracked-seed-43.json + tracking)
    /usr/bin/python3 scripts/match_qa.py --events E.json --tracking T.json

Each check prints how many times it fails and the worst examples (match clock mm:ss). Exit code 1 if any check
fails. GLM task 08 is done when this prints no failures for seed 43 (and seeds 1-5). Python 3.9, stdlib only.

Owner reports this covers (2026-10-17): "the ball sometimes disappears", "sometimes the goalkeeper is not there",
"the ball goes in the goal but nothing happens", "no animation of the keeper catching it", players frozen.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
L, W = 105.0, 68.0
POSTS = (30.34, 37.66)
BAR_M = 2.44
GOAL_AREA_DEPTH, GOAL_AREA_Y = 5.5, (24.84, 43.16)
RESTARTS = {"throw_in", "corner", "goal_kick", "free_kick", "kick_off", "drop_ball", "penalty"}


class Match:
    def __init__(self, events_path: str, tracking_path: str) -> None:
        with open(events_path, encoding="utf-8") as fh:
            self.m = json.load(fh)
        with open(tracking_path, encoding="utf-8") as fh:
            self.t = json.load(fh)
        self.hz = self.t["hz"]
        self.dt = 1.0 / self.hz
        self.periods = self.t["periods"]
        self.n = len(self.t["x"]["ball"])
        self.players = [e for e in self.t["entities"] if e != "ball"]
        self.z = self.t.get("z", {}).get("ball")
        # which x each team defends, per period (from the keepers' average position)
        self.own_x: Dict[Tuple[str, int], float] = {}
        off = 0
        for p in self.periods:
            for team in ("HAR", "COP"):
                xs = [self.x(team + "-1", i) for i in range(off, off + p["frames"]) if self.on(team + "-1", i)]
                avg = sum(xs) / len(xs) if xs else 0
                self.own_x[(team, p["id"])] = 0.0 if avg < L / 2 else L
            off += p["frames"]

    # positions in metres; None when not on the pitch
    def x(self, e: str, i: int) -> float:
        return self.t["x"][e][i] / 10.0

    def y(self, e: str, i: int) -> float:
        return self.t["y"][e][i] / 10.0

    def on(self, e: str, i: int) -> bool:
        v = self.t["x"][e][i]
        return v is not None and v >= 0

    def bz(self, i: int) -> float:
        return max(0.0, self.z[i] / 10.0) if self.z else 0.0

    def frame(self, t_ms: float) -> int:
        off = 0
        for p in self.periods:
            end = p["start_ms"] + p["frames"] * 1000 / self.hz
            if t_ms < end:
                return off + max(0, min(p["frames"] - 1, int(round((t_ms - p["start_ms"]) * self.hz / 1000))))
            off += p["frames"]
        return self.n - 1

    def period_of(self, i: int) -> int:
        off = 0
        for p in self.periods:
            if i < off + p["frames"]:
                return p["id"]
            off += p["frames"]
        return self.periods[-1]["id"]

    def clock(self, i: int) -> str:
        off = 0
        for p in self.periods:
            if i < off + p["frames"]:
                s = (i - off) / self.hz + (0 if p["id"] == 1 else 45 * 60)
                return "%d:%02d" % (s // 60, s % 60)
            off += p["frames"]
        return "?"

    def dist(self, a: str, b: str, i: int) -> float:
        return math.hypot(self.x(a, i) - self.x(b, i), self.y(a, i) - self.y(b, i))

    def ball_dist(self, e: str, i: int) -> float:
        if not (self.on(e, i) and self.on("ball", i)):
            return float("inf")
        return math.hypot(self.x(e, i) - self.x("ball", i), self.y(e, i) - self.y("ball", i))

    def line_gap(self, i: int) -> float:
        """Distance of the ball from the nearest touchline or goal line (m)."""
        bx, by = self.x("ball", i), self.y("ball", i)
        return min(bx, L - bx, by, W - by)


Result = Tuple[str, int, List[str]]


def hidden_spells(mt: Match) -> List[Tuple[int, int]]:
    out, i = [], 0
    while i < mt.n:
        if not mt.on("ball", i):
            j = i
            while j < mt.n and not mt.on("ball", j):
                j += 1
            out.append((i, j))  # [i, j) hidden
            i = j
        else:
            i += 1
    return out


def next_event(mt: Match, t_ms: float) -> Optional[dict]:
    for e in mt.m["events"]:
        if e["t_ms"] >= t_ms:
            return e
    return None


def check_ball_vanishes_mid_pitch(mt: Match) -> Result:
    bad = []
    for i, j in hidden_spells(mt):
        if i == 0 or not mt.on("ball", i - 1):
            continue
        gap = mt.line_gap(i - 1)
        # in the goal mouth after a goal it may vanish only once in the net (checked separately)
        if gap > 2.0:
            bad.append((gap, "%s ball hidden %.1f m inside the pitch for %.1f s" % (mt.clock(i), gap, (j - i) * mt.dt)))
    bad.sort(reverse=True)
    return ("ball disappears inside the pitch", len(bad), [b[1] for b in bad[:8]])


def check_ball_teleports(mt: Match) -> Result:
    bad = []
    restart_frames = {mt.frame(e["t_ms"]) for e in mt.m["events"] if e["type"] in RESTARTS or e.get("subtype") == "kick_off"}
    for i, j in hidden_spells(mt):
        if i == 0 or j >= mt.n or not mt.on("ball", i - 1):
            continue
        jump = math.hypot(mt.x("ball", j) - mt.x("ball", i - 1), mt.y("ball", j) - mt.y("ball", i - 1))
        near_restart = any(abs(f - j) <= 3 * mt.hz for f in restart_frames)
        if jump > 12 and not near_restart:
            bad.append((jump, "%s ball reappears %.0f m away after %.1f s hidden" % (mt.clock(j), jump, (j - i) * mt.dt)))
    for i in range(1, mt.n):
        if mt.on("ball", i) and mt.on("ball", i - 1) and mt.period_of(i) == mt.period_of(i - 1):
            v = math.hypot(mt.x("ball", i) - mt.x("ball", i - 1), mt.y("ball", i) - mt.y("ball", i - 1)) / mt.dt
            if v > 40:
                bad.append((v, "%s ball moves at %.0f m/s" % (mt.clock(i), v)))
    bad.sort(reverse=True)
    return ("ball jumps / teleports", len(bad), [b[1] for b in bad[:8]])


def _crossing(mt: Match, start: int, horizon_s: float = 3.0) -> Optional[Tuple[int, float, float]]:
    """First frame after `start` where the ball is on/over a goal line: (frame, y, z). Extrapolates over a hide."""
    for i in range(start, min(mt.n, start + int(horizon_s * mt.hz))):
        if not mt.on("ball", i):
            # vanished: extrapolate from the last two visible frames
            if i >= 2 and mt.on("ball", i - 1) and mt.on("ball", i - 2):
                x1, y1, x0, y0 = mt.x("ball", i - 1), mt.y("ball", i - 1), mt.x("ball", i - 2), mt.y("ball", i - 2)
                vx, vy = x1 - x0, y1 - y0
                if abs(vx) > 1e-6:
                    line = 0.0 if vx < 0 else L
                    k = (line - x1) / vx
                    if 0 <= k <= 15:
                        z = mt.bz(i - 1) + (mt.bz(i - 1) - mt.bz(i - 2)) * k
                        return (i, y1 + vy * k, max(0.0, z))
            return None
        bx = mt.x("ball", i)
        if bx <= 0 or bx >= L:
            return (i, mt.y("ball", i), mt.bz(i))
    return None


def check_shots(mt: Match) -> List[Result]:
    goal_not_in, looks_goal, save_no_keeper, off_target_hidden = [], [], [], []
    evs = mt.m["events"]
    for k, e in enumerate(evs):
        if e["type"] != "shot":
            continue
        f = mt.frame(e["t_ms"])
        c = _crossing(mt, f)
        if e.get("outcome") == "goal":
            # the ball must be seen crossing between the posts (not vanish before the line)
            seen = c is not None and mt.on("ball", c[0]) and POSTS[0] <= c[1] <= POSTS[1] and c[2] < BAR_M
            if not seen:
                goal_not_in.append("%s goal by %s: ball never seen crossing the line" % (mt.clock(f), e.get("player_id")))
            continue
        if c and POSTS[0] <= c[1] <= POSTS[1] and c[2] < BAR_M:
            looks_goal.append("%s %s by %s (%s) heads into the goal (y %.1f, z %.1f) with no goal" % (
                mt.clock(f), e.get("subtype") or "shot", e.get("player_id"), e.get("outcome"), c[1], c[2]))
        if c and not mt.on("ball", c[0]) and e.get("outcome") in ("off_target", "wide", "over", "miss"):
            off_target_hidden.append("%s off-target shot hidden before it is seen passing the goal" % mt.clock(f))
    for e in evs:
        if e["type"] != "keeper_save":
            continue
        f = mt.frame(e["t_ms"])
        keeper = e.get("player_id") or ""
        near = min((mt.ball_dist(keeper, i) for i in range(f, min(mt.n, f + 4)) if keeper in mt.t["x"]), default=float("inf"))
        if near > 1.0:
            save_no_keeper.append("%s save by %s: ball never reaches the keeper (closest %.1f m)" % (mt.clock(f), keeper, near))
    return [
        ("goal: ball not seen going in", len(goal_not_in), goal_not_in[:8]),
        ("no-goal shot flies into the goal", len(looks_goal), looks_goal[:8]),
        ("save without the keeper touching the ball", len(save_no_keeper), save_no_keeper[:8]),
        ("off-target shot hidden before the line", len(off_target_hidden), off_target_hidden[:8]),
    ]


def check_keepers(mt: Match) -> List[Result]:
    missing, far, kickoff = [], [], []
    for gk in ("HAR-1", "COP-1"):
        miss = sum(1 for i in range(mt.n) if not mt.on(gk, i))
        if miss:
            missing.append("%s not on the pitch for %.1f s" % (gk, miss * mt.dt))
        i, team = 0, gk[:3]
        while i < mt.n:
            own = mt.own_x[(team, mt.period_of(i))]
            d = abs(mt.x(gk, i) - own) if mt.on(gk, i) else 0
            if d > 30:
                j = i
                while j < mt.n and mt.on(gk, j) and abs(mt.x(gk, j) - mt.own_x[(team, mt.period_of(j))]) > 30:
                    j += 1
                worst = max(abs(mt.x(gk, k) - mt.own_x[(team, mt.period_of(k))]) for k in range(i, j))
                far.append((worst, "%s %s %.0f m from their goal for %.1f s" % (mt.clock(i), gk, worst, (j - i) * mt.dt)))
                i = j
            else:
                i += 1
    for e in mt.m["events"]:
        if e.get("subtype") != "kick_off":
            continue
        f = mt.frame(e["t_ms"])
        for p in mt.players:
            if not mt.on(p, f):
                continue
            own = mt.own_x[(p[:3], mt.period_of(f))]
            own_half = mt.x(p, f) <= L / 2 + 1 if own == 0 else mt.x(p, f) >= L / 2 - 1
            if not own_half:
                kickoff.append("%s kick-off: %s in the wrong half (x %.1f)" % (mt.clock(f), p, mt.x(p, f)))
            if p.endswith("-1") and abs(mt.x(p, f) - own) > 6:
                kickoff.append("%s kick-off: keeper %s not in goal (%.0f m out)" % (mt.clock(f), p, abs(mt.x(p, f) - own)))
    far.sort(reverse=True)
    return [
        ("keeper missing from the pitch", len(missing), missing),
        ("keeper more than 30 m from goal", len(far), [b[1] for b in far[:8]]),
        ("kick-off positions wrong", len(kickoff), kickoff[:8]),
    ]


def check_players(mt: Match) -> List[Result]:
    too_many, statues, overlaps = [], [], []
    for team in ("HAR", "COP"):
        i = 0
        while i < mt.n:
            c = sum(1 for p in mt.players if p.startswith(team) and mt.on(p, i))
            if c > 11:
                j = i
                while j < mt.n and sum(1 for p in mt.players if p.startswith(team) and mt.on(p, j)) > 11:
                    j += 1
                too_many.append("%s %s has %d players for %.1f s" % (mt.clock(i), team, c, (j - i) * mt.dt))
                i = j
            else:
                i += 1
    for p in mt.players:
        run = 0
        for i in range(1, mt.n):
            still = mt.on(p, i) and mt.on(p, i - 1) and mt.t["x"][p][i] == mt.t["x"][p][i - 1] and mt.t["y"][p][i] == mt.t["y"][p][i - 1]
            run = run + 1 if still else 0
            if run == int(20 * mt.hz):
                statues.append("%s %s stands perfectly still for 20 s+" % (mt.clock(i - run), p))
    step = mt.hz  # once per second is enough for overlaps
    pairs: Dict[Tuple[str, str], int] = {}
    for i in range(0, mt.n, step):
        on = [p for p in mt.players if mt.on(p, i)]
        for a in range(len(on)):
            for b in range(a + 1, len(on)):
                key = (on[a], on[b])
                if mt.dist(on[a], on[b], i) < 0.5:
                    pairs[key] = pairs.get(key, 0) + 1
                    if pairs[key] == 3:
                        overlaps.append("%s %s and %s overlap (< 0.5 m) for 3 s+" % (mt.clock(i), on[a], on[b]))
                else:
                    pairs[key] = 0
    return [
        ("more than 11 players on a team", len(too_many), too_many[:8]),
        ("players frozen like statues (20 s+)", len(statues), statues[:8]),
        ("players overlapping 3 s+", len(overlaps), overlaps[:8]),
    ]


def check_actor_at_ball(mt: Match) -> Result:
    bad = []
    total = 0
    for e in mt.m["events"]:
        pid = e.get("player_id")
        if not pid or pid not in mt.t["x"] or e["type"] in ("substitution", "card"):
            continue
        f = mt.frame(e["t_ms"])
        d = min((mt.ball_dist(pid, k) for k in (f, min(mt.n - 1, f + 1))), default=float("inf"))
        if d == float("inf"):
            continue
        total += 1
        if d > 2.0:
            bad.append((d, "%s %s by %s is %.1f m from the ball" % (mt.clock(f), e["type"], pid, d)))
    bad.sort(reverse=True)
    allowed = int(total * 0.02)
    n = max(0, len(bad) - allowed)
    return ("player not at the ball for their action (beyond 2%% allowed: %d of %d)" % (len(bad), total), n, [b[1] for b in bad[:8]])


def check_goal_kicks(mt: Match) -> Result:
    bad = []
    for e in mt.m["events"]:
        if e["type"] != "goal_kick":
            continue
        f = mt.frame(e["t_ms"])
        if not mt.on("ball", f):
            bad.append("%s goal kick: ball not on the pitch" % mt.clock(f))
            continue
        own = mt.own_x[(e["team_id"], mt.period_of(f))]
        bx, by = mt.x("ball", f), mt.y("ball", f)
        inside = abs(bx - own) <= GOAL_AREA_DEPTH + 0.5 and GOAL_AREA_Y[0] - 0.5 <= by <= GOAL_AREA_Y[1] + 0.5
        if not inside:
            bad.append("%s goal kick from (%.1f, %.1f), outside the goal area" % (mt.clock(f), bx, by))
    return ("goal kick outside the goal area", len(bad), bad[:8])


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--events", default=os.path.join(HERE, "..", "data", "tracked-seed-43.json"))
    ap.add_argument("--tracking", default=os.path.join(HERE, "..", "data", "tracking-seed-43.json"))
    args = ap.parse_args(argv)
    mt = Match(args.events, args.tracking)
    results: List[Result] = []
    results.append(check_ball_vanishes_mid_pitch(mt))
    results.append(check_ball_teleports(mt))
    results.extend(check_shots(mt))
    results.extend(check_keepers(mt))
    results.extend(check_players(mt))
    results.append(check_goal_kicks(mt))
    results.append(check_actor_at_ball(mt))
    failed = 0
    print("Full-match QA: %s (%d frames, %.0f min)" % (os.path.basename(args.events), mt.n, mt.n * mt.dt / 60))
    for name, count, examples in results:
        mark = "OK  " if count == 0 else "FAIL"
        print("%s %-62s %d" % (mark, name, count))
        for ex in examples:
            print("       - " + ex)
        failed += count > 0
    print("\n%d of %d checks fail." % (failed, len(results)) if failed else "\nAll %d checks pass." % len(results))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

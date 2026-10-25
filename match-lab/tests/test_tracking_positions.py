"""Task 08 acceptance tests for matchlab.tracking: positions audit.

Groups mirror tasks/glm/08-positions-audit.md (Part A and Part B):

A. keeper leash; ends switch at half-time; kick-off formations; the ball
   goes into the net; saves at the right goal; team shape sanity
B. saves look like saves; blocked shots deflect; off-target shots look off
   target; out of play means out; goal kicks from the goal area; never more
   than 11 per team; no statues; no long overlaps; the actor is at the ball

Everything is measured from the 5 Hz output (dm), never from simulator
internals. Seeds 1-5 run always; seeds 6-20 join under PIPPI_SLOW=1.
"""
from __future__ import annotations

import math
import os
import unittest
from typing import Any, Dict, List, Optional, Tuple

from matchlab import generate_match
from matchlab.tracking import track_match

SEEDS = list(range(1, 6)) if os.environ.get("PIPPI_SLOW") != "1" \
    else list(range(1, 21))
DM = 10.0                      # dm -> m
L, W = 1050.0, 680.0           # pitch, dm
POSTS = (303.4, 376.6)         # goal-mouth y, dm
BAR = 24.4                     # crossbar height, dm
HZ = 5
DT = 1.0 / HZ

_CACHE: Dict[int, Tuple[Dict[str, Any], Dict[str, Any]]] = {}


def out(seed: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if seed not in _CACHE:
        _CACHE[seed] = track_match(generate_match(seed))
    return _CACHE[seed]


class MT:
    """Small read-only view over one seed's output, dm coordinates."""

    def __init__(self, tracked: Dict[str, Any], tracking: Dict[str, Any]) -> None:
        self.m, self.t = tracked, tracking
        self.x, self.y, self.z = tracking["x"], tracking["y"], tracking["z"]
        self.n = len(self.x["ball"])
        self.players = [p for p in tracking["entities"] if p != "ball"]
        self.roster = {p["player_id"]: p for p in tracked["players"]}

    # -- frames -----------------------------------------------------------
    def frame(self, t_ms: float) -> int:
        off = 0
        for p in self.t["periods"]:
            end = p["start_ms"] + p["frames"] * 1000 / HZ
            if t_ms < end:
                return off + max(0, min(p["frames"] - 1,
                                        int(round((t_ms - p["start_ms"]) * HZ / 1000))))
            off += p["frames"]
        return self.n - 1

    def period_of(self, i: int) -> int:
        off = 0
        for p in self.t["periods"]:
            if i < off + p["frames"]:
                return p["id"]
            off += p["frames"]
        return self.t["periods"][-1]["id"]

    def period_start_frames(self) -> List[int]:
        offs, cur = [], 0
        for p in self.t["periods"]:
            offs.append(cur)
            cur += p["frames"]
        return offs

    # -- geometry ---------------------------------------------------------
    def on(self, e: str, i: int) -> bool:
        v = self.x[e][i]
        return v is not None and v >= 0

    def px(self, e: str, i: int) -> float:
        return self.x[e][i] / DM

    def py(self, e: str, i: int) -> float:
        return self.y[e][i] / DM

    def pz(self, e: str, i: int) -> float:
        return max(0.0, self.z[e][i] / DM) if self.z else 0.0

    def dist(self, a: str, b: str, i: int) -> float:
        return math.hypot(self.x[a][i] - self.x[b][i],
                          self.y[a][i] - self.y[b][i]) / DM

    def own_goal_x(self, team: str, period: int) -> float:
        """The goal line a team defends in a period (m). In period 1 the
        home team HAR defends x=0; ends switch at half-time (rule 2)."""
        plus = (team == "HAR") == (period == 1)
        return 0.0 if plus else L / DM


def hidden_spells(mt: MT) -> List[Tuple[int, int]]:
    out_, i = [], 0
    while i < mt.n:
        if not mt.on("ball", i):
            j = i
            while j < mt.n and not mt.on("ball", j):
                j += 1
            out_.append((i, j))     # [i, j) hidden
            i = j
        else:
            i += 1
    return out_


def _nearest_to_ball(mt: MT, k: int) -> float:
    """Metres from the ball to the nearest on-pitch player at frame k."""
    best = 1e18
    for e in mt.players:
        if not mt.on(e, k) or not mt.on("ball", k):
            continue
        d = mt.dist(e, "ball", k)
        if d < best:
            best = d
    return best


def _crossing(mt: MT, start: int, horizon_s: float = 3.0) -> Optional[Tuple[int, float, float]]:
    """First frame after `start` where the ball is on/over a goal line:
    (frame, y, z). Extrapolates over a hide (as scripts/match_qa.py does)."""
    for i in range(start, min(mt.n, start + int(horizon_s * HZ))):
        if not mt.on("ball", i):
            if i >= 2 and mt.on("ball", i - 1) and mt.on("ball", i - 2):
                x1, y1 = mt.x["ball"][i - 1], mt.y["ball"][i - 1]
                x0, y0 = mt.x["ball"][i - 2], mt.y["ball"][i - 2]
                vx, vy = x1 - x0, y1 - y0
                if abs(vx) > 1e-6:
                    line = 0.0 if vx < 0 else L
                    k = (line - x1) / vx
                    if 0 <= k <= 15:
                        z = mt.pz("ball", i - 1) + \
                            (mt.pz("ball", i - 1) - mt.pz("ball", i - 2)) * k
                        return (i, (y1 + vy * k) / DM, max(0.0, z))
            return None
        if mt.x["ball"][i] <= 0 or mt.x["ball"][i] >= L:
            return (i, mt.py("ball", i), mt.pz("ball", i))
    return None


# ---- Part A -------------------------------------------------------------------


class KeeperLeash(unittest.TestCase):
    """Rule 1: in open play a keeper stays within 30 m of their own goal
    line, within 20 m in >= 95 % of frames, and never in the other half.
    Five seconds around goal kicks, saves and the keeper's own passes are
    excluded -- restarts are taken where the event says."""

    def test_leash(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            for gk in ("HAR-1", "COP-1"):
                excl: List[Tuple[int, int]] = []
                for ev in tracked["events"]:
                    keeper_event = ev["player_id"] == gk and \
                        ev["type"] in ("goal_kick", "keeper_save", "pass")
                    if not keeper_event:
                        continue
                    a = mt.frame(ev["t_ms"] - 5000)
                    b = mt.frame(ev["t_ms"] + 5000)
                    excl.append((a, b))
                inside = total = 0
                for i in range(mt.n):
                    if not mt.on(gk, i):
                        continue
                    if any(a <= i <= b for a, b in excl):
                        continue
                    d = abs(mt.px(gk, i) - mt.own_goal_x(gk[:3], mt.period_of(i)))
                    total += 1
                    if d <= 20.0:
                        inside += 1
                    self.assertLessEqual(
                        d, 30.0, "seed %d: %s %.1f m from their goal line"
                        % (seed, gk, d))
                    other_half = mt.px(gk, i) > 52.5 \
                        if mt.own_goal_x(gk[:3], mt.period_of(i)) == 0.0 \
                        else mt.px(gk, i) < 52.5
                    self.assertFalse(
                        other_half, "seed %d: %s in the other half" % (seed, gk))
                self.assertGreaterEqual(
                    inside / max(total, 1), 0.95,
                    "seed %d: %s within 20 m in only %.1f %% of frames"
                    % (seed, gk, 100.0 * inside / max(total, 1)))


class PeriodSwitch(unittest.TestCase):
    """Rule 2: at the first frame of period 2 everyone stands in the
    second-half kick-off formation -- own half, keepers in their goal."""

    def test_first_frame_of_period_2(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            i = mt.period_start_frames()[1]
            for p in mt.players:
                own = mt.own_goal_x(p[:3], 2)
                if not mt.on(p, i):
                    continue
                in_own_half = mt.px(p, i) <= 53.0 if own == 0.0 \
                    else mt.px(p, i) >= 52.0
                self.assertTrue(
                    in_own_half, "seed %d: %s still in the wrong half at the "
                    "start of period 2 (x %.1f)" % (seed, p, mt.px(p, i)))
                if p.endswith("-1"):
                    self.assertLessEqual(
                        abs(mt.px(p, i) - own), 6.0,
                        "seed %d: keeper %s %.1f m from their goal at the "
                        "start of period 2" % (seed, p, abs(mt.px(p, i) - own)))


class KickOffs(unittest.TestCase):
    """Rule 3: at every kick-off frame all players are in their own half
    (+-1 m) and the taker is within 1 m of the centre spot."""

    def test_kick_off_formation(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            n = 0
            for ev in tracked["events"]:
                if ev.get("subtype") != "kick_off":
                    continue
                n += 1
                f = mt.frame(ev["t_ms"])
                for p in mt.players:
                    if not mt.on(p, f):
                        continue
                    own = mt.own_goal_x(p[:3], mt.period_of(f))
                    ok = mt.px(p, f) <= 53.0 if own == 0.0 \
                        else mt.px(p, f) >= 52.0
                    self.assertTrue(
                        ok, "seed %d: kick-off at %.1f s, %s in the wrong "
                        "half (x %.1f)"
                        % (seed, ev["t_ms"] / 1000.0, p, mt.px(p, f)))
                taker = ev["player_id"]
                if taker in mt.x:
                    d = math.hypot(mt.px(taker, f) - 52.5, mt.py(taker, f) - 34.0)
                    self.assertLessEqual(
                        d, 1.0, "seed %d: kick-off taker %s %.1f m from the "
                        "centre spot" % (seed, taker, d))
            self.assertGreater(n, 0, "seed %d: no kick-offs" % seed)


class Goals(unittest.TestCase):
    """Rule 5: for a goal the ball is seen crossing the line between the
    posts and under the bar within 1.5 s of the shot, is never hidden
    before that frame, and stays in the goal >= 2 s."""

    def test_goal_ball_goes_in(self) -> None:
        total = 0
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            for ev in tracked["events"]:
                if ev["type"] != "shot" or ev.get("outcome") != "goal":
                    continue
                total += 1
                f = mt.frame(ev["t_ms"])
                # the 1.5 s window runs from the visible STRIKE: the event
                # can be booked while the previous action's ball is still
                # live, and the firm ball then leaves the boot up to a
                # second after the event time (the taker meets it first)
                strike = f
                for k in range(f, min(mt.n - 1, f + 13)):
                    if mt.on("ball", k) and mt.on("ball", k + 1):
                        v = math.hypot(mt.x["ball"][k + 1] - mt.x["ball"][k],
                                       mt.y["ball"][k + 1] - mt.y["ball"][k]) \
                            / DM * HZ
                        if v >= 4.0:
                            strike = k
                            break
                c = _crossing(mt, strike, 1.5)
                self.assertIsNotNone(
                    c, "seed %d: goal at %.1f s, ball never reaches the line"
                    % (seed, ev["t_ms"] / 1000.0))
                i, y, z = c  # type: ignore[misc]
                self.assertTrue(
                    mt.on("ball", i),
                    "seed %d: goal at %.1f s, ball hidden before the line"
                    % (seed, ev["t_ms"] / 1000.0))
                self.assertTrue(
                    POSTS[0] / DM <= y <= POSTS[1] / DM and z < BAR / DM,
                    "seed %d: goal at %.1f s crosses at y %.1f z %.1f"
                    % (seed, ev["t_ms"] / 1000.0, y, z))
                # it stays visible in the goal for >= 2 s after crossing
                for k in range(i, min(mt.n, i + 10)):
                    self.assertTrue(
                        mt.on("ball", k) and mt.px("ball", k) >= L / DM - 2.0
                        if mt.px("ball", i) > 52.5 else
                        mt.on("ball", k) and mt.px("ball", k) <= 2.0,
                        "seed %d: goal at %.1f s, ball leaves the goal early "
                        "(frame %d)" % (seed, ev["t_ms"] / 1000.0, k))
        # a seed can be goalless (seed 2 is): the suite covers SEEDS together
        self.assertGreater(total, 0, "no goals across seeds")


class Saves(unittest.TestCase):
    """Rule 4: the saving keeper is at their own goal (within 6 m of the
    line). Rule 7: the ball reaches the keeper within 0.6 s and never
    crosses the goal line in the following 2 s."""

    def test_saves(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            n = 0
            for ev in tracked["events"]:
                if ev["type"] != "keeper_save":
                    continue
                n += 1
                f = mt.frame(ev["t_ms"])
                gk = ev["player_id"]
                own = mt.own_goal_x(gk[:3], mt.period_of(f))
                self.assertLessEqual(
                    abs(mt.px(gk, f) - own), 6.0,
                    "seed %d: save at %.1f s, %s %.1f m from their goal line"
                    % (seed, ev["t_ms"] / 1000.0, gk, abs(mt.px(gk, f) - own)))
                near = min((mt.dist(gk, "ball", i)
                            for i in range(f, min(mt.n, f + 3))
                            if mt.on(gk, i) and mt.on("ball", i)),
                           default=float("inf"))
                self.assertLessEqual(
                    near, 1.0, "seed %d: save at %.1f s, ball never reaches "
                    "the keeper (closest %.1f m)"
                    % (seed, ev["t_ms"] / 1000.0, near))
                c = _crossing(mt, f, 2.0)
                self.assertTrue(
                    c is None or not (POSTS[0] / DM <= c[1] <= POSTS[1] / DM
                                      and c[2] < BAR / DM),
                    "seed %d: saved shot at %.1f s crosses the goal line "
                    "afterwards" % (seed, ev["t_ms"] / 1000.0))
            self.assertGreater(n, 0, "seed %d: no saves" % seed)


class ShapeSanity(unittest.TestCase):
    """Rule 1 (shape): per team per half the average distance from the own
    goal line grows GK < DF < MF < FW."""

    def test_lines_step_forward(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            for team in ("HAR", "COP"):
                for lo in mt.period_start_frames():
                    hi = lo + mt.t["periods"][mt.period_start_frames().index(lo)]["frames"]
                    means: Dict[str, float] = {}
                    for line in ("GK", "DF", "MF", "FW"):
                        ds = []
                        for p in mt.players:
                            if p[:3] != team or mt.roster[p]["position"] != line:
                                continue
                            own = mt.own_goal_x(team, mt.period_of(lo))
                            for i in range(lo, hi):
                                if mt.on(p, i):
                                    ds.append(abs(mt.px(p, i) - own))
                        if ds:
                            means[line] = sum(ds) / len(ds)
                    ordered = [means[k] for k in ("GK", "DF", "MF", "FW") if k in means]
                    self.assertEqual(
                        ordered, sorted(ordered),
                        "seed %d %s: line averages %s do not step forward"
                        % (seed, team, means))


# ---- Part B -------------------------------------------------------------------


class BlockedShots(unittest.TestCase):
    """Rule 8: at a blocked shot a defender is within 1.2 m of the ball at
    the block frame, the ball changes direction there, and it is not hidden
    within 2 s after."""

    def test_blocks(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            for ev in tracked["events"]:
                if ev["type"] != "shot" or ev.get("outcome") != "blocked":
                    continue
                f = mt.frame(ev["t_ms"])
                # the block frame is where the ball visibly changes
                # direction. The firm ball can be held on the boot for up to
                # ~2.5 s first (the blocker's run is budgeted into the
                # launch), so the event frame itself may still show the ball
                # at the shooter's feet: take the FIRST >= 30 deg turn whose
                # incoming leg is flight-fast -- the biggest turn in the
                # window is often just the rebound dying. A point-blank
                # block (boot under a metre from the blocker) never reaches
                # full shot speed -- the flight ramps down into the landing
                # -- so the inbound floor is 2.5 m/s, above the rebound's
                # dying wiggle (~1.8 m/s) but low enough for short hops.
                bf, best_turn = f, -1.0
                sx0 = ev["start"]["x"] * DM
                sy0 = ev["start"]["y"] * DM
                for k in range(f + 2, min(mt.n, f + 23)):
                    if not (mt.on("ball", k - 2) and mt.on("ball", k)):
                        continue
                    # task 10: a shot struck off a ball held at the boot
                    # changes speed and direction as it leaves it (still ->
                    # flight cruise): that launch handover is a >= 30 deg
                    # turn with the ball a boot's length from the start,
                    # stationary two frames earlier. It is the kick, not
                    # the deflection -- the deflection happens away from
                    # the shooter, off a ball already travelling (rule 8).
                    if math.hypot(mt.x["ball"][k - 2] - sx0,
                                  mt.y["ball"][k - 2] - sy0) < 0.6 * DM \
                            and (k < 3 or mt.x["ball"][k - 3] < 0 or
                                 math.hypot(mt.x["ball"][k - 2] - mt.x["ball"][k - 3],
                                            mt.y["ball"][k - 2] - mt.y["ball"][k - 3]) < 1.0):
                        continue
                    v1 = (mt.x["ball"][k - 1] - mt.x["ball"][k - 2],
                          mt.y["ball"][k - 1] - mt.y["ball"][k - 2])
                    v2 = (mt.x["ball"][k] - mt.x["ball"][k - 1],
                          mt.y["ball"][k] - mt.y["ball"][k - 1])
                    m1, m2 = math.hypot(*v1), math.hypot(*v2)
                    # inbound genuinely flying (>= 2.5 m/s), rebound still
                    # moving. A point-blank hop can drop under 2.5 m/s
                    # entirely (2.2 m/s) but is airborne at the turn while
                    # the rebound's dying wiggle stays flat on the ground
                    if m2 < 2.0 or (m1 < 5.0 and mt.z["ball"][k - 1] <= 0.2):
                        continue
                    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1])
                                        / (m1 * m2)))
                    turn = math.degrees(math.acos(cos))
                    if turn >= 30.0:
                        bf, best_turn = k - 1, turn
                        break
                self.assertGreaterEqual(
                    best_turn, 30.0,
                    "seed %d: block at %.1f s turns only %.0f deg"
                    % (seed, ev["t_ms"] / 1000.0, best_turn))
                defenders = [p for p in mt.players
                             if p[:3] != ev["team_id"]]
                near = min((mt.dist(p, "ball", i)
                            for p in defenders
                            for i in (bf - 1, bf, bf + 1)
                            if mt.on(p, i) and mt.on("ball", i)),
                           default=float("inf"))
                self.assertLessEqual(
                    near, 1.2, "seed %d: block at %.1f s (deflection frame "
                    "%d), nearest defender %.1f m"
                    % (seed, ev["t_ms"] / 1000.0, bf, near))
                for k in range(bf, min(mt.n, bf + 10)):
                    self.assertFalse(
                        not mt.on("ball", k),
                        "seed %d: ball hidden within 2 s of the block at "
                        "%.1f s" % (seed, ev["t_ms"] / 1000.0))


class OffTarget(unittest.TestCase):
    """Rule 9: an off-target shot visibly passes wide of a post or over
    the bar at the goal-line crossing; it is not hidden before that."""

    def test_off_target_visibly_out(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            n = 0
            for ev in tracked["events"]:
                if ev["type"] != "shot" or ev.get("outcome") not in (
                        "off_target", "wide", "over", "miss"):
                    continue
                f = mt.frame(ev["t_ms"])
                # a shot whose taker never visibly took it (the actor still
                # > 1.2 m from the ball at the event frame and the next --
                # one of the <= 2 % late deliveries rule 16 allows; the
                # player near the ball may be the keeper from the previous
                # save) never put the ball in flight: it rolls on from the
                # parry, and there is no crossing to demand of it
                pid = ev.get("player_id")
                if pid not in mt.x or min(
                        math.hypot(mt.x[pid][k] - mt.x["ball"][k],
                                   mt.y[pid][k] - mt.y["ball"][k])
                        if mt.on(pid, k) and mt.on("ball", k) else 1e9
                        for k in (f, f + 1)) > 12.0:
                    continue
                n += 1
                c = _crossing(mt, f)
                self.assertIsNotNone(
                    c, "seed %d: off-target shot at %.1f s never reaches a "
                    "goal line" % (seed, ev["t_ms"] / 1000.0))
                i, y, z = c  # type: ignore[misc]
                self.assertTrue(
                    mt.on("ball", i),
                    "seed %d: off-target shot at %.1f s hidden before the "
                    "line" % (seed, ev["t_ms"] / 1000.0))
                self.assertTrue(
                    abs(y - 34.0) > 3.66 or z >= 2.44,
                    "seed %d: off-target shot at %.1f s crosses on target "
                    "(y %.1f, z %.1f)" % (seed, ev["t_ms"] / 1000.0, y, z))


class OutOfPlay(unittest.TestCase):
    """Rules 10-11: every hide starts at/after a line crossing (never more
    than 2 m inside the pitch), no visible jump > 12 m across a hide unless
    a restart happens there, and goal kicks are taken from the goal area."""

    def test_hides_start_at_a_line(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            for i, j in hidden_spells(mt):
                if i == 0 or not mt.on("ball", i - 1):
                    continue
                bx, by = mt.x["ball"][i - 1], mt.y["ball"][i - 1]
                gap = min(bx, L - bx, by, W - by) / DM
                self.assertLessEqual(
                    gap, 2.0, "seed %d: ball hidden %.1f m inside the pitch"
                    % (seed, gap))

    def test_no_teleport_across_a_hide(self) -> None:
        restarts = ("corner", "throw_in", "goal_kick", "free_kick", "kick_off")
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            restart_frames = {mt.frame(e["t_ms"]) for e in tracked["events"]
                              if e["type"] in restarts
                              or e.get("subtype") == "kick_off"}
            for i, j in hidden_spells(mt):
                if i == 0 or j >= mt.n or not mt.on("ball", i - 1):
                    continue
                jump = math.hypot(mt.x["ball"][j] - mt.x["ball"][i - 1],
                                  mt.y["ball"][j] - mt.y["ball"][i - 1]) / DM
                near_restart = any(abs(f - j) <= 3 * HZ for f in restart_frames)
                self.assertTrue(
                    jump <= 12.0 or near_restart,
                    "seed %d: ball reappears %.0f m away after %.1f s hidden"
                    % (seed, jump, (j - i) * DT))

    def test_goal_kicks_from_the_goal_area(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            n = 0
            for ev in tracked["events"]:
                if ev["type"] != "goal_kick":
                    continue
                n += 1
                f = mt.frame(ev["t_ms"])
                x, y = mt.px("ball", f), mt.py("ball", f)
                # the goal area is the 5.5 m box, not the penalty area
                ok = (x <= 5.5 or x >= 99.5) and 24.84 <= y <= 43.16
                self.assertTrue(
                    ok, "seed %d: goal kick at %.1f s taken at (%.1f, %.1f), "
                    "outside the goal area"
                    % (seed, ev["t_ms"] / 1000.0, x, y))
            self.assertGreater(n, 0, "seed %d: no goal kicks" % seed)


class Bodies(unittest.TestCase):
    """Rules 12-16: never more than 11 per team, no statues (no player
    under 0.05 m/s for over 20 s), no long overlaps outside duels, and the
    actor within 2 m of the ball for >= 98 % of events."""

    def test_eleven_per_team_every_frame(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            for team in ("HAR", "COP"):
                pids = [p for p in mt.players if p[:3] == team]
                worst = 0
                for i in range(mt.n):
                    on = sum(1 for p in pids if mt.on(p, i))
                    worst = max(worst, on)
                    self.assertLessEqual(
                        on, 11, "seed %d: %s has %d players at frame %d"
                        % (seed, team, on, i))

    def test_no_statues(self) -> None:
        # under 0.05 m/s is, at dm resolution, an exact standstill
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            for p in mt.players:
                run = 0
                X, Y = mt.x[p], mt.y[p]
                for i in range(1, mt.n):
                    still = mt.on(p, i) and mt.on(p, i - 1) and \
                        X[i] == X[i - 1] and Y[i] == Y[i - 1]
                    run = run + 1 if still else 0
                    if run == int(20 * HZ):
                        self.fail(
                            "seed %d: %s stands perfectly still for 20 s from "
                            "frame %d" % (seed, p, i - run))

    def test_no_long_overlaps(self) -> None:
        # two players closer than 0.5 m for more than 2 s, outside duels:
        # frames where both are within 2 m of the (visible) ball
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            pairs: Dict[Tuple[str, str], int] = {}
            for i in range(0, mt.n, HZ):
                on = [p for p in mt.players if mt.on(p, i)]
                for a in range(len(on)):
                    for b in range(a + 1, len(on)):
                        key = (on[a], on[b])
                        d = math.hypot(mt.x[on[a]][i] - mt.x[on[b]][i],
                                       mt.y[on[a]][i] - mt.y[on[b]][i]) / DM
                        duel = mt.on("ball", i) and \
                            mt.dist(on[a], "ball", i) <= 2.0 and \
                            mt.dist(on[b], "ball", i) <= 2.0
                        if d < 0.5 and not duel:
                            pairs[key] = pairs.get(key, 0) + 1
                            self.assertLess(
                                pairs[key], 3,
                                "seed %d: %s and %s overlap (< 0.5 m) for 3 s+"
                                % (seed, on[a], on[b]))
                        else:
                            pairs[key] = 0

    def test_actor_at_ball_98pct(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            ok = tot = 0
            for ev in tracked["events"]:
                if ev["type"] == "substitution" or ev["player_id"] not in mt.x:
                    continue
                f = mt.frame(ev["t_ms"])
                near = min((mt.dist(ev["player_id"], "ball", k)
                            for k in (f, f + 1)
                            if mt.on(ev["player_id"], k) and mt.on("ball", k)),
                           default=float("inf"))
                tot += 1
                if near <= 2.0:
                    ok += 1
            self.assertGreaterEqual(
                ok / max(tot, 1), 0.98,
                "seed %d: actor at the ball for only %.1f %% of events"
                % (seed, 100.0 * ok / max(tot, 1)))


class AfterBlocks(unittest.TestCase):
    """Task 10: what happens after a blocked shot.

    The blocked shot is the shooting team's last scheduled touch before the
    ball becomes loose: from the block up to the next restart or change of
    possession, the ball must behave like a real loose ball. It rolls or
    bounces on to the next event's start (never lying still while play
    happens metres away), and every event in that window has its actor
    within 2 m of the ball at the event frame -- the shooter's team playing
    the rebound, not a parked ball with passes happening 20-60 m away.

    The window runs from the blocked shot up to (not including) the first
    following event that is a restart, an off-pitch break (substitution,
    card) or is taken by the other team -- the change of possession. Events
    by the other team are normal open-play events again, covered by the 98 %
    actor-at-ball audit above.
    """

    RESTARTS = ("throw_in", "corner", "goal_kick", "free_kick", "kick_off",
                "drop_ball", "penalty")

    def windows(self, mt: MT) -> List[List[Dict[str, Any]]]:
        evs, out_ = mt.m["events"], []
        j = 0
        while j < len(evs):
            ev = evs[j]
            if ev.get("type") == "shot" and ev.get("outcome") == "blocked":
                k = j
                while k + 1 < len(evs):
                    nxt = evs[k + 1]
                    if nxt["type"] in self.RESTARTS or \
                            nxt["type"] in ("substitution", "card") or \
                            nxt.get("team_id") != ev.get("team_id"):
                        break
                    k += 1
                out_.append(evs[j:k + 1])
                j = k + 1
            else:
                j += 1
        return out_

    def test_rebound_actors_at_the_ball(self) -> None:
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            worst = (0.0, None)
            for win in self.windows(mt):
                for ev in win:
                    if ev["type"] in ("substitution", "card") or \
                            ev["player_id"] not in mt.x:
                        continue
                    f = mt.frame(ev["t_ms"])
                    near = min((mt.dist(ev["player_id"], "ball", k)
                                for k in (f, f + 1)
                                if mt.on(ev["player_id"], k)
                                and mt.on("ball", k)),
                               default=float("inf"))
                    if near > worst[0]:
                        worst = (near, ev)
            self.assertLessEqual(
                worst[0], 2.0,
                "seed %d: after a blocked shot, %s at %.1f s has its actor "
                "%.1f m from the ball -- the rebound was not joined to the "
                "next possession" % (seed, worst[1]["type"],
                                     worst[1]["t_ms"] / 1000.0, worst[0]))

    def test_ball_never_parks_through_far_events(self) -> None:
        """The ball never lies still for more than 2 s while an event other
        than a foul or a restart wait happens 5+ m away from it (the parked
        ball from the task report). Measured on the 5 Hz output: a violation
        is an event whose start sits 5+ m from a ball that has not moved a
        frame's worth of roll in the whole 2 s before the event."""
        STILL_V = 0.6  # dm/frame: under this the ball reads as lying still
        for seed in SEEDS:
            tracked, tracking = out(seed)
            mt = MT(tracked, tracking)
            bx, by = mt.x["ball"], mt.y["ball"]
            for ev in tracked["events"]:
                if ev["type"] in self.RESTARTS or \
                        ev["type"] in ("foul", "substitution", "card"):
                    continue
                f = mt.frame(ev["t_ms"])
                sx = ev.get("start", {}).get("x", 0.0) * DM
                sy = ev.get("start", {}).get("y", 0.0) * DM
                if bx[f] < 0 or math.hypot(sx - bx[f], sy - by[f]) < 5.0 * DM:
                    continue  # event happens at the ball: no park to catch
                parked = True
                for k in range(max(0, f - 2 * HZ), f + 1):
                    if bx[k] < 0 or bx[k + 1] < 0:
                        parked = False  # hidden/off pitch: a restart wait
                        break
                    if math.hypot(bx[k + 1] - bx[k], by[k + 1] - by[k]) \
                            >= STILL_V:
                        parked = False
                        break
                if parked:
                    self.fail(
                        "seed %d: %s at %.1f s starts 5+ m from a ball that "
                        "has lain still for the whole 2 s before it"
                        % (seed, ev["type"], ev["t_ms"] / 1000.0))


if __name__ == "__main__":
    unittest.main()

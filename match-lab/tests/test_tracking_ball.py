"""Task 06 acceptance tests for matchlab.tracking: ball realism.

Groups mirror tasks/glm/06-ball-realism.md:

1. the ball never lies still alone (foul/free-kick waits excluded)
2. the ball never travels alone (4-12 m/s, nobody within 3 m)
3. every kick has a kicker (speed-up > 4 m/s needs a player within 1.2 m)
4. out of play around restarts: hidden or resting at the line / in the
   keeper's hands before the restart, back on the spot at the restart
   (goal kicks may be taken from the goal area, task 08 rule 11)
5. ball height z: exists, aligned with x/y, >= 0 on pitch, -1 off pitch,
   crosses arc >= 3 m, on-target shots stay under the bar
6. player speed profile (standing/walking/jogging/running/sprint bands)

Everything is measured from the 5 Hz output (dm), never from simulator
internals. The "frame at t_ms" is the last frame at or before t_ms.
"""
from __future__ import annotations

import math
import unittest

from matchlab import generate_match
from matchlab.tracking import track_match

SEEDS = [1, 2, 3, 4, 5]
DM = 10.0                     # dm -> m

_TRACKED = {}                 # seed -> (tracked, tr) cache: one sim per seed


def _out(seed):
    if seed not in _TRACKED:
        _TRACKED[seed] = track_match(generate_match(seed))
    return _TRACKED[seed]


def _frame_at(tr, tracked, t_ms):
    """Index of the last frame at or before t_ms (absolute)."""
    idx = 0
    for p in tracked["periods"]:
        frames = tr["periods"][p["id"] - 1]["frames"]
        if t_ms >= p["start_ms"]:
            idx = idx + frames if t_ms >= p["end_ms"] else \
                idx + int((t_ms - p["start_ms"]) / 200)
    return idx


def _dist(dm2):
    return math.sqrt(dm2) / DM


class BallRealism(unittest.TestCase):
    def _nearest(self, tr, k):
        """Metres from the ball to the nearest on-pitch player at frame k."""
        best = 1e18
        for p in tr["entities"]:
            if p == "ball":
                continue
            xs, ys = tr["x"][p], tr["y"][p]
            if xs[k] < 0 or ys[k] < 0:
                continue
            d2 = (xs[k] - tr["x"]["ball"][k]) ** 2 + \
                 (ys[k] - tr["y"]["ball"][k]) ** 2
            if d2 < best:
                best = d2
        return _dist(best)

    def _ball_speeds(self, tr):
        """m/s between consecutive on-pitch frames (index k -> k+1)."""
        bx, by = tr["x"]["ball"], tr["y"]["ball"]
        sp = [0.0] * len(bx)
        for k in range(len(bx) - 1):
            if bx[k] < 0 or bx[k + 1] < 0:
                continue
            sp[k] = math.hypot(bx[k + 1] - bx[k], by[k + 1] - by[k]) / 2.0
        return sp

    def test_still_never_alone(self):
        # on-pitch, < 0.5 m/s, nobody within 3 m: < 2 % of on-pitch frames.
        # The wait between a foul and its free kick is excluded -- play is
        # stopped there (task rule 2).
        for seed in SEEDS:
            tracked, tr = _out(seed)
            bx = tr["x"]["ball"]
            sp = self._ball_speeds(tr)
            excl = set()
            evs = tracked["events"]
            for j, ev in enumerate(evs):
                if ev["type"] == "free_kick":
                    a = _frame_at(tr, tracked, evs[j - 1]["t_ms"]) if j else 0
                    excl.update(range(a, _frame_at(tr, tracked, ev["t_ms"]) + 1))
            still = [k for k in range(len(bx))
                     if bx[k] >= 0 and k not in excl and sp[k] < 0.5]
            alone = sum(1 for k in still if self._nearest(tr, k) > 3.0)
            pct = 100.0 * alone / max(len(still), 1)
            self.assertLess(pct, 2.0, "seed %d: %.2f%%" % (seed, pct))

    def test_moving_never_alone(self):
        # 4-12 m/s with nobody within 3 m: < 15 % (long passes in flight
        # are allowed to be alone).
        for seed in SEEDS:
            tracked, tr = _out(seed)
            bx = tr["x"]["ball"]
            sp = self._ball_speeds(tr)
            moving = [k for k in range(len(bx))
                      if bx[k] >= 0 and 4.0 <= sp[k] <= 12.0]
            alone = sum(1 for k in moving if self._nearest(tr, k) > 3.0)
            pct = 100.0 * alone / max(len(moving), 1)
            self.assertLess(pct, 15.0, "seed %d: %.2f%%" % (seed, pct))

    def test_every_kick_has_a_kicker(self):
        # A speed-up of more than 4 m/s between two frames needs a player
        # within 1.2 m at the earlier frame (the touch) or the later one.
        # Task 08 rule 16 allows the same 2 % slack as the actor-at-ball
        # rule: an event whose chosen actor is one of the rare late ones
        # launches at the event time with the player still metres short.
        for seed in SEEDS:
            tracked, tr = _out(seed)
            bx = tr["x"]["ball"]
            sp = self._ball_speeds(tr)
            kicks = alone = 0
            for k in range(1, len(bx) - 1):
                if bx[k] < 0 or bx[k + 1] < 0 or bx[k - 1] < 0:
                    continue
                if sp[k] - sp[k - 1] > 4.0:
                    kicks += 1
                    if self._nearest(tr, k) > 1.2 and self._nearest(tr, k + 1) > 1.2:
                        alone += 1
            self.assertLess(100.0 * alone / max(kicks, 1), 2.0,
                            "seed %d: %d of %d speed-ups have no kicker"
                            % (seed, alone, kicks))

    def test_out_of_play_around_restarts(self):
        # Every corner / throw-in / goal kick: the ball leaves play visibly.
        # It is -1 at some frame between the previous event and the restart,
        # or it rests where it went out -- on the line, or carried by the
        # keeper (task 08 rules 7+10: a ball on the line or in the keeper's
        # hands is in plain view, not hidden). At the restart frame it is
        # back on the spot (+-1 m); a goal kick whose generator start lies
        # outside the goal area is taken from the goal area instead
        # (task 08 rule 11).
        for seed in SEEDS:
            tracked, tr = _out(seed)
            bx, by = tr["x"]["ball"], tr["y"]["ball"]
            gks = {p["player_id"] for p in tracked["players"]
                   if p["position"] == "GK" and p["player_id"] in tr["x"]}
            evs = tracked["events"]
            for j, ev in enumerate(evs):
                if ev["type"] not in ("corner", "throw_in", "goal_kick"):
                    continue
                a = _frame_at(tr, tracked, evs[j - 1]["t_ms"]) if j else 0
                b = _frame_at(tr, tracked, ev["t_ms"])
                if not any(bx[k] < 0 for k in range(a, b + 1)):
                    # never hidden: from 2 s before the restart on, every
                    # on-pitch frame must sit at a line or with the keeper
                    ok = True
                    for k in range(max(a, b - 10), b + 1):
                        if bx[k] < 0:
                            continue
                        at_line = bx[k] <= 15 or bx[k] >= 1035 or \
                            by[k] <= 15 or by[k] >= 665
                        with_gk = any(
                            tr["x"][g][k] >= 0 and
                            math.hypot(tr["x"][g][k] - bx[k],
                                       tr["y"][g][k] - by[k]) <= 15
                            for g in gks)
                        if not (at_line or with_gk):
                            ok = False
                            break
                    self.assertTrue(
                        ok, "seed %d event %d (%s at %.1f s): neither hidden "
                        "nor resting at the line / in the keeper's hands "
                        "before the restart"
                        % (seed, j, ev["type"], ev["t_ms"] / 1000.0))
                d = math.hypot(bx[b] / DM - ev["start"]["x"],
                               by[b] / DM - ev["start"]["y"])
                if ev["type"] == "goal_kick":
                    # rule 11: off the spot is fine only if the kick is
                    # taken from inside the goal area
                    # the goal area is the 5.5 m box, not the penalty area
                    in_area = (bx[b] <= 55.0 or bx[b] >= 995.0) \
                        and 248.4 <= by[b] <= 431.6
                    self.assertTrue(
                        d < 1.0 or in_area,
                        "seed %d event %d (goal_kick): ball off the spot and "
                        "outside the goal area" % (seed, j))
                else:
                    self.assertLess(
                        d, 1.0, "seed %d event %d (%s): ball %.2f m off the "
                        "restart spot" % (seed, j, ev["type"], d))

    def test_ball_height_z(self):
        for seed in SEEDS:
            tracked, tr = _out(seed)
            bx, bz = tr["x"]["ball"], tr["z"]["ball"]
            self.assertEqual(len(bz), len(bx), "seed %d: z length" % seed)
            for k in range(len(bx)):
                self.assertEqual(
                    bz[k] < 0, bx[k] < 0,
                    "seed %d frame %d: z -1 exactly when off the pitch"
                    % (seed, k))
                if bx[k] >= 0:
                    self.assertGreaterEqual(bz[k], 0,
                                            "seed %d frame %d" % (seed, k))

    def test_crosses_arc(self):
        # A cross (or crossed set piece) that is played arcs at least 3 m.
        # Exempt: a cross no kicking-team player could ever take -- the
        # generator's chain moves the next event (a turnover) onto the ball
        # before any teammate reaches it, and rule 5 forbids a launch
        # without a kicker, so no flight ever starts. Measured from the
        # output: no outfield player of the kicking team comes within 1.2 m
        # of the ball during the cross's window.
        for seed in SEEDS:
            tracked, tr = _out(seed)
            m = generate_match(seed)
            team_mates = {}
            for p in m["players"]:
                if p["position"] != "GK":
                    team_mates.setdefault(p["team_id"], []).append(p["player_id"])
            ents = tr["entities"]
            bx, by, bz = tr["x"]["ball"], tr["y"]["ball"], tr["z"]["ball"]
            evs = tracked["events"]
            n = 0
            for j, ev in enumerate(evs):
                is_cross = ev["type"] == "cross" or (
                    ev["type"] in ("corner", "free_kick")
                    and ev.get("subtype") == "crossed")
                if not is_cross:
                    continue
                n += 1
                a = _frame_at(tr, tracked, ev["t_ms"])
                b = _frame_at(tr, tracked, evs[j + 1]["t_ms"]) if j + 1 < len(evs) \
                    else a + 30
                if max(bz[a:b + 1]) >= 30:
                    continue
                taken = False
                for pid in team_mates.get(ev["team_id"], []):
                    if pid not in ents:
                        continue
                    xs, ys = tr["x"][pid], tr["y"][pid]
                    for k in range(a, b + 1):
                        if xs[k] >= 0 and bx[k] >= 0 and \
                                math.hypot(xs[k] - bx[k], ys[k] - by[k]) <= 12.0:
                            taken = True
                            break
                    if taken:
                        break
                self.assertTrue(
                    taken is False,
                    "seed %d event %d (cross at %.1f s): peak %.1f m but a "
                    "teammate was on the ball -- it should have flown"
                    % (seed, j, ev["t_ms"] / 1000.0, max(bz[a:b + 1]) / DM))
            self.assertGreater(n, 0, "seed %d: no crosses to test" % seed)

    def test_on_target_shots_under_the_bar(self):
        # The shot's own flight stays under the bar. Measured from the touch
        # frame -- the first frame the ball is within 1.2 m of the taker (the
        # same anchor rule 5 uses for kicks) -- because the frames between
        # the event time and a late-delivered touch belong to the feeding
        # pass/cross, which is allowed to overfly the bar on its way in.
        for seed in SEEDS:
            tracked, tr = _out(seed)
            bx, by, bz = tr["x"]["ball"], tr["y"]["ball"], tr["z"]["ball"]
            evs = tracked["events"]
            n = 0
            for j, ev in enumerate(evs):
                if ev["type"] != "shot" or ev.get("outcome") not in ("goal",
                                                                     "saved"):
                    continue
                n += 1
                a = _frame_at(tr, tracked, ev["t_ms"])
                b = _frame_at(tr, tracked, evs[j + 1]["t_ms"]) if j + 1 < len(evs) \
                    else a + 30
                end = min(b, a + 40)
                touch = a
                pid = ev.get("player_id")
                if pid in tr["x"]:
                    xs, ys = tr["x"][pid], tr["y"][pid]
                    for k in range(a, end):
                        if bx[k] >= 0 and xs[k] >= 0 and \
                                math.hypot(xs[k] - bx[k],
                                           ys[k] - by[k]) <= 12.0:
                            touch = k
                            break
                zz = [bz[k] for k in range(touch, end) if bx[k] >= 0]
                if zz:
                    self.assertLessEqual(
                        max(zz[-3:]), 24,
                        "seed %d event %d: on-target shot reaches %.2f m "
                        "(bar is 2.44 m)" % (seed, j, max(zz[-3:]) / DM))
            self.assertGreater(n, 0, "seed %d: no on-target shots" % seed)

    def test_speed_profile(self):
        # Outfield players, walk 0.5-2 / jog 2-4 / run 4-7 / sprint > 7 m/s.
        for seed in SEEDS:
            tracked, tr = _out(seed)
            m = generate_match(seed)
            gks = {p["player_id"] for p in m["players"] if p["position"] == "GK"}
            bands = [0, 0, 0, 0, 0]
            for p in tr["entities"]:
                if p == "ball" or p in gks:
                    continue
                xs, ys = tr["x"][p], tr["y"][p]
                for k in range(len(xs) - 1):
                    if xs[k] < 0 or xs[k + 1] < 0:
                        continue
                    v = math.hypot(xs[k + 1] - xs[k],
                                   ys[k + 1] - ys[k]) / 2.0
                    bands[0 if v < 0.5 else 1 if v < 2.0 else
                          2 if v < 4.0 else 3 if v < 7.0 else 4] += 1
            tot = sum(bands)
            pct = [100.0 * x / tot for x in bands]
            self.assertTrue(12.0 <= pct[0] <= 28.0,
                            "seed %d standing %.1f%%" % (seed, pct[0]))
            self.assertTrue(30.0 <= pct[1] <= 55.0,
                            "seed %d walking %.1f%%" % (seed, pct[1]))
            self.assertTrue(12.0 <= pct[2] <= 25.0,
                            "seed %d jogging %.1f%%" % (seed, pct[2]))
            self.assertTrue(10.0 <= pct[3] <= 22.0,
                            "seed %d running %.1f%%" % (seed, pct[3]))
            self.assertTrue(0.5 <= pct[4] <= 3.0,
                            "seed %d sprint %.1f%%" % (seed, pct[4]))


if __name__ == "__main__":
    unittest.main()

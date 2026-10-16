"""Task 04 acceptance tests for matchlab.tracking.

Groups mirror tasks/glm/04-tracking-synthesizer.md:

1. events unchanged except the actor (seeds 1-5)
2. actor/ball consistency at event times, keepers take goal kicks and saves,
   corner taker on the spot
3. physics: speed / acceleration / ball speed caps
4. pitch bounds, -1 exactly when off, 11 per team (sub window / second yellow
   exceptions), separation
5. shape sanity per period
6. calibration ranges, seeds 1-10 -- SLOW, run with PIPPI_SLOW=1
7. determinism
8. schema validation

Everything is measured from the 5 Hz output files (dm), never from simulator
internals. The "frame at t_ms" is the last frame at or before t_ms: event times
land between frames, and the ball rests on event.start from BALL_REST before
the event until the frame after it.
"""
from __future__ import annotations

import copy
import json
import math
import os
import unittest
from typing import Any, Dict, List, Optional, Tuple

from matchlab import generate_match
from matchlab.tracking import track_match

try:  # works both as `discover -s tests` (top-level module) and as the `tests` package
    from .test_schema import check, load_schema
except ImportError:
    from test_schema import check, load_schema

SPRINT_MS = 25.0 / 3.6        # 25 km/h in m/s (6.94)
DM = 10.0                     # dm -> m
SLOW = os.environ.get("PIPPI_SLOW") == "1"

_CACHE: Dict[int, Tuple[Dict[str, Any], Dict[str, Any]]] = {}


def tracked_pair(seed: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if seed not in _CACHE:
        _CACHE[seed] = track_match(generate_match(seed))
    return _CACHE[seed]


def series(tracking: Dict[str, Any]) -> Tuple[Dict[str, List[int]], Dict[str, List[int]]]:
    return tracking["x"], tracking["y"]


def frame_index(tracking: Dict[str, Any], t_ms: int) -> int:
    """Global frame index of the last 5 Hz frame at or before t_ms."""
    offs: List[int] = []
    cur = 0
    for p in tracking["periods"]:
        offs.append(cur)
        cur += p["frames"]
    for k, p in enumerate(tracking["periods"]):
        if k + 1 == len(tracking["periods"]) or t_ms < tracking["periods"][k + 1]["start_ms"]:
            i = int((t_ms - p["start_ms"]) // 200)
            return offs[k] + max(0, min(i, p["frames"] - 1))
    return 0


def per_player(tracked: Dict[str, Any], tracking: Dict[str, Any]) -> List[Dict[str, float]]:
    """Minutes, km/90, top speed, sprints/90 per player, from the 5 Hz steps."""
    xs, ys = series(tracking)
    n = len(xs["ball"])
    out: List[Dict[str, float]] = []
    for p in tracked["players"]:
        pid = p["player_id"]
        X, Y = xs[pid], ys[pid]
        mins = km = top = 0.0
        run = sprints = 0
        for k in range(n - 1):
            a, b, c, d = X[k], X[k + 1], Y[k], Y[k + 1]
            if a < 0 or b < 0:
                run = 0
                continue
            mins += 0.2 / 60.0
            step = math.hypot(b - a, d - c) / DM
            km += step / 1000.0
            sp = step / 0.2
            top = max(top, sp)
            if sp > SPRINT_MS:
                run += 1
                if run == 5:          # 5 frames = 1 s above 25 km/h
                    sprints += 1
            else:
                run = 0
        out.append({
            "pid": pid, "pos": p["position"], "min": mins,
            "km90": km / mins * 90.0 if mins > 0 else 0.0,
            "top_kmh": top * 3.6,
            "sprints90": sprints / mins * 90.0 if mins > 0 else 0.0,
        })
    return out


# ---- 1. events unchanged except the actor ----------------------------------

UNCHANGED_KEYS = ("idx", "t_ms", "clock_display", "period", "team_id", "type", "subtype",
                  "start", "end", "outcome", "set_piece", "possession_id", "pressure_level")


class EventsUnchanged(unittest.TestCase):
    def test_seeds_1_to_5(self) -> None:
        for seed in range(1, 6):
            original = generate_match(seed)
            tracked, _tracking = tracked_pair(seed)
            self.assertEqual(len(original["events"]), len(tracked["events"]), "seed %d" % seed)
            changed = 0
            yellows: Dict[str, int] = {}
            for j, (orig, new) in enumerate(zip(original["events"], tracked["events"])):
                for key in UNCHANGED_KEYS:
                    self.assertEqual(orig[key], new[key],
                                     "seed %d event %d: %s changed" % (seed, j, key))
                if new["type"] == "substitution":
                    self.assertEqual(orig["player_id"], new["player_id"], "sub ids must stay")
                    self.assertEqual(orig["player_out_id"], new["player_out_id"])
                    continue
                if orig["player_id"] != new["player_id"]:
                    changed += 1
                    self.assertEqual(orig["team_id"], new["team_id"],
                                     "seed %d event %d: actor switched teams" % (seed, j))
                if new["type"] == "card":
                    # the card belongs to the (possibly renamed) fouler, and the
                    # subtype is recomputed from the new ids
                    foul = tracked["events"][j - 1]
                    self.assertEqual(foul["player_id"], new["player_id"])
                    count = yellows.get(new["player_id"], 0) + 1
                    yellows[new["player_id"]] = count
                    self.assertEqual(new["subtype"], "yellow" if count == 1 else "second_yellow")
            self.assertGreater(tracked["tracking"]["actors_changed"], 0, "seed %d" % seed)
            self.assertEqual(tracked["tracking"]["actors_changed"], changed, "seed %d" % seed)


# ---- 2. actor / ball consistency ---------------------------------------------

class ActorsAndBall(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tracked, cls.tracking = tracked_pair(1)
        cls.idx = {p["player_id"]: p for p in cls.tracked["players"]}

    def test_actor_at_spot_98pct(self) -> None:
        xs, ys = series(self.tracking)
        ok = tot = 0
        worst = 0.0
        for ev in self.tracked["events"]:
            if ev["type"] == "substitution" or ev["player_id"] not in self.idx:
                continue
            tot += 1
            f = frame_index(self.tracking, ev["t_ms"])
            d = math.hypot(xs[ev["player_id"]][f] - ev["start"]["x"] * DM,
                           ys[ev["player_id"]][f] - ev["start"]["y"] * DM) / DM
            worst = max(worst, d)
            if d <= 2.5:
                ok += 1
        self.assertGreaterEqual(ok / tot, 0.98, "worst miss %.1f m" % worst)

    def test_ball_at_spot_98pct(self) -> None:
        """keeper_save events carry shooter-frame coordinates ~100 m from the
        shot (generator quirk, see the task Result); they are counted separately."""
        xs, ys = series(self.tracking)
        ok = tot = quirk = 0
        for ev in self.tracked["events"]:
            f = frame_index(self.tracking, ev["t_ms"])
            d = math.hypot(xs["ball"][f] - ev["start"]["x"] * DM,
                           ys["ball"][f] - ev["start"]["y"] * DM) / DM
            if ev["type"] == "keeper_save" and d > 1.0:
                quirk += 1
                continue
            tot += 1
            if d <= 1.0:
                ok += 1
        self.assertGreaterEqual(ok / tot, 0.98,
                                "non-keeper_save ball misses; quirk events: %d" % quirk)

    def test_keepers_take_goal_kicks_and_saves(self) -> None:
        for ev in self.tracked["events"]:
            if ev["type"] in ("goal_kick", "keeper_save"):
                self.assertEqual(self.idx[ev["player_id"]]["position"], "GK")

    def test_corner_taker_on_the_spot(self) -> None:
        xs, ys = series(self.tracking)
        for ev in self.tracked["events"]:
            if ev["type"] != "corner":
                continue
            f = frame_index(self.tracking, ev["t_ms"])
            d = math.hypot(xs[ev["player_id"]][f] - ev["start"]["x"] * DM,
                           ys[ev["player_id"]][f] - ev["start"]["y"] * DM) / DM
            self.assertLessEqual(d, 3.0, "corner taker %.1f m from the arc" % d)


# ---- 3. physics ---------------------------------------------------------------

class Physics(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tracked, cls.tracking = tracked_pair(1)

    def test_player_speeds(self) -> None:
        """p99 per player within 5% of their own v_max; nobody above 38 km/h."""
        xs, ys = series(self.tracking)
        vmax = {p["player_id"]: p["attributes"]["v_max_kmh"] / 3.6
                for p in self.tracked["players"]}
        n = len(xs["ball"])
        for pid, cap in vmax.items():
            X, Y = xs[pid], ys[pid]
            speeds = []
            for k in range(n - 1):
                a, b, c, d = X[k], X[k + 1], Y[k], Y[k + 1]
                if a < 0 or b < 0:
                    continue
                speeds.append(math.hypot(b - a, d - c) / DM / 0.2)
            if not speeds:
                continue
            speeds.sort()
            p99 = speeds[int(len(speeds) * 0.99)]
            self.assertLessEqual(p99, cap * 1.05, "%s p99 %.1f m/s" % (pid, p99))
            self.assertLessEqual(speeds[-1], 38.0 / 3.6 + 1e-9,
                                 "%s hit %.1f km/h" % (pid, speeds[-1] * 3.6))

    def test_acceleration_p99(self) -> None:
        xs, ys = series(self.tracking)
        accels: List[float] = []
        for p in self.tracked["players"]:
            X, Y = xs[p["player_id"]], ys[p["player_id"]]
            prev = 0.0
            for k in range(len(X) - 1):
                a, b, c, d = X[k], X[k + 1], Y[k], Y[k + 1]
                if a < 0 or b < 0:
                    prev = 0.0
                    continue
                sp = math.hypot(b - a, d - c) / DM / 0.2
                accels.append(abs(sp - prev) / 0.2)
                prev = sp
        accels.sort()
        self.assertLessEqual(accels[int(len(accels) * 0.99)], 8.0)

    def test_ball_speed_cap(self) -> None:
        xs, ys = series(self.tracking)
        X, Y = xs["ball"], ys["ball"]
        # -1 frames are the off-pitch marker, not a position: skip them
        worst = max(math.hypot(X[k + 1] - X[k], Y[k + 1] - Y[k]) / DM / 0.2
                    for k in range(len(X) - 1)
                    if X[k] >= 0 and X[k + 1] >= 0)
        self.assertLessEqual(worst, 40.0, "%.1f m/s" % worst)


# ---- 4. pitch bounds, bodies on the pitch, separation --------------------------

class PitchAndBodies(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tracked, cls.tracking = tracked_pair(1)

    def test_bounds_and_off_pitch_marker(self) -> None:
        xs, ys = series(self.tracking)
        for p in self.tracked["players"]:
            X, Y = xs[p["player_id"]], ys[p["player_id"]]
            for k, (x, y) in enumerate(zip(X, Y)):
                if x < 0:
                    self.assertEqual((x, y), (-1, -1), "partial off-pitch marker")
                else:
                    self.assertTrue(0 <= x <= 1050 and 0 <= y <= 680,
                                    "%s frame %d at (%d,%d)" % (p["player_id"], k, x, y))

    def test_eleven_per_team(self) -> None:
        """11 on the pitch per team, except 12 during a substitution window and
        10 after a second yellow (the player is removed, no replacement)."""
        xs, _ys = series(self.tracking)
        periods = self.tracking["periods"]
        # sub windows: t_ms of the sub events .. end of the sub stoppage; a
        # window can hold two subs of one team (11 + 2 incoming = 13 briefly)
        windows: Dict[str, List[Tuple[int, int, int]]] = {"HAR": [], "COP": []}
        for s in self.tracked["stoppages"]:
            if s["type"] != "sub":
                continue
            for ev in self.tracked["events"]:
                if ev["event_id"] in s["related_event_ids"]:
                    windows[ev["team_id"]].append((ev["t_ms"], s["t_end_ms"], 1))
        sent_off: Dict[str, List[int]] = {"HAR": [], "COP": []}
        for ev in self.tracked["events"]:
            if ev["type"] == "card" and ev["subtype"] == "second_yellow":
                sent_off[ev["team_id"]].append(ev["t_ms"])
        pids = {t: [p["player_id"] for p in self.tracked["players"] if p["team_id"] == t]
                for t in ("HAR", "COP")}
        n = len(xs["ball"])
        for k in range(n):
            t_ms = frame_time_ms(self.tracking, k)
            for team in ("HAR", "COP"):
                on = sum(1 for pid in pids[team] if xs[pid][k] >= 0)
                expected = 11
                subs_now = sum(w for a, b, w in windows[team] if a <= t_ms <= b)
                if any(t_off <= t_ms for t_off in sent_off[team]):
                    expected -= 1
                # incoming players are on from the sub event; the outgoing ones
                # leave as they reach the touchline, so the count glides down
                self.assertTrue(expected <= on <= expected + subs_now,
                                "%s frame %d (%d ms): %d on, want %d-%d" % (
                                    team, k, t_ms, on, expected, expected + subs_now))

    def test_separation(self) -> None:
        xs, ys = series(self.tracking)
        close = tot = 0
        n = len(xs["ball"])
        for k in range(n):
            coords = sorted((xs[p["player_id"]][k], ys[p["player_id"]][k], p["player_id"])
                            for p in self.tracked["players"] if xs[p["player_id"]][k] >= 0)
            tot += len(coords)
            for a in range(len(coords)):
                for b in range(a + 1, len(coords)):
                    if coords[b][0] - coords[a][0] > 5:
                        break
                    if math.hypot(coords[b][0] - coords[a][0],
                                  coords[b][1] - coords[a][1]) < 5.0:
                        close += 1
        self.assertLess(close / tot, 0.005, "%.2f%% of player-frames" % (close / tot * 100))


def frame_time_ms(tracking: Dict[str, Any], k: int) -> int:
    cur = 0
    for p in tracking["periods"]:
        if k < cur + p["frames"]:
            return p["start_ms"] + (k - cur) * 200
        cur += p["frames"]
    return tracking["periods"][-1]["start_ms"] + (tracking["periods"][-1]["frames"] - 1) * 200


# ---- 5. shape sanity -----------------------------------------------------------

class Shape(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tracked, cls.tracking = tracked_pair(1)

    def test_spread_and_correlation(self) -> None:
        xs, _ys = series(self.tracking)
        offs: List[Tuple[int, int]] = []
        cur = 0
        for p in self.tracking["periods"]:
            offs.append((cur, cur + p["frames"]))
            cur += p["frames"]
        for team in ("HAR", "COP"):
            pids = [p["player_id"] for p in self.tracked["players"]
                    if p["team_id"] == team and p["position"] != "GK"]
            for lo, hi in offs:
                spreads: List[float] = []
                bx: List[float] = []
                tx: List[float] = []
                for k in range(lo, hi):
                    us = [xs[pid][k] for pid in pids if xs[pid][k] >= 0]
                    if len(us) < 7 or xs["ball"][k] < 0:
                        continue  # ball off the pitch: no meaningful position
                    spreads.append((max(us) - min(us)) / DM)
                    bx.append(xs["ball"][k] / DM)
                    tx.append(sum(us) / len(us) / DM)
                mean_spread = sum(spreads) / len(spreads)
                self.assertTrue(25.0 <= mean_spread <= 50.0,
                                "%s spread %.1f m" % (team, mean_spread))
                mb, mt = sum(bx) / len(bx), sum(tx) / len(tx)
                cov = sum((a - mb) * (b - mt) for a, b in zip(bx, tx))
                vb = sum((a - mb) ** 2 for a in bx) ** 0.5
                vt = sum((b - mt) ** 2 for b in tx) ** 0.5
                corr = cov / (vb * vt)
                self.assertGreater(corr, 0.3, "%s corr %.2f" % (team, corr))


# ---- 6. calibration (slow: seeds 1-10) ------------------------------------------

@unittest.skipUnless(SLOW, "calibration over seeds 1-10; run with PIPPI_SLOW=1")
class Calibration(unittest.TestCase):
    def test_published_ranges(self) -> None:
        for seed in range(1, 11):
            tracked, tracking = tracked_pair(seed)
            per = per_player(tracked, tracking)
            of = [p for p in per if p["pos"] != "GK" and p["min"] >= 60.0]
            gk = [p for p in per if p["pos"] == "GK" and p["min"] >= 60.0]
            self.assertTrue(of, "seed %d: no 60-min outfielder?" % seed)
            for p in of:
                self.assertTrue(8.5 <= p["km90"] <= 12.3,
                                "seed %d %s %.2f km/90" % (seed, p["pid"], p["km90"]))
                self.assertTrue(5.0 <= p["sprints90"] <= 35.0,
                                "seed %d %s %.1f sprints/90" % (seed, p["pid"], p["sprints90"]))
            for p in gk:
                self.assertTrue(4.5 <= p["km90"] <= 7.0,
                                "seed %d %s %.2f km/90" % (seed, p["pid"], p["km90"]))
            fastest = max(p["top_kmh"] for p in per if p["min"] >= 5.0)
            self.assertTrue(34.0 <= fastest <= 37.0,
                            "seed %d fastest %.1f km/h" % (seed, fastest))


# ---- 7. determinism --------------------------------------------------------------

class Determinism(unittest.TestCase):
    def test_same_seed_same_bytes(self) -> None:
        a = track_match(generate_match(2))
        b = track_match(generate_match(2))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_other_seed_differs(self) -> None:
        a = track_match(generate_match(2))
        c = track_match(generate_match(3))
        self.assertNotEqual(json.dumps(a, sort_keys=True), json.dumps(c, sort_keys=True))


# ---- 8. schema ---------------------------------------------------------------------

class Schema(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tracked, cls.tracking = tracked_pair(1)

    def test_tracking_file_validates(self) -> None:
        schema = load_schema("tracking.schema.json")
        errors = check(self.tracking, schema, schema)
        self.assertEqual(errors, [], errors[:5])

    def test_tracked_match_validates(self) -> None:
        schema = load_schema("match.schema.json")
        errors = check(self.tracked, schema, schema)
        self.assertEqual(errors, [], errors[:5])
        event_schema = load_schema("event.schema.json")
        for ev in self.tracked["events"]:
            errors = check(ev, event_schema, event_schema, ev["event_id"])
            self.assertEqual(errors, [], errors[:3])

    def test_attributes_in_range(self) -> None:
        for p in self.tracked["players"]:
            a = p["attributes"]
            self.assertTrue(26 <= a["v_max_kmh"] <= 37, p)
            self.assertTrue(0.85 <= a["endurance"] <= 1.0, p)
            self.assertTrue(0.9 <= a["work_rate"] <= 1.1, p)
            self.assertTrue(0.7 <= a["sprint_bias"] <= 1.3, p)


if __name__ == "__main__":
    unittest.main()

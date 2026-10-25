"""Task 05 tests for matchreader.players.

Groups mirror tasks/glm/05-player-stats-feed.md:

1. counted stats recounted independently (seeds 1-3) + pass_difficulty boundaries
2. physical stats recounted independently from the tracking (seed 1)
3. no future: truncating events/frames at minute m leaves array[m] unchanged
4. monotone arrays; hard_ok <= passes_ok <= passes
5. on_min / off_min vs players_on_pitch and the first/last tracked frame
6. calibration, seeds 1-10 -- SLOW, run with PIPPI_SLOW=1
7. determinism; CLI --seed 43 equals --match/--tracking
8. schema; a broken copy is rejected; no names anywhere
9. data/demo-match.json still equals a fresh --seed 43 build

Everything is measured from build_players output / the 5 Hz files, with the
recounts written as plain loops that do not reuse the players.py helpers.
"""
from __future__ import annotations

import copy
import json
import math
import os
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple

from matchreader.players import build_players, main, pass_difficulty
from matchreader.reader import build_output, dumps, players_on_pitch
from tests import util  # noqa: F401  (puts the sibling match-lab on sys.path)
from matchlab import generate_match
from matchlab.tracking import track_match

from matchreader.schemacheck import check, load_schema

SLOW = os.environ.get("PIPPI_SLOW") == "1"
SPRINT_MS = 25.0 / 3.6
DM = 10.0

_CACHE: Dict[int, Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = {}


def built(seed: int) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """(tracked match, tracking, players feed) for a seed, cached."""
    if seed not in _CACHE:
        tracked, tracking = track_match(generate_match(seed))
        _CACHE[seed] = (tracked, tracking, build_players(tracked, tracking))
    return _CACHE[seed]


# ---- independent helpers (no players.py code) --------------------------------

def own_minute(ev_or_t: int, period: int, p1s: int, p2s: int) -> float:
    t = ev_or_t
    if period == 1:
        m = (t - p1s) / 60000.0
    else:
        m = 45.0 + (t - p2s) / 60000.0
    m = round(m, 1)
    return 44.99 if (period == 1 and m > 45.0) else m


def own_starts(tracked: Dict[str, Any]) -> Tuple[int, int]:
    p = sorted(tracked["periods"], key=lambda q: q["id"])
    return p[0]["start_ms"], p[1]["start_ms"]


def own_difficulty(ev: Dict[str, Any]) -> int:
    length = math.hypot(ev["end"]["x"] - ev["start"]["x"], ev["end"]["y"] - ev["start"]["y"])
    b = 2 if length >= 30 else (1 if length >= 15 else 0)
    plus = (ev["team_id"] == "HAR") == (ev["period"] == 1)
    gain = (ev["end"]["x"] - ev["start"]["x"]) * (1.0 if plus else -1.0)
    if gain >= 10:
        b += 1
    if ev["pressure_level"] >= 4:
        b += 1
    return min(5, 1 + b)


def own_frame_minutes(tracking: Dict[str, Any], p1s: int, p2s: int) -> List[float]:
    out: List[float] = []
    for p in sorted(tracking["periods"], key=lambda q: q["id"]):
        for k in range(p["frames"]):
            out.append(own_minute(p["start_ms"] + k * 200, p["id"], p1s, p2s))
    return out


# ---- 1. counted stats ---------------------------------------------------------

class PassDifficultyTest(unittest.TestCase):
    @staticmethod
    def ev(length_m: float, dx: float, pressure: int, period: int = 1,
           team: str = "HAR") -> Dict[str, Any]:
        return {
            "team_id": team, "period": period, "pressure_level": pressure,
            "start": {"x": 30.0, "y": 34.0},
            "end": {"x": 30.0 + dx, "y": 34.0 + math.sqrt(max(length_m ** 2 - dx ** 2, 0.0))},
        }

    def test_boundaries(self) -> None:
        # length: <15 -> 0, 15..<30 -> 1, >=30 -> 2 (base 1, no forward gain)
        self.assertEqual(pass_difficulty(self.ev(14.9, 0.0, 1)), 1)
        self.assertEqual(pass_difficulty(self.ev(15.0, 0.0, 1)), 2)
        self.assertEqual(pass_difficulty(self.ev(29.9, 0.0, 1)), 2)
        self.assertEqual(pass_difficulty(self.ev(30.0, 0.0, 1)), 3)
        # forward: gains 9.9 vs 10 m toward the goal attacked (length 40 keeps
        # the length bonus clear of the float wobble at exactly 30)
        self.assertEqual(pass_difficulty(self.ev(40.0, 9.9, 1)), 3)
        self.assertEqual(pass_difficulty(self.ev(40.0, 10.0, 1)), 4)
        # backward is never a forward gain, even long
        self.assertEqual(pass_difficulty(self.ev(40.0, -10.0, 1)), 3)
        self.assertEqual(pass_difficulty(self.ev(40.0, 10.0, 1, period=2)), 3)  # HAR p2: -x
        self.assertEqual(pass_difficulty(self.ev(40.0, -10.0, 1, team="COP")), 4)  # COP p1: -x
        # pressure 3 vs 4
        self.assertEqual(pass_difficulty(self.ev(40.0, 10.0, 3)), 4)
        self.assertEqual(pass_difficulty(self.ev(40.0, 10.0, 4)), 5)
        # cap at 5
        self.assertEqual(pass_difficulty(self.ev(40.0, 40.0, 5)), 5)

    def test_matches_events(self) -> None:
        tracked, _tracking, _feed = built(1)
        n = 0
        for ev in tracked["events"]:
            if ev["type"] == "pass":
                self.assertEqual(pass_difficulty(ev), own_difficulty(ev))
                n += 1
        self.assertGreater(n, 300)


class CountedRecountTest(unittest.TestCase):
    MINUTES = (0, 1, 12, 45, 46, 90)

    def test_recount_seeds_1_to_3(self) -> None:
        for seed in (1, 2, 3):
            tracked, _tracking, feed = built(seed)
            p1s, p2s = own_starts(tracked)
            last = feed["last_minute"]
            minutes = self.MINUTES + (last,)
            # recount: (pid, stat) -> sorted minutes of counted events
            rc: Dict[Tuple[str, str], List[float]] = {}
            for ev in tracked["events"]:
                pid = ev["player_id"]
                t = own_minute(ev["t_ms"], ev["period"], p1s, p2s)
                typ = ev["type"]
                keys: List[str] = []
                if typ == "pass":
                    keys = ["passes"]
                    if ev["outcome"] == "success":
                        keys.append("passes_ok")
                        if own_difficulty(ev) >= 4:
                            keys.append("hard_ok")
                elif typ in ("tackle", "interception"):
                    keys = ["ball_wins"]
                elif typ == "shot" or (typ == "free_kick" and ev.get("subtype") == "shoot"):
                    keys = ["shots"]
                elif typ == "keeper_save":
                    keys = ["saves"]
                for key in keys:
                    rc.setdefault((pid, key), []).append(t)
            for entry in feed["players"]:
                pid = entry["player_id"]
                for key in ("passes", "passes_ok", "hard_ok", "ball_wins", "shots", "saves"):
                    times = sorted(rc.get((pid, key), []))
                    for m in minutes:
                        want = sum(1 for t in times if t < m)
                        self.assertEqual(entry["stats"][key][m], want,
                                         "seed %d %s %s[%d]" % (seed, pid, key, m))


# ---- 2. physical stats --------------------------------------------------------

class PhysicalRecountTest(unittest.TestCase):
    MINUTES = (0, 1, 12, 45, 46, 90)

    def test_recount_seed_1(self) -> None:
        tracked, tracking, feed = built(1)
        p1s, p2s = own_starts(tracked)
        fmin = own_frame_minutes(tracking, p1s, p2s)
        last = feed["last_minute"]
        n = len(tracking["x"]["ball"])
        self.assertEqual(len(fmin), n)
        xs, ys = tracking["x"], tracking["y"]

        for entry in feed["players"]:
            pid = entry["player_id"]
            X, Y = xs[pid], ys[pid]
            # own speed / smoothed speed / step arrays
            v = [0.0] * n
            defined = [False] * n
            for k in range(1, n):
                if X[k - 1] >= 0 and X[k] >= 0:
                    v[k] = math.hypot(X[k] - X[k - 1], Y[k] - Y[k - 1]) / DM / 0.2
                    defined[k] = True
            sm = [0.0] * n
            for k in range(1, n):
                w = [v[j] for j in (k, k - 1, k - 2) if j >= 1 and defined[j]]
                if w:
                    sm[k] = sum(w) / len(w)
            steps = [0.0] * n
            for k in range(1, n):
                if X[k - 1] >= 0 and X[k] >= 0:
                    steps[k] = math.hypot(X[k] - X[k - 1], Y[k] - Y[k - 1]) / DM
            for m in self.MINUTES + (last,):
                K = 0
                while K < n and fmin[K] < m:
                    K += 1
                # distance: steps whose end frame is visible
                dist = sum(steps[k] for k in range(K))
                self.assertEqual(entry["stats"]["distance_m"][m],
                                 int(math.floor(dist + 0.5)),
                                 "%s distance_m[%d]" % (pid, m))
                # top speed over visible frames
                top = max((sm[k] for k in range(K)), default=0.0)
                self.assertEqual(entry["stats"]["top_speed_dmh"][m],
                                 int(math.floor(top * 3.6 * 10.0 + 0.5)),
                                 "%s top_speed_dmh[%d]" % (pid, m))
                # sprints: runs above the threshold over the whole match,
                # merged when separated by < 5 frames below; a sprint counts
                # at m only once COMPLETED -- the 5 frames after its end (which
                # settle completion and any merge) must all be visible
                runs: List[List[int]] = []
                k = 1
                while k < n:
                    if sm[k] > SPRINT_MS:
                        j = k
                        while j + 1 < n and sm[j + 1] > SPRINT_MS:
                            j += 1
                        runs.append([k, j])
                        k = j + 1
                    else:
                        k += 1
                merged: List[List[int]] = []
                for r in runs:
                    if merged and r[0] - merged[-1][1] - 1 < 5:
                        merged[-1][1] = r[1]
                        merged[-1][2] += r[1] - r[0] + 1
                    else:
                        merged.append([r[0], r[1], r[1] - r[0] + 1])
                want = sum(1 for r in merged if r[2] >= 5 and r[1] + 5 < K)
                self.assertEqual(entry["stats"]["sprints"][m], want,
                                 "%s sprints[%d]" % (pid, m))


# ---- 3. no future --------------------------------------------------------------

class NoFutureTest(unittest.TestCase):
    def test_truncated_prefix_same_value(self) -> None:
        for m in (12, 46):
            tracked, tracking, feed = built(1)
            p1s, p2s = own_starts(tracked)
            # events visible at minute m
            cut = copy.deepcopy(tracked)
            cut["events"] = [e for e in tracked["events"]
                             if own_minute(e["t_ms"], e["period"], p1s, p2s) < m]
            # frames visible at minute m
            fmin = own_frame_minutes(tracking, p1s, p2s)
            K = sum(1 for f in fmin if f < m)
            f1 = tracking["periods"][0]["frames"]
            cut_tr = {
                "match_id": tracking["match_id"], "seed": tracking["seed"],
                "tracking_version": tracking["tracking_version"], "hz": 5, "unit": "dm",
                "periods": [{"id": 1, "start_ms": tracking["periods"][0]["start_ms"],
                             "frames": min(K, f1)},
                            {"id": 2, "start_ms": tracking["periods"][1]["start_ms"],
                             "frames": max(0, K - f1)}],
                "entities": tracking["entities"],
                "x": {e: s[:K] for e, s in tracking["x"].items()},
                "y": {e: s[:K] for e, s in tracking["y"].items()},
            }
            feed2 = build_players(cut, cut_tr)
            for entry, entry2 in zip(feed["players"], feed2["players"]):
                self.assertEqual(entry["player_id"], entry2["player_id"])
                for key, arr in entry["stats"].items():
                    self.assertEqual(arr[m], entry2["stats"][key][m],
                                     "%s %s[%d] changed by truncation" % (
                                         entry["player_id"], key, m))

    def test_minute_zero_all_zero(self) -> None:
        _t, _tr, feed = built(1)
        for entry in feed["players"]:
            for key, arr in entry["stats"].items():
                self.assertEqual(arr[0], 0, "%s %s[0]" % (entry["player_id"], key))


# ---- 4. monotone -----------------------------------------------------------------

class MonotoneTest(unittest.TestCase):
    def test_non_decreasing_and_nested(self) -> None:
        for seed in (1, 2):
            _t, _tr, feed = built(seed)
            for entry in feed["players"]:
                s = entry["stats"]
                for key, arr in s.items():
                    self.assertEqual(arr, sorted(arr), "%s %s decreases" % (
                        entry["player_id"], key))
                for a, b, c in zip(s["hard_ok"], s["passes_ok"], s["passes"]):
                    self.assertLessEqual(a, b)
                    self.assertLessEqual(b, c)


# ---- 5. minutes on the pitch ------------------------------------------------------

def frame_t_ms(tracking: Dict[str, Any], k: int) -> int:
    cur = 0
    for p in sorted(tracking["periods"], key=lambda q: q["id"]):
        if k < cur + p["frames"]:
            return p["start_ms"] + (k - cur) * 200
        cur += p["frames"]
    raise IndexError(k)


class MinutesTest(unittest.TestCase):
    def test_bookkeeping(self) -> None:
        tracked, tracking, feed = built(1)
        p1s, p2s = own_starts(tracked)
        by_pid = {p["player_id"]: p for p in feed["players"]}
        xs = tracking["x"]

        for ev in tracked["events"]:
            if ev["type"] == "substitution":
                t = own_minute(ev["t_ms"], ev["period"], p1s, p2s)
                self.assertEqual(by_pid[ev["player_id"]]["on_min"], t)
                self.assertEqual(by_pid[ev["player_out_id"]]["off_min"], t)
                # players_on_pitch flips exactly at the sub event
                team = ev["team_id"]
                self.assertIn(ev["player_id"],
                              players_on_pitch(tracked, team, ev["t_ms"], True))
                self.assertNotIn(ev["player_out_id"],
                                 players_on_pitch(tracked, team, ev["t_ms"], True))
            elif ev["type"] == "card" and ev["subtype"] == "second_yellow":
                t = own_minute(ev["t_ms"], ev["period"], p1s, p2s)
                self.assertEqual(by_pid[ev["player_id"]]["off_min"], t)
                team = ev["team_id"]
                self.assertIn(ev["player_id"],
                              players_on_pitch(tracked, team, ev["t_ms"], False))
                self.assertNotIn(ev["player_id"],
                                 players_on_pitch(tracked, team, ev["t_ms"] + 1, False))

        # first/last tracked frame vs on_min/off_min, in TRUE match-clock
        # seconds (45:00 = 2700.0; the raw t_ms skips the half-time break)
        def match_sec(t_ms: int) -> float:
            if t_ms < p2s:
                return (t_ms - p1s) / 1000.0
            return 2700.0 + (t_ms - p2s) / 1000.0

        sub_in_ms: Dict[str, int] = {}
        sub_out_ms: Dict[str, int] = {}
        for ev in tracked["events"]:
            if ev["type"] == "substitution":
                sub_in_ms.setdefault(ev["player_id"], ev["t_ms"])
                sub_out_ms[ev["player_out_id"]] = ev["t_ms"]
        sent_off_ms = {ev["player_id"]: ev["t_ms"] for ev in tracked["events"]
                       if ev["type"] == "card" and ev["subtype"] == "second_yellow"}
        sub_end_ms = {}
        for s in tracked["stoppages"]:
            if s["type"] == "sub":
                for eid in s["related_event_ids"]:
                    ev = next(e for e in tracked["events"] if e["event_id"] == eid)
                    sub_end_ms[ev["t_ms"]] = s["t_end_ms"]
        end_sec = match_sec(tracked["periods"][1]["end_ms"])
        for pid, entry in by_pid.items():
            X = xs[pid]
            on_frames = [k for k, x in enumerate(X) if x >= 0]
            self.assertTrue(on_frames, pid)
            first_t = match_sec(frame_t_ms(tracking, on_frames[0]))
            last_t = match_sec(frame_t_ms(tracking, on_frames[-1]))
            if pid in sub_in_ms:
                # on: the substitute steps on after the player going off has
                # left (task 08 rule 12), so between the sub event and the end
                # of its stoppage
                on_sec = match_sec(sub_in_ms[pid])
                self.assertGreaterEqual(first_t, on_sec - 1.0 - 1e-6, pid)
                self.assertLessEqual(first_t, match_sec(sub_end_ms[sub_in_ms[pid]]) + 1e-6, pid)
            else:
                # starters: on from kick-off (frames are 0.2 s apart)
                self.assertLessEqual(first_t, 1.0 + 1e-6, pid)
            off = entry["off_min"]
            if off is None:
                # never left: on the pitch through the last frame
                self.assertGreaterEqual(last_t, end_sec - 1.0, pid)
            elif pid in sent_off_ms:
                # sent off: removed at the card (decision tick <= 0.5 s later)
                self.assertLessEqual(abs(match_sec(sent_off_ms[pid]) - last_t),
                                     1.0 + 1e-6, pid)
            else:
                # subbed off: the body walks off during the stoppage, so the
                # last on-frame is >= the sub event and <= the stoppage end
                off_ms = sub_out_ms[pid]
                self.assertGreaterEqual(last_t, match_sec(off_ms) - 1e-6, pid)
                self.assertLessEqual(last_t, match_sec(sub_end_ms[off_ms]) + 1.0, pid)


# ---- 6. calibration (slow: seeds 1-10) ----------------------------------------------

@unittest.skipUnless(SLOW, "calibration over seeds 1-10; run with PIPPI_SLOW=1")
class CalibrationTest(unittest.TestCase):
    def test_published_ranges(self) -> None:
        for seed in range(1, 11):
            _t, tracking, feed = built(seed)
            last = feed["last_minute"]
            xs = tracking["x"]
            for entry in feed["players"]:
                pid = entry["player_id"]
                mins = sum(1 for x in xs[pid] if x >= 0) * 0.2 / 60.0
                per90 = entry["stats"]["distance_m"][last] / 1000.0 / mins * 90.0 \
                    if mins > 0 else 0.0
                if mins >= 5.0:
                    self.assertLessEqual(entry["stats"]["top_speed_dmh"][last], 370,
                                         "seed %d %s top %d" % (
                                             seed, pid, entry["stats"]["top_speed_dmh"][last]))
                if mins < 60.0:
                    continue
                if entry["position"] == "GK":
                    self.assertTrue(4.5 <= per90 <= 7.0,
                                    "seed %d %s %.2f km/90" % (seed, pid, per90))
                else:
                    self.assertTrue(8.5 <= per90 <= 12.3,
                                    "seed %d %s %.2f km/90" % (seed, pid, per90))
                    s90 = entry["stats"]["sprints"][last] / mins * 90.0
                    self.assertTrue(5.0 <= s90 <= 35.0,
                                    "seed %d %s %.1f sprints/90" % (seed, pid, s90))


# ---- 7. determinism --------------------------------------------------------------------

class DeterminismTest(unittest.TestCase):
    def test_same_inputs_same_bytes(self) -> None:
        tracked, tracking = track_match(generate_match(2))
        self.assertEqual(dumps(build_players(tracked, tracking)),
                         dumps(build_players(tracked, tracking)))

    def test_cli_seed_equals_files(self) -> None:
        # --seed mode and --match/--tracking mode must agree. The files are written by match-lab's own CLI in this
        # same run, not taken from data/: the committed files come from the owner's Mac, and the long simulation
        # rounds a little differently on Linux (CI), so a fresh seed-43 run there is not byte-identical to them
        # (CI 2026-10-25: COP-11 11.97 km vs 11.91 km). The committed data is checked by the seed-43 QA step.
        from matchlab.track import main as track_main
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.json")
            b = os.path.join(tmp, "b.json")
            tracked_path = os.path.join(tmp, "tracked.json")
            tracking_path = os.path.join(tmp, "tracking.json")
            track_main(["--seed", "43", "--out-match", tracked_path, "--out-tracking", tracking_path])
            main(["--seed", "43", "--out", a])
            main(["--match", tracked_path, "--tracking", tracking_path, "--out", b])
            with open(a, encoding="utf-8") as fh:
                from_a = fh.read()
            with open(b, encoding="utf-8") as fh:
                from_b = fh.read()
        self.assertEqual(from_a, from_b)


# ---- 8. schema ----------------------------------------------------------------------------

class SchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _t, _tr, cls.feed = built(1)

    def test_validates(self) -> None:
        schema = load_schema("players.schema.json")
        self.assertEqual(check(self.feed, schema, schema), [])

    def _rejected(self, mutate, expect: str) -> None:
        bad = copy.deepcopy(self.feed)
        mutate(bad)
        errors = check(bad, load_schema("players.schema.json"),
                       load_schema("players.schema.json"))
        self.assertTrue(any(expect in e for e in errors),
                        "expected %r, got %r" % (expect, errors[:3]))

    def test_negative_stat_rejected(self) -> None:
        self._rejected(lambda f: f["players"][0]["stats"]["passes"].__setitem__(3, -1),
                       "minimum")

    def test_float_stat_rejected(self) -> None:
        self._rejected(lambda f: f["players"][0]["stats"]["sprints"].__setitem__(3, 1.5),
                       "expected type integer")

    def test_missing_stat_rejected(self) -> None:
        self._rejected(lambda f: f["players"][0]["stats"].pop("saves"),
                       "missing required")

    def test_name_rejected(self) -> None:
        self._rejected(lambda f: f["players"][0].update(display_name="Harold Light"),
                       "unexpected property")

    def test_bad_off_min_rejected(self) -> None:
        self._rejected(lambda f: f["players"][0].update(off_min="79.0"),
                       "matches none of the anyOf")

    def test_too_few_players_rejected(self) -> None:
        self._rejected(lambda f: f["players"].pop(), "fewer than")

    def test_no_names_anywhere(self) -> None:
        text = json.dumps(self.feed, sort_keys=True)
        for banned in ("display_name", "first_name", "last_name", "name\""):
            self.assertNotIn(banned, text)


# ---- 9. demo-match untouched -----------------------------------------------------------------

class DemoUnchangedTest(unittest.TestCase):
    def test_demo_match_is_seed_43(self) -> None:
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/.."
        with open(os.path.join(repo, "data", "demo-match.json"), encoding="utf-8") as fh:
            on_disk = fh.read()
        # Built from the tracked events: the tracking may reassign who did what (e.g. the scorer), and viewers see
        # the tracking, so its player ids are the ones the demo must name.
        with open(os.path.join(repo, "data", "tracked-seed-43.json"), encoding="utf-8") as fh:
            tracked = json.load(fh)
        self.assertEqual(on_disk, dumps(build_output(tracked)))


if __name__ == "__main__":
    unittest.main()

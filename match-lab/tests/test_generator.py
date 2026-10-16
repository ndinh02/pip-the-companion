from __future__ import annotations

import unittest

from matchlab import generate_match
from matchlab.generate import dumps

HOME = "HAR"
AWAY = "COP"


def _corner_stats(matches):
    corners = {HOME: 0, AWAY: 0}
    short = {HOME: 0, AWAY: 0}
    for m in matches:
        for ev in m["events"]:
            if ev["type"] == "corner":
                corners[ev["team_id"]] += 1
                if ev["set_piece"]["routine"] == "short":
                    short[ev["team_id"]] += 1
    return corners, short


class DeterminismTest(unittest.TestCase):
    def test_same_seed_is_byte_identical(self):
        self.assertEqual(dumps(generate_match(7)), dumps(generate_match(7)))

    def test_different_seed_differs(self):
        self.assertNotEqual(dumps(generate_match(1)), dumps(generate_match(2)))

    def test_priors_change_the_match(self):
        self.assertNotEqual(dumps(generate_match(1)),
                            dumps(generate_match(1, home_priors={"corner_short_share": 0.9})))


class PriorsTest(unittest.TestCase):
    def test_bad_priors_are_rejected(self):
        with self.assertRaises(ValueError):
            generate_match(1, home_priors={"corner_short_share": 1.5})
        with self.assertRaises(ValueError):
            generate_match(1, away_priors={"nonsense": 0.5})


class StructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.match = generate_match(1)

    def test_events_are_ordered_and_numbered(self):
        events = self.match["events"]
        self.assertGreater(len(events), 800)
        for i, ev in enumerate(events):
            self.assertEqual(ev["idx"], i)
        times = [ev["t_ms"] for ev in events]
        self.assertEqual(times, sorted(times))

    def test_players_are_placeholders(self):
        ids = {p["player_id"] for p in self.match["players"]}
        self.assertEqual(ids, {"%s-%d" % (t, n) for t in (HOME, AWAY) for n in range(1, 15)})
        for ev in self.match["events"]:
            self.assertIn(ev["player_id"], ids)

    def test_periods_and_stoppages(self):
        p1, p2 = self.match["periods"]
        self.assertEqual((p1["id"], p2["id"]), (1, 2))
        self.assertEqual(p1["end_ms"], p2["start_ms"])
        for p in (p1, p2):
            self.assertGreaterEqual(p["added_time_announced_s"], 60)
            self.assertGreaterEqual(p["added_time_actual_s"], 0)
            self.assertGreaterEqual(p["end_ms"] - p["start_ms"], 45 * 60 * 1000)
        for s in self.match["stoppages"]:
            self.assertIn(s["type"], ["injury", "VAR", "sub", "goal", "card", "other"])
            self.assertGreater(s["duration_s"], 0)
        counted = sum(s["duration_s"] for s in self.match["stoppages"] if s["counts_for_added_time"])
        added = sum(p["added_time_actual_s"] for p in self.match["periods"])
        self.assertAlmostEqual(counted, added, delta=2)

    def test_score_matches_goal_events(self):
        for seed in range(1, 11):
            m = generate_match(seed)
            goals = {HOME: 0, AWAY: 0}
            for ev in m["events"]:
                if ev["outcome"] == "goal":
                    goals[ev["team_id"]] += 1
            self.assertEqual(goals, m["final_score"])


class StatisticsTest(unittest.TestCase):
    N = 200

    @classmethod
    def setUpClass(cls):
        cls.matches = [generate_match(seed) for seed in range(1, cls.N + 1)]

    def test_all_coordinates_inside_the_pitch(self):
        for m in self.matches:
            for ev in m["events"]:
                for key in ("start", "end"):
                    self.assertTrue(0.0 <= ev[key]["x"] <= 105.0, (m["seed"], ev["event_id"], ev[key]))
                    self.assertTrue(0.0 <= ev[key]["y"] <= 68.0, (m["seed"], ev["event_id"], ev[key]))

    def test_corners_per_match(self):
        corners, _ = _corner_stats(self.matches)
        mean = (corners[HOME] + corners[AWAY]) / float(self.N)
        self.assertTrue(8.0 <= mean <= 12.0, mean)

    def test_planted_short_corner_share_is_recovered(self):
        corners, short = _corner_stats(self.matches)
        self.assertLess(abs(short[AWAY] / float(corners[AWAY]) - 0.6), 0.05)
        self.assertLess(abs(short[HOME] / float(corners[HOME]) - 0.15), 0.05)

    def test_league_wide_short_share(self):
        # The two planted teams differ on purpose; with equal 0.16 priors the league-wide share
        # must sit in the published 13-18% band.
        league = [generate_match(seed, {"corner_short_share": 0.16}, {"corner_short_share": 0.16})
                  for seed in range(1, 61)]
        c, s = _corner_stats(league)
        share = (s[HOME] + s[AWAY]) / float(c[HOME] + c[AWAY])
        self.assertTrue(0.13 <= share <= 0.18, share)

    def test_ball_in_play_time(self):
        mean_min = sum(m["aggregates"]["ball_in_play_s"] for m in self.matches) / float(self.N) / 60.0
        self.assertTrue(54.0 <= mean_min <= 60.0, mean_min)

    def test_goals_per_match_is_football_like(self):
        mean = sum(sum(m["final_score"].values()) for m in self.matches) / float(self.N)
        self.assertTrue(2.0 <= mean <= 3.5, mean)


if __name__ == "__main__":
    unittest.main()

"""Test 5 — timing policy: per half <= 4 cards, consecutive cards >= 8 min apart,
no non-var card within 60 s after a counted goal, timeline ends at final_score,
cards in time order, period-1 cards at or before minute 45."""
from __future__ import annotations

import unittest
from collections import Counter

from tests import util

SEEDS = (1, 2, 3)
GOAL_QUIET_MS = 60 * 1000


class PolicyTest(unittest.TestCase):
    def test_policy_holds_for_built_matches(self):
        for seed in SEEDS:
            match = util.seed_match(seed)
            demo, accepted = util.seed_demo(seed)
            cards = demo["cards"]
            self.assertEqual(len(cards), len(accepted))

            # cards are in time order
            times = [c["t_in_min"] for c in cards]
            self.assertEqual(times, sorted(times), "seed %d" % seed)

            # period-1 cards sit at or before 45:00
            for card, cand in zip(cards, accepted):
                if cand["period"] == 1:
                    self.assertLessEqual(card["t_in_min"], 45.0, (seed, card["card_id"]))

            # at most 4 cards per half
            per_half = Counter(cand["period"] for cand in accepted)
            for period, n in per_half.items():
                self.assertLessEqual(n, 4, "seed %d period %d has %d cards" % (seed, period, n))

            # consecutive cards are at least 8 minutes apart
            for a, b in zip(cards, cards[1:]):
                self.assertGreaterEqual(b["t_in_min"] - a["t_in_min"], 8.0,
                                        "seed %d: %s -> %s too close" % (seed, a["card_id"], b["card_id"]))

            # no card (except the var card about that goal) within 60 s after a goal
            goal_events = [(e["t_ms"], e["event_id"]) for e in match["events"]
                           if e["outcome"] == "goal"]
            for card, cand in zip(cards, accepted):
                for g_ms, g_id in goal_events:
                    if g_ms < cand["t_ms"] <= g_ms + GOAL_QUIET_MS:
                        self.assertTrue(cand["trigger"] == "var" and cand["goal_event_id"] == g_id,
                                        "seed %d: %s within 60 s after goal %s"
                                        % (seed, card["card_id"], g_id))

    def test_score_timeline_ends_at_final_score(self):
        for seed in SEEDS:
            match = util.seed_match(seed)
            demo, _accepted = util.seed_demo(seed)
            timeline = demo["score_timeline"]
            self.assertEqual(timeline[0]["from_min"], 0)
            self.assertEqual((timeline[-1]["HAR"], timeline[-1]["COP"]),
                             (match["final_score"]["HAR"], match["final_score"]["COP"]),
                             "seed %d" % seed)
            # one entry per counted goal plus kick-off
            goals = sum(1 for e in match["events"] if e["outcome"] == "goal")
            self.assertEqual(len(timeline), goals + 1)
            # scores only ever go up
            for a, b in zip(timeline, timeline[1:]):
                self.assertEqual(b["from_min"] > a["from_min"], True)
                for team in ("HAR", "COP"):
                    self.assertGreaterEqual(b[team], a[team])
                    self.assertLessEqual(b[team] - a[team], 1)


if __name__ == "__main__":
    unittest.main()

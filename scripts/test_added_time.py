"""Run: python3 scripts/test_added_time.py"""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "match-lab"))

from added_time import build, dumps  # noqa: E402
from matchlab import generate_match  # noqa: E402


class AddedTimeTest(unittest.TestCase):
    def test_breakdown_matches_stoppages_for_many_seeds(self):
        for seed in range(1, 41):
            m = generate_match(seed)
            data = build(m)
            self.assertEqual([b["period"] for b in data["boards"]], [1, 2])
            self.assertEqual([b["at_min"] for b in data["boards"]], [45, 90])
            for board, period in zip(data["boards"], m["periods"]):
                self.assertEqual(board["announced_min"] * 60, period["added_time_announced_s"])
                self.assertEqual(board["actual_s"], period["added_time_actual_s"])
                # rounding to whole seconds per type can move the sum by at most 0.5 s per type
                self.assertAlmostEqual(sum(i["seconds"] for i in board["items"]), board["actual_s"], delta=len(board["items"]) + 1)
                secs = [i["seconds"] for i in board["items"]]
                self.assertEqual(secs, sorted(secs, reverse=True))

    def test_every_stoppage_is_counted_once(self):
        m = generate_match(3)
        data = build(m)
        counted = [s for s in m["stoppages"] if s["counts_for_added_time"]]
        non_sub = sum(1 for s in counted if s["type"] != "sub")
        subs = sum(len(s["related_event_ids"]) for s in counted if s["type"] == "sub")
        self.assertEqual(sum(i["count"] for b in data["boards"] for i in b["items"]), non_sub + subs)

    def test_deterministic_and_preview_label(self):
        m = generate_match(1)
        self.assertEqual(dumps(build(m)), dumps(build(m)))
        p = build(m, "mock-001")
        self.assertEqual((p["match_id"], p["preview_for"], p["real_match_id"]), ("mock-001", "mock-001", m["match_id"]))


if __name__ == "__main__":
    unittest.main()

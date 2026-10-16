"""Test 2 — no spoilers: a fact's value never changes when everything after the
moment's own event is deleted and the card's facts are rebuilt from the truncated
copy (events and stoppages after the moment are removed)."""
from __future__ import annotations

import copy
import unittest

from matchreader import reader
from tests import util

SEEDS = (1, 2, 3)


class NoFutureTest(unittest.TestCase):
    def test_facts_unchanged_on_truncated_match(self):
        checked = 0
        for seed in SEEDS:
            match = util.seed_match(seed)
            eligible, _held = reader.candidates(match, reader.load_templates())
            for cand in eligible:
                truncated = copy.deepcopy(match)
                truncated["events"] = [e for e in match["events"] if e["t_ms"] <= cand["t_ms"]]
                truncated["stoppages"] = [s for s in match["stoppages"]
                                          if s["t_start_ms"] <= cand["t_ms"]]
                self.assertEqual(reader.card_facts(truncated, cand),
                                 reader.card_facts(match, cand),
                                 (seed, cand["trigger"], cand["t_in_min"]))
                checked += 1
        self.assertGreater(checked, 20, "expected a decent number of candidates, got %d" % checked)


if __name__ == "__main__":
    unittest.main()

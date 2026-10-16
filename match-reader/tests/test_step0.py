"""Test 7 — Step 0: VAR stoppages carry var.margin_cm (integer 1-40 for offside,
null for foul) and the regenerated data/mock-seed-1.json is unchanged apart from
the new field (its content must equal a fresh generate_match(1))."""
from __future__ import annotations

import os
import unittest

from matchlab.generate import dumps as matchlab_dumps
from tests import util


class VarMarginTest(unittest.TestCase):
    def test_offside_var_has_margin_in_range(self):
        seen_offside = 0
        for seed in range(1, 60):
            for stoppage in util.seed_match(seed)["stoppages"]:
                if stoppage["type"] != "VAR":
                    continue
                margin = stoppage["var"]["margin_cm"]
                if stoppage["var"]["check_type"] == "offside":
                    self.assertIsInstance(margin, int, (seed, stoppage))
                    self.assertTrue(1 <= margin <= 40, (seed, margin))
                    seen_offside += 1
                else:  # foul
                    self.assertIsNone(margin, (seed, stoppage))
        self.assertGreaterEqual(seen_offside, 3, "no offside VAR found in seeds 1-59?")

    def test_seed_1_file_matches_generator(self):
        with open(os.path.join(util.DATA_DIR, "mock-seed-1.json"), encoding="utf-8") as fh:
            on_disk = fh.read()
        self.assertEqual(on_disk, matchlab_dumps(util.seed_match(1)))


if __name__ == "__main__":
    unittest.main()

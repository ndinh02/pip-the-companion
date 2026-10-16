"""Test 3 — copy rules: port of scripts/check-copy.mjs, plus self-tests so a green
run means the checker actually catches bad copy."""
from __future__ import annotations

import copy
import unittest

from matchreader.copycheck import check_copy
from tests import util

SEEDS = (1, 2, 3)


class CopyRulesTest(unittest.TestCase):
    def test_built_matches_are_clean(self):
        for seed in SEEDS:
            demo, _accepted = util.seed_demo(seed)
            self.assertEqual(check_copy(demo), [], "seed %d: %s" % (seed, check_copy(demo)[:5]))


class CheckerSelfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo, _accepted = util.seed_demo(1)
        assert cls.demo["cards"], "seed 1 built with no cards; pick another seed for the fixture"

    def assertRejected(self, mutate, expect):
        bad = copy.deepcopy(self.demo)
        mutate(bad)
        errors = check_copy(bad)
        self.assertTrue(any(expect in e for e in errors),
                        "expected an error containing %r, got %r" % (expect, errors[:3]))

    def test_banned_word_en(self):
        def mutate(d):
            d["cards"][0]["reveal"]["plain"]["en"] = "Check the odds, folks!"
        self.assertRejected(mutate, "banned word")

    def test_banned_word_de(self):
        def mutate(d):
            d["cards"][0]["question"]["text"]["de"] = "Jetzt die Wette!"
        self.assertRejected(mutate, "banned word")

    def test_hard_coded_number(self):
        def mutate(d):
            d["cards"][0]["reveal"]["expert"]["en"] = "They played 3 corners short."
        self.assertRejected(mutate, "hard-coded number")

    def test_placeholder_number_is_fine(self):
        def mutate(d):
            card = d["cards"][0]
            card["reveal"]["expert"]["en"] = "Fact: {" + card["reveal"]["fact_ids"][0] + "}."
        bad = copy.deepcopy(self.demo)
        mutate(bad)
        self.assertEqual(check_copy(bad), [])

    def test_unknown_placeholder(self):
        def mutate(d):
            d["cards"][0]["reveal"]["plain"]["en"] = "They played {nonsense} corners."
        self.assertRejected(mutate, "not in fact_ids")

    def test_too_long_string(self):
        def mutate(d):
            d["cards"][0]["reveal"]["plain"]["en"] = "x" * 201
        self.assertRejected(mutate, "chars > 200")

    def test_leftover_team_placeholder(self):
        def mutate(d):
            d["cards"][0]["reveal"]["plain"]["en"] = "<team> did a thing."
        self.assertRejected(mutate, "leftover <team>")

    def test_answer_not_among_options(self):
        def mutate(d):
            d["cards"][0]["reveal"]["answer"] = "nonsense"
        self.assertRejected(mutate, "answer not among options")


if __name__ == "__main__":
    unittest.main()

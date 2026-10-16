"""Test 4 — every card validates against schemas/overlay_card.schema.json."""
from __future__ import annotations

import copy
import unittest

from matchreader.schemacheck import validate_card
from tests import util

SEEDS = (1, 2, 3)


class CardSchemaTest(unittest.TestCase):
    def test_cards_validate(self):
        checked = 0
        for seed in SEEDS:
            demo, _accepted = util.seed_demo(seed)
            for card in demo["cards"]:
                errors = validate_card(card)
                self.assertEqual(errors, [], "seed %d %s: %s" % (seed, card["card_id"], errors[:3]))
                checked += 1
        self.assertGreater(checked, 5)


class ValidatorSelfTest(unittest.TestCase):
    """The mini validator must reject bad cards, or a green test means nothing."""

    @classmethod
    def setUpClass(cls):
        cls.card = util.seed_demo(1)[0]["cards"][0]

    def assertRejected(self, mutate, expect):
        bad = copy.deepcopy(self.card)
        mutate(bad)
        errors = validate_card(bad)
        self.assertTrue(any(expect in e for e in errors),
                        "expected an error containing %r, got %r" % (expect, errors[:3]))

    def test_too_long_text(self):
        def mutate(c):
            c["question"]["text"]["en"] = "x" * 201
        self.assertRejected(mutate, "maxLength")

    def test_unknown_trigger(self):
        self.assertRejected(lambda c: c.update(trigger="throw_in"), "enum")

    def test_extra_property(self):
        self.assertRejected(lambda c: c.update(odds=1.5), "unexpected property")

    def test_pitch_out_of_range(self):
        def mutate(c):
            c["pitch"]["x"] = 105.5
        self.assertRejected(mutate, "maximum")

    def test_bad_card_id(self):
        self.assertRejected(lambda c: c.update(card_id="C1 Corner"), "does not match")

    def test_missing_reveal(self):
        self.assertRejected(lambda c: c.pop("reveal"), "missing required")


if __name__ == "__main__":
    unittest.main()

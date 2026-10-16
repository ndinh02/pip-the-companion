"""AGENTS.md rule 8: Pippi never repeats a line within a match."""
from __future__ import annotations

import copy
import unittest

from matchreader import reader

from tests.util import seed_match


class NoRepeatedLinesTest(unittest.TestCase):
    def test_no_question_or_reveal_line_repeats_in_any_language(self):
        for seed in range(1, 61):
            out = reader.build_output(seed_match(seed))
            for lang in reader.LANGS:
                questions = [c["question"]["text"][lang] for c in out["cards"]]
                plains = [c["reveal"]["plain"][lang] for c in out["cards"]]
                self.assertEqual(len(questions), len(set(questions)), (seed, lang, questions))
                self.assertEqual(len(plains), len(set(plains)), (seed, lang, plains))

    def test_free_kick_cards_get_different_questions(self):
        tpl = reader.load_templates()
        out = reader.build_output(seed_match(43), tpl)
        fks = [c for c in out["cards"] if c["trigger"] == "free_kick"]
        self.assertGreaterEqual(len(fks), 2)
        self.assertEqual(len({c["question"]["text"]["en"] for c in fks}), len(fks))

    def test_moment_is_held_when_no_unused_line_is_left(self):
        tpl = copy.deepcopy(reader.load_templates())
        # leave exactly one wording for every free-kick question: only one free-kick card may survive
        tpl["free_kick"]["question"]["text"] = reader._variants(tpl["free_kick"]["question"]["text"])[:1]
        out = reader.build_output(seed_match(43), tpl)
        self.assertEqual(sum(1 for c in out["cards"] if c["trigger"] == "free_kick"), 1)
        self.assertTrue(any(h["reason"] == "no_fresh_line" for h in out["moments_held"]))

    def test_all_templates_have_enough_variants_for_a_normal_match(self):
        tpl = reader.load_templates()
        # a half allows 4 cards and a match 8, so the common kinds need several wordings
        self.assertGreaterEqual(len(reader._variants(tpl["free_kick"]["question"]["text"])), 4)
        for key in ("cross", "shoot", "short"):
            self.assertGreaterEqual(len(reader._variants(tpl["free_kick"]["reveal"][key]["plain"])), 4)


if __name__ == "__main__":
    unittest.main()

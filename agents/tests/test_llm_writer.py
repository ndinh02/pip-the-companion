"""The LLM writer without a model: a fake reply stands in for Foundry Local."""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pip_agents import llm_writer  # noqa: E402
from pip_agents.workflow import run_match  # noqa: E402
from matchlab import generate_match  # noqa: E402


def make_writer(replies):
    with mock.patch.object(llm_writer, "resolve_model", return_value="fake-model"):
        w = llm_writer.LLMWriter("fake", base_url="http://127.0.0.1:1")
    it = iter(replies)
    w._fake = mock.patch.object(llm_writer, "_chat", side_effect=lambda *a, **k: next(it))
    return w


class LLMWriterTest(unittest.TestCase):
    def setUp(self):
        self.match = generate_match(43)

    def run_with(self, replies_for_all):
        w = make_writer(replies_for_all)
        w.team_names = {"HAR": "Harbour Lights", "COP": "Copperfield"}
        with w._fake:
            return run_match(self.match, w)

    def test_good_reply_with_placeholders_is_approved_and_scoped(self):
        good = '{"plain": "Cross! Copperfield sent it into the box.", "expert": "They have crossed {fk_cross} of {fk_total} free kicks today."}'
        offside = '{"plain": "Offside check: the attacker was level, so the goal stands.", "expert": "Onside by {var_margin_cm} cm."}'
        replies = []
        for card in run_match(self.match)["cards"]:  # one reply per card, matching its kind
            replies.append({"var": offside}.get(card["trigger"], good))
        trace = self.run_with(replies)
        fk = next(c for c in trace["cards"] if c["trigger"] == "free_kick" and "cross" in c["approved_plain_en"].lower())
        self.assertTrue(fk["approved_by"].startswith("llm:"))
        self.assertIn("{%s_fk_cross}" % fk["card_id"].split("-")[0], fk["approved_expert_en"])

    def test_numbers_betting_and_garbage_are_rejected_then_fall_back(self):
        bad = ['{"plain": "Cross! 3 of 4 again.", "expert": "Crossed 3 of 4."}', "not json at all",
               '{"plain": "Cross! Check the odds.", "expert": "{fk_cross} crosses."}']
        trace = self.run_with(bad * 20)
        for c in trace["cards"]:
            self.assertEqual(c["approved_by"], "template (fallback)", c["card_id"])
            self.assertEqual([a["checker"] for a in c["attempts"]][-1], "pass")
            self.assertTrue(all(a["checker"] == "fail" for a in c["attempts"][:-1]))


if __name__ == "__main__":
    unittest.main()

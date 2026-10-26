"""Run from agents/: python3 -m unittest discover -s tests"""
from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pip_agents import paths  # noqa: E402,F401
from pip_agents.run import build  # noqa: E402
from pip_agents.workflow import run_match  # noqa: E402
from pip_agents.writers import AlwaysLyingWriter, LyingOnceWriter  # noqa: E402
from matchlab import generate_match  # noqa: E402
from matchreader import reader  # noqa: E402


class WorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.match = generate_match(43)
        cls.shipped = reader.build_output(cls.match)

    def test_honest_run_approves_every_card_first_time(self):
        trace = run_match(self.match)
        self.assertEqual(len(trace["cards"]), len(self.shipped["cards"]))
        for c in trace["cards"]:
            self.assertEqual([a["checker"] for a in c["attempts"]], ["pass"], c["card_id"])
        self.assertTrue(trace["shipped_equals_checked"])
        self.assertFalse(trace["uses_ai"])

    def test_a_lie_is_rejected_then_repaired(self):
        target = next(c["card_id"] for c in self.shipped["cards"] if c["reveal"]["fact_ids"])
        entry = next(c for c in run_match(self.match, None, {target: LyingOnceWriter()})["cards"] if c["card_id"] == target)
        first, second = entry["attempts"][0], entry["attempts"][1]
        self.assertEqual(first["checker"], "fail")
        self.assertTrue(any("match events say" in e for e in first["errors"]), first["errors"])
        self.assertTrue(any("hard-coded number" in e for e in first["errors"]), first["errors"])
        self.assertEqual(second["checker"], "pass")
        self.assertEqual(len(entry["attempts"]), 2)

    def test_a_writer_that_never_recovers_falls_back_to_the_template(self):
        target = self.shipped["cards"][-1]["card_id"]
        entry = next(c for c in run_match(self.match, None, {target: AlwaysLyingWriter()})["cards"] if c["card_id"] == target)
        self.assertEqual([a["checker"] for a in entry["attempts"]], ["fail", "fail", "fail", "pass"])
        self.assertTrue(all(any("banned word" in e for e in a["errors"]) for a in entry["attempts"][:3]))
        self.assertEqual(entry["approved_by"], "template (fallback)")

    def test_sabotage_never_changes_what_ships(self):
        for seed in (1, 30, 43):
            match = generate_match(seed)
            shipped = reader.build_output(match)
            ids = [c["card_id"] for c in shipped["cards"]]
            trace = run_match(match, None, {i: (LyingOnceWriter() if n % 2 else AlwaysLyingWriter()) for n, i in enumerate(ids)})
            self.assertTrue(trace["shipped_equals_checked"], seed)
            for entry, card in zip(trace["cards"], shipped["cards"]):
                self.assertEqual(entry["approved_expert_en"], card["reveal"]["expert"]["en"])
                self.assertEqual(entry["approved_plain_en"], card["reveal"]["plain"]["en"])
                self.assertNotIn("odds", entry["approved_plain_en"].lower())

    def test_writers_only_get_numbers_through_tools(self):
        trace = run_match(self.match)
        for c in trace["cards"]:
            asked = {t["fact_id"] for t in c["tool_calls"] if t["tool"] == "get_fact"}
            self.assertEqual(asked, set(c["approved_facts"]), c["card_id"])

    def test_cli_output_is_deterministic_and_has_the_integrity_demo(self):
        a, b = build(43), build(43)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        demo = a["catch_me_lying"]
        self.assertEqual(len(demo["cards"]), 2)
        self.assertTrue(demo["shipped_equals_checked"])


if __name__ == "__main__":
    unittest.main()

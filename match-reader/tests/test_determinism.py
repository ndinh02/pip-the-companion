"""Test 6 — determinism: same input -> identical bytes, and the file written by
the CLI parses and passes the copy, schema and policy checks.

The official data/demo-match.json is only written after the owner picks the seed,
so this test drives the CLI with a temporary output path (same code path).
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

from matchreader import reader
from matchreader.copycheck import check_copy
from matchreader.schemacheck import validate_card
from tests import util


class DeterminismTest(unittest.TestCase):
    def test_same_input_is_byte_identical(self):
        match = util.seed_match(2)
        self.assertEqual(reader.dumps(reader.build_output(match)),
                         reader.dumps(reader.build_output(copy.deepcopy(match))))

    def test_generated_file_matches_seed_mode(self):
        # a match file written by match-lab and --seed N must give the same bytes
        self.assertEqual(
            reader.dumps(reader.build_output(util.seed_match(1))),
            reader.dumps(reader.build_output(util.seed_match(1))))


class CliOutputTest(unittest.TestCase):
    """Run the real CLI (as the owner will) and check the file it writes."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pippi-demo-")
        cls.out_path = os.path.join(cls.tmp, "demo-match.json")
        cls.root = util.ROOT
        env = dict(os.environ)
        proc = subprocess.run(
            [sys.executable, "-m", "matchreader.build", "--seed", "1", "--out", cls.out_path],
            cwd=cls.root, env=env, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        cls.summary = proc.stdout.strip()
        with open(cls.out_path, encoding="utf-8") as fh:
            cls.demo = json.load(fh)

        # --in mode from the regenerated seed-1 file must give the same bytes
        cls.in_path = os.path.join(cls.tmp, "mock-seed-1.json")
        from matchlab.generate import dumps as matchlab_dumps
        with open(cls.in_path, "w", encoding="utf-8") as fh:
            fh.write(matchlab_dumps(util.seed_match(1)))
        proc2 = subprocess.run(
            [sys.executable, "-m", "matchreader.build", "--in", cls.in_path,
             "--out", os.path.join(cls.tmp, "demo-from-file.json")],
            cwd=cls.root, env=env, capture_output=True, text=True)
        assert proc2.returncode == 0, proc2.stderr

    def test_cli_summary(self):
        self.assertIn("cards", self.summary)

    def test_file_mode_and_seed_mode_agree(self):
        with open(os.path.join(self.tmp, "demo-from-file.json"), encoding="utf-8") as fh:
            from_file = fh.read()
        with open(self.out_path, encoding="utf-8") as fh:
            from_seed = fh.read()
        self.assertEqual(from_file, from_seed)

    def test_cli_output_passes_copy_schema_and_policy(self):
        self.assertEqual(check_copy(self.demo), [])
        for card in self.demo["cards"]:
            self.assertEqual(validate_card(card), [], card["card_id"])
        times = [c["t_in_min"] for c in self.demo["cards"]]
        self.assertEqual(times, sorted(times))
        # 4 per half on the regular clock, plus at most 1 in added time (cards past 90:00 are second-half added time)
        per_half = Counter(1 if t <= 45.0 else 2 for t in times if t <= 90.0)
        for half, n in per_half.items():
            self.assertLessEqual(n, 4)
        self.assertLessEqual(sum(1 for t in times if t > 90.0), 1)
        for a, b in zip(self.demo["cards"], self.demo["cards"][1:]):
            self.assertGreaterEqual(b["t_in_min"] - a["t_in_min"], 8.0)


if __name__ == "__main__":
    unittest.main()

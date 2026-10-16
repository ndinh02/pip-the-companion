"""Test 1 — facts are true: a second, simple implementation recounts every fact.

For 5 seeds, recompute corners_short/total, fk_cross/total, the before/after
position counts and subs_used by looping over the events, and compare with what
the reader computed for each candidate moment.
"""
from __future__ import annotations

import unittest

from matchreader import reader
from tests import util

SEEDS = (1, 2, 3, 4, 5)
HAR, COP = "HAR", "COP"


# ---- the second implementation (kept dumb on purpose) ----

def recount_corners(match, ev):
    total = short = 0
    for e in match["events"]:
        if e["type"] == "corner" and e["team_id"] == ev["team_id"] and e["t_ms"] <= ev["t_ms"]:
            total += 1
            if e["set_piece"]["routine"] == "short":
                short += 1
    return short, total


def opp_half(e):
    # Harbour Lights attack +x in period 1, Copperfield in period 2.
    attacks_plus_x = (e["team_id"] == HAR) == (e["period"] == 1)
    return e["start"]["x"] > 52.5 if attacks_plus_x else e["start"]["x"] < 52.5


def recount_free_kicks(match, ev):
    total = crossed = 0
    for e in match["events"]:
        if (e["type"] == "free_kick" and e["team_id"] == ev["team_id"]
                and e["t_ms"] <= ev["t_ms"] and opp_half(e)):
            total += 1
            if e["set_piece"]["routine"] == "cross":
                crossed += 1
    return crossed, total


def recount_on_pitch(match, team, t_ms, inclusive):
    shirts = {p["player_id"]: p["shirt_no"] for p in match["players"] if p["team_id"] == team}
    on = set(pid for pid, no in shirts.items() if no <= 11)
    for e in match["events"]:
        if e["team_id"] != team:
            continue
        if e["t_ms"] > t_ms or (e["t_ms"] == t_ms and not inclusive):
            continue
        if e["type"] == "substitution":
            on.remove(e["player_out_id"])
            on.add(e["player_id"])
        elif e["type"] == "card" and e["subtype"] == "second_yellow":
            on.discard(e["player_id"])
    return on


def recount_subs_used(match, team, t_ms):
    used = 0
    for e in match["events"]:
        if e["type"] == "substitution" and e["team_id"] == team and e["t_ms"] <= t_ms:
            used += 1
    return used


class FactsAreTrueTest(unittest.TestCase):
    def test_every_candidate_fact_recounts(self):
        templates = reader.load_templates()
        checked = {"corner": 0, "free_kick": 0, "substitution": 0, "var": 0}
        for seed in SEEDS:
            match = util.seed_match(seed)
            eligible, _held = reader.candidates(match, templates)
            positions = {p["player_id"]: p["position"] for p in match["players"]}
            for cand in eligible:
                facts = reader.card_facts(match, cand)
                trigger = cand["trigger"]
                checked[trigger] += 1
                if trigger == "corner":
                    short, total = recount_corners(match, cand["event"])
                    self.assertEqual(facts["corners_short"], short, (seed, cand))
                    self.assertEqual(facts["corners_total"], total, (seed, cand))
                    self.assertEqual(facts["league_short_share_pct"], 16)
                elif trigger == "free_kick":
                    crossed, total = recount_free_kicks(match, cand["event"])
                    self.assertEqual(facts["fk_cross"], crossed, (seed, cand))
                    self.assertEqual(facts["fk_total"], total, (seed, cand))
                elif trigger == "substitution":
                    position = {"attack": "FW", "defend": "DF", "fresh": "MF"}[cand["answer"]]
                    before = recount_on_pitch(match, cand["team_id"], cand["t_ms"], False)
                    after = recount_on_pitch(match, cand["team_id"], cand["t_ms"], True)
                    name = {"FW": "forwards", "DF": "defenders", "MF": "midfielders"}[position]
                    self.assertEqual(
                        facts[name + "_before"],
                        sum(1 for pid in before if positions[pid] == position), (seed, cand))
                    self.assertEqual(
                        facts[name + "_after"],
                        sum(1 for pid in after if positions[pid] == position), (seed, cand))
                    if cand["answer"] == "fresh":
                        self.assertEqual(facts["subs_used"],
                                         recount_subs_used(match, cand["team_id"], cand["t_ms"]),
                                         (seed, cand))
                        self.assertEqual(facts["subs_max"], 3)
                elif trigger == "var":
                    self.assertEqual(facts["var_margin_cm"],
                                     cand["stoppage"]["var"]["margin_cm"], (seed, cand))
        for trigger, n in checked.items():
            self.assertGreater(n, 0, "no %s candidate found in seeds %s" % (trigger, SEEDS))

    def test_selected_cards_use_exactly_those_facts(self):
        for seed in SEEDS:
            demo, accepted = util.seed_demo(seed)
            self.assertEqual(len(demo["cards"]), len(accepted))
            for n, (card, cand) in enumerate(zip(demo["cards"], accepted), start=1):
                prefix = "c%d_" % n
                self.assertTrue(all(fid.startswith(prefix) for fid in card["reveal"]["fact_ids"]))
                for fid in card["reveal"]["fact_ids"]:
                    self.assertIn(fid, demo["facts"])
                    self.assertIn("source", demo["facts"][fid])


if __name__ == "__main__":
    unittest.main()

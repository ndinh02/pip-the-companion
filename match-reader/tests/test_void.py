"""Task 11 — "No clear answer": a corner or free kick the match did not settle is void.

A void card carries reveal.void = true, pose "thinks", and a plain line that says what
really happened. Substitutions and VAR are never void.
"""
from __future__ import annotations

import unittest

from matchreader import reader
from matchreader.schemacheck import validate_card
from tests import util


def _event(idx, etype, team, t_ms, start, end, zone=None, period=1):
    return {
        "idx": idx, "event_id": "e%05d" % idx, "type": etype, "team_id": team,
        "period": period, "t_ms": t_ms, "start": {"x": start[0], "y": start[1]},
        "end": {"x": end[0], "y": end[1]}, "outcome": "fail" if etype == "corner" else "success",
        "subtype": None, "player_id": team + "-9", "possession_id": idx,
        "pressure_level": 1,
        "set_piece": ({"delivery": "inswing", "routine": "cross", "target_zone": zone}
                      if etype in ("corner", "free_kick") else None),
    }


def _match_with_third_corner(first_contact):
    """Harbour Lights take three corners (habit needs three), then `first_contact` follows
    the third one. Returns the hand-built match; the third corner is the one under test."""
    minute = 60000
    events = [
        _event(0, "corner", "HAR", 10 * minute, (105.0, 68.0), (93.0, 38.0), "near"),
        _event(1, "corner", "HAR", 20 * minute, (105.0, 68.0), (93.0, 38.0), "near"),
        _event(2, "corner", "HAR", 30 * minute, (105.0, 68.0), (93.0, 38.0), "near"),
    ]
    events.append(first_contact)  # the first contact after the third corner, idx 3
    return {
        "match_id": "hand-built", "seed": 0, "generator_version": "test",
        "competition": "test", "venue": "test", "pitch": {"length": 105, "width": 68},
        "coord_system": "metres", "frame_rate": 10,
        "teams": [
            {"team_id": "HAR", "name": "Harbour Lights", "short_name": "HAR",
             "kit": {"primary": "#2E7FC4", "secondary": "#FFFFFF"}},
            {"team_id": "COP", "name": "Copperfield", "short_name": "COP",
             "kit": {"primary": "#C8692F", "secondary": "#000000"}},
        ],
        "periods": [{"id": 1, "start_ms": 0, "end_ms": 2700000},
                    {"id": 2, "start_ms": 2910000, "end_ms": 5400000}],
        "players": [], "stoppages": [], "events": events,
        "final_score": {"HAR": 0, "COP": 0},
    }


def _defender_clearance(x, y):
    return _event(3, "clearance", "COP", 30 * 60000 + 4000, (x, y), (60.0, 40.0))


def _defender_pass(x, y):
    return _event(3, "pass", "COP", 30 * 60000 + 4000, (x, y), (60.0, 40.0))


def _build_third_corner(first_contact):
    match = _match_with_third_corner(first_contact)
    out = reader.build_output(match)
    cards = [c for c in out["cards"] if c["trigger"] == "corner"]
    return out, cards


class VoidCornerTest(unittest.TestCase):
    def test_clearance_from_inside_six_yard_box_is_void(self):
        # 5 m out from the goal line, on the goal centre line: inside the six-yard box
        out, cards = _build_third_corner(_defender_clearance(100.0, 34.0))
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertIs(card["reveal"]["void"], True)
        self.assertEqual(card["reveal"]["pose"], "thinks")
        self.assertEqual(card["reveal"]["answer"], "near")  # closest valid option
        self.assertEqual(validate_card(card), [])
        void_lines = [v["en"] for v in reader._variants(
            reader.load_templates()["corner"]["reveal"]["void"]["plain"])]
        self.assertIn(card["reveal"]["plain"]["en"], void_lines)

    def test_clearance_from_outside_six_yard_box_is_not_void(self):
        _out, cards = _build_third_corner(_defender_clearance(80.0, 34.0))
        self.assertEqual(len(cards), 1)
        self.assertNotIn("void", cards[0]["reveal"])
        self.assertNotEqual(cards[0]["reveal"]["pose"], "thinks")

    def test_corner_taken_again_straight_away_is_void(self):
        retake = _event(3, "corner", "HAR", 30 * 60000 + 4000, (105.0, 0.0), (93.0, 38.0), "far")
        _out, cards = _build_third_corner(retake)
        self.assertEqual(len(cards), 1)
        self.assertIs(cards[0]["reveal"]["void"], True)

    def test_normal_corner_has_no_void_key(self):
        _out, cards = _build_third_corner(_defender_pass(60.0, 40.0))
        self.assertEqual(len(cards), 1)
        self.assertNotIn("void", cards[0]["reveal"])
        self.assertEqual(validate_card(cards[0]), [])


class VoidFreeKickTest(unittest.TestCase):
    def _free_kick(self):
        return _event(5, "free_kick", "HAR", 1000000, (80.0, 30.0), (90.0, 30.0), "cross")

    def test_free_kick_taken_again_is_void(self):
        match = {"events": [self._free_kick(),
                            _event(6, "free_kick", "HAR", 1005000, (80.0, 30.0), (90.0, 30.0), "cross")],
                 "stoppages": []}
        self.assertTrue(reader._set_piece_void(match, match["events"][0]))

    def test_free_kick_stopped_by_foul_is_void(self):
        match = {"events": [self._free_kick(),
                            _event(6, "foul", "COP", 1002000, (80.0, 30.0), (80.0, 30.0))],
                 "stoppages": []}
        self.assertTrue(reader._set_piece_void(match, match["events"][0]))

    def test_free_kick_with_normal_play_is_not_void(self):
        match = {"events": [self._free_kick(),
                            _event(6, "pass", "COP", 1002000, (90.0, 30.0), (60.0, 40.0))],
                 "stoppages": []}
        self.assertFalse(reader._set_piece_void(match, match["events"][0]))

    def test_substitution_and_var_are_never_void(self):
        sub = _event(5, "substitution", "HAR", 1000000, (50.0, 30.0), (50.0, 30.0))
        match = {"events": [sub, _event(6, "free_kick", "HAR", 1002000, (80, 30), (90, 30))],
                 "stoppages": []}
        self.assertFalse(reader._set_piece_void(match, sub))


class VoidCardsInDemosTest(unittest.TestCase):
    def test_only_corners_and_free_kicks_carry_void(self):
        for seed in (1, 2, 3):
            demo, _accepted = util.seed_demo(seed)
            for card in demo["cards"]:
                if card["trigger"] in ("substitution", "var"):
                    self.assertNotIn("void", card["reveal"], "seed %d %s" % (seed, card["card_id"]))

    def test_normal_cards_have_no_void_key(self):
        for seed in (1, 2, 3):
            demo, _accepted = util.seed_demo(seed)
            for card in demo["cards"]:
                if not card["reveal"].get("void"):
                    self.assertNotIn("void", card["reveal"], "seed %d %s" % (seed, card["card_id"]))

    def test_seed_43_has_exactly_one_void_card(self):
        # Task 11, step 3 (owner decision 2026-10-26): seed 43's naturally void corner (93.2 min,
        # retaken) is shown through the added-time allowance (ADDED_TIME_EXTRA in reader.py).
        demo, _accepted = util.seed_demo(43)
        voids = [c["card_id"] for c in demo["cards"] if c["reveal"].get("void")]
        self.assertEqual(len(voids), 1, voids)


if __name__ == "__main__":
    unittest.main()

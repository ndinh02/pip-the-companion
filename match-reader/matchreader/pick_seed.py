"""Command line: score seeds and print the best demo candidates.

    cd match-reader
    python3 -m matchreader.pick_seed --from 1 --to 200

A seed qualifies when the built match has >= 1 card of each of the four triggers,
>= 6 cards, >= 1 card in each half, and Pip is right at least once and wrong at
least once. Ranking: number of cards (more is better), then closest final score
(smallest goal difference — read as the tightest scoreline for a demo).

The table is printed only; Claude and the owner pick the demo seed (task 03).
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from .build import _load_matchlab
from .reader import build_output

TRIGGERS = ("corner", "free_kick", "substitution", "var")


def score_seed(demo: Dict[str, Any]) -> Dict[str, Any]:
    counts = {t: 0 for t in TRIGGERS}
    right = wrong = 0
    halves = set()
    for card in demo["cards"]:
        counts[card["trigger"]] += 1
        if card["question"]["pippi_call"] == card["reveal"]["answer"]:
            right += 1
        else:
            wrong += 1
        halves.add(1 if card["t_in_min"] <= 45.0 else 2)
    last = demo["score_timeline"][-1]
    total = sum(counts.values())
    qualifies = (all(counts[t] >= 1 for t in TRIGGERS) and total >= 6
                 and halves == {1, 2} and right >= 1 and wrong >= 1)
    return {"counts": counts, "total": total, "right": right, "wrong": wrong,
            "halves": halves, "score": (last["HAR"], last["COP"]), "qualifies": qualifies}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the best demo seeds; Claude and the owner pick one.")
    parser.add_argument("--from", dest="from_seed", type=int, default=1)
    parser.add_argument("--to", dest="to_seed", type=int, default=200)
    parser.add_argument("--top", type=int, default=8, help="how many rows to print")
    args = parser.parse_args(argv)

    generate_match = _load_matchlab()

    rows: List[Tuple[int, Dict[str, Any]]] = []
    for seed in range(args.from_seed, args.to_seed + 1):
        demo = build_output(generate_match(seed))
        rows.append((seed, score_seed(demo)))

    qualified = sum(1 for _seed, s in rows if s["qualifies"])
    rows.sort(key=lambda item: (
        0 if item[1]["qualifies"] else 1,               # qualifying seeds first
        -item[1]["total"],                              # more cards is better
        abs(item[1]["score"][0] - item[1]["score"][1]), # closest final score
        -(item[1]["score"][0] + item[1]["score"][1]),   # then more goals
        item[0],
    ))

    print("seeds %d-%d: %d qualify (need all 4 triggers, >=6 cards, both halves, "
          "Pip right and wrong at least once)" % (args.from_seed, args.to_seed, qualified))
    print()
    print("seed | corner free_kick sub var | total | right/wrong | halves |   score | ok")
    for seed, s in rows[:args.top]:
        print("%4d | %6d %9d %3d %3d | %5d | %6d/%-4d |     %s | %d-%d | %s" % (
            seed, s["counts"]["corner"], s["counts"]["free_kick"],
            s["counts"]["substitution"], s["counts"]["var"], s["total"],
            s["right"], s["wrong"], "".join(str(h) for h in sorted(s["halves"])) or "-",
            s["score"][0], s["score"][1], "yes" if s["qualifies"] else "no"))
    print()
    print("Claude and the owner pick the seed; then: "
          "python3 -m matchreader.build --seed N --out ../data/demo-match.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

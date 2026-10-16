"""Command line: build the demo-match file.

    cd match-reader
    python3 -m matchreader.build --in ../data/mock-seed-1.json --out ../data/demo-match.json
    python3 -m matchreader.build --seed 1 --out ../data/demo-match.json

After the owner picks the demo seed, `--seed N --out ../data/demo-match.json` is the
only way data/demo-match.json is written (task 03, step 2).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional


def _load_matchlab():
    """Import matchlab from the sibling match-lab/ directory."""
    lab = os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "match-lab"))
    if lab not in sys.path:
        sys.path.insert(0, lab)
    from matchlab import generate_match
    return generate_match


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Turn a match-lab match into the web app's demo-match file.")
    parser.add_argument("--in", dest="in_path", help="input match JSON, e.g. ../data/mock-seed-1.json")
    parser.add_argument("--seed", type=int, help="generate this seed with matchlab instead of reading a file")
    parser.add_argument("--out", required=True, help="output JSON path, e.g. ../data/demo-match.json")
    args = parser.parse_args(argv)

    if bool(args.in_path) == bool(args.seed is not None):
        parser.error("give exactly one of --in or --seed")

    from .reader import build_output, dumps

    match: Dict[str, Any]
    if args.seed is not None:
        match = _load_matchlab()(args.seed)
    else:
        with open(args.in_path, encoding="utf-8") as fh:
            match = json.load(fh)

    out = build_output(match)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(dumps(out))

    counts: Dict[str, int] = {}
    for card in out["cards"]:
        counts[card["trigger"]] = counts.get(card["trigger"], 0) + 1
    by_trigger = " ".join("%s=%d" % kv for kv in sorted(counts.items())) or "none"
    last = out["score_timeline"][-1]
    print("wrote %s: %d cards (%s), %d moments held, score HAR %d-%d COP" % (
        args.out, len(out["cards"]), by_trigger, len(out["moments_held"]),
        last["HAR"], last["COP"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

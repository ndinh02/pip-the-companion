"""Command line: python -m matchlab.generate --seed 1 --out ../data/mock-seed-1.json"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

from .generator import generate_match


def dumps(match: Dict[str, Any]) -> str:
    """Canonical JSON text. Same match dict -> same bytes."""
    return json.dumps(match, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate one synthetic match (seeded, reproducible).")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", required=True, help="output JSON path, e.g. ../data/mock-seed-1.json")
    parser.add_argument("--home-priors", help='JSON, e.g. \'{"corner_short_share": 0.3}\' (default: planted Harbour Lights habits)')
    parser.add_argument("--away-priors", help="JSON, same keys (default: planted Copperfield habits)")
    args = parser.parse_args(argv)

    home = json.loads(args.home_priors) if args.home_priors else None
    away = json.loads(args.away_priors) if args.away_priors else None
    match = generate_match(args.seed, home, away)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(dumps(match))
    agg = match["aggregates"]
    print("wrote %s: %d events, corners %s, score %s, ball in play %.1f min" % (
        args.out, agg["events"], agg["corners"], match["final_score"], agg["ball_in_play_s"] / 60.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

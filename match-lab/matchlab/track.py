"""Command line: track one generated match (task 04).

    cd match-lab
    python3 -m matchlab.track --seed 43 \
        --out-match ../data/tracked-seed-43.json \
        --out-tracking ../data/tracking-seed-43.json

Writes two canonical-JSON files (same dict -> same bytes) and prints a short
summary. Deterministic from the seed alone; no network, no AI (AGENTS.md 1-2).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Optional

from . import generate_match
from .tracking import track_match


def dumps(obj: dict) -> str:
    """Canonical JSON text, like matchlab.generate / matchreader.build dumps."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Simulate 5 Hz tracking for one match-lab match and write both files.")
    parser.add_argument("--seed", type=int, required=True, help="match seed to generate and track")
    parser.add_argument("--out-match", required=True, help="tracked match JSON path")
    parser.add_argument("--out-tracking", required=True, help="tracking (5 Hz, dm) JSON path")
    args = parser.parse_args(argv)

    match = generate_match(args.seed)
    t0 = time.time()
    tracked, tracking = track_match(match)
    seconds = time.time() - t0

    for path, obj in ((args.out_match, tracked), (args.out_tracking, tracking)):
        out_dir = os.path.dirname(os.path.abspath(path))
        os.makedirs(out_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(dumps(obj))

    frames = tracking["periods"][0]["frames"] + tracking["periods"][1]["frames"]
    print("wrote %s (%d events, %d actors changed)" % (
        args.out_match, len(tracked["events"]), tracked["tracking"]["actors_changed"]))
    print("wrote %s (%d frames x %d entities, %.1f MB)" % (
        args.out_tracking, frames, len(tracking["entities"]),
        os.path.getsize(args.out_tracking) / 1e6))
    print("simulated %.1f s" % seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())

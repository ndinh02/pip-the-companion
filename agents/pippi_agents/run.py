"""Command line, from agents/:

    python3 -m pippi_agents.run --seed 43 --out ../data/agent-trace.json

Writes the trace of the real run (today: template writer, no AI) plus the "Catch me lying"
integrity demo: the same match with two sabotaged writers, to prove bad text cannot ship.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import List, Optional

from . import paths  # noqa: F401
from .workflow import run_match
from .writers import AlwaysLyingWriter, LyingOnceWriter, TemplateWriter
from matchlab import generate_match


def build(seed: int) -> dict:
    match = generate_match(seed)
    real = run_match(match, TemplateWriter())
    ids = [c["card_id"] for c in real["cards"]]
    with_facts = [c["card_id"] for c in real["cards"] if c["facts_from_events"]]
    sabotage = {}
    if with_facts:
        sabotage[with_facts[0]] = LyingOnceWriter()
    rest = [i for i in ids if i not in sabotage]
    if rest:
        sabotage[rest[-1]] = AlwaysLyingWriter()
    demo = run_match(match, TemplateWriter(), sabotage)
    real["catch_me_lying"] = {
        "what": "Two writers were sabotaged on purpose. The checker rejected their drafts; one was repaired after "
                "feedback, one fell back to the fixed template. The cards that ship are unchanged.",
        "cards": [c for c in demo["cards"] if c["card_id"] in sabotage],
        "shipped_equals_checked": demo["shipped_equals_checked"],
    }
    return real


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    data = build(args.seed)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
    lying = data["catch_me_lying"]["cards"]
    print("wrote %s: %d cards approved by '%s' (uses_ai=%s), %d held; integrity demo: %s; shipped == checked: %s" % (
        args.out, len(data["cards"]), data["writer"], data["uses_ai"], len(data["held"]),
        ", ".join("%s -> %s after %d attempts" % (c["card_id"], c["approved_by"], len(c["attempts"])) for c in lying),
        data["shipped_equals_checked"] and data["catch_me_lying"]["shipped_equals_checked"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

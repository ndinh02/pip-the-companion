"""Command line, from agents/:

    python3 -m pippi_agents.run --seed 43 --out ../data/agent-trace.json
    python3 -m pippi_agents.run --seed 43 --writer llm --model qwen2.5-7b --out ../data/agent-trace-llm.json

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


def _run_llm(args) -> int:
    """Trial run with a local model. Writes a separate trace; the shipped match file is not touched."""
    import time
    from .llm_writer import LLMWriter

    match = generate_match(args.seed)
    writer = LLMWriter(args.model)
    writer.team_names = {t["team_id"]: t["name"] for t in match["teams"]}
    started = time.time()
    data = run_match(match, writer)
    data["model_replies"] = writer.raw
    data["seconds"] = round(time.time() - started, 1)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, sort_keys=True, indent=1, ensure_ascii=False) + "\n")
    first_try = sum(1 for c in data["cards"] if c["attempts"][0]["checker"] == "pass")
    by_model = sum(1 for c in data["cards"] if c["approved_by"].startswith("llm:"))
    print("wrote %s with %s in %ss: %d cards, %d passed the checker first time, %d approved from the model, %d fell back to the template" % (
        args.out, writer.model, data["seconds"], len(data["cards"]), first_try, by_model, len(data["cards"]) - by_model))
    for c in data["cards"]:
        print(" %s  %-26s %s" % (c["card_id"], c["approved_by"][:26], c["approved_plain_en"]))
        for a in c["attempts"]:
            if a["checker"] == "fail":
                print("        rejected draft %d: %s" % (a["attempt"], "; ".join(a["errors"])[:160]))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--writer", choices=["template", "llm"], default="template")
    parser.add_argument("--model", default="qwen2.5-7b", help="Foundry Local model alias (with --writer llm)")
    args = parser.parse_args(argv)
    if args.writer == "llm":
        return _run_llm(args)
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

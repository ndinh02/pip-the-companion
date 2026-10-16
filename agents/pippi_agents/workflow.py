"""Bounded content workflow for one match (brief 7.2 A, 7.3):

    Match Reader (code)  ->  Moment Picker (rules)  ->  Writer  ->  Checker (code)
                                                          ^            |
                                                          +-- retry ---+   max 2 retries, then fixed template

Runs on the owner's machine BEFORE the match. Only approved cards are written to the match file;
nothing here runs while viewers watch.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import WORKFLOW_VERSION, paths  # noqa: F401
from .checker import check_card
from .tools import FactTools
from .writers import TemplateWriter
from matchreader import reader

MAX_RETRIES = 2


def run_card(match: Dict[str, Any], cand: Dict[str, Any], approved_card: Dict[str, Any], writer: Any) -> Dict[str, Any]:
    """One moment through writer -> checker -> retry -> fallback. Returns the trace entry."""
    prefix = approved_card["card_id"].split("-")[0] + "_"
    tools = FactTools(match, cand, prefix)
    truth = tools.truth()
    attempts: List[Dict[str, Any]] = []
    feedback: Optional[List[str]] = None
    final = None
    for attempt in range(1, MAX_RETRIES + 2):
        if hasattr(writer, "moment_key"):
            writer.moment_key = cand.get("reveal_key", "")  # e.g. "offside:stands": what happened, in words for the writer
        draft = writer.write(approved_card, tools, feedback)
        errors = check_card(draft.card, draft.facts, truth, cand.get("reveal_key", ""))
        attempts.append({
            "attempt": attempt, "writer": writer.name, "note": draft.note,
            "expert_en": draft.card["reveal"]["expert"]["en"], "plain_en": draft.card["reveal"]["plain"]["en"],
            "facts": {k: v["value"] for k, v in sorted(draft.facts.items())},
            "checker": "pass" if not errors else "fail", "errors": errors,
        })
        if not errors:
            final = {"source": writer.name, "card": draft.card, "facts": draft.facts}
            break
        feedback = errors
    if final is None:
        fallback = TemplateWriter().write(approved_card, tools, None)
        errors = check_card(fallback.card, fallback.facts, truth, cand.get("reveal_key", ""))
        if errors:  # the fixed template itself is broken: stop, never ship
            raise ValueError("fallback template failed the checker for %s: %s" % (approved_card["card_id"], errors))
        attempts.append({"attempt": len(attempts) + 1, "writer": "template (fallback)", "note": "retries used up",
                         "expert_en": fallback.card["reveal"]["expert"]["en"], "plain_en": fallback.card["reveal"]["plain"]["en"],
                         "facts": {k: v["value"] for k, v in sorted(fallback.facts.items())}, "checker": "pass", "errors": []})
        final = {"source": "template (fallback)", "card": fallback.card, "facts": fallback.facts}
    return {
        "card_id": approved_card["card_id"], "trigger": approved_card["trigger"], "t_in_min": approved_card["t_in_min"],
        "team_id": approved_card["team_id"], "decision": "fire",
        "question_en": approved_card["question"]["text"]["en"],
        "facts_from_events": truth, "tool_calls": tools.calls, "attempts": attempts,
        "approved_by": final["source"], "approved_expert_en": final["card"]["reveal"]["expert"]["en"],
        "approved_plain_en": final["card"]["reveal"]["plain"]["en"],
        "approved_facts": {k: v["value"] for k, v in sorted(final["facts"].items())},
    }


def run_match(match: Dict[str, Any], writer: Any = None, writers_by_card: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The whole match. `writers_by_card` overrides the writer for single cards (used by the integrity demo)."""
    writer = writer or TemplateWriter()
    out, accepted, held = reader._build(match)
    entries = []
    for cand, card in zip(accepted, out["cards"]):
        w = (writers_by_card or {}).get(card["card_id"], writer)
        entries.append(run_card(match, cand, card, w))
    # What ships is exactly the checked content: compare with the match file built by match-reader.
    shipped_ok = all(e["approved_expert_en"] == c["reveal"]["expert"]["en"] and e["approved_plain_en"] == c["reveal"]["plain"]["en"]
                     and all(out["facts"][f]["value"] == v for f, v in e["approved_facts"].items())
                     for e, c in zip(entries, out["cards"]))
    return {
        "match_id": match["match_id"], "seed": match["seed"], "workflow_version": WORKFLOW_VERSION,
        "writer": writer.name, "uses_ai": bool(getattr(writer, "uses_ai", False)), "max_retries": MAX_RETRIES,
        "cards": entries,
        "held": [{"trigger": h["trigger"], "t_in_min": h["t_in_min"], "team_id": h["team_id"], "decision": "hold", "reason": h["reason"]} for h in held],
        "shipped_equals_checked": shipped_ok,
    }

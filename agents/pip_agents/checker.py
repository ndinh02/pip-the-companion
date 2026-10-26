"""The checker is plain code. A text reaches viewers only if it passes every rule here (brief 7.3 step 4)."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from . import paths  # noqa: F401
from matchreader import copycheck, schemacheck


# Words that show the plain line names the real outcome (EN). Keyed by answer id.
ANSWER_WORDS = {
    "near": ["near"], "far": ["far"], "short": ["short"], "central": ["central", "middle"],
    "shoot": ["shoot", "shot"], "cross": ["cross", "into the box", "header"],
    "attack": ["attack", "forward"], "defend": ["defend", "defence", "defender"], "fresh": ["fresh", "midfielder", "energy"],
    "offside": ["offside", "onside"], "foul": ["foul"], "handball": ["handball", "hand"],
}


# A count or frequency in words is a number the code did not supply ("their first cross", "twice", "most of").
COUNT_WORDS = re.compile(
    r"\b(first|second|third|last)\s+(time|cross|corner|free kick|shot|goal|substitution|change|one|of)\b"
    r"|\b(once|twice|again|every time|each time|most of|majority|several times|many times|few times|always|never|record)\b",
    re.IGNORECASE)
# Pip never grades people and cannot know what the room called (AGENTS.md rule 8).
GRADING_WORDS = re.compile(r"\b(wrong|right|guess(ed|es)?|correct(ly)?|everyone|nobody|newcomers?|new friends|friends|you|your|the room|surprised|shocked|disappointed)\b", re.IGNORECASE)
# VAR: the plain line must state the decision that was actually made.
VAR_DECISION_WORDS = {
    "stands": ["stands", "counts", "onside", "no foul", "is given", "allowed"],
    "overturned": ["ruled out", "no goal", "disallowed", "cancelled", "does not count", "doesn't count", "not count", "annulled"],
}


def check_card(card: Dict[str, Any], facts: Dict[str, Dict[str, Any]], truth: Dict[str, int],
               reveal_key: str = "") -> List[str]:
    """Return the list of problems (empty = approved).

    card   the drafted card (same shape as schemas/overlay_card.schema.json)
    facts  the fact table that would ship with the card: {fact_id: {"value": n}}
    truth  the same facts recomputed from the match events by FactTools.truth()
    reveal_key  what happened, e.g. "cross" or "offside:stands" (for the decision check)
    """
    errors: List[str] = []
    # 1. numbers: every shipped fact must equal the value recomputed from the events
    for fid in card["reveal"]["fact_ids"]:
        if fid not in truth:
            errors.append("fact %s does not exist for this moment" % fid)
        elif fid not in facts:
            errors.append("fact %s is missing from the fact table" % fid)
        elif facts[fid]["value"] != truth[fid]:
            errors.append("fact %s says %r but the match events say %r" % (fid, facts[fid]["value"], truth[fid]))
    # 2. copy rules: banned betting words, hard-coded digits, unknown placeholders, length, options
    errors.extend(copycheck.check_copy({"facts": facts, "cards": [card]}))
    # 3. shape: the card format a broadcast graphics partner would receive
    errors.extend("schema: " + e for e in schemacheck.validate_card(card))
    # 4. truth of the reveal: the plain English line must name the match's actual answer. A void card ("no clear
    #    answer", task 11) has no answer by design: its plain line says what really happened instead.
    words = ANSWER_WORDS.get(card["reveal"]["answer"], [card["reveal"]["answer"]])
    if not card["reveal"].get("void") and not any(re.search(r"\b%s" % w, card["reveal"]["plain"]["en"], re.IGNORECASE) for w in words):
        errors.append('plain line does not say what happened (expected one of: %s)' % ", ".join(words))
    # 5. no numbers in words, no grading, the right VAR decision (English lines)
    for part in ("plain", "expert"):
        text = card["reveal"][part]["en"]
        m = COUNT_WORDS.search(text)
        if m:
            errors.append('%s line states a count in words ("%s"): numbers must come from {placeholders}' % (part, m.group(0)))
        m = GRADING_WORDS.search(text)
        if m:
            errors.append('%s line talks about people\'s calls ("%s"): Pip never grades anyone' % (part, m.group(0)))
    decision = reveal_key.split(":")[1] if ":" in reveal_key else ""
    if decision in VAR_DECISION_WORDS:
        plain = card["reveal"]["plain"]["en"].lower()
        if not any(w in plain for w in VAR_DECISION_WORDS[decision]):
            errors.append("plain line does not state the VAR decision (%s)" % ("the goal stands" if decision == "stands" else "the goal is ruled out"))
        wrong = VAR_DECISION_WORDS["overturned" if decision == "stands" else "stands"]
        hit = next((w for w in wrong if w in plain and not (decision == "overturned" and w == "onside")), None)
        if hit:
            errors.append('plain line says "%s", but the decision was the opposite' % hit)
    return errors

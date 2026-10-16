"""The checker is plain code. A text reaches viewers only if it passes every rule here (brief 7.3 step 4)."""
from __future__ import annotations

from typing import Any, Dict, List

from . import paths  # noqa: F401
from matchreader import copycheck, schemacheck


def check_card(card: Dict[str, Any], facts: Dict[str, Dict[str, Any]], truth: Dict[str, int]) -> List[str]:
    """Return the list of problems (empty = approved).

    card   the drafted card (same shape as schemas/overlay_card.schema.json)
    facts  the fact table that would ship with the card: {fact_id: {"value": n}}
    truth  the same facts recomputed from the match events by FactTools.truth()
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
    return errors

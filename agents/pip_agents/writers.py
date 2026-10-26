"""Writers draft a card for one moment. The workflow does not trust any of them: the checker decides.

Today there is ONE real writer, TemplateWriter (no AI). An LLM writer plugs in here once the
provider is chosen (docs/OPEN_QUESTIONS.md #2); it must use FactTools and the same Draft shape.
The two "lying" writers exist only to prove the checker and the repair loop work.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from .tools import FactTools


class Draft:
    def __init__(self, card: Dict[str, Any], facts: Dict[str, Dict[str, Any]], note: str = "") -> None:
        self.card = card
        self.facts = facts
        self.note = note


class TemplateWriter:
    """Fixed, owner-reviewed templates filled by match-reader. Always available; also the fallback."""

    name = "template"
    uses_ai = False

    def write(self, approved_card: Dict[str, Any], tools: FactTools, feedback: Optional[List[str]]) -> Draft:
        facts = {fid: {"value": tools.get_fact(fid), "source": "match-reader"} for fid in approved_card["reveal"]["fact_ids"]}
        return Draft(copy.deepcopy(approved_card), facts)


class LyingOnceWriter(TemplateWriter):
    """Demo only ("Catch me lying"): the first draft contains a made-up number and a corrupted fact.
    After the checker's feedback it writes honestly. Shows the repair loop."""

    name = "lying-once (integrity demo)"

    def write(self, approved_card, tools, feedback):
        draft = super().write(approved_card, tools, feedback)
        if feedback:
            draft.note = "rewrote after checker feedback"
            return draft
        ids = draft.card["reveal"]["fact_ids"]
        if ids:
            first = ids[0]
            draft.facts[first]["value"] = draft.facts[first]["value"] + 3  # corrupt one stat
            draft.card["reveal"]["expert"]["en"] = draft.card["reveal"]["expert"]["en"].replace("{%s}" % first, "9")
            draft.note = "corrupted fact %s and typed a number into the text" % first
        else:
            draft.card["reveal"]["plain"]["en"] += " About 7 times out of 10."
            draft.note = "typed a made-up number into the text"
        return draft


class AlwaysLyingWriter(TemplateWriter):
    """Demo only: never recovers. Shows the fallback to the fixed template after the retries run out."""

    name = "always-lying (integrity demo)"

    def write(self, approved_card, tools, feedback):
        draft = super().write(approved_card, tools, feedback)
        draft.card["reveal"]["plain"]["en"] = "Easy money! " + draft.card["reveal"]["plain"]["en"] + " Check the odds."
        draft.note = "added betting language"
        return draft

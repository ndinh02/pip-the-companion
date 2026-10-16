"""Port of scripts/check-copy.mjs (repo root) for a built demo-match dict.

Same rules: every string <= 200 chars, no banned betting word in EN/DE/VI, no
digit outside {placeholders}, every placeholder in the card's fact_ids and in
facts, answer/pippi_call among the option ids, no leftover <team>.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Set

BANNED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "scripts", "banned-words.json")
LANGS = ("en", "de", "vi")
MAX_LEN = 200


def _banned_regexes() -> Dict[str, "re.Pattern[str]"]:
    with open(BANNED_PATH, encoding="utf-8") as fh:
        banned = json.load(fh)
    regexes = {}
    for lang in LANGS:
        # (?<!letter)(word)(?!letter) — whole words only, case-insensitive.
        # [^\W\d_] is "any letter" in unicode, the Python re equivalent of \p{L}.
        joined = "|".join(re.escape(w) for w in banned[lang])
        regexes[lang] = re.compile(r"(?<![^\W\d_])(" + joined + r")(?![^\W\d_])",
                                   re.IGNORECASE)
    return regexes


def check_copy(match: Dict[str, Any]) -> List[str]:
    """Return a list of error strings (empty list = copy is clean)."""
    regexes = _banned_regexes()
    facts = match["facts"]
    errors: List[str] = []

    def check_text(where: str, lang: str, text: Any, allowed: Set[str]) -> None:
        if not isinstance(text, str) or not text.strip():
            errors.append("%s.%s: empty" % (where, lang))
            return
        if len(text) > MAX_LEN:
            errors.append("%s.%s: %d chars > %d" % (where, lang, len(text), MAX_LEN))
        hit = regexes[lang].search(text)
        if hit:
            errors.append('%s.%s: banned word "%s"' % (where, lang, hit.group(1)))
        if "<team>" in text:
            errors.append("%s.%s: leftover <team>" % (where, lang))
        for m in re.finditer(r"\{([a-z0-9_]+)\}", text):
            name = m.group(1)
            if name not in allowed:
                errors.append("%s.%s: placeholder {%s} not in fact_ids" % (where, lang, name))
            if name not in facts:
                errors.append("%s.%s: placeholder {%s} not in facts" % (where, lang, name))
        # A bare digit in copy means a number the code did not supply.
        if re.search(r"\d", re.sub(r"\{[a-z0-9_]+\}", "", text)):
            errors.append('%s.%s: hard-coded number in "%s"' % (where, lang, text))

    for card in match["cards"]:
        ids = set(card["reveal"]["fact_ids"])
        for fid in ids:
            if fid not in facts:
                errors.append("%s: unknown fact_id %s" % (card["card_id"], fid))
        option_ids = [o["id"] for o in card["question"]["options"]]
        if card["reveal"]["answer"] not in option_ids:
            errors.append("%s: answer not among options" % card["card_id"])
        if card["question"]["pippi_call"] not in option_ids:
            errors.append("%s: pippi_call not among options" % card["card_id"])
        for lang in LANGS:
            check_text("%s.question.text" % card["card_id"], lang,
                       card["question"]["text"][lang], set())
            for o in card["question"]["options"]:
                check_text("%s.option.%s" % (card["card_id"], o["id"]), lang,
                           o["label"][lang], set())
            check_text("%s.reveal.plain" % card["card_id"], lang,
                       card["reveal"]["plain"][lang], ids)
            check_text("%s.reveal.expert" % card["card_id"], lang,
                       card["reveal"]["expert"][lang], ids)

    return errors

"""LLM writer: drafts the English reveal lines with a model served by Foundry Local on the owner's Mac.

Standard library only (works on the Mac's Python 3.9). Talks to Foundry Local's OpenAI-compatible
endpoint. The model never sees or writes numbers: it gets the fact NAMES and writes {placeholders};
code fills the values. Everything it writes goes through the same checker as the templates.

v1 scope: English plain + expert lines. German and Vietnamese stay on the reviewed templates until
re-voicing is built and tested (brief 7.3, Mascot Host).
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import urllib.request
from typing import Any, Dict, List, Optional

from .tools import FactTools
from .writers import Draft

# What each fact means, in words a writer can use. Values are never shown to the model.
FACT_MEANING = {
    "corners_short": "corners this team has played short so far today",
    "corners_total": "corners this team has taken so far today",
    "league_short_share_pct": "league average share of corners played short, in percent",
    "fk_cross": "free kicks in the opponent's half this team has crossed so far today",
    "fk_total": "free kicks in the opponent's half this team has taken so far today",
    "forwards_before": "forwards this team had on the pitch before the substitution",
    "forwards_after": "forwards this team has on the pitch after the substitution",
    "defenders_before": "defenders on the pitch before the substitution",
    "defenders_after": "defenders on the pitch after the substitution",
    "midfielders_before": "midfielders on the pitch before the substitution",
    "midfielders_after": "midfielders on the pitch after the substitution",
    "subs_used": "substitutions this team has used so far",
    "subs_max": "substitutions this team may use in the match",
    "var_margin_cm": "how many centimetres the attacker was offside or onside by",
}

SYSTEM = """You write one reveal for Pip, a friendly bird who watches football with a mixed room: one fan and people new to football.
Rules:
- Two lines: "plain" for newcomers (one or two short sentences, starts by naming what happened, explains why in everyday words) and "expert" for fans (one sentence of data).
- NEVER write a digit or a number word for a statistic. Numbers are filled in by code: write the given {placeholders} exactly, for example {fk_cross}.
- Use only the placeholders you are given. The expert line must use at least one of them.
- No betting words (bet, odds, stake, wager, gamble...), no scores or predictions of who wins, no opinions about referees, players or tactics, no player names.
- Say only what you are told happened. Do not add details (where the ball went, who touched it, what the coach thinks).
- Never mention what anyone guessed or whether they were right or wrong. Never use counts in words (first, twice, again, most of...).
- Write about the match, not about Pip.
- Friendly and curious, never grades anyone. At most 200 characters per line.
Answer with JSON only: {"plain": "...", "expert": "..."}"""


def foundry_endpoint() -> str:
    """The local URL Foundry Local is serving on (its port changes between restarts)."""
    out = subprocess.run(["foundry", "server", "status", "-o", "json"], capture_output=True, text=True, timeout=60)
    return json.loads(out.stdout)["webUrls"][0].rstrip("/")


def resolve_model(base_url: str, alias: str) -> str:
    """Turn an alias such as 'qwen2.5-7b' into the full id Foundry Local serves (GPU variant preferred)."""
    with urllib.request.urlopen(base_url + "/v1/models", timeout=30) as resp:
        ids = [m["id"] for m in json.load(resp)["data"]]
    matches = sorted((i for i in ids if i.startswith(alias + "-instruct") or i.startswith(alias + "-")), key=lambda i: ("gpu" not in i, i))
    if not matches:
        raise ValueError("model %r is not in Foundry Local's catalog" % alias)
    return matches[0]


def _chat(base_url: str, model: str, messages: List[Dict[str, str]], timeout: int = 300) -> str:
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.4, "max_tokens": 300}).encode()
    req = urllib.request.Request(base_url + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["choices"][0]["message"]["content"]


def _parse(text: str) -> Dict[str, str]:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    data = json.loads(text[start:end + 1])
    return {"plain": str(data["plain"]).strip(), "expert": str(data["expert"]).strip()}


VAR_DECISION_TEXT = {
    "offside:stands": " check — the attacker was NOT offside, so the goal stands",
    "offside:overturned": " — the attacker was offside, so the goal is ruled out",
    "foul:stands": " check — no clear foul, so the goal stands",
    "foul:overturned": " — there was a foul, so the goal is ruled out",
}


class LLMWriter:
    """Drafts EN plain + expert lines with a local model. Unusable output becomes checker errors, never a crash."""

    uses_ai = True

    def __init__(self, alias: str = "qwen2.5-7b", base_url: Optional[str] = None) -> None:
        self.base_url = base_url or foundry_endpoint()
        self.model = resolve_model(self.base_url, alias)
        if base_url is None:  # real Foundry Local: make sure the model is in memory (closing a chat unloads it)
            subprocess.run(["foundry", "model", "load", alias], capture_output=True, text=True, timeout=600)
        self.name = "llm:%s" % self.model
        self.raw: List[str] = []  # model replies, for the trace
        self.team_names: Dict[str, str] = {}  # team_id -> name, set by the caller
        self.moment_key = ""  # set by the workflow before each card

    def write(self, approved_card: Dict[str, Any], tools: FactTools, feedback: Optional[List[str]], team_name: str = "") -> Draft:
        prefix = approved_card["card_id"].split("-")[0] + "_"
        fact_ids = tools.list_facts()
        names = [f[len(prefix):] for f in fact_ids]
        options = ", ".join(o["label"]["en"] for o in approved_card["question"]["options"])
        answer = next(o["label"]["en"] for o in approved_card["question"]["options"] if o["id"] == approved_card["reveal"]["answer"])
        lines = [
            "Moment: %s for %s." % (approved_card["trigger"].replace("_", " "),
                                    team_name or self.team_names.get(approved_card["team_id"], approved_card["team_id"])),
            "Question the room answered: %s (options: %s)" % (approved_card["question"]["text"]["en"], options),
            "What actually happened: %s." % (answer + VAR_DECISION_TEXT.get(self.moment_key, "")),
            "Placeholders you may use:" if names else "There are no statistics for this moment: write the expert line without any number.",
        ]
        lines += ["- {%s}: %s" % (n, FACT_MEANING.get(n, n.replace("_", " "))) for n in names]
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}]
        if feedback:
            messages.append({"role": "user", "content": "Your last draft was rejected by the checker:\n- " + "\n- ".join(feedback) + "\nWrite a corrected JSON reply."})

        card = copy.deepcopy(approved_card)
        facts = {fid: {"value": tools.get_fact(fid), "source": "match-reader"} for fid in fact_ids}
        try:
            reply = _chat(self.base_url, self.model, messages)
            self.raw.append(reply)
            out = _parse(reply)
        except Exception as exc:  # unparseable or failed call: let the checker reject it with a clear reason
            card["reveal"]["plain"]["en"] = ""
            return Draft(card, facts, "model reply unusable: %s" % type(exc).__name__)
        # scope placeholders to this card: {fk_cross} -> {c2_fk_cross}
        scope = lambda s: re.sub(r"\{([a-z0-9_]+)\}", lambda m: "{" + (prefix + m.group(1) if m.group(1) in names else m.group(1)) + "}", s)
        card["reveal"]["plain"]["en"] = scope(out["plain"])
        card["reveal"]["expert"]["en"] = scope(out["expert"])
        used = sorted(set(re.findall(r"\{([a-z0-9_]+)\}", card["reveal"]["plain"]["en"] + card["reveal"]["expert"]["en"])))
        # keep the facts the reviewed DE/VI lines still use, plus any the new English lines use
        card["reveal"]["fact_ids"] = sorted(set(approved_card["reveal"]["fact_ids"]) | {u for u in used if u.startswith(prefix)})
        facts = {fid: facts[fid] for fid in card["reveal"]["fact_ids"] if fid in facts}
        return Draft(card, facts, "drafted by %s" % self.model)

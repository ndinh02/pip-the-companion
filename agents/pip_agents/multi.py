"""Multi-agent content workflow (trial run, brief 7.3): five agents share one
record per card and every handoff is recorded as a step.

    Orchestrator (code)  ->  Writer (LLM, facts via MCP tools)  ->  Rule checker (code, the authority)
                              ^                                        |
                              +------ verifier (LLM second look) -----+      retry with feedback, then
                                                                          fixed template fallback
    Editor (LLM) tightens the approved lines, {placeholders} preserved, checker re-runs.
    Translator (LLM) drafts DE + VI, {placeholders} preserved; per language: approved or
    template fallback (DE/VI are drafts until the owner checks them).

Facts reach the writer only through a real MCP server (pip_agents.mcp_server) spoken to
over stdio JSON-RPC by mcp_client.McpClient. The writer's tool calls go through the
OpenAI-compatible tools/tool_calls loop of Foundry Local; if the model will not call the
tools itself, the documented fallback kicks in: the CLIENT calls list_facts through MCP
and injects the result as a message (recorded as emulated in the trace).
"""
from __future__ import annotations

import copy
import json
import re
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from . import WORKFLOW_VERSION, paths  # noqa: F401
from .checker import check_card
from .llm_writer import FACT_MEANING, VAR_DECISION_TEXT, _parse
from .mcp_client import McpClient
from .mcp_server import SERVER_NAME
from .tools import FactTools
from .writers import TemplateWriter
from matchreader import copycheck, reader

MAX_RETRIES = 2          # writer retries before the fixed template takes over (as in workflow.py)
MAX_TOOL_ROUNDS = 6      # writer <-> MCP tool loop bound per attempt
TRANSLATION_LANGS = ("de", "vi")

# The MCP tools, in the OpenAI tool-calling format the model sees (mirrors mcp_server.TOOLS).
MCP_TOOLS_SPEC = [
    {"type": "function", "function": {
        "name": "list_facts",
        "description": "List the facts available for this moment. Each fact_id can be written as a "
                       "{placeholder} in the text; code fills the value.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_fact",
        "description": "Get one fact's value. Values are filled into {placeholders} by code; never type "
                       "a number into the text yourself.",
        "parameters": {"type": "object",
                       "properties": {"fact_id": {"type": "string", "description": "a fact_id returned by list_facts"}},
                       "required": ["fact_id"]}}},
]

WRITER_SYSTEM = """You write one reveal for Pip, a friendly bird who watches football with a mixed room: one fan and people new to football.
Rules:
- Two lines: "plain" for newcomers (one or two short sentences, starts by naming what happened, explains why in everyday words) and "expert" for fans (one sentence of data).
- BEFORE writing, call the list_facts tool to see which {placeholders} exist for this moment. Write each fact_id exactly as the tool returns it, inside braces, for example {c2_corners_total}.
- get_fact shows you a value ONLY so you understand the moment. NEVER copy a number you saw into your lines: write the {placeholder} instead; code fills the value.
- NEVER write a digit or a number word for a statistic. Numbers are filled in by code from the {placeholders}.
- The expert line must use at least one placeholder if any exist. If there are no facts, write the expert line without any number.
- No betting words (bet, odds, stake, wager, gamble...), no scores or predictions of who wins, no opinions about referees, players or tactics, no player names.
- Say only what you are told happened. Do not add details (where the ball went, who touched it, what the coach thinks).
- Never mention what anyone guessed or whether they were right or wrong. Never use counts in words (first, twice, again, most of...).
- Write about the match, not about Pip.
- Friendly and curious, never grades anyone. At most 200 characters per line.
Your FINAL reply after the tool calls must be JSON only: {"plain": "...", "expert": "..."} — no other text around it."""

VERIFIER_SYSTEM = """You verify a drafted football TV reveal against the facts fetched from the match events.
You get the facts (fact_id = value) and the draft, where {placeholders} will be filled by code with exactly those values.
Check that the draft does not contradict the facts and does not invent details the facts do not support.
Only answer false for a concrete mismatch. Answer with JSON only: {"ok": true, "reason": ""} or {"ok": false, "reason": "what contradicts"}"""

EDITOR_SYSTEM = """You are an editor for short football TV lines. Tighten two lines: keep the meaning, the friendly
tone and what happened; cut filler words; make each line shorter and punchier.
Rules:
- Copy every {placeholder} EXACTLY, character for character. Never add, rename or drop one.
- Do not add facts, numbers, digits, names or opinions. No betting words.
- At most 200 characters per line, plain language for newcomers in the "plain" line.
Answer with JSON only: {"plain": "...", "expert": "..."}"""

TRANSLATOR_SYSTEM = {
    "de": "You translate two short football TV lines into German for a mixed room: one fan and people new to football.",
    "vi": "You translate two short football TV lines into Vietnamese for a mixed room: one fan and people new to football.",
}
TRANSLATOR_RULES = """
Rules:
- Translate faithfully and naturally, friendly and curious, never grading anyone.
- Copy every {placeholder} EXACTLY, character for character. Never translate inside the braces.
- Do not add facts, numbers, digits, names or opinions. No betting words.
- At most 200 characters per line.
Answer with JSON only: {"plain": "...", "expert": "..."}"""


def agents_roster(model: str) -> List[Dict[str, Any]]:
    return [
        {"id": "orchestrator", "name": "Orchestrator", "kind": "code", "model": None,
         "role": "walks each card through the pipeline and records every handoff"},
        {"id": "writer", "name": "Writer", "kind": "llm", "model": model,
         "role": "drafts the plain + expert EN lines from facts it must fetch through the MCP tools"},
        {"id": "checker", "name": "Rule checker", "kind": "code", "model": None,
         "role": "the authority: numbers equal the events, placeholders known, banned words, shape, VAR decision"},
        {"id": "verifier", "name": "Fact verifier", "kind": "llm", "model": model,
         "role": "LLM second look: confirms the draft against the fetched facts; the code checker can overrule it"},
        {"id": "editor", "name": "Editor", "kind": "llm", "model": model,
         "role": "tightens the approved lines while preserving every {placeholder} exactly"},
        {"id": "translator", "name": "Translator", "kind": "llm", "model": model,
         "role": "DE and VI drafts of the approved lines (drafts until the owner checks them)"},
    ]


class FoundryClient:
    """Talks to Foundry Local's OpenAI-compatible endpoint. Returns the full message
    object (content + tool_calls) so the writer can run a real tool-calling loop."""

    def __init__(self, alias: str = "qwen2.5-7b", base_url: Optional[str] = None) -> None:
        import subprocess
        from .llm_writer import foundry_endpoint, resolve_model
        self.base_url = base_url or foundry_endpoint()
        self.model = resolve_model(self.base_url, alias)
        if base_url is None:  # real Foundry Local: keep the model in memory
            subprocess.run(["foundry", "model", "load", alias], capture_output=True, text=True, timeout=600)

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None,
             temperature: float = 0.4, max_tokens: int = 400) -> Dict[str, Any]:
        body: Dict[str, Any] = {"model": self.model, "messages": messages,
                                "temperature": temperature, "max_tokens": max_tokens}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        req = urllib.request.Request(self.base_url + "/v1/chat/completions",
                                     data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.load(resp)["choices"][0]["message"]


def placeholders(text: str) -> List[str]:
    return re.findall(r"\{([a-z0-9_]+)\}", text)


def _parse_draft(content: str) -> Dict[str, str]:
    """A plain/expert pair from a model reply. Models drift off JSON ("Plain: x\\nExpert: y"),
    so after the JSON attempt we accept the two clearly labelled lines. Raises if neither works."""
    try:
        return _parse(content)
    except Exception:
        pass
    m = re.search(r'"plain"\s*:\s*"([^"]*)"\s*,\s*"expert"\s*:\s*"([^"]*)"', content, re.IGNORECASE | re.DOTALL)
    if m:
        return {"plain": m.group(1).strip(), "expert": m.group(2).strip()}
    pair: Dict[str, str] = {}
    for line in content.splitlines():
        m = re.match(r"\s*\**\s*(plain|expert)\s*\**\s*[:\-–]\s*(.+?)\s*$", line, re.IGNORECASE)
        if m:
            pair[m.group(1).lower()] = m.group(2).strip().strip('"')
    if "plain" in pair and "expert" in pair:
        return pair
    lines = [l.strip().strip('"') for l in content.strip().splitlines() if l.strip()]
    if len(lines) == 2:  # the prompt's order: the plain line, then the expert line
        return {"plain": lines[0], "expert": lines[1]}
    raise ValueError("no plain/expert pair in the reply")


class Recorder:
    """Collects the steps[] the console shows: one per agent action, in order."""

    def __init__(self) -> None:
        self.steps: List[Dict[str, Any]] = []

    def step(self, agent: str, action: str, to: Optional[str] = None, verdict: str = "info",
             notes: Optional[List[str]] = None, text: Optional[Dict[str, str]] = None,
             ms: Optional[int] = None, via_mcp: bool = False) -> None:
        self.steps.append({
            "n": len(self.steps) + 1, "agent": agent, "action": action, "to": to,
            "verdict": verdict, "notes": [n for n in (notes or []) if n],
            "text": text or {}, "ms": ms, "via_mcp": via_mcp,
        })


def _meaning(fid: str) -> str:
    name = fid.split("_", 1)[1] if "_" in fid else fid
    return FACT_MEANING.get(name, name.replace("_", " "))


class MultiAgentRunner:
    """Runs the five-agent pipeline over a match. `client` only needs .chat(...) -> message dict,
    so tests can substitute a scripted fake (no network)."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self.model = str(getattr(client, "model", "unknown"))
        self.raw: List[str] = []  # every model reply, for the trace

    # ---------- one card ----------
    def run_card(self, match: Dict[str, Any], cand: Dict[str, Any], approved_card: Dict[str, Any],
                 team_names: Dict[str, str]) -> Dict[str, Any]:
        prefix = approved_card["card_id"].split("-")[0] + "_"
        truth = FactTools(match, cand, prefix).truth()  # {prefixed fact_id: value}, recomputed from the events
        rec = Recorder()
        entry: Dict[str, Any] = {
            "card_id": approved_card["card_id"], "trigger": approved_card["trigger"],
            "t_in_min": approved_card["t_in_min"], "team_id": approved_card["team_id"], "decision": "fire",
            "question_en": approved_card["question"]["text"]["en"],
            "facts_from_events": truth, "steps": rec.steps, "attempts": [], "tool_calls": [],
        }
        n_facts = len(truth)
        rec.step("orchestrator", "moment picked", to="writer", verdict="info",
                 notes=["%s at %s' for %s" % (approved_card["trigger"].replace("_", " "), approved_card["t_in_min"],
                                              team_names.get(approved_card["team_id"], approved_card["team_id"])),
                        "%d code-computed fact(s) served through the MCP server" % n_facts])
        attempts: List[Dict[str, Any]] = entry["attempts"]
        mcp_calls: List[Dict[str, Any]] = entry["tool_calls"]

        with McpClient(truth) as mcp:
            feedback: Optional[List[str]] = None
            final: Optional[Dict[str, Any]] = None
            for attempt in range(1, MAX_RETRIES + 2):
                draft = self._writer_draft(approved_card, team_names, cand.get("reveal_key", ""), mcp, feedback, rec)
                mcp_calls.extend(mcp.calls[len(mcp_calls):])
                errors = check_card(draft["card"], draft["facts"], truth, cand.get("reveal_key", ""))
                attempts.append({
                    "attempt": len(attempts) + 1, "writer": "writer (%s)" % self.model, "note": draft["note"],
                    "expert_en": draft["card"]["reveal"]["expert"]["en"],
                    "plain_en": draft["card"]["reveal"]["plain"]["en"],
                    "facts": {k: v["value"] for k, v in sorted(draft["facts"].items())},
                    "checker": "pass" if not errors else "fail", "errors": errors,
                })
                if errors:
                    rec.step("checker", "check draft", to="orchestrator", verdict="fail", notes=errors[:6])
                    feedback = errors
                    continue
                rec.step("checker", "check draft", to="orchestrator", verdict="pass",
                         notes=["numbers, placeholders, banned words, shape, decision: all clean"])
                # LLM second look; the code checker stays the authority either way
                v_ok, v_reason = self._verify(draft, mcp, rec)
                if not v_ok and attempt <= MAX_RETRIES:
                    feedback = ["fact verifier was not convinced: " + v_reason]
                    continue
                final = {"source": "writer (%s)" % self.model, "card": draft["card"], "facts": draft["facts"]}
                break

            template_fallback = False
            if final is None:
                t0 = time.time()
                fb = TemplateWriter().write(approved_card, FactTools(match, cand, prefix), None)
                errors = check_card(fb.card, fb.facts, truth, cand.get("reveal_key", ""))
                if errors:
                    raise ValueError("fallback template failed the checker for %s: %s" % (approved_card["card_id"], errors))
                attempts.append({"attempt": len(attempts) + 1, "writer": "template (fallback)", "note": "retries used up",
                                 "expert_en": fb.card["reveal"]["expert"]["en"],
                                 "plain_en": fb.card["reveal"]["plain"]["en"],
                                 "facts": {k: v["value"] for k, v in sorted(fb.facts.items())},
                                 "checker": "pass", "errors": []})
                rec.step("orchestrator", "fallback", to="checker", verdict="pass", ms=int((time.time() - t0) * 1000),
                         notes=["writer did not pass the checker in %d retries: the fixed, owner-reviewed template takes over" % MAX_RETRIES])
                final = {"source": "template (fallback)", "card": fb.card, "facts": fb.facts}
                template_fallback = True

            # ---- editor: tighten the approved EN lines, placeholders untouched ----
            if not template_fallback:
                final = self._edit_stage(final, truth, cand, rec, attempts)

            # ---- translator: DE + VI drafts of whatever was approved ----
            entry["translations"] = self._translate_stage(final, approved_card, truth, template_fallback, rec)

        entry.update({
            "approved_by": final["source"],
            "approved_expert_en": final["card"]["reveal"]["expert"]["en"],
            "approved_plain_en": final["card"]["reveal"]["plain"]["en"],
            "approved_facts": {k: v["value"] for k, v in sorted(final["facts"].items())},
        })
        rec.step("orchestrator", "card done", verdict="info",
                 notes=["approved by %s" % final["source"],
                        "translations: " + ", ".join("%s %s" % (lang, entry["translations"][lang]["status"])
                                                      for lang in TRANSLATION_LANGS)])
        return entry

    # ---------- writer ----------
    def _writer_draft(self, approved_card: Dict[str, Any], team_names: Dict[str, str], reveal_key: str,
                      mcp: McpClient, feedback: Optional[List[str]], rec: Recorder) -> Dict[str, Any]:
        t0 = time.time()
        card = copy.deepcopy(approved_card)
        prefix = approved_card["card_id"].split("-")[0] + "_"
        options = ", ".join(o["label"]["en"] for o in approved_card["question"]["options"])
        answer = next(o["label"]["en"] for o in approved_card["question"]["options"]
                      if o["id"] == approved_card["reveal"]["answer"])
        moment_key = reveal_key
        lines = [
            "Moment: %s for %s." % (approved_card["trigger"].replace("_", " "),
                                    team_names.get(approved_card["team_id"], approved_card["team_id"])),
            "Question the room answered: %s (options: %s)" % (approved_card["question"]["text"]["en"], options),
            "What actually happened: %s." % (answer + VAR_DECISION_TEXT.get(moment_key, "")),
            "Call the list_facts tool now to see the {placeholders} for this moment, then write the two lines.",
        ]
        messages: List[Dict[str, Any]] = [{"role": "system", "content": WRITER_SYSTEM},
                                          {"role": "user", "content": "\n".join(lines)}]
        if feedback:
            messages.append({"role": "user",
                             "content": "Your last draft was rejected:\n- " + "\n- ".join(feedback) +
                                        "\nCall the tools again if you need to, then write a corrected JSON reply."})
        rounds, called_list, emulated, content = 0, False, False, ""
        while rounds < MAX_TOOL_ROUNDS:
            msg = self.client.chat(messages, tools=MCP_TOOLS_SPEC, max_tokens=512)
            self.raw.append(str(msg.get("content") or "") or json.dumps(msg.get("tool_calls") or [], default=str))
            calls = msg.get("tool_calls") or []
            if not calls:
                content = msg.get("content") or ""
                break
            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for tc in calls:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except ValueError:
                    args = {"_unparseable": fn.get("arguments")}
                try:
                    result: Any = mcp.call_tool(fn.get("name", ""), args)
                except Exception as exc:
                    result = {"error": str(exc)}
                if fn.get("name") == "list_facts":
                    called_list = True
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""),
                                 "content": json.dumps(result, ensure_ascii=False)})
            rounds += 1
        else:  # the model kept calling tools: ask for the answer without tools
            messages.append({"role": "user", "content": "No more tool calls. Write the JSON reply now."})
            msg = self.client.chat(messages)
            self.raw.append(str(msg.get("content") or ""))
            content = msg.get("content") or ""
        if not called_list:
            # documented fallback: the model would not call list_facts itself, so the CLIENT fetches
            # the fact list through the MCP server and injects it as a message (emulated tool call).
            try:
                listing = mcp.call_tool("list_facts", {})
            except Exception as exc:
                listing = {"error": str(exc)}
            messages.append({"role": "user",
                             "content": "The client fetched this tool result for you (list_facts via MCP):\n%s\n"
                                        "Write the JSON reply now." % json.dumps(listing, ensure_ascii=False)})
            msg = self.client.chat(messages)
            self.raw.append(str(msg.get("content") or ""))
            content = msg.get("content") or ""
            emulated = True
        ms = int((time.time() - t0) * 1000)
        try:
            out = _parse_draft(content)
        except Exception as exc:
            card["reveal"]["plain"]["en"] = ""
            card["reveal"]["expert"]["en"] = ""
            rec.step("writer", "draft via MCP tools", to="checker", verdict="fail", ms=ms, via_mcp=True,
                     notes=["model reply unusable: %s (%s)" % (type(exc).__name__, str(exc)[:120])])
            return {"card": card, "facts": {}, "note": "model reply unusable: %s" % type(exc).__name__}
        # scope the placeholders to the full fact ids ({corners_total} -> {c2_corners_total})
        def scope(s: str) -> str:
            return re.sub(r"\{([a-z0-9_]+)\}",
                          lambda m: "{" + (m.group(1) if m.group(1) in mcp.facts
                                           else prefix + m.group(1) if prefix + m.group(1) in mcp.facts
                                           else m.group(1)) + "}", s)
        card["reveal"]["plain"]["en"] = scope(out["plain"])
        card["reveal"]["expert"]["en"] = scope(out["expert"])
        used = sorted(set(placeholders(card["reveal"]["plain"]["en"] + card["reveal"]["expert"]["en"])))
        card["reveal"]["fact_ids"] = sorted(set(approved_card["reveal"]["fact_ids"]) |
                                            {u for u in used if u in mcp.facts})
        # the fact table is filled through the MCP server too: every value the trace shows was fetched
        facts: Dict[str, Dict[str, Any]] = {}
        for fid in card["reveal"]["fact_ids"]:
            try:
                facts[fid] = {"value": mcp.call_tool("get_fact", {"fact_id": fid})["value"], "source": "mcp:pip-facts-mcp"}
            except Exception as exc:
                facts[fid] = {"value": None, "source": "mcp error: %s" % exc}
        notes = ["%d tool call(s) through %s" % (len(mcp.calls), mcp.server)]
        if emulated:
            notes.append("the model did not call list_facts itself: the client fetched it via MCP and injected "
                         "the result (documented tool-call emulation)")
        rec.step("writer", "draft via MCP tools", to="checker", verdict="info", ms=ms, via_mcp=True, notes=notes,
                 text={"plain_en": card["reveal"]["plain"]["en"], "expert_en": card["reveal"]["expert"]["en"]})
        return {"card": card, "facts": facts, "note": "drafted by %s%s" % (self.model, " (emulated tool fetch)" if emulated else "")}

    # ---------- verifier ----------
    def _verify(self, draft: Dict[str, Any], mcp: McpClient, rec: Recorder) -> Tuple[bool, str]:
        t0 = time.time()
        fact_lines = "\n".join("- %s = %s (%s)" % (fid, f["value"], _meaning(fid))
                               for fid, f in sorted(draft["facts"].items())) or "- (no facts for this moment)"
        user = ("Facts fetched from the match events:\n%s\nDraft to verify ({placeholders} are filled by code "
                "with exactly those values):\nplain: %s\nexpert: %s" %
                (fact_lines, draft["card"]["reveal"]["plain"]["en"], draft["card"]["reveal"]["expert"]["en"]))
        try:
            msg = self.client.chat([{"role": "system", "content": VERIFIER_SYSTEM},
                                    {"role": "user", "content": user}], temperature=0.0, max_tokens=200)
            self.raw.append(str(msg.get("content") or ""))
            data = _parse_any(msg.get("content") or "")
            ok, reason = bool(data.get("ok")), str(data.get("reason", ""))[:200]
        except Exception as exc:
            rec.step("verifier", "verify against fetched facts", to="checker", verdict="info",
                     ms=int((time.time() - t0) * 1000), via_mcp=True,
                     notes=["verifier reply unusable (%s); the rule-based checker stays the authority" % type(exc).__name__])
            return True, ""
        rec.step("verifier", "verify against fetched facts", to="checker",
                 verdict="pass" if ok else "fail", ms=int((time.time() - t0) * 1000), via_mcp=True,
                 notes=([reason] if reason else []) +
                        ([] if ok else ["recorded; the rule-based checker (the authority) passed this draft"]))
        return ok, reason

    # ---------- editor ----------
    def _edit_stage(self, final: Dict[str, Any], truth: Dict[str, int], cand: Dict[str, Any],
                    rec: Recorder, attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
        before = final["card"]
        keep_placeholders = sorted(set(placeholders(before["reveal"]["plain"]["en"] +
                                                    before["reveal"]["expert"]["en"])))
        user = 'Tighten these two lines:\nplain: %s\nexpert: %s' % (before["reveal"]["plain"]["en"],
                                                                    before["reveal"]["expert"]["en"])
        messages: List[Dict[str, Any]] = [{"role": "system", "content": EDITOR_SYSTEM},
                                          {"role": "user", "content": user}]
        for try_n in (1, 2):
            t0 = time.time()
            try:
                msg = self.client.chat(messages, temperature=0.3)
                self.raw.append(str(msg.get("content") or ""))
                out = _parse_draft(msg.get("content") or "")
            except Exception as exc:
                rec.step("editor", "tighten lines", to="checker", verdict="fail", ms=int((time.time() - t0) * 1000),
                         notes=["editor reply unusable: %s" % type(exc).__name__])
                continue
            ms = int((time.time() - t0) * 1000)
            edited = copy.deepcopy(before)
            edited["reveal"]["plain"]["en"] = out["plain"]
            edited["reveal"]["expert"]["en"] = out["expert"]
            got = sorted(set(placeholders(out["plain"] + out["expert"])))
            errors: List[str] = []
            if got != keep_placeholders:
                errors.append("editor changed the placeholders (had %s, now %s)" %
                              (keep_placeholders or "none", got or "none"))
            errors.extend(check_card(edited, final["facts"], truth, cand.get("reveal_key", "")))
            attempts.append({
                "attempt": len(attempts) + 1, "writer": "editor (%s)" % self.model,
                "note": "editor pass %d" % try_n,
                "expert_en": edited["reveal"]["expert"]["en"], "plain_en": edited["reveal"]["plain"]["en"],
                "facts": {k: v["value"] for k, v in sorted(final["facts"].items())},
                "checker": "pass" if not errors else "fail", "errors": errors,
            })
            rec.step("editor", "tighten lines", to="checker", verdict="info", ms=ms,
                     text={"plain_en": out["plain"], "expert_en": out["expert"]})
            rec.step("checker", "check edited lines", to="orchestrator", verdict="pass" if not errors else "fail",
                     notes=errors[:6] or ["placeholders preserved: %s" % (", ".join(keep_placeholders) or "none")])
            if not errors:
                return {"source": final["source"] + ", edited", "card": edited, "facts": final["facts"]}
            messages.append({"role": "user",
                             "content": "Rejected by the checker:\n- " + "\n- ".join(errors) +
                                        "\nRewrite, copying every placeholder exactly."})
        rec.step("editor", "fallback", to="orchestrator", verdict="fail",
                 notes=["editing failed twice: the writer's checker-approved draft ships unchanged"])
        return final

    # ---------- translator ----------
    def _translate_stage(self, final: Dict[str, Any], approved_card: Dict[str, Any], truth: Dict[str, int],
                         template_fallback: bool, rec: Recorder) -> Dict[str, Dict[str, str]]:
        card, translations = final["card"], {}
        en_ph = sorted(set(placeholders(card["reveal"]["plain"]["en"] + card["reveal"]["expert"]["en"])))
        for lang in TRANSLATION_LANGS:
            fallback = {"plain": approved_card["reveal"]["plain"][lang],
                        "expert": approved_card["reveal"]["expert"][lang], "status": "fallback"}
            if template_fallback:
                translations[lang] = fallback
                rec.step("translator", "translate to %s" % lang, verdict="info",
                         notes=["template card ships its owner-reviewed %s lines" % lang.upper()])
                continue
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": TRANSLATOR_SYSTEM[lang] + "\n" + TRANSLATOR_RULES},
                {"role": "user", "content": "plain: %s\nexpert: %s" % (card["reveal"]["plain"]["en"],
                                                                       card["reveal"]["expert"]["en"])}]
            done = None
            for try_n in (1, 2):
                t0 = time.time()
                try:
                    msg = self.client.chat(messages, temperature=0.3)
                    self.raw.append(str(msg.get("content") or ""))
                    out = _parse_draft(msg.get("content") or "")
                except Exception as exc:
                    rec.step("translator", "translate to %s" % lang, to="checker", verdict="fail",
                             ms=int((time.time() - t0) * 1000),
                             notes=["translator reply unusable: %s" % type(exc).__name__])
                    break
                ms = int((time.time() - t0) * 1000)
                errors = self._check_translation(lang, out, en_ph, card, final["facts"])
                rec.step("translator", "translate to %s" % lang, to="checker",
                         verdict="pass" if not errors else "fail", ms=ms,
                         notes=errors[:6] or ["placeholders preserved: %s" % (", ".join(en_ph) or "none")],
                         text={"plain_" + lang: out["plain"], "expert_" + lang: out["expert"]})
                if not errors:
                    done = {"plain": out["plain"], "expert": out["expert"], "status": "approved"}
                    break
                messages.append({"role": "user",
                                 "content": "Rejected by the checker:\n- " + "\n- ".join(errors) +
                                            "\nTranslate again, copying every placeholder exactly."})
            if done is None:
                done = fallback
                rec.step("translator", "fallback %s" % lang, verdict="fail",
                         notes=["translation failed: the owner-reviewed template %s lines are used" % lang.upper()])
            translations[lang] = done
        return translations

    def _check_translation(self, lang: str, out: Dict[str, str], en_ph: List[str],
                           card: Dict[str, Any], facts: Dict[str, Dict[str, Any]]) -> List[str]:
        errors: List[str] = []
        got = sorted(set(placeholders(out["plain"] + out["expert"])))
        if got != en_ph:
            errors.append("%s: placeholders changed (had %s, now %s)" % (lang, en_ph or "none", got or "none"))
        probe = copy.deepcopy(card)
        probe["reveal"]["plain"][lang] = out["plain"]
        probe["reveal"]["expert"][lang] = out["expert"]
        errors.extend(copycheck.check_copy({"facts": facts, "cards": [probe]}))
        return errors

    # ---------- the whole match ----------
    def run_match(self, match: Dict[str, Any]) -> Dict[str, Any]:
        out, accepted, held = reader._build(match)
        team_names = {t["team_id"]: t["name"] for t in match["teams"]}
        entries = [self.run_card(match, cand, card, team_names)
                   for cand, card in zip(accepted, out["cards"])]
        shipped_ok = all(e["approved_expert_en"] == c["reveal"]["expert"]["en"]
                         and e["approved_plain_en"] == c["reveal"]["plain"]["en"]
                         and all(out["facts"][f]["value"] == v for f, v in e["approved_facts"].items())
                         for e, c in zip(entries, out["cards"]))
        return {
            "match_id": match["match_id"], "seed": match["seed"], "workflow_version": WORKFLOW_VERSION + "+multi",
            "writer": "multi", "model": self.model, "uses_ai": True, "max_retries": MAX_RETRIES,
            "cards": entries,
            "held": [{"trigger": h["trigger"], "t_in_min": h["t_in_min"], "team_id": h["team_id"],
                      "decision": "hold", "reason": h["reason"]} for h in held],
            "shipped_equals_checked": shipped_ok,
            "agents": agents_roster(self.model),
            "mcp": {"server": SERVER_NAME + " (stdio, JSON-RPC 2.0)", "tools": ["list_facts", "get_fact"],
                    "calls": sum(len(c["tool_calls"]) for c in entries)},
            "note": "Trial run. DE and VI lines are drafts until the owner checks them (AGENTS.md conventions). "
                    "The hosted match plays the reviewed templates.",
            "model_replies": self.raw,
        }


def _parse_any(text: str) -> Dict[str, Any]:
    """JSON object from a model reply that may carry fences or prose (verifier replies)."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text[text.find("{"):text.rfind("}") + 1])

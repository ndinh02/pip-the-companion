"""The multi-agent workflow without a model: a scripted client stands in for Foundry Local,
and the MCP server is the real subprocess (loopback stdio only, no network)."""
from __future__ import annotations

import io
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pip_agents import paths  # noqa: E402,F401
from pip_agents import mcp_server  # noqa: E402
from pip_agents.mcp_client import McpClient  # noqa: E402
from pip_agents.multi import MultiAgentRunner, _parse_draft  # noqa: E402
from matchlab import generate_match  # noqa: E402
from matchreader import reader  # noqa: E402


class ScriptedClient:
    """Stands in for FoundryClient: drafts from the tool results it is given, so the
    pipeline below it (MCP server, checker, editor, translator) runs for real."""

    model = "fake-model"

    def __init__(self, garbage=False, blind=False, bad_edit=False, bad_translation=False):
        self.garbage, self.blind = garbage, blind
        self.bad_edit, self.bad_translation = bad_edit, bad_translation
        self.tool_calls_made = 0

    def chat(self, messages, tools=None, temperature=0.4, max_tokens=400):
        system = messages[0]["content"] if messages else ""
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        if "reveal for Pip" in system:  # the writer
            return self._writer(messages, user, tools)
        if "verify a drafted football TV reveal" in system:
            return {"content": '{"ok": true, "reason": "the draft matches the fetched facts"}'}
        if "editor for short football TV lines" in system:
            return self._editor(user)
        if "translate two short football TV lines" in system:
            return self._translator(system, user)
        raise AssertionError("unexpected system prompt: %r" % system[:60])

    def _draft(self, plain_source, expert_source, fact_id):
        plain = "What happened: " + plain_source
        expert = ("Data point: {%s} today." % fact_id) if fact_id else "No numbers for this moment."
        return {"content": json.dumps({"plain": plain, "expert": expert})}

    def _writer(self, messages, user, tools):
        if self.garbage:
            return {"content": "not json at all"}
        if tools:
            pass
        listing = None
        for m in messages:  # the fact list arrives as a tool message, or injected by the client
            if m.get("role") == "tool":
                listing = json.loads(m["content"])
        if listing is None and tools and not self.blind:
            self.tool_calls_made += 1
            return {"content": "", "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "list_facts", "arguments": "{}"}}]}
        if listing is None:  # blind model: the emulation path injects the listing into a user message
            m = re.search(r"\[\{.*\}\]", user, re.S)
            listing = json.loads(m.group(0)) if m else []
        fact_id = listing[0]["fact_id"] if listing else None
        what = re.search(r"What actually happened: (.+)", user)
        return self._draft(what.group(1) if what else "the moment is over", None, fact_id)

    def _editor(self, user):
        plain, expert = self._two_lines(user)
        if self.bad_edit:  # drops the placeholder from the expert line
            expert = re.sub(r"\{[a-z0-9_]+\}", "plenty", expert)
        return {"content": json.dumps({"plain": plain, "expert": expert})}

    def _translator(self, system, user):
        plain, expert = self._two_lines(user)
        if self.bad_translation:  # renames a placeholder
            expert = re.sub(r"\{([a-z0-9_]+)\}", r"{falsch_\1}", expert)
        return {"content": json.dumps({"plain": "DE-entwurf: " + plain, "expert": "DE-entwurf: " + expert})}

    @staticmethod
    def _two_lines(user):
        plain = re.search(r"plain: (.+)", user).group(1)
        expert = re.search(r"expert: (.+)", user).group(1)
        return plain, expert


class ParseDraftTest(unittest.TestCase):
    def test_all_the_shapes_the_model_actually_answers_in(self):
        cases = [
            '{"plain": "Cross!", "expert": "{c2_corners_total} today."}',
            '```json\n{"plain": "Cross!", "expert": "{c2_corners_total} today."}\n```',
            'Plain: Cross!\nExpert: {c2_corners_total} today.',
            '**Plain** - Cross!\n**Expert** - {c2_corners_total} today.',
            'Cross!\n{c2_corners_total} today.',
        ]
        for c in cases:
            self.assertEqual(_parse_draft(c), {"plain": "Cross!", "expert": "{c2_corners_total} today."}, c)
        with self.assertRaises(ValueError):
            _parse_draft("the model rambled and never delivered two lines")


class McpServerTest(unittest.TestCase):
    FACTS = {"c2_corners_total": 3, "c2_corners_short": 0}

    def test_request_response_cycle_in_process(self):
        out = io.StringIO()
        lines = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "list_facts", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "get_fact", "arguments": {"fact_id": "c2_corners_total"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
             "params": {"name": "get_fact", "arguments": {"fact_id": "nope"}}},
            {"jsonrpc": "2.0", "id": 6, "method": "bogus/method", "params": {}},
            "not json",
        ]
        mcp_server.serve(self.FACTS, io.StringIO("\n".join(json.dumps(x) if not isinstance(x, str) else x for x in lines)), out)
        replies = [json.loads(l) for l in out.getvalue().strip().splitlines()]
        by_id = {r["id"]: r for r in replies if "id" in r}
        self.assertEqual(len(replies), 7)  # the notification gets no reply; the bad line gets a parse error
        self.assertEqual(replies[-1]["error"]["code"], -32700)
        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"], "pip-facts-mcp")
        self.assertEqual([t["name"] for t in by_id[2]["result"]["tools"]], ["list_facts", "get_fact"])
        listing = json.loads(by_id[3]["result"]["content"][0]["text"])
        self.assertEqual([f["fact_id"] for f in listing], ["c2_corners_short", "c2_corners_total"])
        self.assertIn("meaning", listing[0])
        got = json.loads(by_id[4]["result"]["content"][0]["text"])
        self.assertEqual(got["value"], 3)
        self.assertTrue(by_id[5]["result"]["isError"])
        self.assertEqual(by_id[6]["error"]["code"], -32601)

    def test_real_subprocess_roundtrip(self):
        with McpClient(self.FACTS) as mcp:
            self.assertEqual(mcp.tools, ["list_facts", "get_fact"])
            listing = mcp.call_tool("list_facts", {})
            self.assertEqual([f["fact_id"] for f in listing], ["c2_corners_short", "c2_corners_total"])
            self.assertEqual(mcp.call_tool("get_fact", {"fact_id": "c2_corners_total"})["value"], 3)
            with self.assertRaises(RuntimeError):
                mcp.call_tool("get_fact", {"fact_id": "nope"})
            self.assertEqual(len(mcp.calls), 3)
            self.assertIn("error", mcp.calls[2])


class MultiRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.match = generate_match(43)
        cls.out, cls.accepted, cls.held = reader._build(cls.match)
        cls.team_names = {t["team_id"]: t["name"] for t in cls.match["teams"]}

    def run_one_card(self, client, index=0):
        return MultiAgentRunner(client).run_card(self.match, self.accepted[index],
                                                 self.out["cards"][index], self.team_names)

    def test_orchestrator_record_happy_path(self):
        entry = self.run_one_card(ScriptedClient())
        self.assertTrue(entry["approved_by"].startswith("writer (fake-model)"), entry["approved_by"])
        self.assertEqual(entry["attempts"][0]["checker"], "pass")
        agents = [s["agent"] for s in entry["steps"]]
        self.assertEqual(agents[0], "orchestrator")
        for a in ("writer", "checker", "verifier", "editor", "translator"):
            self.assertIn(a, agents, entry["steps"])
        writer_step = next(s for s in entry["steps"] if s["agent"] == "writer")
        self.assertTrue(writer_step["via_mcp"])
        self.assertTrue(entry["tool_calls"])          # every fact fetch went through the MCP server
        self.assertIn("get_fact", [c["tool"] for c in entry["tool_calls"]])
        for lang in ("de", "vi"):
            self.assertEqual(entry["translations"][lang]["status"], "approved", entry["translations"])
        self.assertIn("{", entry["approved_expert_en"])  # numbers stay placeholders
        self.assertNotIn("9", entry["approved_facts"].values())

    def test_blind_model_gets_emulated_tool_fetch(self):
        client = ScriptedClient(blind=True)
        entry = self.run_one_card(client)
        self.assertEqual(client.tool_calls_made, 0)  # the model never called the tools itself
        self.assertTrue(entry["approved_by"].startswith("writer"))
        writer_notes = [n for s in entry["steps"] if s["agent"] == "writer" for n in s["notes"]]
        self.assertTrue(any("emulation" in n for n in writer_notes), writer_notes)
        self.assertTrue(any("emulated tool fetch" in a["note"] for a in entry["attempts"]))

    def test_editor_must_preserve_placeholders(self):
        entry = self.run_one_card(ScriptedClient(bad_edit=True))
        editor_attempts = [a for a in entry["attempts"] if a["writer"].startswith("editor")]
        self.assertEqual(len(editor_attempts), 2)
        self.assertTrue(all(a["checker"] == "fail" for a in editor_attempts))
        self.assertTrue(all("placeholders" in "; ".join(a["errors"]) for a in editor_attempts))
        # fallback: the writer's checker-approved draft ships unchanged
        self.assertEqual(entry["approved_plain_en"], entry["attempts"][0]["plain_en"])
        self.assertIn("fallback", [s["action"] for s in entry["steps"]])

    def test_translator_fallback_is_the_reviewed_template(self):
        entry = self.run_one_card(ScriptedClient(bad_translation=True))
        template = self.out["cards"][0]["reveal"]
        for lang in ("de", "vi"):
            tr = entry["translations"][lang]
            self.assertEqual(tr["status"], "fallback", lang)
            self.assertEqual(tr["plain"], template["plain"][lang], lang)
            self.assertEqual(tr["expert"], template["expert"][lang], lang)

    def test_unusable_writer_falls_back_to_the_fixed_template(self):
        entry = self.run_one_card(ScriptedClient(garbage=True))
        self.assertEqual(entry["approved_by"], "template (fallback)")
        self.assertEqual([a["checker"] for a in entry["attempts"]], ["fail", "fail", "fail", "pass"])
        self.assertTrue(all("unusable" in a["note"] for a in entry["attempts"][:3]))
        self.assertEqual(template_plain := self.out["cards"][0]["reveal"]["plain"]["en"], entry["approved_plain_en"])
        self.assertIsNotNone(template_plain)
        for lang in ("de", "vi"):
            self.assertEqual(entry["translations"][lang]["status"], "fallback")

    def test_whole_match_trace_shape(self):
        data = MultiAgentRunner(ScriptedClient()).run_match(self.match)
        self.assertEqual(data["writer"], "multi")
        self.assertTrue(data["uses_ai"])
        self.assertEqual(data["model"], "fake-model")
        self.assertEqual([a["id"] for a in data["agents"]],
                         ["orchestrator", "writer", "checker", "verifier", "editor", "translator"])
        self.assertEqual(data["mcp"]["tools"], ["list_facts", "get_fact"])
        self.assertEqual(data["mcp"]["calls"], sum(len(c["tool_calls"]) for c in data["cards"]))
        self.assertGreater(data["mcp"]["calls"], 0)
        self.assertEqual(len(data["cards"]), len(self.out["cards"]))
        for c in data["cards"]:
            for key in ("card_id", "trigger", "t_in_min", "team_id", "question_en", "decision", "facts_from_events",
                        "approved_facts", "attempts", "steps", "approved_by", "approved_expert_en",
                        "approved_plain_en", "translations"):
                self.assertIn(key, c)
            for s in c["steps"]:
                self.assertIn(s["verdict"], ("pass", "fail", "info"))
                self.assertIn("via_mcp", s)


if __name__ == "__main__":
    unittest.main()

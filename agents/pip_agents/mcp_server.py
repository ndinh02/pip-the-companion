"""A minimal MCP (Model Context Protocol) server over stdio for one card's facts.

Run as:  python3 -m pip_agents.mcp_server <facts.json>
The facts file maps fact_id -> value (e.g. {"c2_corners_total": 3}).

Speaks newline-delimited JSON-RPC 2.0 on stdin/stdout, the MCP stdio transport:
initialize, notifications/initialized, ping, tools/list, tools/call. Two tools:
  list_facts  -> the fact ids of this moment, with a plain-language meaning
  get_fact    -> one fact's value (the value is filled into {placeholders} by code)

This is a REAL MCP server: the pipeline (mcp_client.McpClient) spawns it as a
subprocess and talks JSON-RPC to it. It never touches the network.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, IO, Optional

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "pip-facts-mcp"
SERVER_VERSION = "1.0.0"

# What each fact means, in words a writer can use (shared with the LLM writer).
from .llm_writer import FACT_MEANING  # noqa: E402

TOOLS = [
    {
        "name": "list_facts",
        "description": "List the facts available for this moment. Each fact_id can be written as a "
                       "{placeholder} in the text; code fills the value.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_fact",
        "description": "Get one fact's value. Values are filled into {placeholders} by code; never type "
                       "a number into the text yourself.",
        "inputSchema": {
            "type": "object",
            "properties": {"fact_id": {"type": "string", "description": "a fact_id returned by list_facts"}},
            "required": ["fact_id"],
        },
    },
]


def _meaning(fact_id: str) -> str:
    name = fact_id.split("_", 1)[1] if "_" in fact_id else fact_id
    return FACT_MEANING.get(name, name.replace("_", " "))


def _text(content: str, is_error: bool = False) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": content}], "isError": is_error}


def handle(request: Dict[str, Any], facts: Dict[str, int]) -> Optional[Dict[str, Any]]:
    """One JSON-RPC request -> response (None for notifications, which get no reply)."""
    method = request.get("method", "")
    rid = request.get("id")
    if method.startswith("notifications/"):
        return None
    try:
        if method == "initialize":
            result: Any = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = request.get("params") or {}
            name = params.get("name", "")
            args = params.get("arguments") or {}
            if name == "list_facts":
                listing = [{"fact_id": fid, "meaning": _meaning(fid)} for fid in sorted(facts)]
                result = _text(json.dumps(listing, ensure_ascii=False))
            elif name == "get_fact":
                fid = str(args.get("fact_id", ""))
                if fid not in facts:
                    result = _text("unknown fact_id %r; call list_facts first" % fid, is_error=True)
                else:
                    result = _text(json.dumps({
                        "fact_id": fid, "value": facts[fid], "meaning": _meaning(fid),
                        "note": "this value is filled into the text by code: write the placeholder {%s} in your "
                                "lines, NEVER the number itself" % fid}, ensure_ascii=False))
            else:
                result = _text("unknown tool %r" % name, is_error=True)
        else:
            if rid is None:
                return None
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found: %s" % method}}
        if rid is None:  # a request without id is a notification: never answer
            return None
        return {"jsonrpc": "2.0", "id": rid, "result": result}
    except Exception as exc:  # a broken request must not kill the server
        if rid is None:
            return None
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32603, "message": "internal error: %s" % exc}}


def serve(facts: Dict[str, int], instream: IO[str], outstream: IO[str]) -> None:
    """Line-delimited JSON-RPC until the input ends."""
    for line in instream:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            response: Optional[Dict[str, Any]] = {"jsonrpc": "2.0", "id": None,
                                                  "error": {"code": -32700, "message": "parse error"}}
        else:
            response = handle(request, facts)
        if response is not None:
            outstream.write(json.dumps(response, ensure_ascii=False) + "\n")
            outstream.flush()


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        sys.stderr.write("usage: python3 -m pip_agents.mcp_server <facts.json>\n")
        return 2
    with open(argv[0], encoding="utf-8") as fh:
        facts = {k: int(v) for k, v in json.load(fh).items()}
    serve(facts, sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

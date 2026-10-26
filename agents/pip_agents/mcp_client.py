"""The pipeline's MCP client: spawns pip_agents.mcp_server as a subprocess and
speaks newline-delimited JSON-RPC 2.0 to it over stdio. Every tool call is
logged so the trace can show exactly which facts were fetched and when.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

from .mcp_server import PROTOCOL_VERSION, SERVER_NAME


class McpClient:
    """One client session against one card's facts. Use as a context manager."""

    def __init__(self, facts: Dict[str, int]) -> None:
        self.facts: Dict[str, int] = dict(facts)
        self.calls: List[Dict[str, Any]] = []  # the log the trace shows
        self.server = SERVER_NAME + " (stdio, JSON-RPC 2.0)"
        self._next_id = 1
        agents_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fd, self._facts_path = tempfile.mkstemp(prefix="pip-facts-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self.facts, fh)
        env = dict(os.environ)
        env["PYTHONPATH"] = agents_dir + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "pip_agents.mcp_server", self._facts_path],
            cwd=agents_dir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=env)
        info = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "pip-agents", "version": "1.0.0"}})
        self.server_info = info.get("serverInfo", {})
        self._notify("notifications/initialized")
        self.tools: List[str] = [t["name"] for t in self._request("tools/list", {})["tools"]]

    # ---- JSON-RPC plumbing ----
    def _send(self, obj: Dict[str, Any]) -> None:
        assert self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(obj) + "\n")
        self._proc.stdin.flush()

    def _read(self) -> Dict[str, Any]:
        assert self._proc.stdout is not None
        line = self._proc.stdout.readline()
        if not line:
            raise IOError("the MCP server closed its stdout")
        return json.loads(line)

    def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        rid = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        while True:  # skip anything that is not the answer to this request
            msg = self._read()
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError("MCP %s failed: %s" % (method, msg["error"].get("message")))
                return msg["result"]

    def _notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    # ---- the tools the agents use ----
    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Call one tool; return its parsed text payload. Every call is logged."""
        arguments = arguments or {}
        t0 = time.time()
        entry: Dict[str, Any] = {"tool": name, "arguments": arguments}
        try:
            result = self._request("tools/call", {"name": name, "arguments": arguments})
            payload = result["content"][0]["text"] if result.get("content") else ""
            if result.get("isError"):
                raise RuntimeError(payload)
            entry["result"] = json.loads(payload)
        except Exception as exc:
            entry["error"] = str(exc)
            entry["ms"] = round((time.time() - t0) * 1000)
            self.calls.append(entry)
            raise
        entry["ms"] = round((time.time() - t0) * 1000)
        self.calls.append(entry)
        return entry["result"]

    def close(self) -> None:
        try:
            if self._proc.poll() is None:
                try:
                    if self._proc.stdin is not None:
                        self._proc.stdin.close()  # EOF: the server's serve() loop ends cleanly
                except OSError:
                    pass
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait()
            for pipe in (self._proc.stdout, self._proc.stderr):
                try:
                    if pipe is not None:
                        pipe.close()
                except OSError:
                    pass
        finally:
            try:
                os.remove(self._facts_path)
            except OSError:
                pass

    def __enter__(self) -> "McpClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

"""Function tools a writer may call. They are the ONLY way a writer gets numbers:
facts are computed by code from the match events, never typed into a prompt (brief 7.3)."""
from __future__ import annotations

from typing import Any, Dict, List

from . import paths  # noqa: F401
from matchreader import reader


class FactTools:
    """Read-only access to one moment's code-computed facts. Every call is logged for the trace."""

    def __init__(self, match: Dict[str, Any], cand: Dict[str, Any], prefix: str) -> None:
        self._values = reader.card_facts(match, cand)
        self._prefix = prefix
        self.calls: List[Dict[str, Any]] = []

    def list_facts(self) -> List[str]:
        ids = sorted(self._prefix + k for k in self._values)
        self.calls.append({"tool": "list_facts", "result": ids})
        return ids

    def get_fact(self, fact_id: str) -> int:
        name = fact_id[len(self._prefix):] if fact_id.startswith(self._prefix) else fact_id
        if name not in self._values:
            self.calls.append({"tool": "get_fact", "fact_id": fact_id, "error": "unknown fact"})
            raise KeyError(fact_id)
        self.calls.append({"tool": "get_fact", "fact_id": fact_id, "result": self._values[name]})
        return self._values[name]

    def truth(self) -> Dict[str, int]:
        """For the checker only: every fact of this moment, recomputed from the events."""
        return {self._prefix + k: v for k, v in self._values.items()}

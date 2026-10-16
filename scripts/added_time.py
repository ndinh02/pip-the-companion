"""Added-time explainer data: why the board shows N minutes, from the stoppage events.

Reads a match-lab match file, writes the breakdown the web app shows at 45' and 90'.
Every number comes from the stoppages in the match file (no AI, no guessing).

    python3 scripts/added_time.py --in data/mock-seed-1.json --out web/public/data/added-time.json

`--as-match-id mock-001` labels the file for a different match id. Use it only to preview the
explainer on the hand-written mock match; drop it once the demo match is generated from the same seed.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional

# Board time sits at the end of regulation: minute 45 (period 1) and 90 (period 2).
BOARD_MINUTE = {1: 45, 2: 90}
# Same order the web app lists them in when seconds tie.
TYPE_ORDER = ["goal", "sub", "injury", "VAR", "card", "other"]


def build(match: Dict[str, Any], as_match_id: Optional[str] = None) -> Dict[str, Any]:
    boards: List[Dict[str, Any]] = []
    for period in match["periods"]:
        totals: Dict[str, Dict[str, float]] = {}
        for s in match["stoppages"]:
            if not s["counts_for_added_time"]:
                continue
            if not period["start_ms"] <= s["t_start_ms"] < period["end_ms"]:
                continue
            row = totals.setdefault(s["type"], {"count": 0, "seconds": 0.0})
            # A sub window with several substitutions is one stoppage but several changes.
            row["count"] += len(s["related_event_ids"]) if s["type"] == "sub" else 1
            row["seconds"] += s["duration_s"]
        items = [{"type": t, "count": int(r["count"]), "seconds": int(round(r["seconds"]))} for t, r in totals.items()]
        items.sort(key=lambda i: (-i["seconds"], TYPE_ORDER.index(i["type"]) if i["type"] in TYPE_ORDER else 99))
        boards.append({
            "period": period["id"],
            "at_min": BOARD_MINUTE[period["id"]],
            "announced_min": period["added_time_announced_s"] // 60,
            "actual_s": period["added_time_actual_s"],
            "items": items,
        })
    out: Dict[str, Any] = {
        "match_id": as_match_id or match["match_id"],
        "seed": match["seed"],
        "source": "stoppages in the match file (match-lab %s)" % match["generator_version"],
        "boards": boards,
    }
    if as_match_id:
        out["preview_for"] = as_match_id
        out["real_match_id"] = match["match_id"]
    return out


def dumps(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, indent=1, ensure_ascii=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="src", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--as-match-id")
    args = parser.parse_args()
    with open(args.src, encoding="utf-8") as fh:
        data = build(json.load(fh), args.as_match_id)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(dumps(data))
    for b in data["boards"]:
        print("period %d: board %d min, %d s counted, %s" % (
            b["period"], b["announced_min"], b["actual_s"], ", ".join("%s x%d %ds" % (i["type"], i["count"], i["seconds"]) for i in b["items"])))


if __name__ == "__main__":
    main()

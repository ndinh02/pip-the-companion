"""Player stats feed (task 05): per player, cumulative stats per match minute.

build_players(tracked_match, tracking) -> dict, the shape of data/players.json:
counted stats (passes, hard passes, ball wins, shots, saves) come from the
tracked events -- the NEW player ids task 04 wrote -- and physical stats
(distance, top speed, sprints) are computed from the 5 Hz tracking file.

Minute index: array[m] = value at the START of minute m, i.e. events/frames
with t < m. The phone shows minute m and must not see anything from m.x
(no spoilers, scope decision D3). Clock via reader.clock_minutes (period 2 =
45 + elapsed); period-1 added time counts as minute 44.99 so first-half
stoppage time never leaks into minute 45.

Pure function of the inputs: no randomness, no network, no AI (AGENTS.md 1-2).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from .reader import HOME, _attacks_plus_x, clock_minutes, dumps

PLAYERS_VERSION = "matchreader-players-0.1.0"
MODEL_NOTE = "distance, top speed and sprints are computed from synthetic tracking data"

COUNTED = ("passes", "passes_ok", "hard_ok", "ball_wins", "shots", "saves")
STATS = COUNTED + ("distance_m", "top_speed_dmh", "sprints")

_DM = 10.0            # tracking unit: decimetres
_DT = 0.2             # 5 Hz
_SPRINT_MS = 25.0 / 3.6   # 25 km/h in m/s (6.94)
_SPRINT_FRAMES = 5        # >= 1.0 s above the threshold completes a sprint
_P1_CLAMP = 44.99         # period-1 added time shows as minute 44.99


def _minute(t_ms: int, match: Dict[str, Any], period: int) -> float:
    """Match-clock minute of an event/frame, with the period-1 clamp."""
    t = clock_minutes(t_ms, match, period)
    return _P1_CLAMP if (period == 1 and t > 45.0) else t


# ---- counted stats --------------------------------------------------------

def pass_difficulty(ev: Dict[str, Any]) -> int:
    """1-5 from event fields only (scope section 2):
    1 + length bonus (<15 m: 0, 15-<30: 1, >=30: 2)
      + forward bonus (gains >= 10 m toward the goal the team attacks)
      + pressure bonus (pressure_level >= 4), capped at 5."""
    dx = ev["end"]["x"] - ev["start"]["x"]
    dy = ev["end"]["y"] - ev["start"]["y"]
    length = math.hypot(dx, dy)
    if length >= 30.0:
        bonus = 2
    elif length >= 15.0:
        bonus = 1
    else:
        bonus = 0
    gain = dx if _attacks_plus_x(ev["team_id"], ev["period"]) else -dx
    if gain >= 10.0:
        bonus += 1
    if ev.get("pressure_level", 0) >= 4:
        bonus += 1
    return min(5, 1 + bonus)


def _counted_times(match: Dict[str, Any],
                   pids: List[str]) -> Dict[str, Dict[str, List[float]]]:
    """Sorted event minutes per player per counted stat."""
    times = {pid: {key: [] for key in COUNTED} for pid in pids}
    for ev in match["events"]:
        pid = ev["player_id"]
        if pid not in times:
            continue
        t = _minute(ev["t_ms"], match, ev["period"])
        typ = ev["type"]
        if typ == "pass":
            times[pid]["passes"].append(t)
            if ev["outcome"] == "success":
                times[pid]["passes_ok"].append(t)
                if pass_difficulty(ev) >= 4:
                    times[pid]["hard_ok"].append(t)
        elif typ in ("tackle", "interception"):
            times[pid]["ball_wins"].append(t)
        elif typ == "shot":
            times[pid]["shots"].append(t)
        elif typ == "free_kick" and ev.get("subtype") == "shoot":
            times[pid]["shots"].append(t)
        elif typ == "keeper_save":
            times[pid]["saves"].append(t)
    for pid in pids:
        for key in COUNTED:
            times[pid][key].sort()
    return times


# ---- physical stats (from the tracking file) --------------------------------

def _frame_minutes(tracking: Dict[str, Any], match: Dict[str, Any]) -> List[float]:
    out: List[float] = []
    for p in sorted(tracking["periods"], key=lambda q: q["id"]):
        for k in range(p["frames"]):
            out.append(_minute(p["start_ms"] + k * 200, match, p["id"]))
    return out


def _physical(pid: str, xs: Dict[str, List[int]], ys: Dict[str, List[int]],
              fmin: List[float], last_minute: int) -> Dict[str, List[int]]:
    X, Y = xs[pid], ys[pid]
    n = min(len(X), len(fmin))

    # raw and 3-frame smoothed speeds, indexed by the step's END frame; a speed
    # is defined only when both frames are on the pitch (x >= 0)
    v = [0.0] * n
    has_v = [False] * n
    for k in range(1, n):
        if X[k - 1] >= 0 and X[k] >= 0:
            v[k] = math.hypot(X[k] - X[k - 1], Y[k] - Y[k - 1]) / _DM / _DT
            has_v[k] = True
    sm = [0.0] * n
    for k in range(1, n):
        lo = max(1, k - 2)
        vals = [v[j] for j in range(lo, k + 1) if has_v[j]]
        sm[k] = sum(vals) / len(vals) if vals else 0.0

    # cumulative distance through frame k (steps with a -1 endpoint ignored)
    dist = [0.0] * n
    for k in range(1, n):
        step = math.hypot(X[k] - X[k - 1], Y[k] - Y[k - 1]) / _DM \
            if X[k - 1] >= 0 and X[k] >= 0 else 0.0
        dist[k] = dist[k - 1] + step

    # sprints: maximal runs of frames with smoothed speed above 25 km/h,
    # merged when separated by < 1 s below the threshold; a sprint needs
    # >= 5 frames above it. A run is only COMPLETED once the 5 frames after
    # its end are visible (they settle both the completion and any merge):
    # sprints[m] then never depends on frames from minute m.x (D3, no spoilers)
    runs: List[List[int]] = []   # [first, last, frames above]
    k = 1
    while k < n:
        if sm[k] > _SPRINT_MS:
            j = k
            while j + 1 < n and sm[j + 1] > _SPRINT_MS:
                j += 1
            runs.append([k, j, j - k + 1])
            k = j + 1
        else:
            k += 1
    merged: List[List[int]] = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 < _SPRINT_FRAMES:
            merged[-1][1] = r[1]
            merged[-1][2] += r[2]
        else:
            merged.append(list(r))
    ends = [r[1] for r in merged if r[2] >= _SPRINT_FRAMES]

    dist_m = [0] * (last_minute + 1)
    top = [0] * (last_minute + 1)
    sprints = [0] * (last_minute + 1)
    k = 0   # frames 0..k-1 are visible (fmin < m)
    se = 0
    seen_d = 0.0
    seen_t = 0.0
    seen_s = 0
    for m in range(last_minute + 1):
        while k < n and fmin[k] < m:
            seen_d = dist[k]
            if sm[k] > seen_t:
                seen_t = sm[k]
            k += 1
        while se < len(ends) and ends[se] + _SPRINT_FRAMES < k:
            seen_s += 1
            se += 1
        dist_m[m] = int(math.floor(seen_d + 0.5))
        top[m] = int(math.floor(seen_t * 3.6 * 10.0 + 0.5))
        sprints[m] = seen_s
    return {"distance_m": dist_m, "top_speed_dmh": top, "sprints": sprints}


# ---- minutes on the pitch ---------------------------------------------------

def _minutes_on_off(match: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, float]]:
    on: Dict[str, float] = {}
    off: Dict[str, float] = {}
    for ev in match["events"]:
        if ev["type"] == "substitution":
            on.setdefault(ev["player_id"], _minute(ev["t_ms"], match, ev["period"]))
            off[ev["player_out_id"]] = _minute(ev["t_ms"], match, ev["period"])
        elif ev["type"] == "card" and ev["subtype"] == "second_yellow":
            off[ev["player_id"]] = _minute(ev["t_ms"], match, ev["period"])
    return on, off


# ---- the feed ----------------------------------------------------------------

def _cumulative(times: List[float], last_minute: int) -> List[int]:
    """array[m] = number of times < m (times sorted)."""
    arr = [0] * (last_minute + 1)
    i = 0
    for m in range(last_minute + 1):
        while i < len(times) and times[i] < m:
            i += 1
        arr[m] = i
    return arr


def build_players(tracked_match: Dict[str, Any], tracking: Dict[str, Any]) -> Dict[str, Any]:
    """The players.json dict. Deterministic: same inputs -> same bytes."""
    events = tracked_match["events"]
    last = 0.0
    for ev in events:
        t = _minute(ev["t_ms"], tracked_match, ev["period"])
        if t > last:
            last = t
    last_minute = max(90, int(math.ceil(last - 1e-9)))

    fmin = _frame_minutes(tracking, tracked_match)
    xs, ys = tracking["x"], tracking["y"]
    pids = [p["player_id"] for p in tracked_match["players"]]
    counted = _counted_times(tracked_match, pids)
    on, off = _minutes_on_off(tracked_match)

    players_out = []
    ordered = sorted(tracked_match["players"],
                     key=lambda p: (0 if p["team_id"] == HOME else 1, p["shirt_no"]))
    for p in ordered:
        pid = p["player_id"]
        stats: Dict[str, List[int]] = {}
        for key in COUNTED:
            stats[key] = _cumulative(counted[pid][key], last_minute)
        stats.update(_physical(pid, xs, ys, fmin, last_minute))
        players_out.append({
            "player_id": pid,
            "team_id": p["team_id"],
            "shirt_no": p["shirt_no"],
            "position": p["position"],
            "on_min": on.get(pid, 0.0) if p["shirt_no"] > 11 else 0.0,
            "off_min": off.get(pid),   # None -> null (never left)
            "stats": {key: stats[key] for key in STATS},
        })

    return {
        "match_id": tracked_match["match_id"],
        "seed": tracked_match["seed"],
        "reader_version": PLAYERS_VERSION,
        "last_minute": last_minute,
        "model": MODEL_NOTE,
        "players": players_out,
    }


# ---- command line -------------------------------------------------------------

def _load_matchlab():
    """Import matchlab (generate + track) from the sibling match-lab/ directory."""
    lab = os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "match-lab"))
    if lab not in sys.path:
        sys.path.insert(0, lab)
    from matchlab import generate_match
    from matchlab.tracking import track_match
    return generate_match, track_match


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build data/players.json (per-player cumulative stats per match minute).")
    parser.add_argument("--seed", type=int,
                        help="generate + track this seed in-process (matchlab)")
    parser.add_argument("--match", help="tracked match JSON, e.g. ../data/tracked-seed-43.json")
    parser.add_argument("--tracking", help="tracking JSON, e.g. ../data/tracking-seed-43.json")
    parser.add_argument("--out", required=True, help="output JSON path, e.g. ../data/players.json")
    args = parser.parse_args(argv)

    if (args.seed is None) == (args.match is None):
        parser.error("give exactly one of --seed or --match (with --tracking)")
    if args.match is not None and args.tracking is None:
        parser.error("--match needs --tracking")

    tracked: Dict[str, Any]
    tracking: Dict[str, Any]
    if args.seed is not None:
        generate_match, track_match = _load_matchlab()
        tracked, tracking = track_match(generate_match(args.seed))
    else:
        with open(args.match, encoding="utf-8") as fh:
            tracked = json.load(fh)
        with open(args.tracking, encoding="utf-8") as fh:
            tracking = json.load(fh)

    out = build_players(tracked, tracking)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(dumps(out))

    busiest = max(out["players"], key=lambda p: p["stats"]["distance_m"][out["last_minute"]])
    print("wrote %s: %d players, last minute %d, %.1f KB; most ground: %s with %.2f km" % (
        args.out, len(out["players"]), out["last_minute"],
        os.path.getsize(args.out) / 1e3, busiest["player_id"],
        busiest["stats"]["distance_m"][out["last_minute"]] / 1000.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

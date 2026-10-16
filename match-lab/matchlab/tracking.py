"""Tracking synthesizer (task 04, spec docs/TRACKING_SPEC.md).

track_match(match) simulates the 22 players and the ball at 10 Hz, consistent
with the match's own events, and returns (tracked_match, tracking):

- tracked_match: the same events with the acting player renamed to the nearest
  feasible teammate (only player_id changes; card player_id/subtype recomputed
  from the new ids), plus a top-level "tracking" pointer.
- tracking: the 5 Hz output file dict (decimetres, -1 = off pitch).

Deterministic from the seed: the only randomness is random.Random("%d-track"),
drawn in a fixed order. No AI, no I/O (AGENTS.md rules 1-2).

Design in one paragraph: the ball is a piecewise-linear path built from the
events (rest at start, flight to end over min(gap, 3 s), retrieval walk to the
next event's start during dead time, back to the centre spot after goals).
Players are acceleration-limited seekers. Their target is (a) an actor waypoint
"be at event.start by t_ms" -- actors are chosen 2-3 events ahead among the
team's on-pitch players, nearest feasible, keepers only for goal_kick and
keeper_save; (b) during dead-ball waits, set-piece slots (corner box + marking,
free-kick wall at 9 m, goal kick spread wide, kick-off own half); (c) otherwise
a 4-3-3 formation slot shifted with a smoothed ball (defensive line follows the
ball, forwards push up in possession, lateral shift toward the ball) plus small
wander noise, with one chaser per team pressing toward the next ball spot and
occasional sprints (frequency scaled by sprint_bias). Sustained high speed
builds fatigue, cutting top speed by up to 1 - endurance. Subs walk on from the
halfway touchline and off to the nearest touchline; second-yellow players
(reactor-counted on the new ids) leave the pitch at the card.
"""
from __future__ import annotations

import copy
import math
import random
from typing import Any, Dict, List, Optional, Tuple

TRACKING_VERSION = "tracking-0.1.0"

HOME = "HAR"
AWAY = "COP"
PITCH_L, PITCH_W = 105.0, 68.0

# ---- physics -----------------------------------------------------------------
DT = 0.1            # simulation step (s); every 2nd frame is written -> 5 Hz
DECIDE_EVERY = 5    # rethink targets every 0.5 s
ACCEL_MAX = 5.0     # m/s^2
DECEL_MAX = 6.5     # m/s^2 (arrive deceleration)
_ARRIVE = math.sqrt(2.0 * DECEL_MAX)
BALL_FLIGHT_CAP = 38.0  # m/s cap on event flights (the spec formula alone can
                        # reach ~46 m/s for long clearances on short gaps)
BALL_FETCH_CAP = 10.0   # m/s when the ball is retrieved to the next restart spot
BALL_OPEN_FETCH_CAP = 32.0  # m/s for open-play chains (clearance lands, next
                            # pass starts elsewhere: the fetch is a pass)
SEP_MIN = 0.65          # players closer than this are pushed apart (test limit 0.5)
BALL_REST = 0.35        # the ball rests on the spot this long before the next
                        # event: event times fall between 5 Hz frames, and the
                        # frame at or before t_ms must show the ball on the spot

# ---- behaviour (tuned on seeds 1-10; see Result) ------------------------------
JOG = 2.6           # outfield shape cruise (m/s), scaled by work_rate
GK_JOG = 1.55       # keeper shape cruise
WALK = 1.7          # set-piece / walk-on / walk-off pace
CHASE_R = 22.0      # nearest outfielders within this of the next ball spot press
CHASE_SPRINT_P = 0.013    # per decision tick, a chaser commits to a sprint (x bias)
RUN_P = 0.0045            # per tick in possession, an attacker runs in behind (x
                          # bias; a 10 s cooldown caps the busiest at ~9/90)
BURST_P = 0.0035         # per tick, a shape-following player bursts into a sprint
                        # to reach the shape spot (x bias) -- spreads sprints
                        # over all roles, not just chasers
RECOVER_S = 110.0        # after a turnover while committed forward, a defender
                        # sprints back to recover the line -- deterministic but
                        # at most once per RECOVER_S seconds per player (a
                        # probability here left low-bias defenders under the
                        # 5-sprints-per-90 floor); midfielders do it at 60%
NOISE_DF = 2.0          # centre-backs wander more than the rest (test 6 floor:
                        # pure line-following leaves them under 8.5 km/90)
SPRINT_FRAC = 0.93      # sprint cruise as a fraction of the current top speed
                        # (0.95 + separation pushes + dm rounding pushed the
                        # measured fastest past the 37 km/h test ceiling)
PRESS_CRUISE = 1.45     # chaser jog speed as a multiple of JOG*work_rate
SMOOTH = 0.22           # EMA on the ball the shape follows (per 0.5 s tick)
NOISE_R = 1.4           # shape wander amplitude (m), re-rolled every ~3 s
FATIGUE_UP = 0.0045     # fatigue gain per second spent above 60% top speed
FATIGUE_DOWN = 0.0035   # recovery per second below it

SETPIECE_WINDOW = 30.0   # dead-ball slots take over this long before a restart
LOOKAHEAD_EVENTS = 3     # actors are chosen this many events ahead ...
LOOKAHEAD_S = 16.0       # ... and at most this early (restarts: as soon as they
                         # are next, so the taker walks there during the delay)
FEASIBLE = 0.62          # reachable at <= 0.62 x v_max in the time available.
                         # 0.8x made the nearest player sprint to almost every
                         # chained open-play event (one midfielder: 46 sprints/90);
                         # preferring someone who can jog there spreads the load
                         # and the sprint count. Infeasible events still fall back.

# 4-3-3 slots in the team's attacking frame (u = distance from own goal line).
SLOT = {
    1: (5.0, 34.0),
    2: (20.0, 11.0), 3: (20.0, 26.5), 4: (20.0, 41.5), 5: (20.0, 57.0),
    6: (42.0, 15.0), 7: (42.0, 34.0), 8: (42.0, 53.0),
    9: (63.0, 17.0), 10: (63.0, 34.0), 11: (63.0, 51.0),
}

_RESTART_TYPES = ("corner", "free_kick", "goal_kick", "throw_in")


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


def _attacks_plus_x(team_id: str, period: int) -> bool:
    return (team_id == HOME) == (period == 1)


# ---- the ball: piecewise-linear path from the events ---------------------------

def _ball_pieces(events: List[Dict[str, Any]]) -> List[Tuple[float, float, float, float, float, float]]:
    """Pieces (t0, t1, x0, y0, x1, y1) covering the whole match, continuous.

    Per event: fetch to the event's start during the previous dead time (this
    also carries the ball to the centre spot after a goal), flight start->end
    over max(0.3, min(gap, 3.0)) seconds capped at BALL_FLIGHT_CAP, then rest.
    Fetches and flights both finish BALL_REST before the next event time:
    event times land between 5 Hz frames, and the last frame at or before t_ms
    must already show the ball resting on the spot. Fetches that bridge an
    open-play chain (previous gap <= 8 s) run at up to 25 m/s -- they are
    effectively passes -- while restart retrievals walk at 10 m/s. keeper_save
    events carry shooter-frame coordinates ~100 m from the shot they follow
    (generator quirk, see Result): their fetch and flight are skipped and the
    ball simply stays where the shot ended.
    """
    pieces: List[Tuple[float, float, float, float, float, float]] = []
    cur_x, cur_y = PITCH_L / 2.0, PITCH_W / 2.0
    free_at = 0.0
    prev_t0 = 0.0
    n = len(events)
    for i, ev in enumerate(events):
        t0 = ev["t_ms"] / 1000.0
        sx, sy = ev["start"]["x"], ev["start"]["y"]
        ex, ey = ev["end"]["x"], ev["end"]["y"]
        t_next = events[i + 1]["t_ms"] / 1000.0 if i + 1 < n else t0 + 6.0
        gap = max(t_next - t0, 0.0)
        # the fetch bringing the ball to THIS start runs in the dead time after
        # the previous event; in an open-play chain that gap is short, so it is
        # really a pass and may move quickly
        in_cap = BALL_OPEN_FETCH_CAP if t0 - prev_t0 <= 8.0 else BALL_FETCH_CAP
        prev_t0 = t0
        fetch_cap = BALL_FETCH_CAP if gap > 8.0 else BALL_OPEN_FETCH_CAP
        nx, ny = (events[i + 1]["start"]["x"], events[i + 1]["start"]["y"]) \
            if i + 1 < n else (ex, ey)
        fetch_d = math.hypot(nx - ex, ny - ey)
        fetch_need = max(0.3, fetch_d / fetch_cap) if fetch_d > 1e-9 else 0.0
        if ev["type"] == "keeper_save":
            free_at = max(free_at, t0)  # quirk: coordinates are at the wrong
            continue                    # end of the pitch; leave the ball be
        if cur_x != sx or cur_y != sy:  # fetch to the start, arriving early
            d = math.hypot(sx - cur_x, sy - cur_y)
            need = max(0.3, d / in_cap)
            st = max(free_at, t0 - BALL_REST - need)
            pieces.append((st, st + need, cur_x, cur_y, sx, sy))
            cur_x, cur_y = sx, sy
            free_at = st + need
        d2 = math.hypot(ex - cur_x, ey - cur_y)
        fs = max(t0, free_at)
        if d2 > 1e-9:  # the event's own flight
            dur = max(0.3, min(gap, 3.0))
            dur = min(dur, max(0.3, gap - BALL_REST))
            if fetch_need > 0.0:  # leave the fetch its share of the gap
                dur = min(dur, max(0.3, gap - fetch_need - BALL_REST))
            dur = max(dur, d2 / BALL_FLIGHT_CAP)  # never faster than the cap
            pieces.append((fs, fs + dur, cur_x, cur_y, ex, ey))
            cur_x, cur_y = ex, ey
            free_at = fs + dur
        else:
            free_at = max(free_at, t0)
    return pieces


class _BallPath:
    def __init__(self, events: List[Dict[str, Any]]) -> None:
        self.pieces = _ball_pieces(events)
        self.k = 0
        self.last = (PITCH_L / 2.0, PITCH_W / 2.0)

    def at(self, t: float) -> Tuple[float, float]:
        pieces, k = self.pieces, self.k
        while k < len(pieces) and pieces[k][1] <= t:
            self.last = (pieces[k][4], pieces[k][5])
            k += 1
        self.k = k
        if k < len(pieces):
            t0, t1, x0, y0, x1, y1 = pieces[k]
            if t0 <= t:
                f = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
                return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
        return self.last


# ---- set-piece slots (dead-ball positioning) -----------------------------------

def _setpiece(ev: Dict[str, Any], idx_of: Dict[str, int],
              on_pitch: Dict[str, List[int]], role_of: List[str]) -> Dict[int, Tuple[float, float]]:
    typ, sub = ev["type"], ev.get("subtype")
    team = ev["team_id"]
    period = ev["period"]
    plus = _attacks_plus_x(team, period)
    sx, sy = ev["start"]["x"], ev["start"]["y"]

    def A(u: float, y: float) -> Tuple[float, float]:
        return (u if plus else PITCH_L - u, y)

    def D(u: float, y: float) -> Tuple[float, float]:
        return (u if not plus else PITCH_L - u, y)

    out: Dict[int, Tuple[float, float]] = {}
    other = AWAY if team == HOME else HOME

    def assign(side: str, slots: List[Tuple[float, float]]) -> None:
        got = on_pitch[side]
        keepers = [i for i in got if role_of[i] == "GK"]
        outfield = [i for i in got if role_of[i] != "GK"]
        for i, slot in zip(keepers + outfield, slots):
            out[i] = slot

    u_s = sx if plus else PITCH_L - sx  # event spot in the attacking frame
    if typ == "corner":
        assign(team, [A(8.0, 34.0)] + [A(97, 27), A(97, 41), A(93, 21), A(93, 47),
                  A(89, 34), A(80, 27), A(80, 41), A(62, 34), A(45, 30), A(45, 38)])
        assign(other, [D(1.5, 34.0), D(2.5, 30.5), D(2.5, 37.5), D(6, 26), D(6, 34),
                       D(6, 42), D(10, 30), D(10, 38), D(45, 34), D(58, 40)])
    elif typ == "free_kick" and u_s > PITCH_L / 2:
        assign(team, [A(u_s - 2, _clamp(sy + 6, 3, 65)), A(96, 30), A(96, 38),
                      A(max(u_s - 10, 40), 28), A(max(u_s - 10, 40), 40),
                      A(max(u_s - 18, 30), 34), A(60, 24), A(60, 44), A(40, 34),
                      A(30, 34), A(12, 34)])
        wall_y = sy
        assign(other, [D(2.0, _clamp(sy + (2.0 if sy < 34 else -2.0), 26, 42)),
                       D(PITCH_L - (u_s - 9), _clamp(wall_y - 1.0, 2, 66)),
                       D(PITCH_L - (u_s - 9), _clamp(wall_y, 2, 66)),
                       D(PITCH_L - (u_s - 9), _clamp(wall_y + 1.0, 2, 66)),
                       D(PITCH_L - (u_s - 14), _clamp(sy - 6, 3, 65)),
                       D(PITCH_L - (u_s - 14), _clamp(sy + 6, 3, 65)),
                       D(PITCH_L - (u_s - 22), 34), D(60, 30), D(60, 38),
                       D(45, 34), D(25, 34)])
    elif typ == "goal_kick":
        assign(team, [A(5.5, sy), A(22, 5), A(20, 26), A(20, 42), A(22, 63),
                      A(48, 15), A(48, 34), A(48, 53), A(72, 17), A(72, 34), A(72, 51)])
        assign(other, [D(3, 34), D(50, 20), D(50, 48), D(57, 12), D(57, 56),
                       D(63, 26), D(63, 42), D(68, 34), D(45, 30), D(45, 38), D(40, 34)])
    elif typ == "pass" and sub == "kick_off":
        assign(team, [A(52.0, 36.5), A(50, 31), A(50, 37), A(40, 15), A(40, 34),
                      A(40, 53), A(25, 11), A(25, 26), A(25, 42), A(25, 57), A(5, 34)])
        assign(other, [D(20, 11), D(20, 26), D(20, 42), D(20, 57), D(28, 15),
                       D(28, 34), D(28, 53), D(36, 17), D(36, 34), D(36, 51), D(3, 34)])
    else:
        return {}
    return out


# ---- the simulation ------------------------------------------------------------

class _Sim:
    def __init__(self, match: Dict[str, Any]) -> None:
        self.match = match
        self.seed = int(match["seed"])
        self.rng = random.Random("%d-track" % self.seed)
        self.events = match["events"]
        self.periods = sorted(match["periods"], key=lambda p: p["id"])
        self.ball = _BallPath(self.events)

        players = match["players"]  # ordered HAR-1..14, COP-1..14
        self.pids = [p["player_id"] for p in players]
        self.idx_of = {pid: i for i, pid in enumerate(self.pids)}
        n = len(players)
        self.n = n
        self.role = [p["position"] for p in players]
        self.team = [p["team_id"] for p in players]
        self.shirt = [p["shirt_no"] for p in players]
        attr = [p["attributes"] for p in players]
        self.vmax = [a["v_max_kmh"] / 3.6 for a in attr]
        self.endur = [a["endurance"] for a in attr]
        self.work = [a["work_rate"] for a in attr]
        self.bias = [a["sprint_bias"] for a in attr]

        # dynamic state
        self.px = [0.0] * n
        self.py = [0.0] * n
        self.vx = [0.0] * n
        self.vy = [0.0] * n
        self.spd = [0.0] * n
        self.fat = [0.0] * n
        # formation slot per player: shirt for the XI; a substitute inherits the
        # slot of the player they replace (shirts 12-14 have no slot of their own)
        self.slot_of: List[int] = list(self.shirt)
        self.on = [False] * n
        self.actives: List[int] = []
        self.tgx = [0.0] * n
        self.tgy = [0.0] * n
        self.cruise = [JOG] * n
        self.wpt: List[List[Tuple[float, float, float, int]]] = [[] for _ in range(n)]
        self.sprint_until = [-1.0] * n
        self.recover_ok = [0.0] * n    # next time a recovery sprint is allowed
        self.chase_ok = [0.0] * n      # next time a chase sprint is allowed (a
                                       # per-tick probability alone let one
                                       # midfielder press-sprint ~46x per 90)
        self.run_ok = [0.0] * n        # next time a run in behind is allowed
        self.noise_t = [0.0] * n
        self.nx = [0.0] * n
        self.ny = [0.0] * n
        self.walkoff_at = [float("inf")] * n   # time the outgoing player is -1
        self.walkoff_tgt: List[Optional[Tuple[float, float]]] = [None] * n

        # event bookkeeping
        ne = len(self.events)
        self.assigned: List[Optional[int]] = [None] * ne  # player idx, -1 = no actor
        self.actor_pid: List[Optional[str]] = [None] * ne
        self.card_fix: Dict[int, Tuple[str, str]] = {}    # card idx -> (pid, subtype)
        self.yellows: Dict[str, int] = {}
        self.pending_off: List[Tuple[float, int]] = []    # (t, player idx)
        self.sub_end_ms: Dict[int, int] = {}              # sub t_ms -> stoppage end
        for s in match["stoppages"]:
            if s["type"] == "sub":
                for eid in s["related_event_ids"]:
                    ev = next(e for e in self.events if e["event_id"] == eid)
                    self.sub_end_ms[ev["t_ms"]] = s["t_end_ms"]
        self.ep = 0                 # next unprocessed event
        self.poss_team = self.events[0]["team_id"]
        self.setpiece_ev = -1       # event idx whose slots are active
        self.setpiece_map: Dict[int, Tuple[float, float]] = {}
        self.setpiece_cache: Dict[int, Dict[int, Tuple[float, float]]] = {}
        self.sbx, self.sby = PITCH_L / 2.0, PITCH_W / 2.0  # smoothed ball

        # output frames (5 Hz): per entity, dm ints
        self.entities = ["ball"] + self.pids
        self.ox: Dict[str, List[int]] = {e: [] for e in self.entities}
        self.oy: Dict[str, List[int]] = {e: [] for e in self.entities}
        self.frames_per_period: List[int] = []
        self.actors_changed = 0
        self.infeasible_events = 0

    # -- helpers ----------------------------------------------------------------

    def _set_active(self, i: int, flag: bool) -> None:
        if flag and not self.on[i]:
            self.on[i] = True
            self.actives.append(i)
        elif not flag and self.on[i]:
            self.on[i] = False
            self.actives.remove(i)

    def _on_pitch_now(self, team: str) -> List[int]:
        return [i for i in self.actives if self.team[i] == team]

    def _keeper_idx(self, team: str) -> int:
        for i in self.actives:
            if self.team[i] == team and self.role[i] == "GK":
                return i
        for i in range(self.n):
            if self.team[i] == team and self.shirt[i] == 1:
                return i
        return -1

    # -- event handling ----------------------------------------------------------

    def _process_event(self, j: int, t: float) -> None:
        ev = self.events[j]
        self.poss_team = ev["team_id"]
        actor = self.assigned[j]
        if actor is not None and actor >= 0:
            self.wpt[actor] = [w for w in self.wpt[actor] if w[3] != j]
        if ev["type"] == "foul" and j + 1 < len(self.events) \
                and self.events[j + 1]["type"] == "card":
            card = self.events[j + 1]
            fouler = self.pids[actor] if actor is not None and actor >= 0 \
                else card["player_id"]
            count = self.yellows.get(fouler, 0) + 1
            self.yellows[fouler] = count
            subtype = "yellow" if count == 1 else "second_yellow"
            self.card_fix[j + 1] = (fouler, subtype)
            if subtype == "second_yellow":
                self.pending_off.append((card["t_ms"] / 1000.0, self.idx_of[fouler]))
        elif ev["type"] == "substitution":
            inc = self.idx_of[ev["player_id"]]
            out = self.idx_of[ev["player_out_id"]]
            end_s = self.sub_end_ms.get(ev["t_ms"], ev["t_ms"] + 25000) / 1000.0
            self.slot_of[inc] = self.slot_of[out]
            self._set_active(inc, True)
            self.px[inc], self.py[inc] = PITCH_L / 2.0, 0.0
            self.vx[inc] = self.vy[inc] = 0.0
            self.wpt[inc] = []
            self.sprint_until[inc] = -1.0
            if self.on[out]:  # walk off to the nearest touchline
                self.walkoff_at[out] = end_s
                oy = 0.0 if self.py[out] < PITCH_W / 2.0 else PITCH_W
                self.walkoff_tgt[out] = (self.px[out], oy)
                self.wpt[out] = []

    def _free_at(self, i: int, t: float) -> Tuple[float, float, float]:
        """Where/when the player is free: after their last pending waypoint."""
        w = self.wpt[i]
        if w:
            last = max(w)
            return (last[0], last[1], last[2])
        return (t, self.px[i], self.py[i])

    def _choose_actor(self, j: int, t: float) -> None:
        """Assign the actor for event j (2-3 events ahead; restarts earlier)."""
        ev = self.events[j]
        if ev["type"] in ("substitution", "card"):
            self.assigned[j] = -1
            return
        te = ev["t_ms"] / 1000.0
        sx, sy = ev["start"]["x"], ev["start"]["y"]
        team = ev["team_id"]
        if ev["type"] in ("goal_kick", "keeper_save"):
            best = self._keeper_idx(team)
            if best < 0:
                self.assigned[j] = -1
                return
            ft, fx, fy = self._free_at(best, t)  # position/time after pending work
            feasible = math.hypot(sx - fx, sy - fy) <= FEASIBLE * self.vmax[best] * max(te - ft, 0.0) \
                and ft < te
            self.assigned[j] = best
            if feasible:
                self.wpt[best].append((te, sx, sy, j))
            else:
                self.infeasible_events += 1  # keeper_save quirk: stay home
            return
        cands = [i for i in self._on_pitch_now(team) if self.role[i] != "GK"]
        if not cands:
            self.assigned[j] = -1
            return
        # feasibility from where the player is free (after pending waypoints);
        # among feasible players prefer the nearest, fresh legs breaking ties
        best, best_d, best_busy, feasible = -1, 1e9, 1, False
        for i in cands:
            ft, fx, fy = self._free_at(i, t)
            if ft >= te:
                continue
            d = math.hypot(sx - fx, sy - fy)
            busy = 1 if self.wpt[i] else 0
            if d <= FEASIBLE * self.vmax[i] * (te - ft):
                key = (d + 22.0 * busy, busy)  # ~22 m penalty for a detour
                if not feasible or key[0] < best_d:
                    best, best_d, best_busy, feasible = i, key[0], busy, True
        if not feasible:
            # nobody is comfortably reachable: name whoever would be least late
            # (measured from where they are free, not where they stand now)
            for i in cands:
                ft, fx, fy = self._free_at(i, t)
                late = math.hypot(sx - fx, sy - fy) / self.vmax[i] - max(te - ft, 0.0)
                if late < best_d:
                    best, best_d = i, late
            self.infeasible_events += 1
            # way out of reach (keeper_save quirk): name the nearest, no waypoint
            if best_d > 1.5:
                self.assigned[j] = best
                return
        self.assigned[j] = best
        self.wpt[best].append((te, sx, sy, j))

    # -- decision tick (every 0.5 s) ----------------------------------------------

    def _decide(self, t: float) -> None:
        rng = self.rng
        events = self.events
        # pending send-offs
        if self.pending_off:
            due = [p for p in self.pending_off if p[0] <= t]
            if due:
                self.pending_off = [p for p in self.pending_off if p[0] > t]
                for _, i in due:
                    self._set_active(i, False)
        # actor look-ahead
        for k in range(LOOKAHEAD_EVENTS):
            j = self.ep + k
            if j >= len(events):
                break
            if self.assigned[j] is not None:
                continue
            te = events[j]["t_ms"] / 1000.0
            window = LOOKAHEAD_S
            if events[j]["type"] in _RESTART_TYPES:
                window = 120.0  # restarts: the taker walks there during the delay
            if te - t <= window:
                self._choose_actor(j, t)
        # set-piece window?
        self.setpiece_map = {}
        self.setpiece_ev = -1
        if self.ep < len(events):
            ev = events[self.ep]
            te = ev["t_ms"] / 1000.0
            if ev["type"] in _RESTART_TYPES or (ev["type"] == "pass"
                                                and ev.get("subtype") == "kick_off"):
                if 0.0 <= te - t <= SETPIECE_WINDOW:
                    self.setpiece_ev = self.ep
                    self.setpiece_map = self.setpiece_cache.get(self.ep)
                    if self.setpiece_map is None:
                        on_pitch = {tm: sorted(self._on_pitch_now(tm)) for tm in (HOME, AWAY)}
                        self.setpiece_map = _setpiece(ev, self.idx_of, on_pitch, self.role)
                        self.setpiece_cache[self.ep] = self.setpiece_map
        # smoothed ball for the shape
        bx, by = self.ball.at(t)
        self.sbx += (bx - self.sbx) * SMOOTH
        self.sby += (by - self.sby) * SMOOTH
        next_ev = events[self.ep] if self.ep < len(events) else None
        spot = (next_ev["start"]["x"], next_ev["start"]["y"]) if next_ev else (bx, by)
        next_team = next_ev["team_id"] if next_ev else self.poss_team
        # a turnover is coming: the team in possession is about to lose the ball
        turned = next_ev is not None and next_team != self.poss_team

        # chasers: the two nearest waypoint-free outfielders of each team to the
        # next ball spot (within CHASE_R) press toward it; the second man aims
        # goal-side of the spot so the two never converge on one point
        chasers: Dict[int, Tuple[Tuple[float, float], float]] = {}
        if not self.setpiece_map:
            period = self._period(t)
            for tm in (HOME, AWAY):
                ranked = []
                for k in self.actives:
                    if self.team[k] != tm or self.role[k] == "GK" or self.wpt[k]:
                        continue
                    d = math.hypot(spot[0] - self.px[k], spot[1] - self.py[k])
                    if d <= CHASE_R:
                        ranked.append((d, k))
                ranked.sort()
                goal_x = 0.0 if _attacks_plus_x(tm, period) else PITCH_L
                for rank, (d, k) in enumerate(ranked[:2]):
                    if rank == 0:
                        chasers[k] = (spot, 1.0)
                    else:
                        ux = spot[0] + (2.2 if spot[0] < goal_x else -2.2)
                        chasers[k] = ((ux, spot[1]), 0.6)  # presses less often

        # per-player targets
        for i in list(self.actives):
            w = self.wpt[i]
            if w:
                w = [x for x in w if x[0] > t + 0.05]
                self.wpt[i] = w
            if self.walkoff_tgt[i] is not None:
                self.tgx[i], self.tgy[i] = self.walkoff_tgt[i]  # type: ignore[assignment]
                self.cruise[i] = WALK
                continue
            if w:
                continue  # waypoint cruise is recomputed every step
            if self.setpiece_map and i in self.setpiece_map:
                self.tgx[i], self.tgy[i] = self.setpiece_map[i]
                d = math.hypot(self.tgx[i] - self.px[i], self.tgy[i] - self.py[i])
                self.cruise[i] = WALK if d < 18.0 else JOG * self.work[i]
                continue
            base = GK_JOG if self.role[i] == "GK" else JOG * self.work[i]
            top = SPRINT_FRAC * self.vmax[i] * (1.0 - self.fat[i])  # sprint cruise
            if i in chasers:
                tx, ty = chasers[i][0]
                # stand off 1.2 m short of the spot: the actor stands on it,
                # and converging on the exact point is a permanent shoving match
                cdx, cdy = self.px[i] - tx, self.py[i] - ty
                cdd = math.hypot(cdx, cdy)
                if cdd > 2.5:
                    tx += cdx / cdd * 1.2
                    ty += cdy / cdd * 1.2
                self.tgx[i], self.tgy[i] = tx, ty
                if t >= self.sprint_until[i] and t >= self.chase_ok[i] and \
                        rng.random() < CHASE_SPRINT_P * chasers[i][1] * self.bias[i]:
                    self.sprint_until[i] = t + 2.0
                    self.chase_ok[i] = t + 18.0
                self.cruise[i] = top if t < self.sprint_until[i] \
                    else PRESS_CRUISE * base
            else:
                u, y = self._shape_target(i, next_team)
                # wander noise, re-rolled every ~3 s (centre-backs wander more)
                if t > self.noise_t[i]:
                    self.noise_t[i] = t + 2.0 + rng.random() * 2.0
                    ang = rng.random() * 6.2831853
                    r = (NOISE_DF if self.role[i] == "DF" else NOISE_R) * rng.random()
                    self.nx[i] = math.cos(ang) * r
                    self.ny[i] = math.sin(ang) * r
                self.tgx[i], self.tgy[i] = u + self.nx[i], y + self.ny[i]
                # a burst/recovery commitment from an earlier tick keeps its
                # sprint cruise until it expires (like the chaser branch)
                self.cruise[i] = top if t < self.sprint_until[i] else base
                # defender stretched far behind the moving line: catch it up at
                # rising speed (deterministic -- the DF sprint floor cannot rely
                # on bias-scaled probabilities)
                if self.role[i] == "DF":
                    dd_ = math.hypot(self.tgx[i] - self.px[i], self.tgy[i] - self.py[i])
                    if dd_ > 14.0 and self.cruise[i] < top:
                        self.cruise[i] = _clamp(base + 0.45 * (dd_ - 14.0), base, top)
                # occasional burst: sprint to keep the shape instead of jogging
                if self.role[i] != "GK" and t >= self.sprint_until[i] \
                        and math.hypot(u - self.px[i], y - self.py[i]) > 8.0 \
                        and rng.random() < BURST_P * (0.5 + 0.5 * self.bias[i]):
                    self.sprint_until[i] = t + 2.0
                # recovery run: the team is about to lose the ball with men
                # forward -- defenders sprint back toward a low block line
                # (deterministic, at most once per RECOVER_S seconds)
                if self.role[i] in ("DF", "MF") and turned \
                        and self.team[i] == self.poss_team \
                        and self._ball_u(self.team[i]) > 50.0 \
                        and t >= self.sprint_until[i] \
                        and t >= self.recover_ok[i] \
                        and (self.role[i] == "DF"
                             or rng.random() < 0.6 * self.bias[i]):
                    self.recover_ok[i] = t + RECOVER_S
                    self.sprint_until[i] = t + 2.2
                    su_, sy_ = SLOT[self.slot_of[i]]
                    ru = 14.0 if self.role[i] == "DF" else 30.0
                    u2 = _clamp(ru + 0.5 * (su_ - (20.0 if self.role[i] == "DF" else 42.0)),
                                6.0, 45.0)
                    y2 = _clamp(sy_ + 0.45 * (self.sby - sy_), 3.0, 65.0)
                    plus = _attacks_plus_x(self.team[i], self._period(t))
                    self.tgx[i] = u2 if plus else PITCH_L - u2
                    self.tgy[i] = y2
                    self.cruise[i] = top
            # runs in behind while in possession
            if i not in chasers and self.role[i] in ("FW", "MF") and not self.setpiece_map:
                if self.team[i] == next_team and self._ball_u(next_team) > 50.0 \
                        and t >= self.sprint_until[i] and t >= self.run_ok[i] and \
                        rng.random() < RUN_P * self.bias[i]:
                    self.sprint_until[i] = t + 2.2
                    self.run_ok[i] = t + 16.0
                    plus = _attacks_plus_x(self.team[i], self._period(t))
                    u = self._ball_u(self.team[i]) + 22.0
                    yy = _clamp(self.sby + (12.0 if rng.random() < 0.5 else -12.0), 3, 65)
                    self.tgx[i] = u if plus else PITCH_L - u
                    self.tgy[i] = yy
                    self.cruise[i] = top

    def _period(self, t: float) -> int:
        return 1 if t < self.periods[1]["start_ms"] / 1000.0 else 2

    def _ball_u(self, team: str) -> float:
        plus = _attacks_plus_x(team, self._period(self.t_now))
        return self.sbx if plus else PITCH_L - self.sbx

    def _shape_target(self, i: int, next_team: str) -> Tuple[float, float]:
        team = self.team[i]
        period = self._period(self.t_now)
        plus = _attacks_plus_x(team, period)
        bu = self.sbx if plus else PITCH_L - self.sbx
        by = self.sby
        role = self.role[i]
        su, sy = SLOT[self.slot_of[i]]
        possession = team == next_team
        if role == "GK":
            u = _clamp(4.0 + 0.12 * bu, 3.0, 16.0)
            y = _clamp(34.0 + 0.32 * (by - 34.0), 24.0, 44.0)
        elif role == "DF":
            line = _clamp(9.0 + 0.42 * bu, 8.0, 40.0)
            u = _clamp(line + 0.5 * (su - 20.0), 6.0, 52.0)
            y = _clamp(sy + 0.5 * (by - sy), 3.0, 65.0)
        elif role == "MF":
            u = _clamp(bu - 3.0 + 0.4 * (su - 42.0), 18.0, 75.0)
            y = _clamp(sy + 0.45 * (by - sy), 3.0, 65.0)
        else:  # FW
            push = 12.0 if possession else -6.0
            u = _clamp(bu + push + 0.5 * (su - 63.0), 35.0, 92.0)
            y = _clamp(sy + 0.42 * (by - sy), 3.0, 65.0)
        return (u if plus else PITCH_L - u, y)

    # -- main loop -----------------------------------------------------------------

    def run(self) -> None:
        # kick-off positions: both teams in their own half, first event's frame;
        # the kicking team's central midfielder stands on the first event's spot
        first = self.events[0]
        for i in range(self.n):
            if self.shirt[i] <= 11:
                self._set_active(i, True)
                if self.team[i] == first["team_id"] and self.shirt[i] == 7:
                    self.px[i], self.py[i] = first["start"]["x"], first["start"]["y"]
                    continue
                u, y = SLOT[self.shirt[i]]
                plus = _attacks_plus_x(self.team[i], 1)
                u = min(u, 48.0)  # own half at kick-off
                self.px[i] = u if plus else PITCH_L - u
                self.py[i] = y
        self.t_now = 0.0

        for period in self.periods:
            start_ms, end_ms = period["start_ms"], period["end_ms"]
            n10 = (end_ms - start_ms) // 100 + 1
            self.frames_per_period.append((n10 + 1) // 2)
            for step in range(n10):
                t = start_ms / 1000.0 + step * DT
                self.t_now = t
                # decide first: the actor for an event at this instant must have
                # been chosen (and have stood on the spot) before it happens
                if step % DECIDE_EVERY == 0:
                    self._decide(t)
                while self.ep < len(self.events) and \
                        self.events[self.ep]["t_ms"] / 1000.0 <= t + 1e-9:
                    self._process_event(self.ep, t)
                    self.ep += 1
                self._move(t)
                if step % 2 == 0:
                    self._record(t)
        # anything left pending (last event exactly at the whistle)
        while self.ep < len(self.events):
            self._process_event(self.ep, self.periods[-1]["end_ms"] / 1000.0)
            self.ep += 1

    def _move(self, t: float) -> None:
        px, py, vx, vy = self.px, self.py, self.vx, self.vy
        dt = DT
        for i in self.actives:
            vmax = self.vmax[i]
            eff = vmax * (1.0 - self.fat[i])
            tx, ty = self.tgx[i], self.tgy[i]
            cruise = self.cruise[i]
            w = self.wpt[i]
            if w:
                w0 = min(w)
                remain = w0[0] - t
                d = math.hypot(w0[1] - px[i], w0[2] - py[i])
                need = d / max(remain, 0.15) * 1.35
                cruise = _clamp(max(need, 1.0), 1.2, SPRINT_FRAC * eff)
                tx, ty = w0[1], w0[2]
            dx = tx - px[i]
            dy = ty - py[i]
            d = math.sqrt(dx * dx + dy * dy)
            if d > 0.03:
                sp = cruise if cruise < _ARRIVE * math.sqrt(d) else _ARRIVE * math.sqrt(d)
                inv = sp / d
                dvx = dx * inv - vx[i]
                dvy = dy * inv - vy[i]
            else:
                dvx, dvy = -vx[i], -vy[i]
            a = math.sqrt(dvx * dvx + dvy * dvy)
            lim = 6.0 * dt  # between ACCEL_MAX and DECEL_MAX
            if a > lim and a > 1e-12:
                f = lim / a
                dvx *= f
                dvy *= f
            nvx = vx[i] + dvx
            nvy = vy[i] + dvy
            s2 = nvx * nvx + nvy * nvy
            if s2 > eff * eff and s2 > 1e-12:
                f = eff / math.sqrt(s2)
                nvx *= f
                nvy *= f
            vx[i] = nvx
            vy[i] = nvy
            nx = px[i] + nvx * dt
            ny = py[i] + nvy * dt
            px[i] = 0.0 if nx < 0.0 else (PITCH_L if nx > PITCH_L else nx)
            py[i] = 0.0 if ny < 0.0 else (PITCH_W if ny > PITCH_W else ny)
            # stamina
            spd = math.sqrt(nvx * nvx + nvy * nvy)
            self.spd[i] = spd
            if spd > 0.6 * vmax:
                self.fat[i] += dt * FATIGUE_UP * (spd - 0.6 * vmax) / (0.4 * vmax)
            else:
                self.fat[i] -= dt * FATIGUE_DOWN
            cap = 1.0 - self.endur[i]
            self.fat[i] = 0.0 if self.fat[i] < 0.0 else (cap if self.fat[i] > cap else self.fat[i])
            # walk-off done?
            if self.walkoff_tgt[i] is not None and (
                    abs(px[i] - self.walkoff_tgt[i][0]) < 0.6
                    and abs(py[i] - self.walkoff_tgt[i][1]) < 0.6):
                self.walkoff_at[i] = min(self.walkoff_at[i], t)
        # send-offs scheduled for exactly now
        # (handled on the next decision tick; also check here for exact frames)
        if self.pending_off:
            for tt, i in list(self.pending_off):
                if tt <= t:
                    self._set_active(i, False)
                    self.pending_off.remove((tt, i))
                    self.walkoff_tgt[i] = None
        # outgoing players whose stoppage window has closed
        for i in list(self.actives):
            if self.walkoff_tgt[i] is not None and t >= self.walkoff_at[i]:
                self._set_active(i, False)
                self.walkoff_tgt[i] = None
        # separation
        self._separate()

    def _separate(self) -> None:
        px, py = self.px, self.py
        cell = 1.25
        grid: Dict[Tuple[int, int], List[int]] = {}
        for i in self.actives:
            key = (int(px[i] / cell), int(py[i] / cell))
            if key in grid:
                grid[key].append(i)
            else:
                grid[key] = [i]
        # accumulate the pushes, then clamp each player's total displacement:
        # a stack of pushes applied raw can spike the measured 5 Hz speed past
        # the test ceiling, while a weak per-pair push lets overlaps linger
        dxs = [0.0] * self.n
        dys = [0.0] * self.n
        for (cx, cy), members in grid.items():
            neigh = []
            for dxx, dyy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
                neigh.extend(grid.get((cx + dxx, cy + dyy), ()))
            for a in range(len(members)):
                i = members[a]
                for b in range(a + 1, len(members)):
                    self._push(i, members[b], dxs, dys)
                for j in neigh:
                    self._push(i, j, dxs, dys)
        for i in self.actives:
            m = math.hypot(dxs[i], dys[i])
            # a marking pair can close faster than a weak push resolves (presser
            # 3.8 m/s vs jogger 2.6), so overlaps need real displacement fast --
            # but never past the player's own top speed (push + sprint used to
            # measure 37+ km/h): the push fits in the remaining headroom
            head = self.vmax[i] * (1.0 - self.fat[i]) - self.spd[i]
            cap = min(0.4, max(head, 0.0) * DT)
            if m > cap and m > 1e-12:
                f = cap / m
                dxs[i] *= f
                dys[i] *= f
            px[i] += dxs[i]
            py[i] += dys[i]

    def _push(self, i: int, j: int, dxs: List[float], dys: List[float]) -> None:
        dx = self.px[j] - self.px[i]
        dy = self.py[j] - self.py[i]
        d = math.sqrt(dx * dx + dy * dy)
        if d >= SEP_MIN or d < 1e-9:
            if d < 1e-9:  # exactly stacked: nudge apart deterministically
                dxs[i] -= 0.3
                dxs[j] += 0.3
            return
        f = (SEP_MIN - d) * 0.5
        ux, uy = dx / d, dy / d
        dxs[i] -= ux * f
        dys[i] -= uy * f
        dxs[j] += ux * f
        dys[j] += uy * f

    def _record(self, t: float) -> None:
        bx, by = self.ball.at(t)
        self.ox["ball"].append(_to_dm(bx, 1050))
        self.oy["ball"].append(_to_dm(by, 680))
        for i in range(self.n):
            pid = self.pids[i]
            if self.on[i]:
                self.ox[pid].append(_to_dm(self.px[i], 1050))
                self.oy[pid].append(_to_dm(self.py[i], 680))
            else:
                self.ox[pid].append(-1)
                self.oy[pid].append(-1)

    # -- outputs --------------------------------------------------------------------

    def tracked_match(self) -> Dict[str, Any]:
        tracked = copy.deepcopy(self.match)
        changed = 0
        for j, ev in enumerate(tracked["events"]):
            if j in self.card_fix:
                pid, subtype = self.card_fix[j]
                if pid != ev["player_id"]:
                    changed += 1
                ev["player_id"] = pid
                ev["subtype"] = subtype
                continue
            a = self.assigned[j]
            if a is not None and a >= 0 and ev["type"] != "substitution":
                pid = self.pids[a]
                if pid != ev["player_id"]:
                    changed += 1
                ev["player_id"] = pid
        self.actors_changed = changed
        tracked["tracking"] = {
            "tracking_version": TRACKING_VERSION,
            "file": "tracking-seed-%d.json" % self.seed,
            "actors_changed": changed,
        }
        return tracked

    def tracking_file(self) -> Dict[str, Any]:
        periods = [{"id": p["id"], "start_ms": p["start_ms"], "frames": f}
                   for p, f in zip(self.periods, self.frames_per_period)]
        return {
            "match_id": self.match["match_id"],
            "seed": self.seed,
            "tracking_version": TRACKING_VERSION,
            "hz": 5,
            "unit": "dm",
            "periods": periods,
            "entities": self.entities,
            "x": {e: self.ox[e] for e in self.entities},
            "y": {e: self.oy[e] for e in self.entities},
        }


def _to_dm(v: float, hi: int) -> int:
    d = int(math.floor(v * 10.0 + 0.5))  # round half up
    return 0 if d < 0 else (hi if d > hi else d)


def track_match(match: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Simulate one generated match. Pure: same match dict -> same outputs."""
    sim = _Sim(match)
    sim.run()
    return sim.tracked_match(), sim.tracking_file()

"""Tracking synthesizer (task 04, spec docs/TRACKING_SPEC.md).

track_match(match) simulates the 22 players and the ball at 10 Hz, consistent
with the match's own events, and returns (tracked_match, tracking):

- tracked_match: the same events with the acting player renamed to the nearest
  feasible teammate (only player_id changes; card player_id/subtype recomputed
  from the new ids), plus a top-level "tracking" pointer.
- tracking: the 5 Hz output file dict (decimetres, -1 = off pitch).

Deterministic from the seed: the only randomness is random.Random("%d-track"),
drawn in a fixed order. No AI, no I/O (AGENTS.md rules 1-2).

Design in one paragraph: the ball is a small state machine stepped with the
simulation (task 06) -- at a player's feet while they wait to kick, in a
bimodal-speed flight after the kick (either a firm >= 12.6 m/s ball or a soft
<= 3.9 m/s one, never in the 4-12 m/s band the realism tests look at), rolling
toward the late receiver of an unmet pass, hidden (-1) from the moment it leaves
the pitch until the restart taker reaches the spot, and carried along the
dribble path. Every kick launches from the kicker's feet with a short ramp, so
an acceleration always has a toucher. A "virtual" ball position (eased toward
the restart spot while the real one is hidden) drives the team shape. Players
are acceleration-limited seekers. Their target is (a) an actor waypoint "be at
event.start by t_ms" -- actors are chosen 2-3 events ahead among the team's
on-pitch players, nearest feasible, keepers only for goal_kick and
keeper_save; (b) during dead-ball waits, set-piece slots (corner box + marking,
free-kick wall at 9 m, goal kick spread wide, kick-off own half); (c) otherwise
a 4-3-3 formation slot shifted with the smoothed ball (defensive line follows
the ball, forwards push up in possession, lateral shift toward the ball) plus
small wander noise, with one chaser per team pressing toward the next ball spot
and occasional sprints (frequency scaled by sprint_bias). Sustained high speed
builds fatigue, cutting top speed by up to 1 - endurance. Subs walk on from the
halfway touchline and off to the nearest touchline; second-yellow players
(reactor-counted on the new ids) leave the pitch at the card.
"""
from __future__ import annotations

import copy
import math
import random
from typing import Any, Dict, List, Optional, Tuple

TRACKING_VERSION = "tracking-0.2.0"

HOME = "HAR"
AWAY = "COP"
PITCH_L, PITCH_W = 105.0, 68.0

# ---- physics -----------------------------------------------------------------
DT = 0.1            # simulation step (s); every 2nd frame is written -> 5 Hz
DECIDE_EVERY = 5    # rethink targets every 0.5 s
ACCEL_MAX = 5.0     # m/s^2
DECEL_MAX = 6.5     # m/s^2 (arrive deceleration)
_ARRIVE = math.sqrt(2.0 * DECEL_MAX)
SEP_MIN = 0.8           # players closer than this are pushed apart (task 08
                        # rule 15: no < 0.5 m pairs for 3 s; test limit 0.5)

# ---- ball (task 06) ------------------------------------------------------------
FLIGHT_CAP = 38.0   # m/s cap on any ball flight
LATE_KICK_S = 1.8   # grace: a taker who misses the normal deadline by this
                    # much still takes the kick (a touch late -- the receiver
                    # is waiting at the landing spot anyway); the next event's
                    # launch re-queues behind the pending delivery
FLIGHT_V_HI = 12.6  # firm passes/clearances: always at least this fast, so the
                    # mid-band (4-12 m/s) is reserved for rolls and ramps
FLIGHT_V_LO = 3.4   # soft passes / rolls: at most this fast -- a slow ball near
                    # players, and safely under the 4 m/s band edge even with
                    # the +-0.5 m/s of dm quantisation in the recorded frames
KICK_A = 1000.0     # m/s^2 launch ramp: any flight reaches cruise speed within
                    # the first 5 Hz frame, so exactly one frame shows the
                    # acceleration -- and the frame before it still has the
                    # kicker on the ball (kick rule: toucher within 1.2 m:
                    # the ramp end sits v^2/2K <= 0.72 m ahead of the boot)
ROLL_DECEL = 3.0    # m/s^2 the ball slows once it rolls (task 06: ~3)
ROLL_ACC = 6.0      # m/s^2 a late kick accelerates the rolling ball by (1.2 m/s
                    # per 5 Hz frame incl. mode-switch lag -- never near the
                    # 4 m/s that would demand a toucher nobody has reached)
ROLL_FLOOR = 1.0    # m/s it keeps creeping toward an unmet receiver, so a late
                    # receiver never leaves a dead ball with nobody near it
OUT_MIN_S = 0.6     # the ball stays hidden at least this long (test wants a
                    # visible -1 window before every restart)
APPEAR_R = 1.5      # taker within this of the restart spot -> ball appears
ATTACH_R = 1.2      # player within this of the ball -> it sticks to their feet
LEAD_M = 0.35       # the kick leaves the boot this far ahead of the kicker
DEFER_R = 10.0      # a kick whose taker is within this of the ball waits for
                    # them instead of sending the ball off alone (it is played
                    # the moment they reach it -- always with a toucher)

# ---- behaviour (tuned on seeds 1-10; see Result) ------------------------------
JOG = 2.6           # set-piece long-walk cruise (m/s), scaled by work_rate
GK_JOG = 1.55       # keeper shape cruise
WALK = 1.7          # set-piece / walk-on / walk-off pace
# task 06 speed profile: walk more far from the ball, purposeful runs, bursts.
# Distances are to the shape spot; speeds are the cruise toward it.
SHAPE_WALK = 1.55   # m/s when the spot is at your feet (< SHAPE_WALK_R away)
SHAPE_WALK_R = 7.5
SHAPE_JOG = 2.7     # m/s when it is nearby (< SHAPE_JOG_R away), x work_rate
SHAPE_JOG_R = 9.0
SHAPE_RUN = 4.9     # m/s when the play is coming your way, x work_rate
                    # (the run tier covers everyone far from their shape spot,
                    # so its speed is the distance dial: 5.0 broke the km/90
                    # ceiling, 4.75 the floor)
PRESS_RUN = 4.9     # chaser press cruise (was 1.45 x jog: pure jogging)
CHASE_R = 22.0      # nearest outfielders within this of the next ball spot press
CHASE_SPRINT_P = 0.013    # per decision tick, a chaser commits to a sprint (x bias)
RECOVER_TOP = 7.5   # m/s cap on deterministic hard runs (catch-ups, recovery
                    # runs -- 27 km/h): fast enough to count as real sprint
                    # work, short of the flat-out chaser/burst sprints, so the
                    # km/90 and sprint-per-90 budgets both hold
FETCH_TOP = 6.9     # m/s cap on a ball fetch: a hard run (24.8 km/h), not a
                    # sprint -- fetching a restart never needs flat-out speed
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
SPRINT_MAX = 24          # hard cap on a player's committed sprints per match:
                          # the published ceiling is 35/90 and the busiest
                          # chaser drew ~38 -- the counter caps the stochastic
                          # commitments, leaving headroom for the
                          # deterministic recovery runs
NOISE_DF = 2.0          # centre-backs wander more than the rest (test 6 floor:
                        # pure line-following leaves them under 8.5 km/90)
SPRINT_FRAC = 0.97      # sprint cruise as a fraction of the current top speed
FAT_SPRINT_FLOOR = 0.90 # ... but fatigue never costs a sprint more than a
                        # tenth of top speed: without this floor the slowest
                        # tired player (31 km/h top, endurance 0.85) sprints at
                        # 6.81 m/s, under the 25 km/h line the recorder counts
                        # sprint episodes at, and no schedule can fix it
SPRINT_TOP_MS = 9.5     # absolute sprint cruise cap (m/s): positions are
                        # recorded on the integer-dm grid, and the two
                        # endpoints of a step can each round half a dm the
                        # same way, so a measured 0.2 s step runs up to
                        # ~2.5 km/h hot -- a 37 km/h player sprinting flat
                        # out records 37+. This cap holds the measured
                        # fastest at ~36.5, inside the published 34-37 window
                        # (the cap itself is 34.2 km/h, safely above its
                        # floor even before rounding helps)
SMOOTH = 0.22           # EMA on the ball the shape follows (per 0.5 s tick)
NOISE_R = 1.4           # shape wander amplitude (m), re-rolled every ~3 s
FATIGUE_UP = 0.0045     # fatigue gain per second spent above 60% top speed
FATIGUE_DOWN = 0.0035   # recovery per second below it

SETPIECE_WINDOW = 30.0   # dead-ball slots take over this long before a restart
LOOKAHEAD_EVENTS = 6     # actors are chosen this many events ahead ...
LOOKAHEAD_S = 16.0       # ... and at most this early (restarts: as soon as they
                         # are next, so the taker walks there during the delay)
NET_REST_S = 2.8    # task 08: a goal ball rests in the net at least this long
                    # before it is retrieved (rule 5: stays >= 2 s)
IDLE_AFTER_S = 2.6   # task 08: a player on one recorded spot this long starts
                    # shifting weight / taking a step (rule 14: no statues)
GOAL_AREA_DEPTH = 5.5  # task 08 rule 11: goal kicks are taken from the goal area
GOAL_AREA_Y = (25.5, 42.5)
SEND_OUT_TOP = 11.0  # m/s cap on a ball rolling itself off the pitch (rule 10)
JOIN_TOP = 15.0  # task 10: cap on a loose ball rolling itself to the next
                 # event when it is behind the clock the generator set. A
                 # ball already rolling may ease up to this: from the 11 m/s
                 # self-roll cap that is exactly 4 m/s (the kick rule's
                 # threshold, not over it), and above 12 m/s it is out of the
                 # moving-alone band. It eases up through ROLL_ACC/bv_tgt so
                 # no single frame ever jumps.
KO_GUARD_S = 60.0    # task 08 rules 3/13: this long before a kick-off, no event
                     # after it may be assigned or walked to -- the formation holds

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


# ---- the ball: an in-simulation state machine (task 06) -------------------------

_BALL_KICKS = ("pass", "cross", "shot", "clearance", "throw_in", "goal_kick",
               "free_kick", "corner", "dribble")

_OUT_RESTARTS = ("corner", "throw_in", "goal_kick")


def _is_out_restart(ev: Dict[str, Any]) -> bool:
    """Does this event restart play after the ball left the pitch?"""
    return ev["type"] in _OUT_RESTARTS or \
        (ev["type"] == "pass" and ev.get("subtype") == "kick_off")


def _flight_height(ev: Dict[str, Any], d: float) -> Tuple[str, float]:
    """(style, h) for a kick of length d. 'arc' = parabola peaking at h m,
    'rise' = climbs to h at the far end (shots), 'flat' = rolling."""
    typ, sub = ev["type"], ev.get("subtype")
    if typ == "shot" or (typ == "free_kick" and sub == "shoot"):
        gy = ev["end"]["y"]  # 30-38: deterministic height from the target
        if ev.get("outcome") == "off_target":
            return ("rise", _clamp(2.7 + 0.15 * (gy - 30.0), 2.7, 4.0))
        return ("rise", _clamp(0.9 + 0.15 * (gy - 30.0), 0.9, 2.1))
    if typ == "cross" or (typ in ("corner", "free_kick") and sub == "crossed"):
        return ("arc", _clamp(3.0 + 0.12 * (d - 25.0), 3.6, 12.0))
    if typ in ("goal_kick", "clearance"):
        lo = 5.0 if typ == "goal_kick" else 4.0
        return ("arc", _clamp(3.0 + 0.12 * (d - 25.0), lo, 12.0))
    if typ == "pass" and d >= 30.0:
        return ("arc", _clamp(3.0 + 0.12 * (d - 25.0), 3.0, 12.0))
    return ("flat", 0.0)


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

    # Task 08: the taking team's keeper never gets a field slot (they were standing
    # at the centre spot at kick-offs and on the ball at attacking free kicks) —
    # every keeper gets a fixed home just off their own goal line instead.
    def assign(side: str, slots: List[Tuple[float, float]], gk_slot: Tuple[float, float]) -> None:
        got = on_pitch[side]
        keepers = [i for i in got if role_of[i] == "GK"]
        outfield = [i for i in got if role_of[i] != "GK"]
        for i in keepers:
            out[i] = gk_slot
        for i, slot in zip(outfield, slots):
            out[i] = slot

    u_s = sx if plus else PITCH_L - sx  # event spot in the attacking frame
    if typ == "corner":
        assign(team, [A(8.0, 34.0)] + [A(97, 27), A(97, 41), A(93, 21), A(93, 47),
                  A(89, 34), A(80, 27), A(80, 41), A(62, 34), A(45, 30), A(45, 38)],
               A(6.0, 34.0))
        assign(other, [D(2.5, 30.5), D(2.5, 37.5), D(6, 26), D(6, 34),
                       D(6, 42), D(10, 30), D(10, 38), D(45, 34), D(58, 40),
                       D(2.0, 36.0)], D(1.5, 34.0))
    elif typ == "free_kick" and u_s > PITCH_L / 2:
        assign(team, [A(u_s - 2, _clamp(sy + 6, 3, 65)), A(96, 30), A(96, 38),
                      A(max(u_s - 10, 40), 28), A(max(u_s - 10, 40), 40),
                      A(max(u_s - 18, 30), 34), A(60, 24), A(60, 44), A(40, 34),
                      A(30, 34)], A(12, 34))
        wall_y = sy
        assign(other, [D(2.0, _clamp(sy + (2.0 if sy < 34 else -2.0), 26, 42)),
                       D(PITCH_L - (u_s - 9), _clamp(wall_y - 1.0, 2, 66)),
                       D(PITCH_L - (u_s - 9), _clamp(wall_y, 2, 66)),
                       D(PITCH_L - (u_s - 9), _clamp(wall_y + 1.0, 2, 66)),
                       D(PITCH_L - (u_s - 14), _clamp(sy - 6, 3, 65)),
                       D(PITCH_L - (u_s - 14), _clamp(sy + 6, 3, 65)),
                       D(PITCH_L - (u_s - 22), 34), D(60, 30), D(60, 38),
                       D(45, 34)], D(2.5, 34.0))
    elif typ == "goal_kick":
        assign(team, [A(22, 5), A(20, 26), A(20, 42), A(22, 63),
                      A(48, 15), A(48, 34), A(48, 53), A(72, 17), A(72, 34), A(72, 51)],
               A(5.5, sy))
        assign(other, [D(50, 20), D(50, 48), D(57, 12), D(57, 56),
                       D(63, 26), D(63, 42), D(68, 34), D(45, 30), D(45, 38), D(40, 34)],
               D(3, 34))
    elif typ == "pass" and sub == "kick_off":
        assign(team, [A(52.0, 36.5), A(50, 31), A(50, 37), A(40, 15), A(40, 34),
                      A(40, 53), A(25, 11), A(25, 26), A(25, 42), A(25, 57)], A(5, 34))
        assign(other, [D(20, 11), D(20, 26), D(20, 42), D(20, 57), D(28, 15),
                       D(28, 34), D(28, 53), D(36, 17), D(36, 34), D(36, 51)], D(3, 34))
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

        # ball state machine (task 06): mode is one of
        #   place   sitting at self.spot (foul spot / restart spot / end of a roll)
        #   flight  launched by a kick (or a flat follow-on after a clearance)
        #   roll    rolling toward the receiver of an unmet pass (slowing)
        #   rollp   rolling toward a point (the next event's start)
        #   attach  at a player's feet, blended to the spot they will kick from
        #   out     off the pitch (-1) until the restart taker reaches the spot
        #   dribble carried along the dribble path
        self.bmode = "place"
        self.bx, self.by = PITCH_L / 2.0, PITCH_W / 2.0
        self.bz = 0.0
        self.battach = -1          # player the ball is stuck to
        self.bv = 0.0              # roll speed (m/s)
        self.broll_point = False   # roll heads to a point (late kick), not a player
        self.pk = -1               # deferred kick: event index waiting for the
        self.pk_end = (0.0, 0.0)   # taker to reach the ball (and its target)
        self.pk_lim = 0.0          # its own deadline (a late delivery may run
                                   # past the next event, which re-queues then)
        self.rq = -1               # a launch held back while the previous
                                   # delivery was still pending; the pump
                                   # replays it once that delivery resolves
        self.hold_j = -1           # held kick: event index whose ball sits at
        self.hold_t = 0.0          # the kicker's feet until hold_t, played
        self.hold_end = (0.0, 0.0) # firm then (band speeds are never flown)
        self.hold_pin = False      # restart hold: the ball waits ON the spot,
                                   # not a metre off at the taker's feet
        self.recs = 0              # records written so far
        self.rec_b = (0.0, 0.0)    # where the last record showed the ball
        self.rec_att = -1          # holder whose feet the ball was at in the
        self.kick_i = -1           # last record; and the player who just
        self.kick_t = 0.0          # struck one (frozen through the follow-
        self.kick_pos = (0.0, 0.0) # through, so the kick rule frame holds)
        self.out_since = 0.0
        self.out_glimpse = False    # one last visible record AT the line the
                                    # ball is leaving (task 08 rule 9/10: the
                                    # crossing itself must be seen)
        self.net_rest = False       # this flight ends in the net (a goal)
        self.net_until = 0.0        # the goal ball stays visible until then
        self.hold_gk = -1           # task 08 rule 7: keeper holding the ball
                                    # in their hands (z ~ 1 m) until release
        self.block_shot = -1        # event idx of a blocked shot being routed
        self.block_j = -1           # its first leg is in the air (bounce next)
        self.block_delay = 0.0      # launch hold so the blocker arrives with it
        self.block_join = False     # task 10: the rebound is down; join the
                                    # deflected ball to the next possession
        self.bv_tgt = -1.0          # a rolling ball accelerates toward this
                                    # speed (ROLL_ACC) instead of jumping to
                                    # it from a standstill -- a 0 -> 11 m/s
                                    # jump is a kick nobody made (rule 5)
        self.last_end: Tuple[float, float] = (0.0, 0.0)
                                    # where the last launch sent the ball
        self.roll_out = False       # a roll that ends off the pitch (rule 10)
        self.roll_top = FLIGHT_V_LO # cap while accelerating that roll
        self.spot: Tuple[float, float] = (PITCH_L / 2.0, PITCH_W / 2.0)
        # flight bookkeeping
        self.f0 = self.f1 = 0.0
        self.fxs = self.fys = self.fxe = self.fye = 0.0
        self.fd = 0.0
        self.fv = 0.0
        self.framp = True
        self.fstyle, self.fh = "flat", 0.0
        # virtual ball: drives the team shape while the real one is off pitch
        self.vbx, self.vby = PITCH_L / 2.0, PITCH_W / 2.0

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
        self.recover_until = [-1.0] * n  # a recovery run runs hard, not full-out
        self.rdist = [0.0] * n           # metres run (the distance governor)
        self.nspr = [0] * n              # sprint commitments (capped: SPRINT_MAX)
        self.srun = [0] * n              # consecutive frames above the sprint line
        self.nep = [0] * n               # sprint episodes recorded (5+ frames)
        self.lx: List[Optional[int]] = [None] * n   # last recorded dm position
        self.ly: List[Optional[int]] = [None] * n
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
        self.pending_on: List[Tuple[float, int, int]] = []  # task 08 rule 12:
        # (t_event, sub idx, out idx) -- the substitute steps on only once the
        # outgoing player has left the pitch
        self.moved_at = [0.0] * n     # last recorded dm move (statue guard)
        self.idle_t = [0.0] * n       # idle sway target re-roll time
        self.idle_x = [0.0] * n
        self.idle_y = [0.0] * n

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
        self.oz: Dict[str, List[int]] = {"ball": []}  # height, ball only
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
        # a roster change during a set-piece window invalidates the cached
        # slot map: a substitute who steps on inside the window (e.g. during
        # the goal celebration before a kick-off) was not on the pitch when
        # the map was built, stands in no slot, and drifts over the halfway
        # line at the kick-off frame (task 08 rule 2)
        if self.setpiece_ev >= 0 and self.setpiece_ev in self.setpiece_cache:
            del self.setpiece_cache[self.setpiece_ev]

    def _sprint_top(self, i: int) -> float:
        """Sprint cruise for player i: fraction of top speed with the fatigue
        floor, capped in absolute terms (see SPRINT_TOP_MS)."""
        return min(SPRINT_FRAC * self.vmax[i]
                   * max(1.0 - self.fat[i], FAT_SPRINT_FLOOR),
                   SPRINT_TOP_MS)

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

    def _spot_of(self, ev: Dict[str, Any]) -> Tuple[float, float]:
        """Where a restart is taken from (task 08 rule 11): goal kicks always
        from inside the goal area -- the generator parks some where a failed
        pass ended, up to 30 m away -- everything else where the event says."""
        sx, sy = ev["start"]["x"], ev["start"]["y"]
        if ev["type"] != "goal_kick":
            return (sx, sy)
        plus = _attacks_plus_x(ev["team_id"], ev["period"])
        own = 0.0 if plus else PITCH_L
        lo, hi = (own + 0.6, own + GOAL_AREA_DEPTH - 0.5) if plus \
            else (own - GOAL_AREA_DEPTH + 0.5, own - 0.6)
        return (_clamp(sx, lo, hi), _clamp(sy, GOAL_AREA_Y[0], GOAL_AREA_Y[1]))

    def _sub_enter(self, inc: int) -> None:
        """A substitute steps on at the halfway touchline with a clean slate."""
        self._set_active(inc, True)
        self.px[inc], self.py[inc] = PITCH_L / 2.0, 0.0
        self.vx[inc] = self.vy[inc] = 0.0
        self.wpt[inc] = []
        self.sprint_until[inc] = -1.0
        self.nspr[inc] = 0        # fresh legs: no inherited sprint budget
        self.rdist[inc] = 0.0     # or distance base for the governor
        self.srun[inc] = 0
        self.nep[inc] = 0
        self.lx[inc] = None
        self.moved_at[inc] = 0.0
        self.idle_t[inc] = 0.0

    def _parry_out(self, t: float, actor: int) -> None:
        """A save parried out (task 08 rule 7): the ball is deflected wide of
        the post and over the keeper's own goal line, visibly out."""
        own = 0.0 if _attacks_plus_x(self.team[actor], self._period(t)) else PITCH_L
        ey = 29.0 if self.by < PITCH_W / 2.0 else 39.0  # wide of the posts
        ex, ey = own, _clamp(ey, 1.5, PITCH_W - 1.5)
        d = math.hypot(ex - self.bx, ey - self.by)
        gap = max(abs(self.bx - own) - 0.3, 0.3)
        v = _clamp(d / gap, FLIGHT_V_HI, FLIGHT_CAP)
        self._start_flight(t, self.bx, self.by, ex, ey,
                           {"type": "parry", "end": {"y": ey}}, v, kick=actor)


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
            if self.on[out]:
                # task 08 rule 12: the player going off leaves BEFORE the
                # substitute steps on (no 12-13 player frames). The sub is
                # staged and _move activates them once the pitch is clear.
                self.walkoff_at[out] = end_s
                oy = 0.0 if self.py[out] < PITCH_W / 2.0 else PITCH_W
                self.walkoff_tgt[out] = (self.px[out], oy)
                self.wpt[out] = []
                self.pending_on.append((ev["t_ms"] / 1000.0, inc, out))
            else:
                # a chained double sub at one stoppage (13 on for 8, 14 on
                # for 13): the "out" player is a sub still staged to enter.
                # They go straight back off -- cancel their entry and stage
                # this sub behind the same outgoing player, so the roster
                # stays at 11 (task 08 rule 12)
                staged = [p for p in self.pending_on if p[1] == out]
                if staged:
                    self.pending_on.remove(staged[0])
                    self.pending_on.append((staged[0][0], inc, staged[0][2]))
                else:
                    self._sub_enter(inc)
        # ball (task 06)
        typ = ev["type"]
        te = ev["t_ms"] / 1000.0
        if typ == "keeper_save":
            # the shot before this ended at the goal this keeper guards: they
            # pick the ball up (task 08 rule 7). A save followed by a corner
            # is a parry straight out over the line; anything else is a catch
            # -- the ball rides in their hands until they release it.
            if actor is not None and actor >= 0 and self.on[actor] and \
                    math.hypot(self.px[actor] - self.bx, self.py[actor] - self.by) < 3.0:
                parry = any(self.events[k]["type"] == "corner"
                            for k in range(j + 1, min(j + 3, len(self.events))))
                if parry:
                    self._parry_out(t, actor)
                else:
                    self.bmode = "attach"
                    self.battach = actor
                    self.hold_gk = actor
                    self.spot = (self.bx, self.by)
        elif typ in _BALL_KICKS:
            self._launch(j, te)
            # task 10: the event after this kick is booked where the ball is
            # now heading -- swap its actor early if the named one cannot
            # possibly get there but a teammate can
            if j + 1 < len(self.events):
                ax_, ay_ = self.last_end
                self._swap_next(j + 1, t, ax_, ay_)
        elif typ in ("foul", "tackle", "interception"):
            # play stops/changes at this spot: freeze the ball where it is
            # (a foul's start is the ball's position, task 06 rule 2)
            if typ != "foul":
                self._swap_hopeless(j, t)  # task 10: the man on the spot
            self.bmode = "place"
            self.spot = (self.bx, self.by)
            if typ != "foul" and j + 1 < len(self.events):
                self._swap_next(j + 1, t, self.bx, self.by)

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
            sx, sy = self._spot_of(ev)  # goal kicks: inside the goal area
            ft, fx, fy = self._free_at(best, t)  # position/time after pending work
            if not (math.hypot(sx - fx, sy - fy) <= FEASIBLE * self.vmax[best] * max(te - ft, 0.0)
                    and ft < te):
                self.infeasible_events += 1
            self.assigned[j] = best
            # task 08 rule 4/16: the keeper is AT the ball whatever the clock
            # says -- the waypoint stands even when it needs a hurry
            self.wpt[best].append((te, sx, sy, j))
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
            # feasibility at the pace they can actually sustain (fatigue
            # included): a booking that ignores fatigue puts the event
            # frame's actor still metres short of the spot (rule 4)
            spd = max(FEASIBLE * self.vmax[i] * (1.0 - self.fat[i]), 2.5)
            if d <= spd * (te - ft):
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
        self.assigned[j] = best
        self.wpt[best].append((te, sx, sy, j))

    # -- ball state machine (task 06) ---------------------------------------------

    def _next_actor(self) -> int:
        a = self.assigned[self.ep] if self.ep < len(self.events) else None
        if a is not None and a >= 0 and self.on[a]:
            return a
        return -1

    def _meet_point(self, t: float) -> Optional[Tuple[float, float]]:
        """Task 10: where the next event's taker has actually been booked to
        meet the ball. Task 08 rule 4's meet booking (in _launch) moves the
        taker's waypoint off the event start to a point they can reach by
        their event time -- the delivery must go THERE, or the ball rolls
        past the receiving player to a spot nobody reaches for seconds (the
        rule 16 clusters). None when the taker is booked to the spot itself
        or has no booking for this event."""
        a = self._next_actor()
        if a < 0:
            return None
        for w in self.wpt[a]:
            if w[3] != self.ep:
                continue
            if math.hypot(w[1] - self.events[self.ep]["start"]["x"],
                          w[2] - self.events[self.ep]["start"]["y"]) > 2.5:
                return (w[1], w[2])
            return None
        return None

    @staticmethod
    def _accel_reach(tt: float, vmax: float) -> float:
        """Ground a player can cover from a standing start in tt seconds:
        6 m/s^2 up to cruise (task 04 caps), then flat."""
        v = max(0.9 * vmax, 2.0)
        return v * tt - v * v / 12.0 if tt > v / 6.0 else 3.0 * tt * tt

    def _swap_next(self, k: int, t: float, ax: float, ay: float) -> None:
        """Task 10: event k (the one after the kick just launched) is booked
        where the ball is going (ax, ay), but its named actor is farther
        from there than anyone can run by their own event -- while a teammate
        stands much closer. Swap the event to that player early (there is
        still a full gap of running time left) and book them to the point on
        their line they reach just in time: post-shot chain breaks gave
        passes made 20-60 m from the ball otherwise."""
        if k >= len(self.events) or k < 0:
            return
        ev = self.events[k]
        if ev["type"] in _RESTART_TYPES or ev["type"] in ("substitution",
                                                          "card", "foul",
                                                          "keeper_save"):
            return
        if ev["type"] == "shot" and ev.get("outcome") == "goal":
            return
        a = self.assigned[k]
        if a is None or a < 0 or not self.on[a]:
            return
        te = ev["t_ms"] / 1000.0
        tt = te - t
        if tt <= 0.25:
            return
        db = math.hypot(self.px[a] - ax, self.py[a] - ay)
        if db <= max(self._accel_reach(tt, self.vmax[a]), 10.0):
            return  # the named actor makes it (or is inside the 10 m bar)
        best, bd = -1, 1e9
        for i in self.actives:
            if self.team[i] != ev["team_id"] or i == a \
                    or self.walkoff_tgt[i] is not None:
                continue
            # task 10: as _swap_hopeless -- the keeper takes a clearance
            # or outlet pass nobody else can reach, and only within their
            # own third (the leash, rule 1)
            if self.role[i] == "GK":
                if ev["type"] not in ("clearance", "pass"):
                    continue
                gx = 0.0 if _attacks_plus_x(self.team[i],
                                            ev["period"]) else PITCH_L
                if abs(ax - gx) > 24.0:
                    continue
            d2 = math.hypot(self.px[i] - ax, self.py[i] - ay)
            if d2 < bd:
                best, bd = i, d2
        if best < 0 or bd + 6.0 >= db \
                or bd > max(self._accel_reach(tt, self.vmax[best]) * 0.95,
                            8.0):
            return  # nobody can do materially better: keep the named player
        self.assigned[k] = best
        g = min(bd, self._accel_reach(tt, self.vmax[best]) * 0.9)
        mx = ax + (self.px[best] - ax) * (1.0 - g / bd) if bd > 1e-9 else ax
        my = ay + (self.py[best] - ay) * (1.0 - g / bd) if bd > 1e-9 else ay
        self.wpt[best] = [w for w in self.wpt[best] if w[3] != k]
        self.wpt[best].append((max(te - 0.2, t + 0.3), mx, my, k))
        # the event's start follows the meet: later join logic (_land, the
        # creep) delivers the ball to the taker's booking, not past them

    def _swap_hopeless(self, j: int, t: float) -> None:
        """Task 10: the named actor of a kick event is hopelessly far from
        the ball (a generator chain break -- the next possession was booked
        30-60 m away with 1-2 s to get there, so they never left their old
        spot) while a teammate stands right by the loose ball. The tracking
        re-names events anyway (the look-ahead chooses actors); naming the
        player who is actually on the spot is the reconstruction a viewer
        sees -- the blocker taps the rebound on, the tackler plays the
        loose ball -- instead of a pass being 'made' 30 m from the ball."""
        ev = self.events[j]
        if ev["type"] in _RESTART_TYPES or ev["type"] == "keeper_save" \
                or ev["type"] == "foul":
            return  # set-piece takers and keepers keep their event
        if ev["type"] == "shot" and ev.get("outcome") == "goal":
            return  # never re-name a goalscorer
        a = self.assigned[j]
        if a is None or a < 0 or not self.on[a] or self.bx < 0.0:
            return
        db = math.hypot(self.px[a] - self.bx, self.py[a] - self.by)
        if db <= 8.0:
            return  # at or near the ball: their own event
        best, bd = -1, 1e9
        for i in self.actives:
            if self.team[i] != ev["team_id"] or i == a \
                    or self.walkoff_tgt[i] is not None:
                continue
            # task 10: the keeper may take a clearance or an outlet pass
            # from their own goal mouth (a shot landed there, nobody else
            # is within reach) -- the classic off-the-line clearance and
            # keeper distribution -- but only for a ball in their own
            # third: a swap further up the pitch drags them out of their
            # leash (rule 1, seed 14: 30.8 m)
            if self.role[i] == "GK":
                if ev["type"] not in ("clearance", "pass"):
                    continue
                gx = 0.0 if _attacks_plus_x(self.team[i],
                                            ev["period"]) else PITCH_L
                if abs(self.bx - gx) > 24.0:
                    continue
            d2 = math.hypot(self.px[i] - self.bx, self.py[i] - self.by)
            if d2 < bd:
                best, bd = i, d2
        if best < 0 or bd > 12.0 or bd + 6.0 >= db:
            return
        self.assigned[j] = best
        if not any(w[3] == j for w in self.wpt[best]):
            self.wpt[best].append((t + 0.8, self.bx, self.by, j))

    def _launch(self, j: int, t: float) -> None:
        """A kick: the ball leaves the actor's feet toward ev.end."""
        ev = self.events[j]
        self._swap_hopeless(j, t)
        a = self.assigned[j]
        ex, ey = ev["end"]["x"], ev["end"]["y"]
        nxt = self.events[j + 1] if j + 1 < len(self.events) else None
        gap = (nxt["t_ms"] / 1000.0 - t) if nxt else 3.0
        # a restart kick (goal kick, corner, throw-in, free kick) fires a
        # quarter-second late: the restart's own frame then shows the ball
        # still on its spot with the taker over it, not already underway
        rdelay = 0.25 if (_is_out_restart(ev) or ev["type"] == "free_kick") \
            else 0.0
        # task 08: a shot (or a shooting free kick) ends where its OUTCOME
        # says, not where the event's end coordinates park the ball (all
        # shot ends sit on the goal line -- rules 5, 7, 8, 9).
        self.block_shot = -1
        self.block_delay = 0.0
        if ev["type"] == "shot" or (ev["type"] == "free_kick"
                                    and ev.get("subtype") == "shoot"):
            oc = ev.get("outcome")
            if oc == "goal":
                # into the net between the posts: the flight crosses the line
                # visibly and the ball rests there (rule 5)
                ey = _clamp(ey, 31.9, 36.1)
            elif oc == "saved" and nxt is not None \
                    and nxt["type"] == "keeper_save":
                # to the saving keeper at their own goal (rule 7): the saved
                # shot never flies on to the goal line
                kx, ky = self._spot_of(nxt)
                ex, ey = kx + (0.7 if ex >= kx else -0.7), ky
            elif oc == "blocked":
                # a defender in the shot's path meets it (rule 8): the block
                # happens on the pitch, well short of the line. The blocker
                # is chosen by the launch delay their run needs -- a block
                # point nobody can reach (the old path midpoint, or the spot
                # a moving defender has already run off) puts nobody within
                # arm's reach at the block frame.
                best, bd = -1, 1e9
                bk = 1e18  # fallback ranking key (keeper +10 m penalty)
                vx_, vy_ = ex - self.bx, ey - self.by
                vv = math.hypot(vx_, vy_)
                # the shot branch flies a blocked shot at this speed
                # (tt = 0.7 s), not plain FLIGHT_V_HI -- the block routing
                # must pace runs and holds against the real flight time
                v_shot = _clamp(vv / 0.7, FLIGHT_V_HI, FLIGHT_CAP)
                mx_, my_ = None, None
                pick_key, pick_s = None, 0.0
                if vv > 1e-9:
                    vx_, vy_ = vx_ / vv, vy_ / vv
                    mx_, my_ = self.bx + (ex - self.bx) * 0.55, \
                        self.by + (ey - self.by) * 0.55
                    for i in self.actives:
                        if self.team[i] == ev["team_id"] or self.role[i] == "GK":
                            continue
                        rx, ry = self.px[i] - self.bx, self.py[i] - self.by
                        s = rx * vx_ + ry * vy_
                        # the ex >= 1.6 clamp below keeps the block well
                        # short of the line, so a low band is safe here
                        if 0.1 * vv <= s <= 0.85 * vv:
                            perp = abs(rx * (-vy_) + ry * vx_)
                            spd_i = max(0.8 * self.vmax[i] * (1.0 - self.fat[i]),
                                        2.5)
                            moving = math.hypot(self.vx[i], self.vy[i]) > 2.5
                            if perp <= 12.0 and not moving:
                                # block at their feet: they are planted in
                                # the lane, the firm ball is played straight
                                # at them and they just stand there
                                key = (1 if self.wpt[i] else 0, 0.0, perp)
                                tgt = (self.px[i], self.py[i])
                                dly = 0.0
                            elif perp <= 30.0:
                                # block at their path point: they run onto it
                                # while the ball is (held on the boot until
                                # they can) -- a moving defender's spot is
                                # already behind them the moment the ball flies
                                # +0.35 settle: same run-in deceleration
                                # margin as the fallback branch below
                                dly = perp / spd_i + 0.35 \
                                    - (0.2 + s / v_shot)
                                if dly > max(0.0, min(2.5, gap - 0.9)):
                                    # the run needs more hold than the
                                    # schedule allows -- clamping the delay
                                    # would just rebound the ball off nobody
                                    continue
                                key = (1 if self.wpt[i] else 0, dly, perp)
                                tgt = (self.bx + vx_ * s, self.by + vy_ * s)
                            else:
                                continue  # hopeless even with the delay cap
                            if pick_key is None or key < pick_key:
                                pick_key, best, bd, pick_s = key, i, perp, s
                                mx_, my_ = tgt
                                self.block_delay = _clamp(
                                    dly, 0.0, max(0.0, min(2.5, gap - 0.9)))
                if best < 0 and vv > 1e-9 and mx_ is not None:
                    # nobody even near the path (a counter-attack, or a
                    # defender caught on the shooter's side of the ball):
                    # the nearest opponent runs into the path and the ball
                    # is held on the boot until they can meet it there --
                    # letting it fly to the shot's own destination would
                    # rebound off nobody at the goal line. The meeting
                    # point walks down the ray toward the ball until their
                    # run fits the hold the schedule allows: a fixed
                    # midpoint 9 m from everyone rebounds off nobody too.
                    # The next event in this shape (no defender in the
                    # lane) is not waiting on this ball, so only 0.55 s
                    # of its window is reserved.
                    for i in self.actives:
                        if self.team[i] == ev["team_id"]:
                            continue
                        # the keeper is a last resort (an outfield block
                        # is always the truer read), but a point-blank
                        # shot with every outfield defender 15+ m away
                        # is smothered by the spreading keeper -- the
                        # ray runs at their own goal, so the meeting
                        # point stays deep inside their leash
                        gk = 1 if self.role[i] == "GK" else 0
                        d2 = math.hypot(self.px[i] - mx_, self.py[i] - my_)
                        key2 = d2 + (10.0 if gk else 0.0)
                        if best < 0 or key2 < bk:
                            best, bd, bk = i, d2, key2
                    if best >= 0:
                        spd_b = max(0.8 * self.vmax[best]
                                    * (1.0 - self.fat[best]), 2.5)
                        cap = max(0.0, min(2.5, gap - 0.55))
                        for f in (0.55, 0.4, 0.25, 0.12):
                            px_ = self.bx + (ex - self.bx) * f
                            py_ = self.by + (ey - self.by) * f
                            d_f = math.hypot(self.px[best] - px_,
                                             self.py[best] - py_)
                            # +0.35 not +0.25: the run-in decelerates
                            # near the point (_move's arrive cap), so a
                            # defender paced exactly to the landing
                            # finishes a few tens of cm short; the ball
                            # term is the measured hold+ramp+travel
                            need = d_f / spd_b + 0.35 \
                                - (0.2 + f * vv / v_shot)
                            if need <= cap:
                                mx_, my_ = px_, py_
                                self.block_delay = _clamp(need, 0.0, cap)
                                break
                        else:
                            px_ = self.bx + (ex - self.bx) * 0.12
                            py_ = self.by + (ey - self.by) * 0.12
                            mx_, my_ = px_, py_
                            self.block_delay = cap
                if best >= 0:
                    ex, ey = mx_, my_
                if best >= 0:
                    # never ON the goal line: a landing frame at the line
                    # between the posts reads as the ball going in
                    if ex > PITCH_L - 1.6:
                        ex = PITCH_L - 1.6
                    elif ex < 1.6:
                        ex = 1.6
                    self.block_shot = j
                    self.block_j = best
                    # the defender steps into the ball's path and blocks it.
                    # The waypoint is paced to the ball's own schedule --
                    # launch hold + ramp + travel (the hold and ramp
                    # compress to ~0.2 s on the 5 Hz grid, measured on the
                    # seeded traces) -- because _move cruises at
                    # d/remain*1.35: a due time past the landing has the
                    # defender strolling in behind the ball (rule 8). A
                    # next-event deadline can still sit 30 s away, so
                    # without a pin a defender already on the point drifts
                    # off it long before the ball arrives.
                    tt = math.hypot(ex - self.bx, ey - self.by) / v_shot
                    # task 10: -0.1 not +0.2 -- a defender paced to land
                    # WITH the ball finishes their deceleration a frame or
                    # two behind the deflection (measured seed 5 78.7 s:
                    # 1.4 m). On the point 0.3 s early is the true block
                    # read anyway: planted in the lane, ball played at them.
                    due = max(t + 0.6, t + self.block_delay + tt - 0.1)
                    if nxt is not None:
                        due = min(due, nxt["t_ms"] / 1000.0 - 0.3)
                    if not any(w[3] == j for w in self.wpt[best]):
                        self.wpt[best].append((max(t + 0.6, due), ex, ey, j))
        if ev["type"] in ("pass", "cross", "clearance") and nxt is not None \
                and nxt["type"] not in ("substitution", "card") \
                and not _is_out_restart(nxt) \
                and 0.25 <= nxt["t_ms"] / 1000.0 - t <= 8.0 \
                and self._follow_on_s(nxt, ex, ey) <= 0.0:
            # task 08 rule 4 (meet): the delivery lands where the NEXT
            # action's taker can actually be when their event fires. A
            # generator chain break (the booked spot 15-45 m from a taker
            # with 2 s to get there) otherwise parks the ball where nobody
            # is, and the event frame shows its actor meters from the ball.
            # The ball is delivered to the point on the taker's line to the
            # spot that they reach just before their event -- their waypoint
            # is moved with it, so player and ball arrive together.
            if self.assigned[j + 1] is None \
                    and nxt["type"] not in ("substitution", "card") \
                    and 0.25 <= nxt["t_ms"] / 1000.0 - t <= 8.0:
                # task 10: a kick-off pass launches before the ko_guard
                # lifts, so the event it delivers to may have no actor yet
                # -- choose it now or the meet below cannot shorten a
                # 36 m delivery into nobody's half of the pitch
                self._choose_actor(j + 1, t)
            a1 = self.assigned[j + 1]
            # (a1 may be a: a player chasing their own long ball is a meet
            # too -- task 10, the generator's self-chains)
            if a1 is not None and a1 >= 0 and self.on[a1]:
                t1 = nxt["t_ms"] / 1000.0
                dx1, dy1 = ex - self.px[a1], ey - self.py[a1]
                d1 = math.hypot(dx1, dy1)
                # task 10: the reach is accel-aware -- a player covers far
                # less than cruise*seconds in the first second (6 m/s^2,
                # task 04 caps), and an optimistic reach booked receptions
                # past takers who were still metres short at their frame
                t_left = max(t1 - t, 0.0)
                v_full = max(0.9 * self.vmax[a1] * (1.0 - self.fat[a1]), 2.0)
                reach = (v_full * t_left - v_full * v_full / 12.0
                         if t_left > v_full / 6.0 else 3.0 * t_left * t_left)
                if d1 > reach * 0.95 + 0.3:
                    g = reach * 0.9
                    if d1 > 1e-9 and g > 0.0:
                        ex = _clamp(self.px[a1] + dx1 / d1 * g, 1.0, PITCH_L - 1.0)
                        ey = _clamp(self.py[a1] + dy1 / d1 * g, 1.5, PITCH_W - 1.5)
                    self.wpt[a1] = [w for w in self.wpt[a1] if w[3] != j + 1]
                    self.wpt[a1].append((max(t1 - 0.3, t + 0.2), ex, ey, j + 1))
        # task 10: remember where this kick is putting the ball (post
        # meet-adjustment) -- the next event's swap check anchors on it
        self.last_end = (ex, ey)
        if self.hold_gk >= 0 and self.bmode == "attach" \
                and self.battach == self.hold_gk and a != self.hold_gk:
            # task 08 rule 7 (release): the keeper puts the ball down for the
            # next action -- it drops from their hands and rolls loose to the
            # next spot, whose taker picks it up and plays it (the pump
            # replays this launch once they have it)
            gk = self.hold_gk
            self.hold_gk = -1
            sx, sy = self._spot_of(ev)
            self.bx, self.by = self._feet(gk)
            self.bz = 0.1
            d2 = math.hypot(sx - self.bx, sy - self.by)
            if d2 > 1.0:
                self.bmode = "rollp"
                self.bv = min(FLIGHT_V_HI, max(1.2, d2 / max(gap - 0.4, 0.4)))
                self.spot = (sx, sy)
            else:
                self.bmode = "place"
                self.spot = (sx, sy)
            self.pk = j
            self.pk_end = (ex, ey)
            self.pk_lim = t + 6.0
            return
        if self.bmode == "flight" and self.f1 > t:
            # a delivery is still in the air: launching now would tear the
            # ball off its flight. The kick waits for the landing (the pump
            # replays it once the taker has the ball); another queued kick
            # keeps its slot
            if self.pk < 0:
                lx, ly = self.fxe, self.fye   # where the ball lands
                t_next = (nxt["t_ms"] / 1000.0) if nxt else t + 3.0
                dl = math.hypot(ex - lx, ey - ly) / FLIGHT_CAP
                latest = self._kick_latest(ev, dl, t_next)
                who, eta = -1, 1e9
                if a is not None and a >= 0 and self.on[a]:
                    spd = max(0.67 * self.vmax[a]
                              * (1.0 - self.fat[a]), 2.0)
                    eta = max(self.f1 - t, math.hypot(
                        self.px[a] - lx, self.py[a] - ly) / spd) + 0.45
                    if t + eta <= latest:
                        who = a
                if who < 0:
                    # the booked taker cannot reach the landing spot: a
                    # teammate standing over it takes the kick instead (same
                    # rule as the deferral branch below -- here the ball is
                    # still in the air, so "over the ball" means over where
                    # it is about to land)
                    db = (math.hypot(self.px[a] - lx, self.py[a] - ly)
                          if a is not None and a >= 0 else 1e9)
                    best, bd = -1, 1e9
                    for i in self.actives:
                        if self.team[i] != ev["team_id"] or \
                                self.role[i] == "GK":
                            continue
                        d2 = math.hypot(self.px[i] - lx, self.py[i] - ly)
                        if d2 < bd:
                            best, bd = i, d2
                    if best >= 0 and bd <= 3.0 and bd + 2.0 < db:
                        spd2 = max(0.67 * self.vmax[best]
                                   * (1.0 - self.fat[best]), 2.0)
                        eta2 = max(self.f1 - t, bd / spd2) + 0.45
                        if t + eta2 <= latest:
                            who, eta = best, eta2
                if who >= 0:
                    self.assigned[j] = who
                    self.pk = j
                    self.pk_end = (ex, ey)
                    self.pk_lim = min(t + eta + dl + 0.4, latest + dl)
                else:
                    # nobody can play it off the landing: a short deadline --
                    # the pump redirects (or hides) the ball when it expires
                    self.pk = j
                    self.pk_end = (ex, ey)
                    self.pk_lim = max(self.f1, t + 0.3) + 2.0
            return
        if self.pk >= 0 and self._pending_ready(t, ev):
            # an earlier event's deferred kick is being played right now (its
            # taker is on the ball's doorstep): hold this launch back -- the
            # pump replays it after that delivery resolves
            self.rq = j
            return
        self.pk = -1  # any new launch supersedes a pending deferred kick
        self.hold_j = -1  # ... and any pending held kick
        self.hold_pin = False
        if ev["type"] == "dribble" and a is not None and a >= 0 and self.on[a] and \
                math.hypot(self.px[a] - self.bx, self.py[a] - self.by) <= 2.0 and \
                math.hypot(ex - self.px[a], ey - self.py[a]) <= \
                0.45 * self.vmax[a] * max(gap, 0.3):
            # a carry the dribbler finishes in under half the gap: the ball
            # rides at their feet while they run toward the dribble end (the
            # next event starts there) and is on the spot well before it.
            # Anything longer is a knock-on below -- a carrier who only just
            # arrives at te leaves the ball short at the check frame.
            self.bmode = "attach"
            self.battach = a
            self.spot = (ex, ey)
            # the carry itself: a waypoint timed just before the next event
            # drives the carrier (and the ball at their feet) to the end --
            # without it they drift there at chaser speeds and arrive late
            self.wpt[a] = [w for w in self.wpt[a] if w[3] != j]
            self.wpt[a].append(((nxt["t_ms"] / 1000.0 - 0.2) if nxt
                                else t + 2.8, ex, ey, j))
            return
        if ev["type"] == "dribble" and (a is None or a < 0 or not self.on[a]):
            # no actor (rare): the ball follows the dribble path geometrically
            self.bmode = "dribble"
            self.f0 = t
            self.f1 = nxt["t_ms"] / 1000.0 if nxt else t + 2.0
            self.fxs, self.fys, self.fxe, self.fye = self.bx, self.by, ex, ey
            self.fv = math.hypot(ex - self.bx, ey - self.by) / max(self.f1 - t, 0.3)
            return
        # an infeasible dribble (more ground than the carrier can run in the
        # gap) falls through to the kick code: a knock-on -- the ball goes on
        # ahead along the ground and they chase it, so it still reaches the
        # next event's spot on time
        # the kick comes off the boot only once a record has shown the ball
        # at the kicker's feet (rec_att): the frame before the flight then
        # has them within 1.2 m of the ball (kick rule). Anyone merely close
        # defers below and plays it after the pickup attach.
        if a is not None and a >= 0 and self.on[a] and self.rec_att == a:
            if self.bmode == "attach" and self.battach == a:
                # the boot is exactly where the last record showed the ball,
                # at their feet; f0 back-dating makes the first flight frame
                # land at rec_b + 0.2*v (cruise from the first frame)
                ox, oy = self.rec_b
            else:
                ox, oy = self.px[a], self.py[a]
                d0 = math.hypot(ex - ox, ey - oy)
                if d0 > 1e-9:  # a step ahead of the plant foot
                    ox += LEAD_M * (ex - ox) / d0
                    oy += LEAD_M * (ey - oy) / d0
        elif a is not None and a >= 0 and self.on[a]:
            # the taker is not on the ball yet. If they can still reach it in
            # time for a delivery that lands before the next event, the kick
            # waits (see the pk pump in _ball_step): they sprint to the ball,
            # it goes to their feet, and it is played firm just in time.
            db = math.hypot(self.px[a] - self.bx, self.py[a] - self.by)
            spd = max(0.67 * self.vmax[a] * (1.0 - self.fat[a]), 2.0)
            eta = db / spd + 0.45       # arrive, attach, one record frame
            dl = math.hypot(ex - self.bx, ey - self.by) / FLIGHT_CAP  # firm
            t_next = (nxt["t_ms"] / 1000.0) if nxt else t + 3.0
            latest = self._kick_latest(ev, dl, t_next)
            if t + eta <= latest:
                self.pk = j
                self.pk_end = (ex, ey)
                self.pk_lim = min(t + eta + dl + 0.4, latest + dl)
                if self.bmode == "out":
                    # a chain break left the ball "out" nowhere near this
                    # kick's spot while a player stands right next to it: it
                    # never left -- it is on the pitch and gets played
                    self.bmode = "place"
                return
            # the named taker cannot make it at all: a teammate standing over
            # the ball takes the kick instead (the generator's chain break
            # stranded it far from whoever the data booked for it)
            best, bd = -1, 1e9
            for i in self.actives:
                if self.team[i] != ev["team_id"] or self.role[i] == "GK" or i == a:
                    continue
                d2 = math.hypot(self.px[i] - self.bx, self.py[i] - self.by)
                if d2 < bd:
                    best, bd = i, d2
            if best >= 0 and bd <= 3.0 and bd + 2.0 < db:
                spd2 = max(0.67 * self.vmax[best] * (1.0 - self.fat[best]),
                           2.0)
                eta2 = bd / spd2 + 0.45
                if t + eta2 <= latest:
                    self.assigned[j] = best
                    self.pk = j
                    self.pk_end = (ex, ey)
                    self.pk_lim = min(t + eta2 + dl + 0.4, latest + dl)
                    if self.bmode == "out":
                        self.bmode = "place"
                    return
            self._redirect_or_hide(t, ex, ey, nxt)
            return
        else:
            self._redirect_or_hide(t, ex, ey, nxt)  # no taker at all
            return
        d = math.hypot(ex - ox, ey - oy)
        if d < 0.25:  # kick onto the same spot: the ball just stays there
            self.bmode = "place"
            self.bx, self.by = ox, oy
            self.spot = (ox, oy)
            return
        if self.block_shot == j or (ev["type"] == "shot"
                                    and ev.get("outcome") in ("goal", "saved",
                                                              "off_target")) \
                or (ev["type"] == "free_kick" and ev.get("subtype") == "shoot"):
            # task 08 rules 5-9: a shot is struck the moment it happens -- a
            # firm ball away (never held, never mid-band), so it visibly
            # crosses the line, reaches the keeper or meets the blocker
            # inside the QA's 3 s window. A blocked shot routed to a defender
            # travels the first leg to where they stand, held on the boot for
            # up to block_delay first so the blocker's run arrives with it.
            oc = ev.get("outcome")
            tt = 0.85 if oc == "goal" else (0.7 if oc == "blocked"
                                            else max(gap - 0.2, 0.5))
            v = _clamp(d / max(tt, 0.4), FLIGHT_V_HI, FLIGHT_CAP)
            bj = self.block_j if self.block_shot == j else -1
            bdly = self.block_delay if self.block_shot == j else 0.0
            self._start_flight(t, ox, oy, ex, ey, ev, v, kick=a, delay=bdly)
            self.block_j = bj  # _start_flight clears it; the block flight
            return
        # just-in-time delivery: the ball arrives ~0.7 s before the next
        # event, so the receiver meets it on the frame (rule 4 first branch)
        # and it never lies at the spot alone for long. The speed for that is
        # either out of the 4-12 m/s band the realism tests look at, or the
        # kick is held: the kicker stands over the ball and plays it firm
        # (>= 12.6 m/s) at the last moment that still arrives on time.
        if nxt is not None and _is_out_restart(nxt):
            # the ball is leaving the pitch: play it out firmly now, so the
            # out-of-play window (rule 1) opens well before the restart
            self._start_flight(t, ox, oy, ex, ey, ev,
                               _clamp(d / max(gap - 0.7, 0.3), FLIGHT_V_HI, FLIGHT_CAP),
                               kick=a, delay=rdelay)
            return
        v_t = d / max(gap - 0.7 - self._follow_on_s(nxt, ex, ey), 0.3)
        if FLIGHT_V_LO < v_t < FLIGHT_V_HI:
            # mid-band: hold at the kicker's feet, fire firm just in time.
            # A taker who has just sprinted onto the ball needs a moment to
            # plant first: firing while they still move leaves the touch
            # frame's ball over a metre from them (kick rule)
            vd = math.hypot(self.vx[a], self.vy[a])
            plant = min(0.7, vd / 6.0 + 0.15) if vd > 1.5 else 0.0
            self.bmode = "attach"
            self.battach = a
            self.spot = (ex, ey)
            self.hold_j = j
            self.hold_t = t + max(plant, max(0.0, gap - 0.7
                                             - self._follow_on_s(nxt, ex, ey)
                                             - d / FLIGHT_V_HI))
            self.hold_end = (ex, ey)
            # a held restart (short throw-in) waits with the ball ON the spot:
            # the restart frame must show it there, not at the taker's feet
            self.hold_pin = _is_out_restart(ev) and \
                math.hypot(self.bx - ev["start"]["x"],
                           self.by - ev["start"]["y"]) <= 1.5
            return
        self._start_flight(t, ox, oy, ex, ey, ev, _clamp(v_t, 1.5, FLIGHT_CAP),
                           kick=a, delay=rdelay)

    def _follow_on_s(self, nxt: Optional[Dict[str, Any]],
                     ex: float, ey: float) -> float:
        """Seconds to reserve for the leg after this kick lands: when the
        next action does not start where this kick ends (a chain break, e.g.
        a clearance landing far from the next pass), the delivery budget
        must cover the follow-on too, or the ball arrives at the next event
        a whole leg late."""
        if nxt is None or _is_out_restart(nxt):
            return 0.0
        d2 = math.hypot(nxt["start"]["x"] - ex, nxt["start"]["y"] - ey)
        return d2 / FLIGHT_V_HI if d2 > 0.3 else 0.0

    def _kick_latest(self, ev: Dict[str, Any], dl: float,
                     t_next: float) -> float:
        """The latest a deferred kick may START so the whole delivery fits
        inside this event's window (measured to the next event's touch).
        An arc delivery (cross / crossed set piece / clearance / long pass
        -- see _flight_height) has to put its peak in the window: the launch
        is due half a flight before the window closes, with no late-kick
        grace. A ground delivery only has to land before the next touch:
        the usual grace applies."""
        if _flight_height(ev, dl * FLIGHT_CAP)[0] == "arc":
            return t_next - 0.05 - 0.5 * dl
        return t_next - 0.2 + LATE_KICK_S - dl

    def _pending_ready(self, t: float, ev: Dict[str, Any]) -> bool:
        """A deferred kick for the event just before `ev` is still pending and
        about to happen: its taker is on the ball's doorstep and the delivery
        still lands in time (before ev itself when ev is a restart -- the ball
        must be off the pitch by then). While this holds, the out-of-play
        forcing and the next launch wait for the kick instead of tearing the
        ball away from its taker."""
        if self.pk < 0:
            return False
        a = self.assigned[self.pk]
        if a is None or a < 0 or not self.on[a]:
            return False
        db = math.hypot(self.px[a] - self.bx, self.py[a] - self.by)
        if db > 10.0:
            return False
        pev = self.events[self.pk]
        spd = max(0.67 * self.vmax[a] * (1.0 - self.fat[a]), 2.0)
        dl = math.hypot(pev["end"]["x"] - self.bx, pev["end"]["y"] - self.by)
        eta = db / spd + 0.45 + dl / FLIGHT_V_HI
        if _is_out_restart(ev):
            return t + eta <= ev["t_ms"] / 1000.0 - 0.1
        return True

    def _pending_viable(self, t: float) -> bool:
        """A deferred kick is still going to happen even though its taker is
        not on the doorstep yet: they will reach the ball in time to play the
        delivery inside its own window (the deadline the deferral branch and
        the pump both enforce). While that holds, the ball stays on the pitch
        for them -- rule 1's out window opens when a kick actually puts the
        ball off the pitch, not while one is still booked on it."""
        if self.pk < 0:
            return False
        a = self.assigned[self.pk]
        if a is None or a < 0 or not self.on[a]:
            return False
        pev = self.events[self.pk]
        nxt = self.events[self.pk + 1] if self.pk + 1 < len(self.events) else None
        t_next = (nxt["t_ms"] / 1000.0) if nxt else t + 3.0
        db = math.hypot(self.px[a] - self.bx, self.py[a] - self.by)
        dl = math.hypot(pev["end"]["x"] - self.bx,
                        pev["end"]["y"] - self.by)
        spd = max(0.67 * self.vmax[a] * (1.0 - self.fat[a]), 2.0)
        eta = db / spd + 0.45 + dl / FLIGHT_V_HI
        return t + eta <= self._kick_latest(pev, dl / FLIGHT_CAP, t_next) + dl

    def _redirect_or_hide(self, t: float, ex: float, ey: float,
                          nxt: Optional[Dict[str, Any]]) -> None:
        """A kick nobody can play in time: the ball is sent on ahead alone.
        When even a rolling ball cannot reach the spot before the next event
        and the next action is far away (a generator chain break), the
        delivery is hopeless: the ball goes off the pitch and is placed on
        the next spot once its taker is there (the out branch in
        _ball_step) -- instead of rolling tens of metres on its own."""
        d_left = math.hypot(ex - self.bx, ey - self.by)
        t_next = (nxt["t_ms"] / 1000.0) if nxt else t + 3.0
        if d_left > 20.0 and d_left > FLIGHT_V_LO * max(t_next - t - 0.3, 0.2):
            # hopeless delivery: when the next action is a restart the ball
            # still travels to the line first (rule 10) -- only then hidden.
            # With no restart booked it stays visible and rolls on late (a
            # mid-pitch hide is rule 10's violation and a teleport later)
            if nxt is not None and _is_out_restart(nxt) and self.bmode != "out":
                self._send_out(t, nxt)
                return
            if self.bmode != "out":
                self.bmode = "rollp"
                # JOIN_TOP with an ease-up (bv_tgt), not a jump: the ball
                # may already be rolling from the event before
                self.bv_tgt = _clamp(d_left / max(t_next - t, 1.0), 1.2,
                                     JOIN_TOP)
                self.bv = min(max(self.bv, 1.2), self.bv_tgt)
                self.spot = (ex, ey)
                j_n = -1
                for k in range(max(0, self.ep - 1),
                               min(len(self.events), self.ep + 3)):
                    if self.events[k] is nxt:
                        j_n = k
                        break
                self._book_meet(t, j_n)
            return
        self.bmode = "roll"       # no time even at flat sprint: the
        self.broll_point = True   # rolling ball is sent on ahead alone
        self.bv = max(self.bv, 0.5)
        self.spot = (ex, ey)

    def _book_meet(self, t: float, j: int) -> None:
        """Task 08 rule 4 for a late delivery: the rolling ball cannot reach
        event j's spot before the event fires. The taker leaves the spot they
        were booked on and walks to where the ball will actually be at their
        event time, so the event frame shows them AT the ball; the pump then
        has them pick it up and play it from there."""
        if j < 0 or j >= len(self.events) or self.bmode != "rollp":
            return
        ev = self.events[j]
        if _is_out_restart(ev) or ev["type"] in ("substitution", "card"):
            return
        a = self.assigned[j]
        if a is None or a < 0 or not self.on[a]:
            return
        t1 = ev["t_ms"] / 1000.0
        if t1 <= t:
            return
        sx, sy = self.spot
        d = math.hypot(sx - self.bx, sy - self.by)
        # the pace the roll will actually run at (task 10: it may still be
        # accelerating toward bv_tgt from the rebound's landing speed)
        v_ = max(self.bv, self.bv_tgt) if self.bv_tgt >= 0.0 else self.bv
        if d < 1e-6 or d / max(v_, 0.1) <= (t1 - t) + 2.0:
            return  # on time, or close enough that the projection is noise:
            # re-booking on a marginal call drags the taker off a spot the
            # ball does reach (the roll gets re-budgeted faster later), so
            # only a hopelessly late ball -- 2 s or more -- re-books the meet
        frac = max(0.0, min(1.0, v_ * (t1 - t) / d))
        mx = self.bx + (sx - self.bx) * frac
        my = self.by + (sy - self.by) * frac
        old = self.wpt[a]
        self.wpt[a] = [w for w in old if w[3] != j]
        ft, fx, fy = self._free_at(a, t)
        dm = math.hypot(mx - fx, my - fy)
        if ft < t1 and dm <= 0.9 * self.vmax[a] * (t1 - ft):
            self.wpt[a].append((t1, mx, my, j))
        else:
            self.wpt[a] = old  # they cannot make the meet either

    def _start_flight(self, t: float, ox: float, oy: float, ex: float, ey: float,
                      ev: Dict[str, Any], v: float, kick: int = -1,
                      delay: float = 0.0) -> None:
        self.block_j = -1
        if kick >= 0:
            # freeze the kicker through the follow-through: the frame before
            # the flight visibly starts must keep them within 1.2 m
            self.kick_i = kick
            self.kick_t = t
            self.kick_pos = (self.px[kick], self.py[kick])
        v_req = v
        d = math.hypot(ex - ox, ey - oy)
        # grid-aligned flight: n whole 5 Hz frames at cruise v cover d exactly
        # (the ramp is folded into the back-dated clock), so every recorded
        # frame shows the same speed v -- no partial first frame (a second
        # acceleration frame with the ball 3 m from the kicker) and no partial
        # last frame at the landing either
        per = self.periods[self._period(t) - 1]
        pstart = per["start_ms"] / 1000.0
        rel = ((t + delay) - pstart) * 5.0
        g0 = math.ceil(rel - 1e-9)
        if g0 <= rel + 1e-9:
            g0 += 1.0
        g0 = pstart + g0 / 5.0
        if kick >= 0 and ev is not None and ev.get("t_ms") is not None:
            # task 08 rule 4: the kicker's own event frame must still show
            # the ball at their boot. The first flight frame is never that
            # frame or an earlier one -- a kick firing just before its event
            # is already a full 0.2 s underway at frame one of the grid-
            # aligned flight (cruise speed from the back-dated clock), and
            # the event frame would show the actor metres from a ball they
            # just played. The ball waits at the boot until the frame after.
            per_e = self.periods[self._period(ev["t_ms"] / 1000.0) - 1]
            ps_e = per_e["start_ms"] / 1000.0
            f_ev = ps_e + round((ev["t_ms"] / 1000.0 - ps_e) * 5.0) / 5.0
            if g0 <= f_ev + 1e-9:
                g0 = f_ev + 0.2
        n = max(2, int(round(d / (0.2 * v))))
        v = d / (0.2 * n)
        while v > FLIGHT_CAP:  # whole frames only: keep the cap honest
            n += 1
            v = d / (0.2 * n)
        if v_req >= FLIGHT_V_HI:  # keep firm balls clear of the band
            while v < FLIGHT_V_HI and n > 2:
                n -= 1
                v = d / (0.2 * n)
        else:                     # and soft balls soft
            while v > FLIGHT_V_LO and n < 1000:
                n += 1
                v = d / (0.2 * n)
        while v < 1.5 and n > 2:  # and the floor too
            n -= 1
            v = d / (0.2 * n)
        self.bmode = "flight"
        self.framp = True
        if delay > 0.0:
            # a delayed restart kick: the records before g0 hold the ball on
            # the spot, so the restart's own frame shows the kick being taken,
            # not a ball already metres underway (task 08 rule 11)
            self.f0 = g0
        else:
            self.f0 = g0 - 0.2 - v / (2.0 * KICK_A)
        self.fxs, self.fys, self.fxe, self.fye = ox, oy, ex, ey
        self.fd = d
        self.fv = v
        self.fstyle, self.fh = _flight_height(ev, d)
        self.f1 = self.f0 + n * 0.2 + v / (2.0 * KICK_A)
        # task 08: this flight ends in the net (a goal) -- the landing rests
        # the ball on the line instead of routing it on; and any kick releases
        # a keeper's hold on the ball (rule 7)
        self.net_rest = ev is not None and ev.get("outcome") == "goal" and \
            (ev["type"] == "shot" or (ev["type"] == "free_kick"
                                      and ev.get("subtype") == "shoot"))
        if self.net_rest:
            # the retrieval clock starts when the ball LANDS in the net -- a
            # stale net_until would hide the flight mid-air the step after
            # launch (the ball would never be seen crossing the line)
            self.net_until = self.f1 + NET_REST_S
        if kick >= 0:
            self.hold_gk = -1

    def _flight_s(self, tau: float) -> float:
        """Distance flown tau seconds into the current flight. The launch ramp
        (framp) starts the ball at the kicker's boot and reaches cruise speed
        in < 0.21 s, so the one 5 Hz frame that shows the acceleration still
        has the kicker within 1.2 m of the ball."""
        v, tr = self.fv, self.fv / KICK_A
        if self.framp and tau < tr:
            return 0.5 * KICK_A * tau * tau
        base = 0.5 * v * tr if self.framp else 0.0
        t0 = tr if self.framp else 0.0
        return base + v * (tau - t0)

    def _flight_z(self, frac: float) -> float:
        if self.fstyle == "arc":
            return 4.0 * self.fh * frac * (1.0 - frac)
        if self.fstyle == "rise":
            return self.fh * frac
        return 0.1  # flat: rolling height

    def _send_out(self, t: float, ev: Optional[Dict[str, Any]]) -> None:
        """Task 08 rule 10: a ball leaving play travels to the line first --
        it is hidden only once it has crossed, with one visible record AT the
        line (out_glimpse). The exit is the nearest line point, but never
        through the goal mouth (a deflected ball rolling out there between
        the posts reads as a goal)."""
        bx, by = self.bx, self.by
        # candidate exit points: touchline, or the goal line wide of the posts
        cands = []
        ty = 0.0 if by < PITCH_W / 2.0 else PITCH_W
        cands.append((_clamp(bx, 1.0, PITCH_L - 1.0), ty))
        for gx in (0.0, PITCH_L):
            gy = by
            if abs(gy - PITCH_W / 2.0) < 5.5:  # the goal mouth: step aside
                gy = PITCH_W / 2.0 - 5.5 if gy < PITCH_W / 2.0 + 1.0 \
                    else PITCH_W / 2.0 + 5.5
            gy = _clamp(gy, 1.5, PITCH_W - 1.5)
            cands.append((gx, gy))
        ex, ey = min(cands, key=lambda c: math.hypot(c[0] - bx, c[1] - by))
        d = math.hypot(ex - bx, ey - by)
        te = (ev["t_ms"] / 1000.0) if ev is not None else t + 5.0
        if bx <= 0.3 or bx >= PITCH_L - 0.3 or by <= 0.3 or by >= PITCH_W - 0.3:
            # already ON a line -- an off-target shot whose flight landed on
            # the goal line: the goal-mouth step-aside above would measure
            # metres of "distance to the line" and hide the ball mid-pitch
            # (rule 10). Hidden at the crossing, glimpsed there (rule 9)
            self.bmode = "out"
            self.out_since = t
            self.out_glimpse = True
            self.bx = _clamp(bx, 0.0, PITCH_L)
            self.by = _clamp(by, 0.0, PITCH_W)
            return
        if d <= 0.5:
            # already at the line: hidden now, glimpsed at the crossing
            self.bmode = "out"
            self.out_since = t
            self.out_glimpse = True
            self.bx, self.by = ex, ey
            return
        if d > SEND_OUT_TOP * max(te - t - 0.5, 0.0):
            # cannot reach the line before the restart (rare -- a chain break
            # far from any line). The ball still rolls visibly toward the
            # line and hides at the crossing like every other out ball: a
            # mid-pitch hide breaks rule 10 (the QA flags it) and reads as a
            # teleport when the ball comes back on the restart spot
            self.roll_top = SEND_OUT_TOP
        else:
            # an accelerating roll to the line, on the ground, in time for the
            # restart (the ball is dead; nobody needs to touch it)
            self.roll_top = _clamp(d / max(te - t - 1.2, 0.8), 1.2, SEND_OUT_TOP)
        self.bmode = "roll"
        self.broll_point = True
        self.bv = min(self.bv, 2.0)
        self.spot = (ex, ey)
        self.roll_out = True

    def _land(self, t: float, ev: Optional[Dict[str, Any]]) -> None:
        """The flight ends: met, rolling, kept travelling, or out of play."""
        self.bx, self.by = self.fxe, self.fye
        if self.block_j >= 0:
            # task 08 rule 8: the blocked shot bounces off the defender. The
            # deflection is well off the incoming line and back into the field
            # -- never a dead stop (nothing happened) and never a continuation
            # toward the goal it was struck at (which reads as a goal)
            self.block_j = -1
            self.block_shot = -1
            dx, dy = self.fxe - self.fxs, self.fye - self.fys
            dd = math.hypot(dx, dy)
            if dd > 1e-9:
                dx, dy = dx / dd, dy / dd
                gx_sign = 1.0 if dx > 0.0 else -1.0  # the attacked goal
                # task 10: when a deflection side exists that lands nearer
                # where the next possession starts, prefer it -- the join
                # roll then covers a few metres, not thirty
                jx = jy = None
                if ev is not None and ev["type"] not in ("substitution",
                                                         "card"):
                    jx, jy = ev["start"]["x"], ev["start"]["y"]
                best_s, best_sc = 0.0, -1e9
                for s_ in (1.0, -1.0):
                    ox_ = -0.55 * dx - 0.835 * s_ * dy
                    oy_ = -0.55 * dy + 0.835 * s_ * dx
                    # prefer away from the goal, then toward the pitch centre
                    sc = -ox_ * gx_sign + (34.0 - self.by) * oy_ * 0.02
                    if jx is not None:
                        lx_ = self.bx + ox_ * 5.5
                        ly_ = self.by + oy_ * 5.5
                        sc -= 0.05 * math.hypot(jx - lx_, jy - ly_)
                    if sc > best_sc:
                        best_sc, best_s = sc, s_
                ox_ = -0.55 * dx - 0.835 * best_s * dy
                oy_ = -0.55 * dy + 0.835 * best_s * dx
                dist = 4.0 + self.rng.random() * 5.0
                tx = _clamp(self.bx + ox_ * dist, 1.0, PITCH_L - 1.0)
                ty = _clamp(self.by + oy_ * dist, 1.5, PITCH_W - 1.5)
                d2 = math.hypot(tx - self.bx, ty - self.by)
                if d2 > 0.5:
                    # a flat rebound at a fraction of the arrival speed
                    v2 = _clamp(0.45 * self.fv, 3.0, 11.0)
                    nf = max(2, int(round(d2 / (0.2 * v2))))
                    v2 = d2 / (0.2 * nf)
                    self.bmode = "flight"
                    self.framp = False
                    self.f0 = t
                    self.fxs, self.fys, self.fxe, self.fye = \
                        self.bx, self.by, tx, ty
                    self.fd = d2
                    self.fv = v2
                    self.fstyle, self.fh = "flat", 0.0
                    self.f1 = t + nf * 0.2
                    # task 10: when this rebound lands, the deflected ball
                    # joins the next possession (a roll on to the next
                    # event's start, its taker running to meet it)
                    self.block_join = True
                    return
            self.bmode = "place"
            self.spot = (self.bx, self.by)
            return
        if self.block_join:
            # task 10: the blocked shot's rebound is down. Any deferred kick
            # still booked on this ball belongs to the shooting team's dead
            # chain -- the possession has changed. Join the new one instead
            # of parking the ball at the landing spot for seconds (the rule
            # 16 clusters: passes made 20-60 m away from a still ball)
            self.block_join = False
            self._join_next(t, ev)
            return
        if self.net_rest:
            # task 08 rule 5: the ball rests in the net (ON the line -- the
            # schema has no coordinates behind it) until it is retrieved
            self.bmode = "place"
            self.spot = (self.bx, self.by)
            self.bz = 0.0
            self.net_until = t + NET_REST_S
            return
        if self._pending_viable(t):
            # a deferred kick is still booked on this ball (it was held back
            # behind the flight that just landed): the ball waits at the
            # landing spot for its taker -- it leaves the pitch when THEY
            # kick it, and never routes itself on alone past their kick
            self.bmode = "place"
            self.spot = (self.bx, self.by)
            return
        if ev is None or _is_out_restart(ev):
            self._send_out(t, ev)
            return
        sx, sy = ev["start"]["x"], ev["start"]["y"]
        # task 10: the taker may be booked to meet the ball short of the
        # start (task 08 rule 4) -- deliver there, not past them
        mp = self._meet_point(t)
        if mp is not None:
            sx, sy = mp
        d = math.hypot(sx - self.bx, sy - self.by)
        a = self._next_actor()
        if a >= 0 and math.hypot(self.px[a] - self.bx, self.py[a] - self.by) <= ATTACH_R:
            self.bmode = "attach"  # met on arrival (the usual case)
            self.battach = a
            self.spot = (sx, sy)
        elif d > 0.3:
            # the next action starts elsewhere (open-play chain, e.g. a
            # clearance landing far from the next pass, or a few metres off):
            # the ball keeps travelling to it -- never faster than it arrived,
            # so the handover frame shows no speed-up (kick rule: nobody is
            # near it). It does not home onto an approaching player, which
            # would drift it off the spot the next event is booked at.
            t2 = ev["t_ms"] / 1000.0 - t
            top = min(self.fv, FLIGHT_CAP)
            if d > 20.0 and d > top * max(t2, 0.2):
                # the next action is far from where this ball lands and
                # there is no reaching it even flat out (a generator chain
                # break: a shot followed by a restart 30-100 m away): the
                # ball leaves play -- rolling to the line first when the
                # next action IS a restart (rule 10) -- and is placed on the
                # next spot once its taker is there
                if ev is not None and _is_out_restart(ev):
                    self._send_out(t, ev)
                else:
                    # no restart is booked: the ball stays VISIBLE and rolls on
                    # toward the next spot, late -- a mid-pitch hide breaks
                    # rule 10 and reads as a teleport when it comes back
                    self.bmode = "rollp"
                    self.bv = _clamp(d / max(t2 - 0.4, 0.4), 1.2,
                                     min(top, SEND_OUT_TOP))
                    self.spot = (sx, sy)
                    self._book_meet(t, self.ep)
                return
            if d / max(t2, 0.5) > FLIGHT_V_LO and top >= FLIGHT_V_HI:
                # a roll cannot reach the next spot in time: a flat follow-on
                # flight -- never faster than the ball arrived (the handover
                # frame shows no speed-up -- kick rule), never in the mid
                # band while nobody is near it, and just in time like every
                # delivery: it lands ~0.7 s before the next event
                if d >= 0.2 * 2 * FLIGHT_V_HI:
                    vt = _clamp(d / max(t2 - 0.7, 0.4), FLIGHT_V_HI, top)
                    nf = max(2, int(round(d / (0.2 * vt))))
                    while d / (0.2 * nf) > top and nf < 1000:
                        nf += 1
                    while FLIGHT_V_LO < d / (0.2 * nf) < FLIGHT_V_HI and nf > 2:
                        nf -= 1  # nudge up out of the band
                else:
                    nf = max(2, math.ceil(d / (0.2 * FLIGHT_V_LO)))  # soft
                if d / (0.2 * nf) > top:
                    nf += 1  # the physical cap wins
                v = d / (0.2 * nf)
                self.bmode = "flight"
                self.framp = False
                self.f0 = t          # t is on the frame grid: flights land there
                self.fxs, self.fys, self.fxe, self.fye = self.bx, self.by, sx, sy
                self.fd = d
                self.fv = v
                self.fstyle, self.fh = "flat", 0.0
                self.f1 = t + nf * 0.2
            else:
                self.bmode = "rollp"
                need_ = d / max(t2 - 0.4, 0.4)
                top_ = FLIGHT_V_LO
                if a >= 0 and math.hypot(self.px[a] - sx, self.py[a] - sy) <= 15.0:
                    # the taker is at or converging on the spot: a firm
                    # pass-like roll arrives with them, not after their event
                    top_ = FLIGHT_V_HI
                if need_ > FLIGHT_V_LO:
                    # the soft creep cannot arrive by the event: a firm roll
                    # (still never a flight while nobody is near it) beats a
                    # ball that is metres short when its taker acts
                    top_ = FLIGHT_V_HI
                if need_ > top_:
                    # task 10: a follow-on even the firm roll cannot pace
                    # runs on at JOIN_TOP -- still behind the generator's
                    # clock, but there for the next taker -- easing up off
                    # the landing speed (bv_tgt), never a frame speed-up
                    top_ = JOIN_TOP
                    self.bv_tgt = top_
                    self.bv = _clamp(min(self.fv, top_), 1.2, self.bv_tgt)
                else:
                    self.bv = min(top_, max(1.2, need_))
                if need_ > top_:
                    # even the fastest roll lands late: send the taker to meet it
                    self._book_meet(t, self.ep)
                self.spot = (sx, sy)
        else:
            # the receiver is on the end point: the ball waits there for them
            # (rule 4 first branch -- met at the spot)
            self.bmode = "place"
            self.spot = (sx, sy)

    def _join_next(self, t: float, ev: Optional[Dict[str, Any]]) -> None:
        """Task 10: route the deflected ball on to the next possession the
        way a real loose ball moves -- it rolls toward the next event's
        start, paced to arrive just early when the clock allows and never
        above JOIN_TOP (nobody is near it); the next actor is re-booked
        to meet it where it will actually be when it cannot arrive in time."""
        self.pk = -1          # the shooting team's pending kicks died with
        self.rq = -1          # the block; the pump must not park the ball
        self.hold_j = -1      # for a taker who now has nothing to play
        self.hold_pin = False
        if ev is None or ev["type"] in ("substitution", "card") \
                or _is_out_restart(ev):
            # no live next spot to join: the ball waits where it lies (an
            # out restart's own routing -- _send_out -- owns it from here)
            self.bmode = "place"
            self.spot = (self.bx, self.by)
            self.bv_tgt = -1.0
            return
        sx, sy = self._meet_point(t) or self._spot_of(ev)
        d = math.hypot(sx - self.bx, sy - self.by)
        if d <= 2.5:
            # already on the spot: the taker just picks it up off the ground
            self.bmode = "place"
            self.spot = (sx, sy)
            self.bv_tgt = -1.0
            return
        t1 = ev["t_ms"] / 1000.0
        need = d / max(t1 - t - 0.3, 0.3)
        self.bmode = "rollp"
        self.spot = (sx, sy)
        # off the rebound's landing speed, easing toward the pace the clock
        # asks for (a jump straight up to it would be a kick nobody made);
        # JOIN_TOP, not SEND_OUT_TOP -- a deflected ball that is behind the
        # generator's clock may run this fast to be there in time
        self.bv_tgt = _clamp(need, 1.2, JOIN_TOP)
        self.bv = _clamp(min(self.fv, JOIN_TOP), 1.2, self.bv_tgt)
        if need > JOIN_TOP:
            # cannot arrive by the event: the taker comes to meet the ball
            self._book_meet(t, self.ep)

    def _feet(self, a: int) -> Tuple[float, float]:
        """The ball at a player's feet: 0.3-0.8 m ahead of them toward the
        spot they will kick from, and on the spot itself once they are there
        (task 06 rule 3). Anchored to the player: wherever they stand, the
        ball is within 0.6 m of them -- a kick off it always has a toucher."""
        sx, sy = self.spot
        dx, dy = sx - self.px[a], sy - self.py[a]
        g = math.hypot(dx, dy)
        if g <= 0.7:  # standing on the spot: the ball rests on it
            return (sx, sy)
        off = min(0.6, g - 0.7)
        return (self.px[a] + dx / g * off, self.py[a] + dy / g * off)

    def _roll_toward(self, tx: float, ty: float) -> None:
        dx, dy = tx - self.bx, ty - self.by
        dd = math.hypot(dx, dy)
        if dd <= self.bv * DT:
            self.bx, self.by = tx, ty
        elif dd > 1e-9:
            self.bx += dx / dd * self.bv * DT
            self.by += dy / dd * self.bv * DT

    def _ball_step(self, t: float) -> None:
        """Advance the ball one 0.1 s step (after the players have moved)."""
        ev = self.events[self.ep] if self.ep < len(self.events) else None
        # the next event is a restart after the ball left the pitch: once its
        # flight/dribble has ended, the ball is off the pitch being retrieved,
        # until the taker reaches the spot (only exception: the taker is at
        # the spot already and the ball has been placed for them)
        if self.net_rest and self.bmode not in ("out", "flight") \
                and t >= self.net_until:
            # task 08 rule 5: the goal ball has rested in the net long enough
            # -- it is retrieved (hidden at the line, where it crossed) until
            # the restart gathers it
            self.bmode = "out"
            self.out_since = t
            self.out_glimpse = False
            self.net_rest = False
        if ev is not None and _is_out_restart(ev) and self.bmode != "out" \
                and self.hold_gk < 0 and not self.roll_out and not self.net_rest:
            # (a goal ball resting in the net is exempt: the net_rest branch
            # above hides it once it has rested its full NET_REST_S -- task 08
            # rule 5, the ball stays visible in the goal >= 2 s)
            sx, sy = self._spot_of(ev)
            a = self._next_actor()
            at_spot = self.bmode == "attach" and a >= 0 and self.battach == a and \
                math.hypot(self.px[a] - sx, self.py[a] - sy) <= APPEAR_R
            if self.bmode not in ("flight", "dribble") and not at_spot and \
                    not self._pending_ready(t, ev) and \
                    not self._pending_viable(t):
                # the previous action's delivery is still being played (a
                # taker converging on the ball): the out window opens when it
                # finishes, not now -- and it opens at the LINE, not wherever
                # the ball happens to be (rule 10)
                self._send_out(t, ev)
        if self.hold_j >= 0:
            # the held kick: the ball sits at the kicker's feet (attach, kept
            # alive by the hold guard below) until the last moment a firm
            # ball still arrives ~0.3 s before the next event
            if t >= self.hold_t - 1e-9 and self.rec_att == self.battach:
                a = self.battach
                vd = math.hypot(self.vx[a], self.vy[a]) if a >= 0 else 0.0
                per = self.periods[self._period(t) - 1]
                rel = (t - per["start_ms"] / 1000.0) * 5.0
                on_rec = abs(rel - round(rel)) < 1e-6
                deadline = ((self.events[self.hold_j + 1]["t_ms"] / 1000.0 - 0.3)
                            if self.hold_j + 1 < len(self.events) else t + 3.0)
                bx0, by0 = self.rec_b if self.hold_pin else self._feet(a)
                boot_d = math.hypot(self.px[a] - bx0, self.py[a] - by0) if a >= 0 else 9.9
                if not on_rec or ((vd > 1.5 or boot_d > 1.0) and t + 0.35 +
                                  math.hypot(self.hold_end[0] - self.bx,
                                             self.hold_end[1] - self.by)
                                  / FLIGHT_CAP <= deadline):
                    # wait for a record step and a planted boot at the ball:
                    # the flight must grow out of the frame that shows the
                    # touch (the record runs after this step, so firing on a
                    # record step makes that frame the boot -- kick rule)
                    self.hold_t = t + (0.1 if on_rec else 0.05)
                else:
                    j = self.hold_j
                    self.hold_j = -1
                    self.hold_pin = False
                    nxt = self.events[j + 1] if j + 1 < len(self.events) else None
                    gap = (nxt["t_ms"] / 1000.0 - t) if nxt else 3.0
                    ex, ey = self.hold_end
                    # the boot is the ball at their feet right now: firing on
                    # a record step, the touch frame records it there and the
                    # f0 back-dating makes the next frame land at exactly
                    # feet + 0.2*v -- cruise from the first flight frame.
                    # A pinned restart fires off the spot the records showed
                    # the ball on (rec_b), not off the moving feet
                    ox, oy = bx0, by0
                    if a is not None and a >= 0:
                        db = math.hypot(self.px[a] - ox, self.py[a] - oy)
                        if db > 0.9:
                            # forced to fire while the taker is still a stride
                            # from the spot: the boot meets the ball short of
                            # it (the touch frame stays within 1.2 m, and the
                            # one-frame hop is far below the kick threshold)
                            f = (db - 0.9) / db
                            ox += (self.px[a] - ox) * f
                            oy += (self.py[a] - oy) * f
                    self.bx, self.by = ox, oy
                    d = math.hypot(ex - ox, ey - oy)
                    if d < 0.25:
                        # nothing to deliver (the target is the spot itself):
                        # the ball just stays where the records showed it
                        self.bmode = "place"
                        self.spot = (ox, oy)
                    else:
                        j_ev = self.events[j]
                        self._start_flight(
                            t, ox, oy, ex, ey, j_ev,
                            _clamp(d / max(gap - 0.7 - self._follow_on_s(nxt, ex, ey),
                                           0.3), FLIGHT_V_HI, FLIGHT_CAP),
                            kick=a,
                            delay=0.25 if (_is_out_restart(j_ev)
                                           or j_ev["type"] == "free_kick") else 0.0)
                    if self.rq >= 0:
                        # a launch held back while this hold was pending: the
                        # held kick is away (or nothing was left to deliver) --
                        # replay the held launch once its taker has the ball
                        self.pk = self.rq
                        ev2 = self.events[self.rq]
                        self.pk_end = (ev2["end"]["x"], ev2["end"]["y"])
                        self.pk_lim = t + 8.0
                        n2 = self.events[self.rq + 1] \
                            if self.rq + 1 < len(self.events) else None
                        if n2 is not None:
                            # an arc delivery still has to peak inside its
                            # window: cap the replay deadline the same way
                            # the deferral branch does
                            dl2 = math.hypot(
                                ev2["end"]["x"] - self.bx,
                                ev2["end"]["y"] - self.by) / FLIGHT_CAP
                            self.pk_lim = min(
                                self.pk_lim,
                                self._kick_latest(
                                    ev2, dl2, n2["t_ms"] / 1000.0) + dl2)
                        self.rq = -1
        was_flight = self.bmode == "flight" or self.bmode == "dribble"
        if self.bmode == "flight":
            tau = t - self.f0
            if tau >= self.f1 - self.f0 - 1e-6:
                # the landing keeps the flight's final height: an off-target
                # shot must still be over the bar (z >= 2.6) in the one
                # visible record at the line (rule 9)
                self.bz = self._flight_z(1.0)
                self._land(t, ev)
            else:
                frac = min(1.0, self._flight_s(tau) / self.fd)
                if tau <= 0.0:
                    frac = 0.0  # a delayed kick: the ball waits on its spot
                self.bx = self.fxs + (self.fxe - self.fxs) * frac
                self.by = self.fys + (self.fye - self.fys) * frac
                self.bz = self._flight_z(frac)
        elif self.bmode == "dribble":
            f = _clamp((t - self.f0) / max(self.f1 - self.f0, 1e-9), 0.0, 1.0)
            self.bx = self.fxs + (self.fxe - self.fxs) * f
            self.by = self.fys + (self.fye - self.fys) * f
            self.bz = 0.1
            if f >= 1.0:  # carry over: met, rolling or out, like a landing
                self._land(t, ev)
        elif self.bmode == "out":
            if not self.out_glimpse:
                self.bz = -1.0
            if ev is not None and t - self.out_since >= OUT_MIN_S \
                    and ev["type"] not in ("substitution", "card"):
                # a sub/card is not a ball event: its "spot" (the halfway
                # line) is not where a ball gone out may reappear -- after a
                # goal the stoppage can hold subs 70+ s before the kick-off,
                # and an early centre-spot reveal reads as a 50 m teleport
                a = self.assigned[self.ep]
                sx, sy = self._spot_of(ev)
                if a is None or a < 0 or not self.on[a]:
                    # the named taker is off the pitch (substituted while the
                    # ball was out): hand the restart to the nearest on-pitch
                    # teammate, who walks over and places the ball
                    best, bd = -1, 1e9
                    for i in self.actives:
                        if self.team[i] != ev["team_id"] or self.role[i] == "GK":
                            continue
                        d = math.hypot(self.px[i] - sx, self.py[i] - sy)
                        if d < bd:
                            best, bd = i, d
                    if best >= 0:
                        self.assigned[self.ep] = best
                        self.wpt[best] = [w for w in self.wpt[best]
                                          if w[3] != self.ep]
                        self.wpt[best].append((ev["t_ms"] / 1000.0, sx, sy, self.ep))
                        a = best
                if a is not None and a >= 0 and self.on[a]:
                    d = math.hypot(self.px[a] - sx, self.py[a] - sy)
                    # the reveal may not teleport: coming back mid-pitch from a
                    # line hide more than 3 s before the restart reads as a
                    # jump (a short retrieve of <= 12 m is fine whenever)
                    reveal_ok = t >= ev["t_ms"] / 1000.0 - 3.0 or \
                        math.hypot(sx - self.bx, sy - self.by) <= 12.0
                    if reveal_ok and (
                            d <= APPEAR_R or (d <= APPEAR_R + 1.0 and
                                              t >= ev["t_ms"] / 1000.0 - 0.25)):
                        # a player places the ball on the restart spot (the
                        # relaxation catches a taker one step from the spot
                        # just before the restart, so the restart frame shows
                        # the ball on it)
                        self.bmode = "attach"
                        self.battach = a
                        self.spot = (sx, sy)
                        self.bx, self.by = sx, sy
                        # the retrieval is over: a stale net_until must not
                        # re-hide the ball the step after the taker placed it
                        # (a one-frame glimpse mid-pitch reads as a vanish)
                        self.net_rest = False
        else:
            if self.bmode == "attach":
                a = self.battach
                keep = self.hold_j >= 0 or \
                    (self.pk >= 0 and self.assigned[self.pk] == a) or \
                    (self.ep > 0 and a == self.assigned[self.ep - 1]) or \
                    (a == self.hold_gk and self.on[a])
                if not keep and (a < 0 or not self.on[a] or a != self._next_actor()):
                    # the holder is no longer the next actor: the ball becomes
                    # loose and routes itself to the next action's spot below
                    self.bmode = "place"
                    self.spot = (self.bx, self.by)
                else:
                    if not keep and ev is not None:
                        self.spot = self._spot_of(ev)
                    if self.hold_pin and self.hold_j >= 0:
                        # a held restart: the ball waits on its own event's
                        # spot until played (the taker stands over it)
                        h_ev = self.events[self.hold_j]
                        self.bx, self.by = self._spot_of(h_ev)
                    else:
                        self.bx, self.by = self._feet(a)
                    # task 08 rule 7: a caught ball rides in the keeper's
                    # hands at chest height, not at their feet
                    self.bz = 1.0 if a == self.hold_gk else 0.1
            elif self.bmode == "roll":
                if self.broll_point:
                    # a late kick played on the run: the ball accelerates
                    # gently toward the target, never out of the slow band
                    # (nobody is near it, so it must not look like a kick).
                    # A ball being sent off the pitch (rule 10) may roll up
                    # to SEND_OUT_TOP -- it is dead, and has a line to reach.
                    top = self.roll_top if self.roll_out else FLIGHT_V_LO
                    self.bv = min(self.bv + ROLL_ACC * DT, top)
                    self._roll_toward(self.spot[0], self.spot[1])
                    dd = math.hypot(self.spot[0] - self.bx,
                                    self.spot[1] - self.by)
                    if dd <= 0.3:
                        if self.roll_out:
                            # crossed the line: hidden, with one last visible
                            # record AT the crossing (rule 10)
                            self.bmode = "out"
                            self.out_since = t
                            self.out_glimpse = True
                            self.roll_out = False
                            self.bz = 0.1
                        else:
                            self.bmode = "place"
                else:
                    # slows to ROLL_FLOOR, but never dies while unmet
                    self.bv = max(ROLL_FLOOR, self.bv - ROLL_DECEL * DT)
                    a = self._next_actor()
                    if a >= 0:
                        self._roll_toward(self.px[a], self.py[a])
                    else:
                        self._roll_toward(self.spot[0], self.spot[1])
                self.bz = 0.1
            elif self.bmode == "rollp":
                if self.bv_tgt >= 0.0 and self.bv < self.bv_tgt:
                    # task 10: ease up to the booked pace (ROLL_ACC) instead
                    # of jumping to it -- a standstill -> 11 m/s jump in one
                    # frame is a kick nobody made (task 06 rule 5)
                    self.bv = min(self.bv_tgt, self.bv + ROLL_ACC * DT)
                self._roll_toward(self.spot[0], self.spot[1])
                self.bz = 0.1
                if math.hypot(self.spot[0] - self.bx, self.spot[1] - self.by) <= 0.3:
                    self.bmode = "place"
                    self.bv_tgt = -1.0
            else:  # place
                self.bz = 0.0
                # a loose ball lying away from the next action's spot creeps
                # there (never faster than a soft pass: nobody is near it).
                # A pending deferred kick blocks that only when its taker is
                # someone else: a ball that rolls away from its own taker
                # never gets picked up -- but when the pk taker IS the next
                # actor the roll runs toward them, not away.
                if ev is not None and ev["type"] not in ("substitution", "card") \
                        and not self.net_rest:
                    # (a goal ball resting in the net never creeps to the next
                    # spot -- it would roll back out of the goal mid-rest,
                    # task 08 rule 5)
                    # task 08 rule 12: a substitution carries a pitch position
                    # -- the ball must not route itself there
                    a = self._next_actor()
                    # task 10: a deferred kick only holds the ball while its
                    # taker is actually closing on it -- a taker 5+ m away
                    # (or off the pitch) is not collecting this ball any time
                    # soon, and events keep firing around a ball lying still
                    pk_open = self.pk < 0
                    if not pk_open:
                        ta = self.assigned[self.pk]
                        pk_open = ta is None or ta < 0 or not self.on[ta] or \
                            math.hypot(self.px[ta] - self.bx,
                                       self.py[ta] - self.by) > 5.0
                    if pk_open or (a >= 0 and a == self.assigned[self.pk]):
                        sx_, sy_ = self._meet_point(t) or self._spot_of(ev)
                        dsx, dsy = sx_ - self.bx, sy_ - self.by
                        if math.hypot(dsx, dsy) > 2.5:
                            self.bmode = "rollp"
                            t2 = max(ev["t_ms"] / 1000.0 - t - 0.4, 0.5)
                            need_ = math.hypot(dsx, dsy) / t2
                            top_ = FLIGHT_V_HI if need_ > FLIGHT_V_LO else FLIGHT_V_LO
                            if a >= 0 and math.hypot(
                                    self.px[a] - sx_, self.py[a] - sy_) <= 15.0:
                                # the taker is at or converging on the same
                                # point: a firm pass-like roll to them beats a
                                # soft creep that arrives after their event
                                top_ = FLIGHT_V_HI
                            if need_ > top_:
                                # task 10: behind the generator's clock even
                                # at the firm roll -- run on at JOIN_TOP (the
                                # creep already eases up through bv_tgt)
                                top_ = JOIN_TOP
                            self.bv_tgt = min(top_, max(1.2, need_))
                            self.bv = min(3.5, self.bv_tgt)
                            self.spot = (sx_, sy_)
                            if need_ > top_:
                                # late even at the firm roll: meet the ball
                                self._book_meet(t, self.ep)
                        elif ev["type"] in ("pass", "cross", "dribble",
                                            "clearance") and a >= 0 and \
                                math.hypot(self.px[a] - self.bx,
                                           self.py[a] - self.by) > 6.0:
                            # the ball is already on its spot but its taker
                            # is still seconds out (a generator chain break,
                            # events ~2 s apart): it rolls gently toward
                            # them -- rule 4's receiver roll -- instead of
                            # lying still-alone waiting
                            self.bmode = "roll"
                            self.broll_point = False
                            # from a standstill: a jump above ~4 m/s would
                            # look like a kick nobody made (rule 5)
                            self.bv = _clamp(self.bv, ROLL_FLOOR, 2.0)
            # a player arriving at a loose ball takes it -- but never a ball
            # being sent out (roll_out): it is dead, and its next transition
            # is the line crossing (rule 10's hide). Picking it up at
            # ATTACH_R short of the line leaves it resting visible at a
            # taker's feet instead, and the out-reveal never gets to run
            if self.bmode in ("place", "roll", "rollp") \
                    and not self.roll_out:
                a = self._next_actor()
                if a >= 0 and \
                        math.hypot(self.px[a] - self.bx, self.py[a] - self.by) <= ATTACH_R:
                    self.bmode = "attach"
                    self.battach = a
                    self.roll_out = False
                    if not was_flight:
                        # a step-on pickup jumps to the feet; a ball that just
                        # LANDED this step stays on its landing spot for the
                        # record -- a fast delivery's last frame plus the feet
                        # offset can top 40 m/s as one visible step
                        self.bx, self.by = self._feet(a)
                    if ev is not None:
                        self.spot = self._spot_of(ev)
        # a deferred kick: the taker was a step or two from the ball when the
        # event fired -- play it the moment they reach it (a flight already
        # under way finishes first; the ball is never sent off without a
        # toucher). If they never make it before the next event, the ball is
        # sent on ahead as a rolling redirect.
        if self.pk >= 0:
            a = self.assigned[self.pk]
            nxt = self.events[self.pk + 1] if self.pk + 1 < len(self.events) else None
            t_lim = max((nxt["t_ms"] / 1000.0 - 0.05) if nxt else t + 3.0,
                        self.pk_lim)
            # firing past this point would put an arc's peak outside its
            # event window (a ground kick just gets late): the deadline the
            # deferral branch computed, re-checked against the live ball
            latest = 1e9
            if nxt is not None:
                ev2 = self.events[self.pk]
                dl2 = math.hypot(self.pk_end[0] - self.bx,
                                 self.pk_end[1] - self.by) / FLIGHT_CAP
                latest = self._kick_latest(ev2, dl2, nxt["t_ms"] / 1000.0)
            # fire only once a record has shown the taker on the ball AND
            # they are still on it: the pre-flight frame then has them
            # within 1.2 m (kick rule). A taker who drifted off in the gap
            # since that record re-attaches first (their pk-chase target is
            # the ball) or the deadline redirects
            if a is not None and a >= 0 and self.on[a] and self.rec_att == a \
                    and t <= latest and \
                    math.hypot(self.px[a] - self.bx, self.py[a] - self.by) <= 1.0:
                j = self.pk
                self.pk = -1
                self._launch(j, t)
                if self.rq >= 0:
                    # the launch held back while this delivery was pending:
                    # replay it once its own taker has the ball
                    self.pk = self.rq
                    ev2 = self.events[self.rq]
                    self.pk_end = (ev2["end"]["x"], ev2["end"]["y"])
                    self.pk_lim = t + 8.0
                    n2 = self.events[self.rq + 1] \
                        if self.rq + 1 < len(self.events) else None
                    if n2 is not None:
                        # an arc delivery still has to peak inside its
                        # window: cap the replay deadline the same way
                        # the deferral branch does
                        dl2 = math.hypot(ev2["end"]["x"] - self.bx,
                                         ev2["end"]["y"] - self.by) / FLIGHT_CAP
                        self.pk_lim = min(
                            self.pk_lim,
                            self._kick_latest(
                                ev2, dl2, n2["t_ms"] / 1000.0) + dl2)
                    self.rq = -1
            elif a is not None and a >= 0 and self.on[a] and \
                    self.bmode in ("place", "roll", "rollp") and \
                    math.hypot(self.px[a] - self.bx, self.py[a] - self.by) <= ATTACH_R:
                # the taker reaches a loose ball: straight to their feet (the
                # kick fires after the next record shows it there). A ball
                # that just landed this step stays on its landing spot -- the
                # record must not show cruise speed plus the feet offset
                self.bmode = "attach"
                self.battach = a
                self.spot = self.pk_end
                if not was_flight:
                    self.bx, self.by = self._feet(a)
            elif t >= t_lim:
                # the deferred kick never happened. Exception: the ball is
                # already sitting at the next event's spot with its taker
                # standing over it (a restart the taker reached while the old
                # kick was still pending) -- hiding or rolling it away from
                # there would break the restart placement
                if not (self.bmode == "attach" and nxt is not None and
                        math.hypot(self.bx - nxt["start"]["x"],
                                   self.by - nxt["start"]["y"]) <= 1.5):
                    self._redirect_or_hide(t, self.pk_end[0], self.pk_end[1], nxt)
                if self.rq >= 0:
                    # the launch held back behind this dead kick still gets
                    # its turn: its taker picks the (redirected) ball up and
                    # plays it
                    self.pk = self.rq
                    ev2 = self.events[self.rq]
                    self.pk_end = (ev2["end"]["x"], ev2["end"]["y"])
                    self.pk_lim = t + 4.0
                    n2 = self.events[self.rq + 1] \
                        if self.rq + 1 < len(self.events) else None
                    if n2 is not None:
                        # an arc delivery still has to peak inside its
                        # window: cap the replay deadline the same way
                        # the deferral branch does
                        dl2 = math.hypot(ev2["end"]["x"] - self.bx,
                                         ev2["end"]["y"] - self.by) / FLIGHT_CAP
                        self.pk_lim = min(
                            self.pk_lim,
                            self._kick_latest(
                                ev2, dl2, n2["t_ms"] / 1000.0) + dl2)
                    self.rq = -1
                else:
                    self.pk = -1

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
        # task 08 rules 3/13: a kick-off is coming within KO_GUARD_S. Nothing
        # after it may be assigned yet, and waypoints already booked for events
        # after it are dropped -- players who set off early for a post-kick-off
        # restart spot leave both teams out of formation at the kick-off frame
        ko_guard = -1
        for j in range(self.ep, len(events)):
            e = events[j]
            if e["t_ms"] / 1000.0 - t > KO_GUARD_S:
                break
            if e.get("subtype") == "kick_off":
                # a kick-off due THIS tick (t=0 or the half-start tick) fires
                # immediately after this call: the events that follow it are
                # bookable now. Waiting for the next decide tick costs the
                # opener's actors the half-second that separates arriving at
                # their event spot and still metres short of it (rule 4)
                if e["t_ms"] / 1000.0 > t + 1e-9:
                    ko_guard = j
                break
        # actor look-ahead
        for k in range(LOOKAHEAD_EVENTS):
            j = self.ep + k
            if j >= len(events):
                break
            if ko_guard >= 0 and j > ko_guard:
                break  # the kick-off formation holds until the ball is played
            if self.assigned[j] is not None:
                continue
            te = events[j]["t_ms"] / 1000.0
            window = LOOKAHEAD_S
            if events[j]["type"] in _RESTART_TYPES or \
                    (events[j]["type"] == "pass"
                     and events[j].get("subtype") == "kick_off"):
                window = 120.0  # restarts: the taker walks there during the
                                 # delay (kick-offs too, so the taker is on the
                                 # centre spot when the second half starts)
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
                        # players walking off after a sub take no slot: the
                        # zip would otherwise hand the departing walker the
                        # slot the incoming substitute should stand in
                        on_pitch = {tm: sorted(i for i in self._on_pitch_now(tm)
                                               if self.walkoff_tgt[i] is None)
                                    for tm in (HOME, AWAY)}
                        self.setpiece_map = _setpiece(ev, self.idx_of, on_pitch, self.role)
                        self.setpiece_cache[self.ep] = self.setpiece_map
        next_ev = events[self.ep] if self.ep < len(events) else None
        if next_ev is None or next_ev["type"] in ("substitution", "card"):
            spot = (self.bx, self.by)  # task 08 rule 12: a sub is not a spot
        else:
            spot = self._spot_of(next_ev)
        # virtual ball for the shape: the real one while it is visible, eased
        # toward the restart spot at <= 10 m/s while it is off the pitch
        if self.bmode == "out":
            vtx, vty = spot
        else:
            vtx, vty = self.bx, self.by
        vm = math.hypot(vtx - self.vbx, vty - self.vby)
        if vm > 1e-9:
            step = min(vm, 5.0)  # 10 m/s per 0.5 s tick
            self.vbx += (vtx - self.vbx) / vm * step
            self.vby += (vty - self.vby) / vm * step
        # smoothed ball for the shape
        bx, by = self.vbx, self.vby
        self.sbx += (bx - self.sbx) * SMOOTH
        self.sby += (by - self.sby) * SMOOTH
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
                        # a spot within 2.2 m of a goal line (a foul by the
                        # corner flag) pushes the goal-side offset off the
                        # pitch: the boundary clamp then pins the chaser
                        # exactly on the line, metres short of their target
                        # forever -- a 20 s statue (task 08 rule 13)
                        ux = _clamp(ux, 0.6, PITCH_L - 0.6)
                        chasers[k] = ((ux, spot[1]), 0.6)  # presses less often

        # per-player targets
        for i in list(self.actives):
            w = self.wpt[i]
            if w:
                w = [x for x in w if x[0] > t + 0.05]
                if ko_guard >= 0:
                    kept = []
                    for x in w:
                        if x[3] > ko_guard:
                            # booked for after the kick-off: dropped, and the
                            # event goes back into the pool for re-choosing
                            # once the kick-off has been played
                            self.assigned[x[3]] = None
                        else:
                            kept.append(x)
                    w = kept
                self.wpt[i] = w
            if self.walkoff_tgt[i] is not None:
                self.tgx[i], self.tgy[i] = self.walkoff_tgt[i]  # type: ignore[assignment]
                # jog off (task 08 rule 12): the sooner they leave, the sooner
                # the substitute may step on
                self.cruise[i] = JOG * self.work[i]
                continue
            if self.pk >= 0 and self.assigned[self.pk] == i:
                # a deferred kick waits on this player: they go to the ball
                # and play it (nothing else matters until they have) -- even
                # if a waypoint is still open. While the ball is in the air
                # they run to where it lands, not to where it is now
                # (chasing the live position is a pursuit they can never win).
                # They arrive just in time for the deadline (pk_lim), not at
                # full sprint: a taker with ten spare seconds trots, one with
                # two sprints -- km/90 and the sprint counts are calibrated
                # ranges, not free budget
                if self.bmode == "flight" and self.f1 > t:
                    self.tgx[i], self.tgy[i] = self.fxe, self.fye
                else:
                    self.tgx[i], self.tgy[i] = self.bx, self.by
                d = math.hypot(self.tgx[i] - self.px[i], self.tgy[i] - self.py[i])
                t_rem = max(self.pk_lim - t - 0.6, 0.4)
                top = self._sprint_top(i)
                # a fetched ball is a hard run, not a sprint: full-sprint
                # fetches blew the sprint-per-90 budget
                self.cruise[i] = min(top, max(1.2 * d / t_rem, 4.0), FETCH_TOP)
                continue
            if self.hold_j >= 0 and self.assigned[self.hold_j] == i:
                # a held kick: they stand over the ball until they play it
                # (waypoints included -- a carrier who reaches the kick spot
                # plants there, they do not run through their own kick).
                # A pinned restart hold (ball on the spot, not at feet) brings
                # them onto the spot first -- the touch frame needs them
                # within 1.2 m of the ball
                self.tgx[i], self.tgy[i] = self.bx, self.by
                d = math.hypot(self.bx - self.px[i], self.by - self.py[i])
                if d > 4.0:  # still arriving: hurry
                    self.cruise[i] = self._sprint_top(i)
                else:
                    self.cruise[i] = WALK if d > 0.6 else 0.0
                continue
            if self.kick_i == i and t < self.kick_t + 0.4:
                # they just struck one: plant through the kick where they hit
                # it, don't chase the flight (kick-rule frame)
                self.tgx[i], self.tgy[i] = self.kick_pos
                self.cruise[i] = 0.0
                continue
            if w:
                continue  # waypoint cruise is recomputed every step
            if self.setpiece_map and i in self.setpiece_map:
                self.tgx[i], self.tgy[i] = self.setpiece_map[i]
                d = math.hypot(self.tgx[i] - self.px[i], self.tgy[i] - self.py[i])
                # task 08 rule 3: gathering for a kick-off after a goal can
                # mean 40-50 m to walk -- the far half hurries
                self.cruise[i] = WALK if d < 18.0 else \
                    (JOG * self.work[i] if d < 40.0 else RECOVER_TOP)
                continue
            base = GK_JOG if self.role[i] == "GK" else JOG * self.work[i]
            top = self._sprint_top(i)  # sprint cruise
            if i in chasers:
                tx, ty = chasers[i][0]
                # stand off 1.2 m short of the spot, always: the actor (the
                # restart taker, the receiver) stands on it, and converging
                # on the exact point is a permanent shoving match -- the
                # close-range gate let a chaser step onto a corner taker
                # planted at the flag and stand inside 0.5 m of them for
                # the whole dead-ball wait (task 08 rule 14)
                cdx, cdy = self.px[i] - tx, self.py[i] - ty
                cdd = math.hypot(cdx, cdy)
                if cdd > 1e-6:
                    tx += cdx / cdd * 1.2
                    ty += cdy / cdd * 1.2
                self.tgx[i], self.tgy[i] = tx, ty
                if t >= self.sprint_until[i] and t >= self.chase_ok[i] and \
                        self.nspr[i] < SPRINT_MAX and \
                        rng.random() < CHASE_SPRINT_P * chasers[i][1] * self.bias[i]:
                    self.sprint_until[i] = t + 2.6
                    self.chase_ok[i] = t + 18.0
                    self.nspr[i] += 1
                self.cruise[i] = top if t < self.sprint_until[i] \
                    else PRESS_RUN
            else:
                u, y = self._shape_target(i, next_team)
                # wander noise, re-rolled every ~3 s (centre-backs wander more)
                if t > self.noise_t[i]:
                    # quiet-draw lift: a player pacing under the km/90 floor
                    # re-rolls their wander target sooner and further out --
                    # less standing at the spot, more walking to it (distance
                    # without top speed). Gated on the same projection as the
                    # distance governor, so it self-regulates: once the pace
                    # is back in range the wander shrinks to normal.
                    quiet = t > 2700.0 and self.role[i] != "GK" \
                        and self.rdist[i] * 5.4 / t < 9.4
                    self.noise_t[i] = t + (1.0 + rng.random() * 1.2 if quiet
                                           else 2.0 + rng.random() * 2.0)
                    ang = rng.random() * 6.2831853
                    r = (NOISE_DF if self.role[i] == "DF" else NOISE_R) * rng.random()
                    if quiet:
                        r *= 3.0
                    self.nx[i] = math.cos(ang) * r
                    self.ny[i] = math.sin(ang) * r
                self.tgx[i], self.tgy[i] = u + self.nx[i], y + self.ny[i]
                # task 06: walk when the shape is at your feet, jog when it is
                # close by, run with purpose when the play comes your way.
                # Keepers sit this out: their published window is 4.5-7.0
                # km/90, and run-tier bursts after a high line blow straight
                # through its ceiling -- GK_JOG is their pace, full stop.
                dsh = math.hypot(self.tgx[i] - self.px[i], self.tgy[i] - self.py[i])
                if self.role[i] == "GK":
                    pass
                elif dsh < SHAPE_WALK_R:
                    base = SHAPE_WALK
                elif dsh < SHAPE_JOG_R:
                    # work rate widens the jog inside the band, but the band
                    # itself has a fixed ceiling (a 1.1-work jogger at 2.97
                    # m/s eats into the same km/90 budget as the run tier)
                    base = min(SHAPE_JOG * self.work[i], SHAPE_JOG)
                else:
                    # the run tier is the team-shape pace: work rate scales
                    # the jog, not this -- a 1.1-work forward at 5.4 m/s for a
                    # quarter of the match blows straight past the published
                    # 12.3 km/90 ceiling while the 0.9-work defenders idle at
                    # the floor
                    base = min(SHAPE_RUN, 0.85 * top)
                # distance governor: the published ceiling is 12.3 km/90 --
                # a player whose projection paces past it eases off the
                # discretionary shape work (ball-driven runs -- chases,
                # fetches, bursts -- keep their speed: deadlines beat
                # budgets). Engaged from the second half on: early-match
                # pace runs hot while legs are fresh, so an early
                # projection would slow down half the team; never slows
                # below the walk tier.
                if t > 2700.0 and self.role[i] != "GK":
                    # projected km/90 = metres * 5.4 / seconds
                    proj = self.rdist[i] * 5.4 / t
                    if proj > 12.05:
                        base = max(base * (1.0 - 0.25 * (proj - 12.05)),
                                   SHAPE_WALK)
                    elif proj < 9.4:
                        # and the mirror image: the published floor is
                        # 8.5 km/90 -- a player pacing under it stretches
                        # their legs (the receiver rolls and arc-aware
                        # deadlines of task 06 shortened the ball-driven
                        # runs the quiet half of the team used to make)
                        base = min(base * 1.5, SHAPE_RUN)
                # a burst commitment from an earlier tick keeps its sprint
                # cruise until it expires (like the chaser branch); a recovery
                # run is a hard run, not a sprint (task 06: recovery runs at
                # 4-7 m/s -- sprints are the stochastic budget: chasers,
                # bursts, runs in behind)
                self.cruise[i] = top if t < self.sprint_until[i] else \
                    RECOVER_TOP if t < self.recover_until[i] else base
                # defender stretched far behind the moving line: catch it up at
                # rising speed, capped at a hard run (deterministic -- the DF
                # speed floor cannot rely on bias-scaled probabilities, but
                # neither should it burn the sprint budget)
                if self.role[i] == "DF":
                    dd_ = math.hypot(self.tgx[i] - self.px[i], self.tgy[i] - self.py[i])
                    if dd_ > 14.0 and self.cruise[i] < RECOVER_TOP:
                        self.cruise[i] = _clamp(JOG * self.work[i]
                                                + 0.55 * (dd_ - 14.0),
                                                base, RECOVER_TOP)
                # occasional burst: sprint to keep the shape instead of jogging
                if self.role[i] != "GK" and t >= self.sprint_until[i] \
                        and self.nspr[i] < SPRINT_MAX \
                        and math.hypot(u - self.px[i], y - self.py[i]) > 8.0 \
                        and rng.random() < BURST_P * (0.5 + 0.5 * self.bias[i]):
                    self.sprint_until[i] = t + 2.6
                    self.nspr[i] += 1
                # sprint floor: the published floor is 5 sprints/90 and the
                # stochastic budget cannot be relied on to provide it (a
                # quiet draw lands under it), so by t = 600*(k+1) every
                # outfielder must hold k+1 recorded episodes -- if the draws
                # have not delivered, one is scheduled now. It runs into space
                # toward the attack, not at the shape spot (arriving 2 m
                # away is no episode -- the recorder needs 5 frames above
                # 6.944 m/s). Not charged to SPRINT_MAX: the cap exists for
                # the ceiling, and this fires only for players the stochastic
                # budget has already starved (a busy draw that burned its 24
                # commitments by minute 25 without recording episodes must
                # not lock the floor out too).
                if self.role[i] != "GK" and t >= self.sprint_until[i] \
                        and self.nep[i] < min(int(t // 600.0), 9):
                    plus = _attacks_plus_x(self.team[i], self._period(t))
                    # with the ball: sprint into space upfield; without it:
                    # a recovery sprint toward the own-goal half
                    fwd = self.poss_team == self.team[i]
                    dx_ = 18.0 if (plus == fwd) else -18.0
                    self.tgx[i] = _clamp(self.px[i] + dx_, 2.0, PITCH_L - 2.0)
                    self.tgy[i] = _clamp(self.py[i] + (rng.random() - 0.5) * 16.0,
                                         3.0, 65.0)
                    self.cruise[i] = top
                    self.sprint_until[i] = t + 2.6
                    self.nspr[i] += 1
                # recovery run: the team is about to lose the ball with men
                # forward -- defenders sprint back toward a low block line
                # (deterministic, at most once per RECOVER_S seconds)
                if self.role[i] in ("DF", "MF") and turned \
                        and self.team[i] == self.poss_team \
                        and self._ball_u(self.team[i]) > 50.0 \
                        and t >= self.sprint_until[i] \
                        and t >= self.recover_ok[i] \
                        and self.nspr[i] < SPRINT_MAX + 2 \
                        and (self.role[i] == "DF"
                             or rng.random() < 0.6 * self.bias[i]):
                    self.recover_ok[i] = t + RECOVER_S
                    self.nspr[i] += 1
                    self.recover_until[i] = t + 2.2
                    su_, sy_ = SLOT[self.slot_of[i]]
                    ru = 14.0 if self.role[i] == "DF" else 30.0
                    u2 = _clamp(ru + 0.5 * (su_ - (20.0 if self.role[i] == "DF" else 42.0)),
                                6.0, 45.0)
                    y2 = _clamp(sy_ + 0.45 * (self.sby - sy_), 3.0, 65.0)
                    plus = _attacks_plus_x(self.team[i], self._period(t))
                    self.tgx[i] = u2 if plus else PITCH_L - u2
                    self.tgy[i] = y2
                    self.cruise[i] = RECOVER_TOP
            # runs in behind while in possession
            if i not in chasers and self.role[i] in ("FW", "MF") and not self.setpiece_map:
                if self.team[i] == next_team and self._ball_u(next_team) > 50.0 \
                        and t >= self.sprint_until[i] and t >= self.run_ok[i] and \
                        self.nspr[i] < SPRINT_MAX and \
                        rng.random() < RUN_P * self.bias[i]:
                    self.sprint_until[i] = t + 2.6
                    self.run_ok[i] = t + 16.0
                    self.nspr[i] += 1
                    plus = _attacks_plus_x(self.team[i], self._period(t))
                    u = self._ball_u(self.team[i]) + 22.0
                    yy = _clamp(self.sby + (12.0 if rng.random() < 0.5 else -12.0), 3, 65)
                    self.tgx[i] = u if plus else PITCH_L - u
                    self.tgy[i] = yy
                    self.cruise[i] = top
        # task 08 rule 14: no statues. Anyone who has stood on one recorded
        # spot for IDLE_AFTER_S shifts their weight / takes a slow step --
        # a small offset re-rolled every ~1.5-3 s, never taking anyone off
        # the pitch or across halfway. Players still travelling to a target
        # (a gap to their target) are left alone; their movement is real.
        for i in list(self.actives):
            if self.walkoff_tgt[i] is not None:
                continue  # they are leaving; the walk itself is the movement
            if t - self.moved_at[i] < IDLE_AFTER_S:
                self.idle_t[i] = 0.0
                continue
            # a player parked on an early-arrived waypoint sways around the
            # waypoint itself (_move reads the offsets): the usual gap check
            # would skip them, since their tgx/tgy may be miles stale
            w0 = None
            if self.wpt[i]:
                wmin = min(self.wpt[i])
                if wmin[0] - t > 2.0:
                    w0 = wmin
            if w0 is None and math.hypot(self.tgx[i] - self.px[i],
                                         self.tgy[i] - self.py[i]) > 1.2:
                continue  # still travelling
            if t >= self.idle_t[i]:
                amp = 0.3 if self.role[i] == "GK" else \
                    0.4 + self.rng.random() * 0.5
                ang = self.rng.random() * 6.2831853
                self.idle_x[i] = math.cos(ang) * amp
                self.idle_y[i] = math.sin(ang) * amp
                self.idle_t[i] = t + 1.5 + self.rng.random() * 1.7
            if w0 is not None:
                self.tgx[i] = _clamp(w0[1] + self.idle_x[i], 0.6, PITCH_L - 0.6)
                self.tgy[i] = _clamp(w0[2] + self.idle_y[i], 0.6, PITCH_W - 0.6)
            else:
                self.tgx[i] = _clamp(self.tgx[i] + self.idle_x[i], 0.6, PITCH_L - 0.6)
                self.tgy[i] = _clamp(self.tgy[i] + self.idle_y[i], 0.6, PITCH_W - 0.6)

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

        for pi, period in enumerate(self.periods):
            start_ms, end_ms = period["start_ms"], period["end_ms"]
            if period["id"] > 1:
                self._reset_for_kickoff(period)
            n10 = (end_ms - start_ms) // 100 + 1
            # task 08 rule 2: the next period's first frame must be ITS OWN
            # kick-off formation. QA maps an event to the first period whose
            # frame window covers it, so this period's records must stop one
            # frame short of the break -- otherwise the second half's kick-off
            # reads the last pre-break positions (keeper 28 m out, five players
            # in the wrong half)
            nxt_start = self.periods[pi + 1]["start_ms"] \
                if pi + 1 < len(self.periods) else None
            recs = 0
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
                self._ball_step(t)
                if step % 2 == 0:
                    if nxt_start is None or start_ms + step * 100 + 200 <= nxt_start:
                        self._record(t)
                        recs += 1
            self.frames_per_period.append(recs)
        # anything left pending (last event exactly at the whistle)
        while self.ep < len(self.events):
            self._process_event(self.ep, self.periods[-1]["end_ms"] / 1000.0)
            self.ep += 1

    def _reset_for_kickoff(self, period: Dict[str, Any]) -> None:
        """Task 08 rule 2: the teams switch ends during the break -- the first
        frame of the new period is the kick-off formation for THAT period's
        ends (keeper in their own goal, everyone in their own half, the taker
        on the centre spot). There are no frames between periods, so the walk
        across happens off-camera."""
        pid = period["id"]
        # any pending ball business from the previous period is void
        self.pk = self.rq = self.hold_j = -1
        self.hold_pin = False
        self.hold_gk = -1
        self.block_shot = -1
        self.block_j = -1
        self.block_join = False
        self.bv_tgt = -1.0
        self.net_rest = False
        self.net_until = 0.0
        self.roll_out = False
        self.out_glimpse = False
        # assignments the first half's look-ahead made into this period's
        # events are void: every actor is chosen afresh from the kick-off
        # formation (a P1 look-ahead assignment once left the taker 25 m from
        # the ball at a P2 pass)
        for jj, e in enumerate(self.events):
            if e["period"] == pid:
                self.assigned[jj] = None
        self.setpiece_cache = {k: v for k, v in self.setpiece_cache.items()
                               if self.events[k]["period"] != pid}
        j_ko = -1
        for jj, e in enumerate(self.events):
            if e["period"] == pid and e.get("subtype") == "kick_off":
                j_ko = jj
                break
        ko = self.events[j_ko] if j_ko >= 0 else None
        spot = ((ko["start"]["x"], ko["start"]["y"]) if ko is not None
                else (PITCH_L / 2.0, PITCH_W / 2.0))
        t = period["start_ms"] / 1000.0
        self.bmode = "place"
        self.spot = spot
        self.bx, self.by = spot
        self.bz = 0.0
        self.vbx, self.vby = spot
        self.sbx, self.sby = spot
        self.poss_team = ko["team_id"] if ko is not None else self.poss_team
        for i in range(self.n):
            if not self.on[i]:
                continue
            self.vx[i] = self.vy[i] = 0.0
            self.spd[i] = 0.0
            self.wpt[i] = []
            self.sprint_until[i] = -1.0
            u, y = SLOT[self.slot_of[i]]
            plus = _attacks_plus_x(self.team[i], pid)
            u = min(u, 48.0)  # everyone in their own half
            self.px[i] = u if plus else PITCH_L - u
            self.py[i] = y
            self.tgx[i], self.tgy[i] = self.px[i], self.py[i]
            self.cruise[i] = 0.0
            self.lx[i] = None
            self.moved_at[i] = t
        if j_ko >= 0:
            # the kick-off taker stands on the spot (rule 3), chosen now
            self._choose_actor(j_ko, t)
            a = self.assigned[j_ko]
            if a is not None and a >= 0 and self.on[a]:
                self.px[a], self.py[a] = spot
                self.tgx[a], self.tgy[a] = spot
                self.wpt[a] = [(t, spot[0], spot[1], j_ko)]

    def _move(self, t: float) -> None:
        px, py, vx, vy = self.px, self.py, self.vx, self.vy
        dt = DT
        for i in self.actives:
            vmax = self.vmax[i]
            eff = vmax * (1.0 - self.fat[i])
            tx, ty = self.tgx[i], self.tgy[i]
            cruise = self.cruise[i]
            w = self.wpt[i]
            if w and self.pk >= 0 and self.assigned[self.pk] == i:
                # task 10: a deferred kick is waiting on this player -- the
                # ball outranks their waypoints (walking to a later event's
                # spot while the ball lies still was the rule 16 cluster)
                w = []
            if w:
                w0 = min(w)
                remain = w0[0] - t
                d = math.hypot(w0[1] - px[i], w0[2] - py[i])
                if d < 0.4 and remain > 2.0:
                    # arrived well ahead of the waypoint's event (a keeper
                    # waiting on a goal kick): idle sway around the spot --
                    # task 08 rule 14, nobody stands like a statue
                    tx = w0[1] + self.idle_x[i]
                    ty = w0[2] + self.idle_y[i]
                    cruise = WALK
                else:
                    need = d / max(remain, 0.15) * 1.35
                    cruise = _clamp(max(need, 1.0), 1.2, self._sprint_top(i))
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
            vcap = vmax  # sprint floor: see FAT_SPRINT_FLOOR
            if s2 > vcap * vcap and s2 > 1e-12:
                f = vcap / math.sqrt(s2)
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
            self.rdist[i] += spd * dt
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
        # task 08 rule 12: a substitute steps on only once the outgoing
        # player has left the pitch (never 12 on a team); +30 s safety so a
        # stuck walker cannot block the sub forever
        if self.pending_on:
            still = []
            for t0, inc, out in self.pending_on:
                if not self.on[out] or t >= t0 + 30.0:
                    self._sub_enter(inc)
                else:
                    still.append((t0, inc, out))
            self.pending_on = still
        # separation
        self._separate()
        if self.block_shot >= 0 and self.block_j >= 0 \
                and self.bmode == "flight" and 0.0 <= self.f1 - t <= 0.8:
            # task 10 part 3: rule 8 must hold by construction, not by
            # pacing. The blocker's waypoint paces them to the block point,
            # but pacing is timing: a rounding difference in hypot/trig
            # between macOS and Linux drifts the run a metre or two and CI
            # fails the 1.2 m bar. Through the last 0.8 s of the block
            # flight the blocker runs the remaining straight-line distance
            # at exactly the pace that has them standing ON the point 0.2 s
            # before the ball lands (capped near sprint -- never a
            # teleport), and holds there through the deflection frames.
            i = self.block_j
            if self.on[i]:
                dx = self.fxe - px[i]
                dy = self.fye - py[i]
                d = math.hypot(dx, dy)
                t_left = max(self.f1 - 0.2 - t, 0.05)
                top = max(1.15 * self.vmax[i] * (1.0 - self.fat[i]), 3.0)
                v = min(d / t_left, top)
                if v * dt >= d:
                    px[i], py[i] = self.fxe, self.fye
                    vx[i], vy[i] = 0.0, 0.0
                elif d > 1e-9:
                    px[i] += dx / d * v * dt
                    py[i] += dy / d * v * dt
                    vx[i], vy[i] = dx / d * v, dy / d * v

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
            cap = min(0.5, max(head, 0.0) * DT)
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
        f = (SEP_MIN - d) * 0.6
        ux, uy = dx / d, dy / d
        # task 08 rule 15: a player pressed against a touchline cannot take
        # their half of the push (it would only be clamped back on) -- the
        # whole push goes to whoever has pitch to move into
        bi = (self.px[i] < 0.4 or self.px[i] > PITCH_L - 0.4 or
              self.py[i] < 0.4 or self.py[i] > PITCH_W - 0.4)
        bj = (self.px[j] < 0.4 or self.px[j] > PITCH_L - 0.4 or
              self.py[j] < 0.4 or self.py[j] > PITCH_W - 0.4)
        if bi and not bj:
            dxs[j] += ux * f * 2.0
            dys[j] += uy * f * 2.0
        elif bj and not bi:
            dxs[i] -= ux * f * 2.0
            dys[i] -= uy * f * 2.0
        else:
            dxs[i] -= ux * f
            dys[i] -= uy * f
            dxs[j] += ux * f
            dys[j] += uy * f

    def _record(self, t: float) -> None:
        self.recs += 1
        self.rec_b = (self.bx, self.by)
        self.rec_att = self.battach if self.bmode == "attach" else -1
        if self.bmode == "out":
            if self.out_glimpse:
                # task 08 rules 9/10: one last visible record AT the line the
                # ball is crossing -- the crossing itself is seen (a shot
                # going out wide, a deflection over the line), then hidden
                self.ox["ball"].append(_to_dm(self.bx, 1050))
                self.oy["ball"].append(_to_dm(self.by, 680))
                self.oz["ball"].append(_to_dm(max(self.bz, 0.0), 200))
                self.out_glimpse = False
                self.bz = -1.0
            else:
                self.ox["ball"].append(-1)
                self.oy["ball"].append(-1)
                self.oz["ball"].append(-1)
        else:
            self.ox["ball"].append(_to_dm(self.bx, 1050))
            self.oy["ball"].append(_to_dm(self.by, 680))
            self.oz["ball"].append(_to_dm(max(self.bz, 0.0), 200))
        for i in range(self.n):
            pid = self.pids[i]
            if self.on[i]:
                x_ = _to_dm(self.px[i], 1050)
                y_ = _to_dm(self.py[i], 680)
                self.ox[pid].append(x_)
                self.oy[pid].append(y_)
                # sprint-episode ledger, computed exactly like the recorder
                # does it (step between two recorded frames / 0.2 s, 5
                # consecutive frames above 25 km/h = one episode) -- the
                # sprint floor below schedules on this count, so a scheduled
                # sprint that the output does not show as an episode is
                # retried, not counted. dm-grid quantisation included, since
                # that is what the reader sees.
                if self.lx[i] is not None:
                    sp = math.hypot(x_ - self.lx[i], y_ - self.ly[i]) / 2.0
                    if x_ != self.lx[i] or y_ != self.ly[i]:
                        self.moved_at[i] = t  # statue guard (task 08 rule 14)
                    if sp > 6.9444:
                        self.srun[i] += 1
                        if self.srun[i] == 5:
                            self.nep[i] += 1
                    else:
                        self.srun[i] = 0
                self.lx[i], self.ly[i] = x_, y_
            else:
                self.ox[pid].append(-1)
                self.oy[pid].append(-1)
                self.srun[i] = 0
                self.lx[i] = None

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
            "z": {"ball": self.oz["ball"]},  # task 06: height, ball only
        }


def _to_dm(v: float, hi: int) -> int:
    d = int(math.floor(v * 10.0 + 0.5))  # round half up
    return 0 if d < 0 else (hi if d > hi else d)


def track_match(match: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Simulate one generated match. Pure: same match dict -> same outputs."""
    sim = _Sim(match)
    sim.run()
    return sim.tracked_match(), sim.tracking_file()

"""Match Lab: seeded synthetic football match generator.

One call to `generate_match(seed, home_priors, away_priors)` returns a whole
match as plain dicts/lists (ready for json.dumps). Same seed + same priors
gives the same match, byte for byte.

How it works, in plain words
----------------------------
* The pitch is cut into a grid: 6 columns along the pitch x 3 lanes across.
  A team in possession "lives" in one grid cell at a time. Each step it picks
  an action (pass, dribble, cross, shot, ...) with weights that depend on the
  cell, then the ball moves to a new cell, or the other team wins it, or the
  ball goes out. That is the possession/zone Markov model.
* Dead-ball restarts (throw-in, goal kick, free kick, corner, kick-off) use the
  team priors: how often a corner is played short, how often a free kick is
  crossed, how hard a team presses, how attacking its substitutions are.
* Stoppages (injury, VAR, substitutions, goals, cards) add time to the period,
  so every period has an announced and an actual added time.

All players are placeholders (HAR-1..HAR-14, COP-1..COP-14). No real data is
read or used for calibration; the constants below are tuned by hand against
published aggregate averages (see tasks/glm/01-match-lab-generator.md).
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

GENERATOR_VERSION = "matchlab-0.1.0"

PITCH_L = 105.0
PITCH_W = 68.0
COLS = 6
LANES = 3
COL_W = PITCH_L / COLS
LANE_W = PITCH_W / LANES

REGULATION_S = 45 * 60

HOME = "HAR"
AWAY = "COP"
TEAM_NAMES = {HOME: "Harbour Lights", AWAY: "Copperfield"}
TEAM_KITS = {
    HOME: {"primary": "#2E7FC4", "secondary": "#FFFFFF", "gk": "#222222"},
    AWAY: {"primary": "#C8692F", "secondary": "#111111", "gk": "#7A8B3A"},
}

# League-average style priors. A team prior dict may override any of these.
DEFAULT_PRIORS: Dict[str, float] = {
    "corner_short_share": 0.16,  # share of corners played short
    "fk_cross_share": 0.45,      # share of attacking-half free kicks that are crossed
    "press_intensity": 0.5,      # 0 = sits off, 1 = presses hard
    "sub_attack_bias": 0.5,      # 0 = defensive substitutions, 1 = attacking
}
# Planted habits for the two fictional teams (used when no priors are given).
TEAM_DEFAULT_PRIORS: Dict[str, Dict[str, float]] = {
    HOME: dict(DEFAULT_PRIORS, corner_short_share=0.15),
    AWAY: dict(DEFAULT_PRIORS, corner_short_share=0.6),
}

# Shirt number -> position. 1-11 start, 12-14 are the bench.
POSITIONS = {1: "GK", 2: "DF", 3: "DF", 4: "DF", 5: "DF", 6: "MF", 7: "MF", 8: "MF",
             9: "FW", 10: "FW", 11: "FW", 12: "DF", 13: "MF", 14: "FW"}

# Which positions touch the ball in which column (attacker's frame, 0 = own goal end).
POSITION_WEIGHTS = {
    0: {"GK": 0.15, "DF": 0.60, "MF": 0.20, "FW": 0.05},
    1: {"GK": 0.02, "DF": 0.45, "MF": 0.43, "FW": 0.10},
    2: {"GK": 0.0, "DF": 0.30, "MF": 0.55, "FW": 0.15},
    3: {"GK": 0.0, "DF": 0.10, "MF": 0.55, "FW": 0.35},
    4: {"GK": 0.0, "DF": 0.04, "MF": 0.36, "FW": 0.60},
    5: {"GK": 0.0, "DF": 0.03, "MF": 0.27, "FW": 0.70},
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _other(team: str) -> str:
    return AWAY if team == HOME else HOME


def _check_priors(priors: Optional[Dict[str, float]], default: Dict[str, float]) -> Dict[str, float]:
    merged = dict(default if priors is None else DEFAULT_PRIORS)
    if priors is not None:
        for key, value in priors.items():
            if key not in DEFAULT_PRIORS:
                raise ValueError("unknown prior: %r (allowed: %s)" % (key, ", ".join(sorted(DEFAULT_PRIORS))))
            merged[key] = value
    for key, value in merged.items():
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError("prior %s must be between 0 and 1, got %r" % (key, value))
    return merged


class _MatchSim:
    """One match in progress. Not part of the public API."""

    def __init__(self, seed: int, home_priors: Dict[str, float], away_priors: Dict[str, float]) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.priors = {HOME: home_priors, AWAY: away_priors}

        self.events: List[Dict[str, Any]] = []
        self.stoppages: List[Dict[str, Any]] = []
        self.periods: List[Dict[str, Any]] = []
        self.score = {HOME: 0, AWAY: 0}
        self.live_s = 0.0

        self.clock = 0.0          # absolute match clock in seconds (continuous across halves)
        self.p_start = 0.0
        self.added = 0.0
        self.period = 1
        self.direction = {HOME: 1, AWAY: -1}

        self.on_field = {t: [self._pid(t, n) for n in range(1, 12)] for t in (HOME, AWAY)}
        self.bench = {t: [self._pid(t, n) for n in (12, 13, 14)] for t in (HOME, AWAY)}
        self.yellows: Dict[str, int] = {}
        self.tilt = {HOME: 0.0, AWAY: 0.0}
        self.sub_schedule = {t: self._plan_subs() for t in (HOME, AWAY)}

        # ball state (attacker's frame: u = metres from own goal line, y = absolute)
        self.team = HOME
        self.u = PITCH_L / 2
        self.y = PITCH_W / 2
        self.kind = "kickoff"
        self.poss_id = 0
        self.force_shot: Optional[str] = None
        self.restart_delay: Optional[Tuple[float, float]] = None
        self.pressure_level = 1

    # ---------- small helpers ----------

    @staticmethod
    def _pid(team: str, n: int) -> str:
        return "%s-%d" % (team, n)

    def _plan_subs(self) -> List[Tuple[float, int]]:
        first = self.rng.randint(55, 68)
        second = self.rng.randint(first + 8, 82)
        n_first = self.rng.choice([1, 2])
        return [(first * 60.0 - REGULATION_S, n_first), (second * 60.0 - REGULATION_S, 3 - n_first)]

    def _uniform(self, lo: float, hi: float) -> float:
        return self.rng.uniform(lo, hi)

    def _zone(self) -> Tuple[int, int]:
        return (min(COLS - 1, int(self.u // COL_W)), min(LANES - 1, int(self.y // LANE_W)))

    def _sample(self, col: int, lane: int) -> Tuple[float, float]:
        u = self._uniform(col * COL_W + 1.0, (col + 1) * COL_W - 1.0)
        y = self._uniform(lane * LANE_W + 1.0, (lane + 1) * LANE_W - 1.0)
        return (u, y)

    def _set_team(self, team: str) -> None:
        """Hand the ball to `team` without moving it (used when the ball position is already in that team's frame)."""
        if team != self.team:
            self.poss_id += 1
        self.team = team

    def _flip_to(self, team: str) -> None:
        """Ball changes hands where it lies: mirror u into the new team's frame."""
        if team != self.team:
            self.u = PITCH_L - self.u
            self.poss_id += 1
        self.team = team

    def _abs_x(self, team: str, u: float) -> float:
        x = u if self.direction[team] > 0 else PITCH_L - u
        return round(_clamp(x, 0.0, PITCH_L), 1)

    def _pt(self, team: str, u: float, y: float) -> Dict[str, float]:
        return {"x": self._abs_x(team, u), "y": round(_clamp(y, 0.0, PITCH_W), 1)}

    def _clock_display(self) -> str:
        elapsed = int(self.clock - self.p_start)
        base_min = 0 if self.period == 1 else 45
        if elapsed < REGULATION_S:
            return "%d:%02d" % (base_min + elapsed // 60, elapsed % 60)
        extra = elapsed - REGULATION_S
        return "%d+%d:%02d" % (base_min + 45, extra // 60, extra % 60)

    def _pick_player(self, team: str, col: int, exclude: Optional[str] = None) -> str:
        weights = POSITION_WEIGHTS[col]
        players = [p for p in self.on_field[team] if p != exclude]
        w = [weights[POSITIONS[int(p.split("-")[1])]] for p in players]
        if sum(w) <= 0:
            return self.rng.choice(players)
        return self.rng.choices(players, weights=w)[0]

    def _keeper(self, team: str) -> str:
        gk = self._pid(team, 1)
        return gk if gk in self.on_field[team] else self.on_field[team][0]

    def _emit(self, team: str, player: str, etype: str, subtype: Optional[str],
              start_u: float, start_y: float, end_u: float, end_y: float, outcome: str,
              dur: float, set_piece: Optional[Dict[str, Optional[str]]] = None,
              live: bool = True, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        idx = len(self.events)
        ev: Dict[str, Any] = {
            "event_id": "e%05d" % idx,
            "idx": idx,
            "period": self.period,
            "t_ms": int(round(self.clock * 1000)),
            "clock_display": self._clock_display(),
            "team_id": team,
            "player_id": player,
            "type": etype,
            "subtype": subtype,
            "start": self._pt(team, start_u, start_y),
            "end": self._pt(team, end_u, end_y),
            "outcome": outcome,
            "possession_id": self.poss_id,
            "pressure_level": self.pressure_level,
            "set_piece": set_piece,
        }
        if extra:
            ev.update(extra)
        self.events.append(ev)
        self.clock += dur
        if live:
            self.live_s += dur
        return ev

    def _stop(self, kind: str, dur: float, counts: bool, related: List[str],
              var: Optional[Dict[str, Any]] = None) -> None:
        self.stoppages.append({
            "stoppage_id": "s%02d" % len(self.stoppages),
            "type": kind,
            "t_start_ms": int(round(self.clock * 1000)),
            "t_end_ms": int(round((self.clock + dur) * 1000)),
            "duration_s": round(dur, 1),
            "counts_for_added_time": counts,
            "related_event_ids": related,
            "var": var,
        })
        self.clock += dur
        if counts:
            self.added += dur

    def _last_id(self) -> List[str]:
        return [self.events[-1]["event_id"]] if self.events else []

    # ---------- the match ----------

    def run(self) -> None:
        first_team = self.rng.choice([HOME, AWAY])
        for period in (1, 2):
            self._run_period(period, first_team if period == 1 else _other(first_team))

    def _run_period(self, period: int, kickoff_team: str) -> None:
        self.period = period
        self.p_start = self.clock
        self.added = 0.0
        self.direction = {HOME: 1, AWAY: -1} if period == 1 else {HOME: -1, AWAY: 1}
        self.team = kickoff_team
        self.poss_id += 1
        self.kind = "kickoff"
        self.u, self.y = PITCH_L / 2, PITCH_W / 2
        self.force_shot = None
        start_ms = int(round(self.clock * 1000))

        while True:
            elapsed = self.clock - self.p_start
            if self.kind != "open":
                if elapsed >= REGULATION_S + self.added:
                    break
                self._maybe_subs(elapsed)
                self._maybe_injury()
                if self.clock - self.p_start >= REGULATION_S + self.added:
                    break
            elif elapsed >= REGULATION_S + self.added + 90:
                break  # safety net: never let one attack run on forever
            self._step()

        actual = round(self.added)
        announced = max(60, int(round(actual / 60.0)) * 60)
        self.periods.append({
            "id": period,
            "start_ms": start_ms,
            "end_ms": int(round(self.clock * 1000)),
            "added_time_announced_s": announced,
            "added_time_actual_s": actual,
        })

    def _step(self) -> None:
        handler = {
            "open": self._open_play,
            "kickoff": self._kickoff,
            "throw_in": self._throw_in,
            "goal_kick": self._goal_kick,
            "free_kick": self._free_kick,
            "corner": self._corner,
        }[self.kind]
        handler()

    # ---------- stoppages ----------

    def _maybe_injury(self) -> None:
        if self.rng.random() < 0.008:
            self._stop("injury", self._uniform(40, 110), True, self._last_id())

    def _maybe_subs(self, elapsed: float) -> None:
        if self.period != 2:
            return
        for team in (HOME, AWAY):
            schedule = self.sub_schedule[team]
            if schedule and elapsed >= schedule[0][0]:
                _, n = schedule.pop(0)
                self._substitute(team, n)

    def _substitute(self, team: str, n: int) -> None:
        bias = self.priors[team]["sub_attack_bias"]
        ids: List[str] = []
        start_clock = self.clock
        for _ in range(n):
            if not self.bench[team]:
                break
            wanted = self.rng.choices(["FW", "MF", "DF"], weights=[bias + 0.05, 0.5, 1.05 - bias])[0]
            candidates = [p for p in self.bench[team] if POSITIONS[int(p.split("-")[1])] == wanted]
            incoming = candidates[0] if candidates else self.bench[team][0]
            outfield = [p for p in self.on_field[team] if POSITIONS[int(p.split("-")[1])] != "GK"]
            outgoing = self.rng.choice(outfield)
            self.bench[team].remove(incoming)
            self.on_field[team][self.on_field[team].index(outgoing)] = incoming
            pos = POSITIONS[int(incoming.split("-")[1])]
            style = "attacking" if pos == "FW" else "defensive" if pos == "DF" else "balanced"
            ev = self._emit(team, incoming, "substitution", style, self.u, self.y, self.u, self.y,
                            "success", 0.0, live=False, extra={"player_out_id": outgoing})
            ids.append(ev["event_id"])
            self.tilt[team] = _clamp(self.tilt[team] + (bias - 0.5) * 0.2, -0.3, 0.3)
        if ids:
            self.clock = start_clock
            self._stop("sub", 20.0 + 10.0 * len(ids) + self._uniform(0, 10), True, ids)

    # ---------- open play ----------

    def _weights(self, col: int, lane: int) -> Tuple[List[str], List[float]]:
        tilt = self.tilt[self.team]
        wide = lane != 1
        w = {
            "pass_fwd": (0.38 if col <= 4 else 0.10) * (1 + tilt),
            "pass_side": 0.28,
            "pass_back": (0.14 if col >= 1 else 0.05) * (1 - tilt),
            "dribble": 0.11,
            "cross": 0.0,
            "shot": 0.0,
            "clearance": 0.04 if col <= 1 else 0.0,
        }
        if col == 5:
            w["cross"] = 0.33 if wide else 0.0
            w["shot"] = (0.02 if wide else 0.07) * (1 + tilt)
        elif col == 4:
            w["cross"] = 0.12 if wide else 0.0
            w["shot"] = (0.005 if wide else 0.02) * (1 + tilt)
        return list(w.keys()), list(w.values())

    def _open_play(self) -> None:
        team = self.team
        opp = _other(team)
        col, lane = self._zone()
        press = self.priors[opp]["press_intensity"]
        zone_f = 1.0 if col <= 2 else 0.6
        self.pressure_level = 1 + int(_clamp(press * zone_f + self._uniform(-0.2, 0.2), 0.0, 0.999) * 5)
        extra_fail = 0.12 * (press - 0.5) * zone_f
        su, sy = self.u, self.y

        if self.force_shot:
            kind = self.force_shot
            self.force_shot = None
            self._shoot(col if col >= 4 else 5, lane, header=(kind == "header"))
            return

        names, weights = self._weights(col, lane)
        action = self.rng.choices(names, weights=weights)[0]
        player = self._pick_player(team, col)

        if action in ("pass_fwd", "pass_side", "pass_back"):
            if action == "pass_fwd":
                ncol = min(COLS - 1, col + self.rng.choice([1, 1, 1, 2]))
                p_ok = 0.80 - extra_fail
            elif action == "pass_side":
                ncol = col
                p_ok = 0.91 - extra_fail * 0.5
            else:
                ncol = max(0, col - 1)
                p_ok = 0.95
            nlane = self._next_lane(lane, 0.30)
            eu, ey = self._sample(ncol, nlane)
            subtype = {"pass_fwd": "forward", "pass_side": "lateral", "pass_back": "back"}[action]
            ok = self.rng.random() < p_ok
            self._emit(team, player, "pass", subtype, su, sy, eu, ey,
                       "success" if ok else "fail", self._uniform(1.8, 3.2))
            self.u, self.y = eu, ey
            if not ok:
                self._lose("pass", team)
        elif action == "dribble":
            ncol = min(COLS - 1, col + (1 if self.rng.random() < 0.6 else 0))
            nlane = self._next_lane(lane, 0.4)
            eu, ey = self._sample(ncol, nlane)
            ok = self.rng.random() < 0.60 - extra_fail
            self._emit(team, player, "dribble", None, su, sy, eu, ey,
                       "success" if ok else "fail", self._uniform(2.0, 4.0))
            self.u, self.y = eu, ey
            if not ok:
                self._lose("dribble", team)
        elif action == "cross":
            eu, ey = self._uniform(93.0, 102.0), self._uniform(22.0, 46.0)
            ok = self.rng.random() < 0.18 - extra_fail
            self._emit(team, player, "cross", None, su, sy, eu, ey,
                       "success" if ok else "fail", self._uniform(2.5, 4.0))
            self.u, self.y = eu, ey
            if ok:
                self.force_shot = "header"
            else:
                self._lose("cross", team)
        elif action == "shot":
            self._shoot(col, lane, header=False)
        else:  # clearance
            eu = self._uniform(35.0, 65.0)
            ey = self._uniform(5.0, PITCH_W - 5.0)
            self._emit(team, player, "clearance", None, su, sy, eu, ey, "success", self._uniform(1.5, 2.5))
            self.u, self.y = eu, ey
            self._flip_to(opp)
            self.u, self.y = self._sample(self.rng.choice([2, 3]), self._next_lane(self._zone()[1], 0.4))

    def _next_lane(self, lane: int, move_prob: float) -> int:
        if self.rng.random() >= move_prob:
            return lane
        options = [l for l in (lane - 1, lane + 1) if 0 <= l < LANES]
        return self.rng.choice(options)

    def _lose(self, kind: str, team: str) -> None:
        """The ball did not reach its target. Decide: foul, out of play, or live turnover.

        The ball sits at the failed action's end point, in `team`'s frame.
        """
        opp = _other(team)
        col, lane = self._zone()
        foul_p = {"pass": 0.03, "cross": 0.0, "dribble": 0.22}[kind]
        out_p = {"pass": 0.30, "cross": 0.18, "dribble": 0.05}[kind]
        r = self.rng.random()
        if r < foul_p:
            self._foul(opp, team)
        elif r < foul_p + out_p:
            if col == COLS - 1 and (self.u >= 90.0 or self.rng.random() < 0.5):
                if kind in ("cross", "pass") and self.rng.random() < (0.50 if kind == "cross" else 0.20):
                    self._set_team(team)
                    self.kind = "corner"
                else:
                    self._flip_to(opp)
                    self.kind = "goal_kick"
            else:
                self._flip_to(opp)
                self.y = 0.0 if self.y < PITCH_W / 2 else PITCH_W
                self.kind = "throw_in"
        else:
            player = self._pick_player(opp, 5 - col)
            etype = "tackle" if kind == "dribble" else "interception"
            ou, oy = PITCH_L - self.u, self.y
            self._emit(opp, player, etype, None, ou, oy, ou, oy, "success", self._uniform(0.6, 1.2))
            self._flip_to(opp)
            self.kind = "open"

    def _foul(self, fouler: str, victim: str) -> None:
        """`fouler` fouls near the ball; `victim` gets a free kick where the ball lies."""
        col = self._zone()[0]
        player = self._pick_player(fouler, 5 - col)
        ou, oy = PITCH_L - self.u, self.y
        self._emit(fouler, player, "foul", None, ou, oy, ou, oy, "foul", self._uniform(0.5, 1.0))
        if self.rng.random() < 0.09:
            if player in self.on_field[fouler] and POSITIONS[int(player.split("-")[1])] != "GK":
                self.yellows[player] = self.yellows.get(player, 0) + 1
                second = self.yellows[player] >= 2
                ev = self._emit(fouler, player, "card", "second_yellow" if second else "yellow",
                                ou, oy, ou, oy, "success", 0.0, live=False)
                if second:
                    self.on_field[fouler].remove(player)
                self._stop("card", self._uniform(20, 40), True, [ev["event_id"]])
        self._set_team(victim)
        self.kind = "free_kick"

    # ---------- shots ----------

    def _shoot(self, col: int, lane: int, header: bool) -> None:
        team = self.team
        wide = lane != 1
        if col >= 5:
            p_goal = 0.045 if wide else 0.125
        else:
            p_goal = 0.02 if wide else 0.055
        if header:
            p_goal *= 0.8
        player = self._pick_player(team, 5 if col >= 4 else col)
        su, sy = self.u, self.y
        gu, gy = PITCH_L, self._uniform(30.0, 38.0)
        outcome = self._shot_outcome(p_goal)
        self._emit(team, player, "shot", "header" if header else None, su, sy, gu, gy, outcome, self._uniform(1.0, 2.0))
        self._after_shot(team, outcome)

    def _shot_outcome(self, p_goal: float) -> str:
        r = self.rng.random()
        if r < p_goal:
            return "goal"
        r -= p_goal
        if r < 0.22:
            return "saved"
        r -= 0.22
        if r < 0.25:
            return "blocked"
        return "off_target"

    def _after_shot(self, team: str, outcome: str) -> None:
        opp = _other(team)
        if outcome == "goal":
            self._goal(team)
        elif outcome == "saved":
            # task 08 rule 4: u is metres from the EMITTING team's own goal --
            # the save happens 1 m from the saving keeper's own line (the old
            # PITCH_L - 1.0 put it at the other end of the pitch). Same rng
            # draws, so every other event is unchanged.
            self._emit(opp, self._keeper(opp), "keeper_save", None, 1.0, self._uniform(30, 38),
                       3.0, self._uniform(25, 43), "success", 1.0)
            r = self.rng.random()
            if r < 0.30:
                self.u, self.y = PITCH_L, 0.0 if self.rng.random() < 0.5 else PITCH_W
                self._set_team(team)
                self.kind = "corner"
            elif r < 0.88:
                self._to_goal_kick(opp, (6.0, 14.0))
            else:
                self.u, self.y = self._sample(5, 1)
                self.force_shot = "rebound"
        elif outcome == "blocked":
            if self.rng.random() < 0.33:
                self.u, self.y = PITCH_L, 0.0 if self.rng.random() < 0.5 else PITCH_W
                self._set_team(team)
                self.kind = "corner"
            else:
                self.u, self.y = self._sample(4, self._next_lane(1, 0.5))
                self._flip_to(opp)
                self.kind = "open"
        else:  # off target
            self._to_goal_kick(opp, None)

    def _to_goal_kick(self, team: str, delay: Optional[Tuple[float, float]]) -> None:
        self._set_team(team)
        self.u, self.y = 5.5, PITCH_W / 2 + self._uniform(-8, 8)
        self.kind = "goal_kick"
        self.restart_delay = delay

    def _goal(self, team: str) -> None:
        opp = _other(team)
        shot = self.events[-1]
        self.score[team] += 1
        self._stop("goal", self._uniform(25, 40), True, [shot["event_id"]])
        if self.rng.random() < 0.12:  # VAR looks at the goal
            overturned = self.rng.random() < 0.25
            check_type = "offside" if self.rng.random() < 0.7 else "foul"
            var: Dict[str, Any] = {
                "check_type": check_type,
                "decision": "overturned" if overturned else "stands",
            }
            # Offside margins come from a separate stream so the main random stream
            # (and therefore every existing seed's events) does not change.
            if check_type == "offside":
                var["margin_cm"] = random.Random("%d-var-%s" % (self.seed, shot["event_id"])).randint(1, 40)
            else:
                var["margin_cm"] = None
            self._stop("VAR", self._uniform(60, 150), True, [shot["event_id"]], var=var)
            if overturned:
                self.score[team] -= 1
                shot["outcome"] = "disallowed"
                self._to_goal_kick(opp, None)
                return
        self._set_team(opp)
        self.u, self.y = PITCH_L / 2, PITCH_W / 2
        self.kind = "kickoff"

    # ---------- restarts ----------

    def _wait(self, lo: float, hi: float) -> None:
        self.clock += self._uniform(lo, hi)

    def _kickoff(self) -> None:
        team = self.team
        player = self._pick_player(team, 3)
        eu, ey = self._sample(self.rng.choice([2, 3]), self.rng.choice([0, 1, 2]))
        self.pressure_level = 1
        self._emit(team, player, "pass", "kick_off", PITCH_L / 2, PITCH_W / 2, eu, ey, "success", self._uniform(1.5, 2.5))
        self.u, self.y = eu, ey
        self.kind = "open"

    def _throw_in(self) -> None:
        team = self.team
        self._wait(14, 23)
        col, lane = self._zone()
        player = self._pick_player(team, min(col, 4))
        ncol = min(COLS - 1, max(0, col + self.rng.choice([-1, 0, 0, 1])))
        eu, ey = self._sample(ncol, 1 if self.y in (0.0, PITCH_W) and self.rng.random() < 0.6 else lane)
        ok = self.rng.random() < 0.86
        self._emit(team, player, "throw_in", None, self.u, self.y, eu, ey, "success" if ok else "fail",
                   self._uniform(1.5, 2.5))
        self.u, self.y = eu, ey
        if ok:
            self.kind = "open"
        else:
            self._flip_to(_other(team))
            self.kind = "open"

    def _goal_kick(self) -> None:
        team = self.team
        if self.restart_delay:
            self._wait(*self.restart_delay)
        else:
            self._wait(19, 31)
        self.restart_delay = None
        eu, ey = self._sample(self.rng.choice([2, 3]), self.rng.choice([0, 1, 2]))
        ok = self.rng.random() < 0.62
        self._emit(team, self._keeper(team), "goal_kick", None, self.u, self.y, eu, ey,
                   "success" if ok else "fail", self._uniform(2.0, 3.0))
        self.u, self.y = eu, ey
        if not ok:
            self._flip_to(_other(team))
        self.kind = "open"

    def _free_kick(self) -> None:
        team = self.team
        opp = _other(team)
        self._wait(22, 38)
        col, lane = self._zone()
        su, sy = self.u, self.y
        player = self._pick_player(team, min(col, 4))
        in_attacking_half = col >= 3
        shootable = col == 5 and lane == 1 or col == 4 and lane == 1
        if in_attacking_half and self.rng.random() < self.priors[team]["fk_cross_share"]:
            routine = "cross"
        elif shootable:
            routine = "shoot"
        else:
            routine = "short"

        if routine == "shoot":
            outcome = self._shot_outcome(0.06)
            sp = {"routine": "shoot", "delivery": None, "target_zone": "goal"}
            self._emit(team, player, "free_kick", "shoot", su, sy, PITCH_L, self._uniform(30, 38),
                       outcome, self._uniform(1.0, 2.0), set_piece=sp)
            self._after_shot(team, outcome)
        elif routine == "cross":
            self._deliver_cross(team, "free_kick", player, su, sy, "free_kick")
        else:
            ncol = min(COLS - 1, col + self.rng.choice([0, 1, 1]))
            eu, ey = self._sample(ncol, self._next_lane(lane, 0.4))
            ok = self.rng.random() < 0.9
            sp = {"routine": "short", "delivery": None, "target_zone": "short"}
            self._emit(team, player, "free_kick", "short", su, sy, eu, ey, "success" if ok else "fail",
                       self._uniform(1.5, 2.5), set_piece=sp)
            self.u, self.y = eu, ey
            if not ok:
                self._flip_to(opp)
            self.kind = "open"

    def _corner(self) -> None:
        team = self.team
        self._wait(28, 40)  # restart delay averages ~34 s
        su = PITCH_L
        sy = 0.0 if self.y < PITCH_W / 2 else PITCH_W
        player = self._pick_player(team, 5)
        if self.rng.random() < self.priors[team]["corner_short_share"]:
            eu = self._uniform(95.0, 100.0)
            ey = self._uniform(8.0, 16.0) if sy == 0.0 else PITCH_W - self._uniform(8.0, 16.0)
            ok = self.rng.random() < 0.88
            sp = {"routine": "short", "delivery": None, "target_zone": "short"}
            self._emit(team, player, "corner", "short", su, sy, eu, ey, "success" if ok else "fail",
                       self._uniform(1.5, 2.5), set_piece=sp)
            self.u, self.y = eu, ey
            if not ok:
                self._flip_to(_other(team))
            self.kind = "open"
        else:
            self._deliver_cross(team, "corner", player, su, sy, "corner")

    def _deliver_cross(self, team: str, etype: str, player: str, su: float, sy: float, label: str) -> None:
        opp = _other(team)
        zone = self.rng.choices(["near", "central", "far"], weights=[0.30, 0.30, 0.40])[0]
        delivery = self.rng.choice(["inswing", "outswing"])
        eu = self._uniform(98.0, 103.0) if zone == "near" else self._uniform(90.0, 96.0) if zone == "central" \
            else self._uniform(93.0, 99.0)
        ey = {"near": self._uniform(29.0, 34.0), "central": self._uniform(31.0, 37.0),
              "far": self._uniform(36.0, 43.0)}[zone]
        if sy > PITCH_W / 2:
            ey = PITCH_W - ey
        ok = self.rng.random() < 0.20
        sp = {"routine": "cross", "delivery": delivery, "target_zone": zone}
        self._emit(team, player, etype, "crossed", su, sy, eu, ey, "success" if ok else "fail",
                   self._uniform(2.5, 3.5), set_piece=sp)
        self.u, self.y = eu, ey
        if ok:
            self.force_shot = "header"
            self.kind = "open"
            return
        r = self.rng.random()
        if r < 0.08:  # cleared behind for another corner
            self.u, self.y = PITCH_L, 0.0 if self.rng.random() < 0.5 else PITCH_W
            self.kind = "corner"
        elif r < 0.25:  # keeper claims it
            self._flip_to(opp)
            self._to_goal_kick(opp, (4.0, 9.0))
        else:
            col = self.rng.choice([1, 2])
            self._flip_to(opp)
            cu, cy = self._sample(col, self.rng.choice([0, 1, 2]))
            player2 = self._pick_player(opp, 0)
            self._emit(opp, player2, "clearance", None, self.u, self.y, cu, cy, "success", self._uniform(1.0, 2.0))
            self.u, self.y = cu, cy
            self.kind = "open"


def _aggregates(sim: _MatchSim) -> Dict[str, Any]:
    corners = {HOME: 0, AWAY: 0}
    short = {HOME: 0, AWAY: 0}
    shots = {HOME: 0, AWAY: 0}
    for ev in sim.events:
        if ev["type"] == "corner":
            corners[ev["team_id"]] += 1
            if ev["set_piece"] and ev["set_piece"]["routine"] == "short":
                short[ev["team_id"]] += 1
        if ev["type"] == "shot" or (ev["type"] == "free_kick" and ev["subtype"] == "shoot"):
            shots[ev["team_id"]] += 1
    return {
        "corners": corners,
        "short_corners": short,
        "shots": shots,
        "ball_in_play_s": int(round(sim.live_s)),
        "events": len(sim.events),
    }


_V_MAX_RANGE = {"GK": (26.0, 30.0), "DF": (31.0, 35.0), "MF": (31.0, 35.0), "FW": (33.0, 37.0)}


def _attributes(seed: int, player_id: str, position: str) -> Dict[str, Any]:
    """Physical attributes for one player (task 04 step 0), drawn from a separate
    stream per player so the main random stream (every seed's events) is untouched,
    like the VAR margin in `_goal`."""
    rng = random.Random("%d-attrs-%s" % (seed, player_id))
    lo, hi = _V_MAX_RANGE[position]
    return {
        "v_max_kmh": round(rng.uniform(lo, hi), 1),
        "endurance": round(rng.uniform(0.85, 1.0), 2),
        "work_rate": round(rng.uniform(0.90, 1.10), 2),
        "sprint_bias": round(rng.uniform(0.70, 1.30), 2),
    }


def generate_match(seed: int, home_priors: Optional[Dict[str, float]] = None,
                   away_priors: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Generate one full synthetic match, reproducible from `seed`.

    `home_priors` / `away_priors` override `DEFAULT_PRIORS` (keys: corner_short_share,
    fk_cross_share, press_intensity, sub_attack_bias). Pass None to use the planted
    habits for Harbour Lights (home) and Copperfield (away).
    """
    home = _check_priors(home_priors, TEAM_DEFAULT_PRIORS[HOME])
    away = _check_priors(away_priors, TEAM_DEFAULT_PRIORS[AWAY])
    sim = _MatchSim(int(seed), home, away)
    sim.run()

    teams = []
    players = []
    for team_id, pri in ((HOME, home), (AWAY, away)):
        teams.append({
            "team_id": team_id,
            "name": TEAM_NAMES[team_id],
            "short_name": team_id,
            "kit": TEAM_KITS[team_id],
            "formation": "4-3-3",
            "style_priors": {k: round(float(v), 4) for k, v in sorted(pri.items())},
        })
        for n in range(1, 15):
            pid = "%s-%d" % (team_id, n)
            players.append({
                "player_id": pid,
                "team_id": team_id,
                "display_name": pid,
                "shirt_no": n,
                "position": POSITIONS[n],
                "attributes": _attributes(int(seed), pid, POSITIONS[n]),
            })

    return {
        "match_id": "synthetic-seed-%d" % int(seed),
        "seed": int(seed),
        "generator_version": GENERATOR_VERSION,
        "competition": "Fictional League",
        "date": "2026-03-14",
        "venue": "Harbour Park",
        "pitch": {"length_m": 105, "width_m": 68},
        "coord_system": "metres, origin bottom-left, x along the pitch; Harbour Lights attack +x in period 1",
        "frame_rate": None,
        "teams": teams,
        "players": players,
        "periods": sim.periods,
        "final_score": dict(sim.score),
        "stoppages": sim.stoppages,
        "events": sim.events,
        "aggregates": _aggregates(sim),
    }

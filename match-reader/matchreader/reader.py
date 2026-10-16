"""Match Reader: one generated match (match-lab output) -> the web app's demo-match file.

Input : data/mock-seed-N.json (or the dict returned by matchlab.generate_match).
Output: the shape of web/public/data/fake-match.json — a score timeline, per-moment
        facts computed from the events, "Call it!" cards, and the held-back log.

Pure function of the input file: no randomness, no network, no AI (AGENTS.md hard
rules 1-2). Every number comes from code; every sentence comes from
templates/cards.json, which this package never edits. When a reveal template is
missing — or names the other team (two draft lines hard-code "Copperfield") — the
moment is held with reason "no_template" instead of showing wrong copy.
"""
from __future__ import annotations

import copy
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

READER_VERSION = "matchreader-0.1.0"

# Fictional teams, decided in AGENTS.md. Harbour Lights attack +x in period 1,
# Copperfield attack -x; they swap for period 2.
HOME = "HAR"
AWAY = "COP"
HALF_X = 52.5  # pitch midline in metres (105 x 68 pitch)

# ---- Timing policy (brief section 5.2). Claude can tune these constants. ----
MAX_PER_HALF = 4     # at most this many cards per half
MIN_GAP_MIN = 8.0    # minutes that must separate two cards
GOAL_QUIET_S = 60.0  # no card within this many seconds after a counted goal event,
                     # except the var card about that very goal

# Long breaks first: a VAR check freezes play longest, a corner least.
TRIGGER_PRIORITY = {"var": 0, "substitution": 1, "free_kick": 2, "corner": 3}

# Copied from matchlab.generator.DEFAULT_PRIORS["corner_short_share"] (kept as a
# literal so the reader works without match-lab on sys.path). Must stay in sync.
LEAGUE_CORNER_SHORT_SHARE = 0.16

SUBS_MAX = 3  # bench players = shirts 12-14

LANGS = ("en", "de", "vi")

_HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_PATH = os.path.join(_HERE, "..", "templates", "cards.json")

_POSITION_OF_ANSWER = {"attack": "FW", "defend": "DF", "fresh": "MF"}
_POSITION_NAME = {"FW": "forwards", "DF": "defenders", "MF": "midfielders"}


def dumps(obj: Dict[str, Any]) -> str:
    """Canonical JSON text, like matchlab.generate.dumps. Same dict -> same bytes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def load_templates() -> Dict[str, Any]:
    with open(TEMPLATES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# ---- clock, pitch direction, line-ups -------------------------------------

def _periods_by_id(match: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    return {p["id"]: p for p in match["periods"]}


def period_of(t_ms: int, match: Dict[str, Any]) -> int:
    periods = sorted(match["periods"], key=lambda p: p["id"])
    return 1 if t_ms < periods[1]["start_ms"] else 2


def clock_minutes(t_ms: int, match: Dict[str, Any], period: int) -> float:
    """Minutes on the match clock shown to viewers, 1 decimal (45 + ... in period 2)."""
    p = _periods_by_id(match)[period]
    if period == 1:
        minutes = (t_ms - p["start_ms"]) / 60000.0
    else:
        minutes = 45.0 + (t_ms - p["start_ms"]) / 60000.0
    return round(minutes, 1)


def _attacks_plus_x(team_id: str, period: int) -> bool:
    return (team_id == HOME) == (period == 1)


def _in_opponent_half(ev: Dict[str, Any]) -> bool:
    """Free kick sits on the side of the pitch the team attacks."""
    if _attacks_plus_x(ev["team_id"], ev["period"]):
        return ev["start"]["x"] > HALF_X
    return ev["start"]["x"] < HALF_X


def _positions(match: Dict[str, Any]) -> Dict[str, str]:
    return {p["player_id"]: p["position"] for p in match["players"]}


def players_on_pitch(match: Dict[str, Any], team_id: str, t_ms: int,
                     include_events_at: bool) -> Set[str]:
    """Players of `team_id` on the pitch at `t_ms`, rebuilt from the events.

    Starts from the XI (shirts 1-11), applies earlier substitution events
    (player_id in, player_out_id out) and removes second-yellow sendings-off.
    With include_events_at, events at exactly t_ms (the rest of a sub window)
    count too.
    """
    on = {p["player_id"] for p in match["players"]
          if p["team_id"] == team_id and 1 <= p["shirt_no"] <= 11}
    for ev in match["events"]:
        if ev["team_id"] != team_id:
            continue
        if ev["t_ms"] < t_ms or (include_events_at and ev["t_ms"] == t_ms):
            if ev["type"] == "substitution":
                on.discard(ev["player_out_id"])
                on.add(ev["player_id"])
            elif ev["type"] == "card" and ev["subtype"] == "second_yellow":
                on.discard(ev["player_id"])
    return on


def _count_position(match: Dict[str, Any], team_id: str, t_ms: int,
                    include_events_at: bool, position: str) -> int:
    pos = _positions(match)
    return sum(1 for pid in players_on_pitch(match, team_id, t_ms, include_events_at)
               if pos[pid] == position)


def _score_before(match: Dict[str, Any], t_ms: int) -> Dict[str, int]:
    """Counted goals per team from events strictly before t_ms ("disallowed" is not a goal)."""
    goals = {t["team_id"]: 0 for t in match["teams"]}
    for ev in match["events"]:
        if ev["t_ms"] < t_ms and ev["outcome"] == "goal":
            goals[ev["team_id"]] += 1
    return goals


# ---- facts (task 1a) -------------------------------------------------------

def card_facts(match: Dict[str, Any], cand: Dict[str, Any]) -> Dict[str, int]:
    """Unscoped facts for one candidate. Only events up to and including the
    moment's own event are used — the reveal is the next thing viewers see."""
    team = cand["team_id"]
    trigger = cand["trigger"]
    facts: Dict[str, int] = {}

    if trigger == "corner":
        total = short = 0
        for ev in match["events"]:
            if (ev["type"] == "corner" and ev["team_id"] == team
                    and ev["idx"] <= cand["event"]["idx"]):
                total += 1
                if ev["set_piece"]["routine"] == "short":
                    short += 1
        facts["corners_total"] = total
        facts["corners_short"] = short
        facts["league_short_share_pct"] = int(round(LEAGUE_CORNER_SHORT_SHARE * 100))

    elif trigger == "free_kick":
        total = crossed = 0
        for ev in match["events"]:
            if (ev["type"] == "free_kick" and ev["team_id"] == team
                    and ev["idx"] <= cand["event"]["idx"] and _in_opponent_half(ev)):
                total += 1
                if ev["set_piece"]["routine"] == "cross":
                    crossed += 1
        facts["fk_total"] = total
        facts["fk_cross"] = crossed

    elif trigger == "substitution":
        # Only the pair the reveal template talks about (plus the sub counter
        # for "fresh legs").
        position = _POSITION_OF_ANSWER[cand["answer"]]
        name = _POSITION_NAME[position]
        facts[name + "_before"] = _count_position(match, team, cand["t_ms"], False, position)
        facts[name + "_after"] = _count_position(match, team, cand["t_ms"], True, position)
        if cand["answer"] == "fresh":
            subs_used = sum(1 for ev in match["events"]
                            if ev["type"] == "substitution" and ev["team_id"] == team
                            and ev["t_ms"] <= cand["t_ms"])
            facts["subs_used"] = subs_used
            facts["subs_max"] = SUBS_MAX

    elif trigger == "var":
        facts["var_margin_cm"] = cand["stoppage"]["var"]["margin_cm"]

    return facts


# ---- candidate moments (task 1b + 1c) --------------------------------------

def _variants(node: Any) -> List[Dict[str, str]]:
    """A template text is one {en,de,vi} dict or a list of such variants."""
    return node if isinstance(node, list) else [node]


def _template_ok(templates: Dict[str, Any], trigger: str, reveal_key: str,
                 team_name: str, other_name: str) -> bool:
    """A template is usable when it exists and never names the other team.
    (Two draft reveal lines hard-code "Copperfield"; on a Harbour Lights card
    they would say the wrong team, so those moments are held instead.)"""
    reveal = templates[trigger]["reveal"]
    if reveal_key not in reveal:
        return False
    texts: List[str] = []
    for variant in _variants(templates[trigger]["question"]["text"]):
        texts.extend(variant.values())
    for variant in _variants(reveal[reveal_key]["plain"]):
        texts.extend(variant.values())
    for lang in LANGS:
        texts.append(reveal[reveal_key]["expert"][lang])
    for text in texts:
        if other_name in text.replace("<team>", team_name):
            return False
    return True


def candidates(match: Dict[str, Any],
               templates: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (eligible candidates, held moments). One candidate per event/stoppage
    of the four trigger kinds; eligibility per task 1b, Pip's call per task 1c."""
    events = match["events"]
    pos_of_player = _positions(match)
    names = {t["team_id"]: t["name"] for t in match["teams"]}
    eligible: List[Dict[str, Any]] = []
    held: List[Dict[str, Any]] = []
    seq = 0

    def hold(trigger: str, t_in_min: float, team_id: str, reason: str) -> None:
        held.append({"trigger": trigger, "t_in_min": t_in_min,
                     "team_id": team_id, "reason": reason})

    def in_p1_added_time(period: int, t_in_min: float) -> bool:
        return period == 1 and t_in_min > 45.0

    # --- corners ---
    corner_pref = ["far", "near", "short", "central"]  # tie order for Pip's call
    for ev in events:
        if ev["type"] != "corner":
            continue
        period = ev["period"]
        t = clock_minutes(ev["t_ms"], match, period)
        team = ev["team_id"]
        if in_p1_added_time(period, t):
            hold("corner", t, team, "added_time")
            continue
        corners_total = sum(1 for e in events if e["type"] == "corner"
                            and e["team_id"] == team and e["idx"] <= ev["idx"])
        if corners_total < 3:
            hold("corner", t, team, "habit_not_clear_yet")
            continue
        answer = ev["set_piece"]["target_zone"]
        counts = {"near": 0, "far": 0, "short": 0, "central": 0}
        for e in events:
            if e["type"] == "corner" and e["team_id"] == team and e["idx"] < ev["idx"]:
                counts[e["set_piece"]["target_zone"]] += 1
        if sum(counts.values()) == 0:
            pippi = "far"
        else:
            pippi = max(corner_pref, key=lambda z: (counts[z], -corner_pref.index(z)))
        eligible.append({"seq": seq, "trigger": "corner", "event": ev, "stoppage": None,
                         "t_ms": ev["t_ms"], "period": period, "t_in_min": t, "team_id": team,
                         "pitch": ev["start"], "answer": answer, "pippi_call": pippi,
                         "reveal_key": answer, "goal_event_id": None})
        seq += 1

    # --- free kicks ---
    fk_pref = ["cross", "shoot", "short"]
    for ev in events:
        if ev["type"] != "free_kick":
            continue
        period = ev["period"]
        t = clock_minutes(ev["t_ms"], match, period)
        team = ev["team_id"]
        if in_p1_added_time(period, t):
            hold("free_kick", t, team, "added_time")
            continue
        if not _in_opponent_half(ev):
            hold("free_kick", t, team, "own_half")
            continue
        fk_total = sum(1 for e in events if e["type"] == "free_kick" and e["team_id"] == team
                       and e["idx"] <= ev["idx"] and _in_opponent_half(e))
        if fk_total < 2:
            hold("free_kick", t, team, "sample_too_small")
            continue
        answer = ev["set_piece"]["routine"]
        counts = {"shoot": 0, "cross": 0, "short": 0}
        for e in events:
            if (e["type"] == "free_kick" and e["team_id"] == team and e["idx"] < ev["idx"]
                    and _in_opponent_half(e)):
                counts[e["set_piece"]["routine"]] += 1
        if sum(counts.values()) == 0:
            pippi = "cross"
        else:
            pippi = max(fk_pref, key=lambda z: (counts[z], -fk_pref.index(z)))
        eligible.append({"seq": seq, "trigger": "free_kick", "event": ev, "stoppage": None,
                         "t_ms": ev["t_ms"], "period": period, "t_in_min": t, "team_id": team,
                         "pitch": ev["start"], "answer": answer, "pippi_call": pippi,
                         "reveal_key": answer, "goal_event_id": None})
        seq += 1

    # --- substitutions: first event of each sub window (events sharing t_ms) ---
    window_first: Dict[int, Dict[str, Any]] = {}
    for ev in events:
        if ev["type"] == "substitution" and ev["t_ms"] not in window_first:
            window_first[ev["t_ms"]] = ev
    for t_ms, first in sorted(window_first.items()):
        period = first["period"]
        t = clock_minutes(t_ms, match, period)
        team = first["team_id"]
        if in_p1_added_time(period, t):
            hold("substitution", t, team, "added_time")
            continue
        incoming_pos = pos_of_player[first["player_id"]]
        answer = {"FW": "attack", "DF": "defend", "MF": "fresh"}[incoming_pos]
        if answer in ("attack", "defend"):
            before = _count_position(match, team, t_ms, False, incoming_pos)
            after = _count_position(match, team, t_ms, True, incoming_pos)
            if before == after:
                hold("substitution", t, team, "no_visible_change")
                continue
        score = _score_before(match, t_ms)
        other = AWAY if team == HOME else HOME
        if score[team] < score[other]:
            pippi = "attack"
        elif score[team] > score[other]:
            pippi = "defend"
        else:
            pippi = "fresh"
        eligible.append({"seq": seq, "trigger": "substitution", "event": first, "stoppage": None,
                         "t_ms": t_ms, "period": period, "t_in_min": t, "team_id": team,
                         "pitch": first["start"], "answer": answer, "pippi_call": pippi,
                         "reveal_key": answer, "goal_event_id": None})
        seq += 1

    # --- VAR stoppages ---
    events_by_id = {ev["event_id"]: ev for ev in events}
    for stoppage in match["stoppages"]:
        if stoppage["type"] != "VAR":
            continue
        var = stoppage["var"]
        shot = events_by_id[stoppage["related_event_ids"][0]]
        t_ms = stoppage["t_start_ms"]
        period = period_of(t_ms, match)
        t = clock_minutes(t_ms, match, period)
        team = shot["team_id"]
        if in_p1_added_time(period, t):
            hold("var", t, team, "added_time")
            continue
        reveal_key = "%s:%s" % (var["check_type"], var["decision"])
        other = AWAY if team == HOME else HOME
        if not _template_ok(templates, "var", reveal_key, names[team], names[other]):
            hold("var", t, team, "no_template")
            continue
        eligible.append({"seq": seq, "trigger": "var", "event": shot, "stoppage": stoppage,
                         "t_ms": t_ms, "period": period, "t_in_min": t, "team_id": team,
                         "pitch": shot["start"], "answer": var["check_type"],
                         "pippi_call": "offside", "reveal_key": reveal_key,
                         "goal_event_id": shot["event_id"]})
        seq += 1

    # --- template sanity for the set-piece triggers (missing / wrong-team copy) ---
    keep: List[Dict[str, Any]] = []
    for cand in eligible:
        trigger = cand["trigger"]
        other = AWAY if cand["team_id"] == HOME else HOME
        if not _template_ok(templates, trigger, cand["reveal_key"],
                            names[cand["team_id"]], names[other]):
            hold(trigger, cand["t_in_min"], cand["team_id"], "no_template")
            continue
        keep.append(cand)
    return keep, held


# ---- selection (task 1d) ----------------------------------------------------

# Average length of the natural break before play restarts (published restart averages, brief 8.1).
# Live, Pip cannot know the real length in advance; it only uses these to decide whether a break is
# long enough to ask in. The question then stays open until play actually restarts.
EXPECTED_BREAK_S = {"corner": 34, "free_kick": 28, "substitution": 40, "var": 100}
MIN_ANSWER_WINDOW_S = 10  # newcomers need at least this long to read and answer
_QUIET_TYPES = ("substitution", "card", "foul")  # happen while the ball is dead


def moment_times(match: Dict[str, Any], cand: Dict[str, Any]) -> Dict[str, int]:
    """When the question opens (ball dead), when it closes (play restarts) and when the outcome is visible.
    Each is a signal a live event feed delivers at that moment; none needs knowledge of the future."""
    events = match["events"]
    if cand["trigger"] == "var":
        st = cand["stoppage"]
        nxt = next((e for e in events if e["t_ms"] >= st["t_end_ms"] and e["type"] not in _QUIET_TYPES), None)
        restart = nxt["t_ms"] if nxt else st["t_end_ms"]
        shot = cand["event"]
        pass_ev = next((e for e in reversed(events) if e["t_ms"] < shot["t_ms"] and e["team_id"] == shot["team_id"]
                        and e["type"] in ("pass", "cross", "free_kick", "corner", "throw_in")), None)
        times = {"dead_ms": st["t_start_ms"], "restart_ms": restart, "reveal_ms": st["t_end_ms"]}
        if pass_ev and shot["t_ms"] - pass_ev["t_ms"] < 15000:
            times["frame_ms"] = pass_ev["t_ms"]  # the frame VAR judges offside on
        return times
    if cand["trigger"] == "substitution":
        t = cand["t_ms"]
        nxt = next((e for e in events if e["t_ms"] > t and e["type"] not in _QUIET_TYPES), None)
        restart = nxt["t_ms"] if nxt else t
        return {"dead_ms": t, "restart_ms": restart, "reveal_ms": max(t, restart - 2000)}
    ev = cand["event"]  # corner / free kick: the kick itself restarts play
    prev = next((e for e in reversed(events) if e["t_ms"] < ev["t_ms"] and e["type"] not in ("substitution", "card")), None)
    dead = min((prev["t_ms"] + 1000) if prev else ev["t_ms"] - 20000, ev["t_ms"] - 3000)
    nxt = next((e for e in events if e["t_ms"] > ev["t_ms"]), None)
    reveal = min(max(nxt["t_ms"] if nxt else ev["t_ms"], ev["t_ms"] + 2000), ev["t_ms"] + 6000)
    return {"dead_ms": dead, "restart_ms": ev["t_ms"], "reveal_ms": reveal}


def select_cards(match: Dict[str, Any], eligible: List[Dict[str, Any]],
                 held: List[Dict[str, Any]],
                 templates: Optional[Dict[str, Any]] = None
                 ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Greedy in time order, as a live system must work; accept a candidate only if it breaks
    no rule against the cards already accepted (priority var > substitution > free_kick >
    corner only breaks exact ties).

    With `templates`, a card is also refused (`no_fresh_line`) when the question or the
    reveal text of its kind has no unused variant left: Pip never repeats a line
    within a match (AGENTS.md rule 8)."""
    goal_events = [(ev["t_ms"], ev["event_id"]) for ev in match["events"]
                   if ev["outcome"] == "goal"]
    # Live, Pip cannot know what comes later: decide in time order (priority only breaks exact ties).
    ordered = sorted(eligible, key=lambda c: (c["t_ms"], TRIGGER_PRIORITY[c["trigger"]], c["seq"]))
    accepted: List[Dict[str, Any]] = []

    def fresh_line_left(cand: Dict[str, Any]) -> bool:
        if templates is None:
            return True
        tpl = templates[cand["trigger"]]
        same = [a for a in accepted if a["trigger"] == cand["trigger"]]
        same_key = [a for a in same if a["reveal_key"] == cand["reveal_key"]]
        return (len(same) < len(_variants(tpl["question"]["text"]))
                and len(same_key) < len(_variants(tpl["reveal"][cand["reveal_key"]]["plain"])))

    for cand in ordered:
        reason: Optional[str] = None
        if EXPECTED_BREAK_S.get(cand["trigger"], 0) < MIN_ANSWER_WINDOW_S:
            reason = "break_usually_too_short"
        elif not fresh_line_left(cand):
            reason = "no_fresh_line"
        elif sum(1 for a in accepted if a["period"] == cand["period"]) >= MAX_PER_HALF:
            reason = "max_per_half"
        elif any(abs(cand["t_in_min"] - a["t_in_min"]) < MIN_GAP_MIN for a in accepted):
            reason = "too_close_to_previous_card"
        else:
            for g_ms, g_id in goal_events:
                if g_ms < cand["t_ms"] <= g_ms + GOAL_QUIET_S * 1000.0:
                    if cand["trigger"] == "var" and cand["goal_event_id"] == g_id:
                        continue  # the var card about this very goal is exempt
                    reason = "after_goal"
                    break
        if reason is None:
            accepted.append(cand)
        else:
            held.append({"trigger": cand["trigger"], "t_in_min": cand["t_in_min"],
                         "team_id": cand["team_id"], "reason": reason})

    accepted.sort(key=lambda c: (c["t_ms"], c["seq"]))
    held.sort(key=lambda h: (h["t_in_min"], h["trigger"], h["team_id"]))
    return accepted, held


# ---- output (task 1e) -------------------------------------------------------

def _scope_text(text: str, team_name: str, prefix: str) -> str:
    return re.sub(r"\{([a-z0-9_]+)\}", lambda m: "{" + prefix + m.group(1) + "}",
                  text.replace("<team>", team_name))


def _fact_source(name: str) -> str:
    if name == "league_short_share_pct":
        return "match-lab default priors"
    return "match-reader"


def _build(match: Dict[str, Any],
           templates: Optional[Dict[str, Any]] = None
           ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    if templates is None:
        templates = load_templates()
    eligible, held = candidates(match, templates)
    accepted, held = select_cards(match, eligible, held, templates)

    team_by_id = {t["team_id"]: t for t in match["teams"]}
    facts_out: Dict[str, Any] = {}
    cards: List[Dict[str, Any]] = []
    seen_question: Dict[str, int] = {}
    seen_reveal: Dict[Tuple[str, str], int] = {}
    for n, cand in enumerate(accepted, start=1):
        prefix = "c%d_" % n
        # card_id must match ^[a-z0-9-]{1,40}$ in overlay_card.schema.json, so the
        # trigger slug drops the underscore ("free_kick" -> "freekick", like
        # fake-match.json's "c4-freekick"). fact ids keep underscores.
        slug = cand["trigger"].replace("_", "")
        team = team_by_id[cand["team_id"]]
        tpl = templates[cand["trigger"]]
        reveal_tpl = tpl["reveal"][cand["reveal_key"]]
        # next unused wording, in time order (select_cards guarantees there is one)
        q_text = _variants(tpl["question"]["text"])[seen_question.get(cand["trigger"], 0)]
        plain_text = _variants(reveal_tpl["plain"])[seen_reveal.get((cand["trigger"], cand["reveal_key"]), 0)]
        seen_question[cand["trigger"]] = seen_question.get(cand["trigger"], 0) + 1
        key = (cand["trigger"], cand["reveal_key"])
        seen_reveal[key] = seen_reveal.get(key, 0) + 1
        fact_ids = [prefix + fid for fid in reveal_tpl["fact_ids"]]
        values = card_facts(match, cand)
        for fid in reveal_tpl["fact_ids"]:
            if fid not in values:
                raise ValueError("template %s needs fact %r the reader does not compute"
                                 % (cand["reveal_key"], fid))
            facts_out[prefix + fid] = {"value": values[fid], "source": _fact_source(fid)}
        cards.append({
            "card_id": "c%d-%s" % (n, slug),
            "moment_id": "m-%s-%d" % (slug, round(cand["t_in_min"])),
            "trigger": cand["trigger"],
            "t_in_min": cand["t_in_min"],
            "t_ms": cand["t_ms"],  # exact match time, for real-time replay from tracking
            **moment_times(match, cand),
            "expected_break_s": EXPECTED_BREAK_S[cand["trigger"]],
            "team_id": cand["team_id"],
            "pitch": {"x": cand["pitch"]["x"], "y": cand["pitch"]["y"]},
            "question": {
                "text": {lang: _scope_text(q_text[lang], team["name"], prefix)
                         for lang in LANGS},
                "options": copy.deepcopy(tpl["question"]["options"]),
                "pippi_call": cand["pippi_call"],
            },
            "reveal": {
                "answer": cand["answer"],
                "pose": "wow" if cand["pippi_call"] == cand["answer"] else "oops",
                "plain": {lang: _scope_text(plain_text[lang], team["name"], prefix)
                          for lang in LANGS},
                "expert": {lang: _scope_text(reveal_tpl["expert"][lang], team["name"], prefix)
                           for lang in LANGS},
                "fact_ids": fact_ids,
            },
        })

    kickoff = {"from_min": 0}
    kickoff.update({t["team_id"]: 0 for t in match["teams"]})
    timeline = [kickoff]
    running = {t["team_id"]: 0 for t in match["teams"]}
    for ev in match["events"]:
        if ev["outcome"] != "goal":
            continue
        running[ev["team_id"]] += 1
        entry = {"from_min": clock_minutes(ev["t_ms"], match, ev["period"])}
        entry.update(running)
        # Exact times let the screen show the goal like TV: scorer, celebration, then the kick-off restart.
        restart = next((e["t_ms"] for e in match["events"]
                        if e["t_ms"] > ev["t_ms"] and e.get("subtype") == "kick_off"), None)
        entry.update({"t_ms": ev["t_ms"], "team_id": ev["team_id"], "player_id": ev["player_id"],
                      "restart_ms": restart})
        timeline.append(entry)
    if dict(running) != {t: match["final_score"][t] for t in running}:
        raise ValueError("counted goals %s do not match final_score %s"
                         % (running, match["final_score"]))

    out = {
        "match_id": match["match_id"],
        "seed": match["seed"],
        "generator_version": match["generator_version"],
        "reader_version": READER_VERSION,
        "competition": match["competition"],
        "venue": match["venue"],
        "pitch": match["pitch"],
        "coord_system": match["coord_system"],
        "teams": [{"team_id": t["team_id"], "name": t["name"], "short_name": t["short_name"],
                   "kit": {"primary": t["kit"]["primary"], "secondary": t["kit"]["secondary"]}}
                  for t in match["teams"]],
        "score_timeline": timeline,
        "facts": facts_out,
        "cards": cards,
        "moments_held": held,
    }
    return out, accepted, held


def build_output(match: Dict[str, Any], templates: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The full demo-match dict (task 1e). Deterministic: same input -> same bytes."""
    out, _accepted, _held = _build(match, templates)
    return out

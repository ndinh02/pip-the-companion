import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import Mascot, { askPose } from "../components/Mascot";
import Crest from "../components/Crest";
import { nextRoomName, ROOM_NAMES } from "../lib/roomNames";
import AddedBreakdown from "../components/AddedBreakdown";
import Pitch from "../components/Pitch";
import ScorerSpotlight from "../components/ScorerSpotlight";
import { avatarOf } from "../lib/avatar";
import { choiceStyle } from "../lib/choices";
import { CAMERAS, type CameraId } from "../lib/cameras";
import { addedHeadline } from "../lib/addedTime";
import { lastTvRoom, type RoomStatus, useRoomChannel } from "../lib/channel";
import { buildHalf, HALF_MIN } from "../lib/halfTime";
import { advance, buildTimeline, hurrying, nextMoment, type MomentKind, clockBase, clockLabel, clockMinute, formatClock, skipAhead, startClock, viewAt, type Clock, type Mode } from "../lib/matchClock";
import { deadShot, goalShot } from "../lib/deadTime";
import { loadTracking, nearestToBall, positionsAt, type Tracking } from "../lib/tracking";
import { deviceLang, fmt, ui } from "../lib/i18n";
import { NAME } from "../lib/brand";
import { answerLabel, fill, loadAddedTime, loadMatch, loadPlayers, randomRoom, ROOM_RE, scoreAt, t } from "../lib/match";
import { LANGS, type HistoryItem, type AddedTime, type Lang, type Match, type Msg, type PlayersFeed, type StateMsg } from "../lib/types";

// The 3D view is a big library: load it only on the shared screen (phones never download it).
const Stadium3D = lazy(() => import("../components/Stadium3D"));
const TICK_MS = 100;
const REPLAY_PRE_MS = 2_500; // a replay starts this long before play restarted
const REPLAY_POST_MS = 2_000; // and runs this long past the outcome
const REPLAY_SLOWMO = 0.5; // replays run at half speed, like TV
const SPEEDS = [1, 4, 16];
const MOMENT_KEY: Record<MomentKind, Parameters<typeof ui>[0]> = {
  goal: "mGoal", var: "mVar", corner: "mCorner", free_kick: "mFreeKick", substitution: "mSub", added: "mAdded", half: "mHalf", full: "mFull",
};
const GOAL_POP_MS = 8_000; // Pip celebrates in the corner this long after a goal
const SPOTLIGHT_FROM_MS = 3_000; // the scorer's quick profile, from this long after the goal...
const SPOTLIGHT_TO_MS = 17_000; // ...until this long after it
const SCORER_FRESH_MS = 5 * 60_000; // phones offer the scorer's profile this long after a goal

/** /tv without a room code is the TV's front door: start a room, or resume the one this TV ran a moment ago. */
export default function Tv() {
  const [params, setParams] = useSearchParams();
  const r = params.get("room")?.toUpperCase() ?? "";
  if (!ROOM_RE.test(r)) return <TvHome fresh={!!params.get("fresh")} start={(room) => setParams({ room }, { replace: true })} />;
  return <TvRoom key={r} room={r} />;
}

function TvHome({ fresh, start }: { fresh: boolean; start: (room: string) => void }) {
  const [lang, setLang] = useState<Lang>(deviceLang);
  const last = fresh ? null : lastTvRoom();
  useEffect(() => {
    if (fresh) start(randomRoom()); // another tab on this TV runs the last room: start a new one straight away
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fresh]);
  return (
    <div className="tvn-home">
      <Mascot pose="wave" size={200} />
      {last ? (
        <>
          <h2>{ui("tvBack", lang)}</h2>
          <p>{fmt(ui("tvWasRunning", lang), { code: last })}</p>
          <button onClick={() => start(last)}>{fmt(ui("tvResume", lang), { code: last })}</button>
          <button className="tvn-textbtn" onClick={() => start(randomRoom())}>{ui("tvOrNew", lang)}</button>
        </>
      ) : (
        <>
          <h2>{NAME}</h2>
          <p>{ui("tvTag", lang)}</p>
          <button onClick={() => start(randomRoom())}>{ui("tvStart", lang)}</button>
        </>
      )}
      <span className="tvn-url">{location.host}/tv</span>
      <div className="tvn-home-langs">
        {LANGS.map((l) => <button key={l} className={l === lang ? "on" : ""} onClick={() => setLang(l)}>{l.toUpperCase()}</button>)}
      </div>
    </div>
  );
}

const CLOCK_KEEP_MS = 3 * 60 * 60 * 1000;
type SavedClock = { tMs: number; halfDone: boolean; mode: Mode; speed: number; at: number };

function TvRoom({ room }: { room: string }) {
  const [params, setParams] = useSearchParams();
  const [match, setMatch] = useState<Match | null>(null);
  const [added, setAdded] = useState<AddedTime | null>(null);
  const [players, setPlayers] = useState<PlayersFeed | null>(null);
  const [tracking, setTracking] = useState<Tracking | null>(null);
  const [trackingDone, setTrackingDone] = useState(false);
  const follows = useRef(new Map<string, string>()); // device -> player id
  const [error, setError] = useState<string | null>(null);
  const [lang, setLang] = useState<Lang>("en");
  const [answerTick, setAnswerTick] = useState(0);
  // The match clock is saved on this TV, so "Resume room" carries on where the match was instead of at 0'.
  const clockKey = `pip:tv-clock:${room}`;
  const restored = useMemo(() => {
    try {
      const v = JSON.parse(localStorage.getItem(clockKey) ?? "null") as SavedClock | null;
      return v && Date.now() - v.at < CLOCK_KEEP_MS ? v : null;
    } catch {
      return null;
    }
  }, [clockKey]);
  const [clk, setClk] = useState<Clock>(() =>
    restored ? { ...startClock(restored.mode), tMs: restored.tMs, halfDone: restored.halfDone, speed: restored.speed } : startClock(params.get("mode") === "full" ? "full" : "highlights"),
  );
  // The room opens in the lobby; the host presses Kick off when everyone is in (room prototype).
  const [kicked, setKicked] = useState(!!restored);
  const clkRef = useRef(clk);
  clkRef.current = clk;
  useEffect(() => {
    if (!kicked) return;
    const save = () => {
      const c = clkRef.current;
      try {
        localStorage.setItem(clockKey, JSON.stringify({ tMs: c.tMs, halfDone: c.halfDone, mode: c.mode, speed: c.speed, at: Date.now() } satisfies SavedClock));
      } catch {
        /* private mode: the clock lives as long as this page */
      }
    };
    const id = setInterval(save, 2000);
    window.addEventListener("pagehide", save);
    return () => {
      clearInterval(id);
      window.removeEventListener("pagehide", save);
    };
  }, [kicked, clockKey]);
  const [camera, setCamera] = useState<CameraId | "tactical">(() => (params.get("cam") as CameraId | "tactical") ?? "auto");

  useEffect(() => {
    loadMatch()
      .then((m) => {
        setMatch(m);
        loadTracking(m).then((tr) => {
          setTracking(tr);
          setTrackingDone(true);
        });
        loadPlayers(m).then(setPlayers).catch(() => undefined);
        return loadAddedTime(m).then(setAdded);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const tl = useMemo(() => (match && trackingDone ? buildTimeline(match, tracking, added) : null), [match, tracking, trackingDone, added]);

  // The clock never stops for Pip; only half-time pauses (as football does) and the operator's Pause button.
  useEffect(() => {
    if (!tl || !kicked) return;
    let last = Date.now();
    const id = setInterval(() => {
      const now = Date.now();
      const dt = now - last;
      last = now;
      setClk((c) => advance(tl, c, dt, now, allAnsweredRef.current));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [tl, kicked]);

  const allAnsweredRef = useRef(false);
  const view = tl ? viewAt(tl, clk) : null;
  const phase = view?.phase ?? "play";
  const card = view?.card ?? null;
  const phaseRef = useRef({ phase, cardId: card?.card_id });
  phaseRef.current = { phase, cardId: card?.card_id };

  const answers = useRef(new Map<string, Map<string, string>>()); // card_id -> device -> option
  const devices = useRef(new Set<string>());
  const animals = useRef(new Map<string, string>()); // device -> the animal that phone picked
  const animalOf = (d: string) => animals.current.get(d) ?? avatarOf(d);
  const tally = useMemo(() => {
    const out: Record<string, number> = {};
    if (card) answers.current.get(card.card_id)?.forEach((opt) => (out[opt] = (out[opt] ?? 0) + 1));
    return out;
    // answerTick is the change signal for the mutable ref above
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [card?.card_id, answerTick]);
  const answered = Object.values(tally).reduce((a, b) => a + b, 0);
  // The TV shows counts only until the reveal, never who picked what (owner decision 2026-10-23): nobody is put on
  // the spot in front of the room.
  allAnsweredRef.current = devices.current.size > 0 && answered >= devices.current.size;

  const [link, setLink] = useState<RoomStatus>("ok"); // "offline" = this screen cannot reach the server (the alarm)
  const send = useRoomChannel(room, "tv", (m: Msg) => {
    if (m.t === "hello") {
      devices.current.add(m.device);
      if (m.animal) animals.current.set(m.device, m.animal);
    } else if (m.t === "bye") {
      devices.current.delete(m.device);
      animals.current.delete(m.device);
      follows.current.delete(m.device);
    } else if (m.t === "follow") {
      // Only known player ids are accepted; the screen keeps a count per player, never who follows.
      if (m.player_id && tracking?.entities.includes(m.player_id)) follows.current.set(m.device, m.player_id);
      else follows.current.delete(m.device);
    } else if (m.t === "answer") {
      devices.current.add(m.device);
      const now = phaseRef.current;
      // Answers count only while the ball is dead. Once play restarts they are locked: the outcome is on its way.
      if (now.phase !== "ask" || now.cardId !== m.card_id || !card) return;
      if (!card.question.options.some((o) => o.id === m.option)) return; // only known option ids
      const per = answers.current.get(m.card_id) ?? new Map<string, string>();
      per.set(m.device, m.option);
      answers.current.set(m.card_id, per);
    } else return;
    setAnswerTick((n) => n + 1);
  }, setLink);

  const half = useMemo(
    () => (match && phase === "half" ? buildHalf(match, answers.current, scoreAt(match, HALF_MIN)) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [match, phase, answerTick],
  );
  const board = view?.board ?? null;
  // The latest goal stays "fresh" for phones (a profile button) for a few match minutes.
  const scorer = tl?.goals.filter((g) => clk.tMs >= g.t_ms && clk.tMs < g.t_ms + SCORER_FRESH_MS).pop()?.player_id ?? null;
  const minute = tl ? Math.floor(clockMinute(tl, clk.tMs)) : 0;
  const people = [...devices.current].map(animalOf);
  const clockMin = tl ? clockMinute(tl, clk.tMs) : 0;
  const base = tl ? clockBase(tl, clk.tMs) : 45;
  const clock = formatClock(clockMin, base);
  // How fast the match clock runs right now; 0 when it stands still (lobby, paused, half-time, full time).
  const clockRate = kicked && clk.running && clk.halfUntil === null && phase !== "full" && phase !== "half" ? clk.speed : 0;

  // The score changes when the ball is in the goal on screen (from the tracking), not at the minute in the event list.
  // Phones get exactly this score, so the room never sees two different numbers.
  const score = { HAR: 0, COP: 0 };
  if (tl && match) {
    for (const g of tl.goals) if (clk.tMs >= g.t_ms) score[g.team_id as "HAR" | "COP"] += 1;
    if (!tl.goals.length) Object.assign(score, scoreAt(match, clockMinute(tl, clk.tMs)));
  }
  // Every question the match has answered so far, with the room's picks (phones show it as the chat history).
  const doneKey = (match?.cards ?? [])
    .filter((c) => (c.reveal_ms !== undefined ? clk.tMs >= c.reveal_ms : c.t_in_min < minute))
    .map((c) => c.card_id).join(",");
  const history = useMemo<HistoryItem[]>(
    () => (doneKey ? doneKey.split(",") : []).map((id) => {
      const tallyH: Record<string, number> = {};
      const by: Record<string, string[]> = {};
      answers.current.get(id)?.forEach((opt, dev) => {
        tallyH[opt] = (tallyH[opt] ?? 0) + 1;
        (by[opt] ??= []).push(animalOf(dev));
      });
      return { card_id: id, tally: tallyH, by };
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [doneKey, answerTick],
  );
  // The room's name: the host taps through a fixed list (no typing, AGENTS.md rule 5); kept on this TV.
  const nameKey = `pip:tv-name:${room}`;
  const [roomName, setRoomName] = useState<string>(() => {
    try {
      return localStorage.getItem(nameKey) ?? ROOM_NAMES[room.charCodeAt(0) % ROOM_NAMES.length];
    } catch {
      return ROOM_NAMES[0];
    }
  });
  const renameRoom = () =>
    setRoomName((n) => {
      const v = nextRoomName(n);
      try {
        localStorage.setItem(nameKey, v);
      } catch {
        /* private mode */
      }
      return v;
    });

  // Push state to phones whenever something that matters changes (and on a heartbeat for late joiners).
  const lastSent = useRef("");
  const revealLeft = view?.phase === "reveal" && view.progress !== null ? ((1 - view.progress) * 12_000) / clk.speed : 0;
  const broadcast = useCallback(() => {
    const now = Date.now();
    const msg: StateMsg = {
      t: "state", phase: kicked ? phase : "lobby", minute, clock, clock_min: clockMin, clock_base: base, clock_rate: clockRate, card: kicked ? card : null, board, half,
      // No countdown while a question is open: live, nobody knows when play restarts.
      deadline: phase === "reveal" ? now + revealLeft : 0,
      total_ms: phase === "reveal" ? 12_000 / clk.speed : 0,
      tally, answered, scorer, joined: devices.current.size,
      answered_by: card ? [...(answers.current.get(card.card_id)?.keys() ?? [])].map(animalOf) : [],
      people, score, room_name: roomName, history,
    };
    const key = JSON.stringify([msg.phase, msg.minute, msg.card?.card_id, msg.board?.period, msg.half?.rows.length, msg.tally, msg.scorer, people, clockRate, score, roomName, doneKey]);
    if (key !== lastSent.current) {
      lastSent.current = key;
      send(msg);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, minute, clock, clockMin, base, card, board, half, tally, answered, scorer, revealLeft, clk.speed, send, kicked, people.join(""), clockRate, score.HAR, score.COP, roomName, history]);
  useEffect(broadcast, [broadcast]);
  // Heartbeat: resend the latest state every 1.5 s (late joiners, and phones keep their clock in step). The timer is
  // stable; it calls whatever broadcast is current, so the time it sends is never stale.
  const broadcastRef = useRef(broadcast);
  broadcastRef.current = broadcast;
  useEffect(() => {
    const id = setInterval(() => {
      lastSent.current = "";
      broadcastRef.current();
    }, 1500);
    return () => clearInterval(id);
  }, []);

  // On-screen furniture the host can put away: the corner QR, the lobby card, the half/full-time chip, help, "More".
  const [cornerOpen, setCornerOpen] = useState(false);
  const [lobbyHidden, setLobbyHidden] = useState(false);
  const [chip, setChip] = useState<{ phase: string; at: number; closed: boolean }>({ phase: "", at: 0, closed: false });
  useEffect(() => {
    if (phase === "half" || phase === "full") setChip({ phase, at: Date.now(), closed: false });
  }, [phase]);
  const [help, setHelp] = useState(() => {
    try {
      return !localStorage.getItem("pip:tv-help-seen"); // first time on this TV: show how it works
    } catch {
      return false;
    }
  });
  const closeHelp = () => {
    setHelp(false);
    try {
      localStorage.setItem("pip:tv-help-seen", "1");
    } catch {
      /* private mode */
    }
  };
  const [more, setMore] = useState(false);

  if (error) return <div className="center">Could not load the match: {error}</div>;
  if (!match || !tl || !view) return <div className="center">…</div>;

  const home = match.teams[0];
  const away = match.teams[1];
  const joinUrl = `${location.origin}/play/${room}`;
  // At the reveal, show the moment again like TV does: from just before the kick to just after the outcome.
  const replayLen = card ? card.reveal_ms + REPLAY_POST_MS - (card.restart_ms - REPLAY_PRE_MS) : 0;
  const intoReveal = card && phase === "reveal" ? clk.tMs - card.reveal_ms : -1;
  const replaying = !!card && phase === "reveal" && card.trigger !== "var" && card.trigger !== "substitution" && intoReveal >= 0 && intoReveal * REPLAY_SLOWMO < replayLen;
  // While the question is open the picture keeps moving: replays of what happened, then live (see lib/deadTime).
  const shot = replaying ? null : deadShot(card, phase, clk.tMs) ?? (card ? null : goalShot(tl, clk.tMs));
  const slow = replaying || !!shot?.slow;
  const viewMs = shot ? shot.viewMs : replaying && card ? card.restart_ms - REPLAY_PRE_MS + intoReveal * REPLAY_SLOWMO : clk.tMs;
  const dots = tracking ? positionsAt(tracking, viewMs) : null;
  // The player who takes the set piece (or scored, for VAR), ringed while the moment plays out.
  const ringId = card && tracking ? nearestToBall(positionsAt(tracking, card.restart_ms), card.team_id) : null;
  const followed: Record<string, number> = {};
  follows.current.forEach((pid) => (followed[pid] = (followed[pid] ?? 0) + 1));
  const now = Date.now();
  const goalNow = tl.goals.find((g) => clk.tMs >= g.t_ms && clk.tMs < g.t_ms + GOAL_POP_MS) ?? null;
  const goalTeam = goalNow ? match.teams.find((x) => x.team_id === goalNow.team_id) : undefined;
  const nextKind = clk.skipped ? nextMoment(tl, clk.skipped.to, clk.halfDone) : null;
  const host = location.host;
  const joined = Math.max(devices.current.size, answered);
  // Pip's note: full while the room is answering, a one-line strip once everyone is in (or play restarted), full
  // again for the outcome (correct answer filled in), then one line again for the rest of the reveal.
  const revealOpen = phase === "reveal" && (view.progress ?? 0) < 0.6;
  const noteCompact = (phase === "ask" && allAnsweredRef.current) || phase === "locked" || (phase === "reveal" && !revealOpen);
  const chipShown = (phase === "half" || phase === "full") && chip.phase === phase && !chip.closed && (phase === "full" || now - chip.at < 15_000);
  const spotlight = tl.goals.find((g) => clk.tMs >= g.t_ms + SPOTLIGHT_FROM_MS && clk.tMs < g.t_ms + SPOTLIGHT_TO_MS) ?? null;
  const setMode = (mode: Mode) => setClk((c) => ({ ...c, mode }));

  return (
    <div className={`tv ${slow ? "replaying" : ""}`}>
      {link === "offline" && <div className="tv-alarm" role="alert">{ui("tvOffline", lang)}</div>}
      {tracking && camera !== "tactical" ? (
        <Suspense fallback={<Pitch dots={dots} teams={match.teams} />}>
          <Stadium3D
            tracking={tracking}
            teams={match.teams}
            tMs={viewMs}
            speed={slow ? clk.speed * REPLAY_SLOWMO : clk.speed}
            running={clk.running && clk.halfUntil === null && (shot?.running ?? true)}
            camera={camera}
            focus={
              replaying
                ? { kind: "replay", playerId: ringId }
                : shot
                  ? { kind: shot.focus, x: card?.pitch.x, y: card?.pitch.y, playerId: shot.playerId ?? null, defending: match.teams.find((x) => x.team_id !== card?.team_id)?.team_id }
                  : card && phase === "locked" && card.trigger !== "substitution"
                    ? { kind: "setpiece", x: card.pitch.x, y: card.pitch.y }
                    : { kind: "play" }
            }
            ringId={card ? ringId : null}
            goals={tl.goals}
            followed={followed}
            replay={slow}
            badge={shot ? shot.badge : replaying ? "REPLAY" : null}
          />
        </Suspense>
      ) : (
        <>
          <Pitch marker={card?.pitch} dots={dots} teams={match.teams} ringId={ringId} followed={followed} easeMs={TICK_MS} />
          {(shot?.badge || replaying) && <div className="replay-badge">{shot?.badge ?? "REPLAY"}</div>}
        </>
      )}

      {/* Scoreboard stays clear of the card (top-left, inside the 5% safe area). */}
      <div className="scoreboard" aria-label="Scoreboard">
        <Crest team={home} size={30} />
        <span className="team">{home.short_name}</span>
        <span className="score">{score.HAR} – {score.COP}</span>
        <span className="team">{away.short_name}</span>
        <Crest team={away} size={30} />
        <span className="clock">{clock}</span>
        {kicked && clockRate === 0 && phase !== "half" && phase !== "full" && <span className="clock-paused">{ui("lvPaused", lang).toUpperCase()}</span>}
      </div>

      {goalNow && (
        <div className="goal-pop" role="status" key={goalNow.t_ms} style={{ borderColor: goalTeam?.kit.primary }}>
          <Mascot pose="wow" size={72} />
          <div>
            <strong>{ui("goal", lang)}</strong>
            <div>{goalTeam?.name} · {goalNow.player_id.split("-")[0]} #{goalNow.player_id.split("-")[1]}</div>
          </div>
        </div>
      )}

      {tl && hurrying(tl, clk, allAnsweredRef.current) && (
        <div className="skip-note" role="status">{ui("skippingWait", lang)} ▸▸</div>
      )}

      {clk.skipped && now < clk.skipped.until && (
        <div className="skip-note" role="status">
          {ui("skippingTo", lang)} {clockLabel(tl, clk.skipped.to)} ▸▸
          {nextKind && <span className="skip-next"> · {ui("next", lang)}: {ui(MOMENT_KEY[nextKind], lang)}</span>}
        </div>
      )}

      {(kicked || lobbyHidden) && (cornerOpen ? (
        // The full join card, only when someone asks for it; × puts it away again.
        <div className="tvn-corner open">
          <QRCodeSVG value={joinUrl} size={128} bgColor="#FFFFFF" fgColor="#14202F" />
          <div>
            <span className="tvn-mini">{host}</span>
            <b>{room}</b>
            <span className="tvn-faces">{people.slice(0, 6).join("")}{people.length > 6 ? ` +${people.length - 6}` : ""}</span>
          </div>
          <button className="tvn-x" onClick={() => setCornerOpen(false)} aria-label={ui("tvClose", lang)}>×</button>
        </div>
      ) : (
        // Out of the way during play: the code and the room's animals; tap for the QR. Pulses when someone joins.
        <button className="tvn-pill" key={people.length} onClick={() => setCornerOpen(true)} aria-label={ui("tvShowQr", lang)}>
          <span className="tvn-pill-qr" aria-hidden="true">▦</span>
          <b>{room}</b>
          {people.length > 0 && <span className="tvn-faces">{people.slice(0, 5).join("")}{people.length > 5 ? ` +${people.length - 5}` : ""}</span>}
        </button>
      ))}
      {!kicked && !lobbyHidden && (
        <div className="tvn-lobby">
          <div className="tvn-lobby-card">
            <span className="tvn-lobby-pip"><Mascot pose="wave" size={160} /></span>
            <button className="tvn-x" onClick={() => setLobbyHidden(true)} aria-label={ui("tvHide", lang)}>×</button>
            <div className="tvn-qr"><QRCodeSVG value={joinUrl} size={256} bgColor="#FFFFFF" fgColor="#14202F" /></div>
            <div className="tvn-lobby-text">
              <button className="tvn-name" onClick={renameRoom} title={ui("tvRename", lang)}>{roomName} <span aria-hidden="true">↻</span></button>
              <div className="tvn-code">{room}</div>
              <div className="tvn-lab">{fmt(ui("tvScanType", lang), { host })}</div>
              <div className="tvn-ppl">{people.length ? people.map((a, k) => <span key={k}>{a}</span>) : <span className="tvn-wait">…</span>}</div>
              <div className="tvn-lab">{fmt(ui("tvHereKick", lang), { n: people.length })}</div>
              <button className="tvn-kick" onClick={() => setKicked(true)}>{ui("tvKick", lang)} ▸</button>
            </div>
          </div>
        </div>
      )}

      {kicked && card && (phase === "ask" || phase === "locked" || phase === "reveal") && (noteCompact ? (
        // One line: the room is in (or play is back on), or the outcome has been shown.
        <section className={`tvn-note compact ${phase}`} aria-live="polite">
          <Mascot pose={phase === "reveal" ? (card.reveal.void ? "thinks" : card.reveal.pose) : "watching"} size={56} />
          {phase === "reveal" ? (
            card.reveal.void
              ? <b>{ui("noClear", lang)}</b>
              : <b><span className="tvn-tick">✓</span> {answerLabel(card, card.reveal.answer, lang)} · {fmt(ui("tvCalledIt", lang), { n: tally[card.reveal.answer] ?? 0, m: joined })}</b>
          ) : (
            <b>✓ {joined ? fmt(ui("tvAllIn", lang), { n: answered, m: joined }) : fmt(ui("tvAnswersIn", lang), { n: answered })}</b>
          )}
        </section>
      ) : (
        // Pip's note (room prototype): a paper card in the lower-left safe area. Counts only until the reveal, never who.
        <section className={`tvn-note ${phase}`} aria-live="polite">
          <span className="tvn-pip">
            <Mascot pose={phase === "reveal" ? (card.reveal.void ? "thinks" : card.reveal.pose) : askPose(card.trigger)} size={120} />
          </span>
          {phase === "ask" && (
            <>
              <h2>{t(card.question.text, lang)}</h2>
              <ul>
                {card.question.options.map((o, i) => (
                  <li key={o.id}><i className="tvn-sw" style={{ background: choiceStyle(i).bg }} />{t(o.label, lang)}<span className="tvn-n" key={tally[o.id] ?? 0}>{tally[o.id] ?? 0}</span></li>
                ))}
              </ul>
              <div className="tvn-says">{ui("shoutIt", lang)}</div>
            </>
          )}
          {phase === "reveal" && card.reveal.void && (
            <>
              <h2>{ui("noClear", lang)}</h2>
              <p>{fill(t(card.reveal.plain, lang), match.facts)}</p>
            </>
          )}
          {phase === "reveal" && !card.reveal.void && (
            <>
              <h2>{t(card.question.text, lang)}</h2>
              <ul>
                {card.question.options.map((o, i) => {
                  const right = o.id === card.reveal.answer;
                  return (
                    <li key={o.id} className={right ? "ans" : "not"}>
                      {right ? <span className="tvn-tick">✓</span> : <i className="tvn-sw" style={{ background: choiceStyle(i).bg }} />}
                      {t(o.label, lang)}<span className="tvn-n">{tally[o.id] ?? 0}</span>
                    </li>
                  );
                })}
              </ul>
              <p>{fill(t(card.reveal.plain, lang), match.facts)}</p>
            </>
          )}
        </section>
      ))}

      {spotlight && players && !card && (
        <ScorerSpotlight match={match} feed={players} playerId={spotlight.player_id} minute={clockMinute(tl, clk.tMs)} lang={lang} />
      )}

      {phase === "added" && board && (
        <section className="lower-third added" aria-live="polite">
          <div className="lt-head">
            <Mascot pose="thinks" size={88} />
            <div>
              <div className="eyebrow">{ui("addedTime", lang)} · {board.at_min}'</div>
              <h1>{addedHeadline(board.announced_min, lang)}</h1>
            </div>
          </div>
          <p className="plain">{ui("addedWhy", lang)}</p>
          <AddedBreakdown board={board} lang={lang} />
          <div className="bar"><i style={{ width: `${(1 - (view.progress ?? 0)) * 100}%` }} /></div>
        </section>
      )}

      {chipShown && (
        // Half-time is ad time on real TV: a small chip that leaves by itself (or with ×). The recap is on the phones.
        <div className="tvn-chip" role="status">
          <Mascot pose={phase === "full" ? "wave" : "perch"} size={64} />
          <div>
            <b>{phase === "full" ? ui("fullTime", lang) : ui("halfTime", lang)} · {home.short_name} {score.HAR}–{score.COP} {away.short_name}</b>
            <span>{ui("tvCallsOnPhones", lang)}</span>
          </div>
          <button className="tvn-x" onClick={() => setChip((c) => ({ ...c, closed: true }))} aria-label={ui("tvClose", lang)}>×</button>
        </div>
      )}

      {/* Controls for a first-time host (or a judge): the two things you need, "?" for how it works, the rest in More. */}
      <div className="tvc" role="group" aria-label={ui("tvControls", lang)}>
        {!kicked ? (
          <button className="tvc-main" onClick={() => setKicked(true)}>{ui("tvKick", lang)} ▸</button>
        ) : (
          <>
            <button className="tvc-main" onClick={() => setClk((c) => ({ ...c, running: !c.running }))}>{clk.running ? `❚❚ ${ui("tvPause", lang)}` : `▶ ${ui("tvPlay", lang)}`}</button>
            <button onClick={() => setClk((c) => skipAhead(tl, c, Date.now()))}>⏭ {ui("tvNext", lang)}</button>
          </>
        )}
        <button className="tvc-round" onClick={() => setHelp(true)} aria-label={ui("tvHelpTitle", lang)}>?</button>
        <button onClick={() => setMore((m) => !m)} aria-expanded={more}>⋯ {ui("tvMore", lang)}</button>
        {more && (
          <div className="tvc-more">
            <div><span>{ui("tvSpeed", lang)}</span>{SPEEDS.map((v) => <button key={v} className={clk.speed === v ? "on" : ""} onClick={() => setClk((c) => ({ ...c, speed: v }))}>×{v}</button>)}</div>
            <div><span>{ui("tvWatch", lang)}</span>
              <button className={clk.mode === "highlights" ? "on" : ""} onClick={() => setMode("highlights")}>{ui("tvHighlights", lang)}</button>
              <button className={clk.mode === "full" ? "on" : ""} onClick={() => setMode("full")}>{ui("tvFullMatch", lang)}</button>
            </div>
            <div><span>{ui("tvCamera", lang)}</span>
              <select value={camera} onChange={(e) => setCamera(e.target.value as CameraId | "tactical")}>
                {CAMERAS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            </div>
            <div><span>{ui("rmLang", lang)}</span>{LANGS.map((l) => <button key={l} className={l === lang ? "on" : ""} onClick={() => setLang(l)}>{l.toUpperCase()}</button>)}</div>
            <div className="tvc-row">
              <button onClick={() => { answers.current.clear(); setClk((c) => ({ ...startClock(c.mode), speed: c.speed })); setAnswerTick((n) => n + 1); setMore(false); }}>{ui("tvRestart", lang)}</button>
              <button onClick={() => setParams({ room: randomRoom() })}>{ui("tvNewRoom", lang)}</button>
              <a href={joinUrl} target="_blank" rel="noreferrer">{ui("tvOpenPhone", lang)} ↗</a>
            </div>
          </div>
        )}
      </div>

      {help && (
        <div className="tvn-help" role="dialog" aria-modal="true" aria-label={ui("tvHelpTitle", lang)}>
          <div className="tvn-help-in">
            <span className="tvn-lobby-pip"><Mascot pose="wave" size={150} /></span>
            <h2>{ui("tvHelpTitle", lang)}</h2>
            <ol>
              <li>{ui("tvHelp1", lang)}</li>
              <li>{ui("tvHelp2", lang)}</li>
              <li>{ui("tvHelp3", lang)}</li>
              <li>{ui("tvHelp4", lang)}</li>
            </ol>
            <button className="tvn-kick" onClick={closeHelp}>{ui("gotIt", lang)}</button>
          </div>
        </div>
      )}
    </div>
  );
}

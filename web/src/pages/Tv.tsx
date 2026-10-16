import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import Mascot from "../components/Mascot";
import AddedBreakdown from "../components/AddedBreakdown";
import HalfTimeCard from "../components/HalfTimeCard";
import Pitch from "../components/Pitch";
import { CAMERAS, type CameraId } from "../lib/cameras";
import { addedHeadline } from "../lib/addedTime";
import { useRoomChannel } from "../lib/channel";
import { buildHalf, HALF_MIN } from "../lib/halfTime";
import { advance, buildTimeline, clockLabel, clockMinute, skipAhead, startClock, viewAt, type Clock, type Mode } from "../lib/matchClock";
import { deadShot, goalShot } from "../lib/deadTime";
import { loadTracking, nearestToBall, positionsAt, type Tracking } from "../lib/tracking";
import { nowKey, ui } from "../lib/i18n";
import { answerLabel, fill, loadAddedTime, loadMatch, randomRoom, ROOM_RE, scoreAt, t } from "../lib/match";
import { LANGS, type AddedTime, type Lang, type Match, type Msg, type StateMsg } from "../lib/types";

// The 3D view is a big library: load it only on the shared screen (phones never download it).
const Stadium3D = lazy(() => import("../components/Stadium3D"));
const TICK_MS = 100;
const REPLAY_PRE_MS = 2_500; // a replay starts this long before play restarted
const REPLAY_POST_MS = 2_000; // and runs this long past the outcome
const REPLAY_SLOWMO = 0.5; // replays run at half speed, like TV
const SPEEDS = [1, 4, 16];
const GOAL_POP_MS = 8_000; // Pip celebrates in the corner this long after a goal

export default function Tv() {
  const [params, setParams] = useSearchParams();
  const [match, setMatch] = useState<Match | null>(null);
  const [added, setAdded] = useState<AddedTime | null>(null);
  const [tracking, setTracking] = useState<Tracking | null>(null);
  const [trackingDone, setTrackingDone] = useState(false);
  const follows = useRef(new Map<string, string>()); // device -> player id
  const [error, setError] = useState<string | null>(null);
  const [lang, setLang] = useState<Lang>("en");
  const [answerTick, setAnswerTick] = useState(0);
  const [clk, setClk] = useState<Clock>(() => startClock(params.get("mode") === "full" ? "full" : "highlights"));
  const [camera, setCamera] = useState<CameraId | "tactical">(() => (params.get("cam") as CameraId | "tactical") ?? "auto");

  const room = useMemo(() => {
    const r = params.get("room")?.toUpperCase() ?? "";
    return ROOM_RE.test(r) ? r : randomRoom();
  }, [params]);
  useEffect(() => {
    if (params.get("room") !== room) setParams({ room }, { replace: true });
  }, [room, params, setParams]);

  useEffect(() => {
    loadMatch()
      .then((m) => {
        setMatch(m);
        loadTracking(m).then((tr) => {
          setTracking(tr);
          setTrackingDone(true);
        });
        return loadAddedTime(m).then(setAdded);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const tl = useMemo(() => (match && trackingDone ? buildTimeline(match, tracking, added) : null), [match, tracking, trackingDone, added]);

  // The clock never stops for Pip; only half-time pauses (as football does) and the operator's Pause button.
  useEffect(() => {
    if (!tl) return;
    let last = Date.now();
    const id = setInterval(() => {
      const now = Date.now();
      const dt = now - last;
      last = now;
      setClk((c) => advance(tl, c, dt, now));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [tl]);

  const view = tl ? viewAt(tl, clk) : null;
  const phase = view?.phase ?? "play";
  const card = view?.card ?? null;
  const phaseRef = useRef({ phase, cardId: card?.card_id });
  phaseRef.current = { phase, cardId: card?.card_id };

  const answers = useRef(new Map<string, Map<string, string>>()); // card_id -> device -> option
  const devices = useRef(new Set<string>());
  const tally = useMemo(() => {
    const out: Record<string, number> = {};
    if (card) answers.current.get(card.card_id)?.forEach((opt) => (out[opt] = (out[opt] ?? 0) + 1));
    return out;
    // answerTick is the change signal for the mutable ref above
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [card?.card_id, answerTick]);
  const answered = Object.values(tally).reduce((a, b) => a + b, 0);

  const send = useRoomChannel(room, "tv", (m: Msg) => {
    if (m.t === "hello") {
      devices.current.add(m.device);
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
  });

  const half = useMemo(
    () => (match && phase === "half" ? buildHalf(match, answers.current, scoreAt(match, HALF_MIN)) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [match, phase, answerTick],
  );
  const board = view?.board ?? null;
  const minute = tl ? Math.floor(clockMinute(tl, clk.tMs)) : 0;
  const clock = tl ? clockLabel(tl, clk.tMs) : "0'";

  // Push state to phones whenever something that matters changes (and on a heartbeat for late joiners).
  const lastSent = useRef("");
  const revealLeft = view?.phase === "reveal" && view.progress !== null ? ((1 - view.progress) * 12_000) / clk.speed : 0;
  const broadcast = useCallback(() => {
    const now = Date.now();
    const msg: StateMsg = {
      t: "state", phase, minute, clock, card, board, half,
      // No countdown while a question is open: live, nobody knows when play restarts.
      deadline: phase === "reveal" ? now + revealLeft : 0,
      total_ms: phase === "reveal" ? 12_000 / clk.speed : 0,
      tally, answered,
    };
    const key = JSON.stringify([msg.phase, msg.minute, msg.card?.card_id, msg.board?.period, msg.half?.rows.length, msg.tally]);
    if (key !== lastSent.current) {
      lastSent.current = key;
      send(msg);
    }
  }, [phase, minute, clock, card, board, half, tally, answered, revealLeft, clk.speed, send]);
  useEffect(broadcast, [broadcast]);
  useEffect(() => {
    const id = setInterval(() => {
      lastSent.current = "";
      broadcast();
    }, 1500);
    return () => clearInterval(id);
  }, [broadcast]);

  if (error) return <div className="center">Could not load the match: {error}</div>;
  if (!match || !tl || !view) return <div className="center">…</div>;

  const score = scoreAt(match, clockMinute(tl, clk.tMs));
  const home = match.teams[0];
  const away = match.teams[1];
  const joinUrl = `${location.origin}/play/${room}`;
  const team = card ? match.teams.find((x) => x.team_id === card.team_id) : undefined;
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
  const goalNow = tl.goals.find((g) => clk.tMs >= g.t_ms && clk.tMs < g.t_ms + GOAL_POP_MS) ?? null;
  const goalTeam = goalNow ? match.teams.find((x) => x.team_id === goalNow.team_id) : undefined;
  const nowLine = card ? nowKey(card.trigger) : null;
  const setMode = (mode: Mode) => setClk((c) => ({ ...c, mode }));
  const now = Date.now();

  return (
    <div className={`tv ${slow ? "replaying" : ""}`}>
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
        <span className="team" style={{ borderColor: home.kit.primary }}>{home.short_name}</span>
        <span className="score">{score.HAR} – {score.COP}</span>
        <span className="team" style={{ borderColor: away.kit.primary }}>{away.short_name}</span>
        <span className="clock">{clock}</span>
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

      {clk.skipped && now < clk.skipped.until && (
        <div className="skip-note" role="status">{ui("skippingTo", lang)} {clockLabel(tl, clk.skipped.to)} ▸▸</div>
      )}

      <div className="join">
        <QRCodeSVG value={joinUrl} size={96} bgColor="#F6F3EC" fgColor="#0E1A2B" />
        <div>
          <strong>{ui("scan", lang)}</strong>
          <div className="mono">{room}</div>
          <div className="dim">{devices.current.size} {ui("phonesJoined", lang)}</div>
        </div>
      </div>

      {card && (phase === "ask" || phase === "locked" || phase === "reveal") && (
        <section className={`lower-third ${phase === "locked" ? "ask locked" : phase}`} aria-live="polite">
          <div className="lt-head">
            <Mascot pose={phase === "reveal" ? card.reveal.pose : "asks"} size={88} />
            <div>
              <div className="eyebrow">{ui("callIt", lang)} · {team?.name}</div>
              <h1>{t(card.question.text, lang)}</h1>
            </div>
          </div>

          {(phase === "ask" || phase === "locked") && (
            <>
              {phase === "ask" && nowLine && <p className="now-line">{ui(nowLine, lang)}</p>}
              <ul className="opts">
                {card.question.options.map((o) => (
                  <li key={o.id}>{t(o.label, lang)}<span className="count" key={tally[o.id] ?? 0}>{tally[o.id] ?? 0}</span></li>
                ))}
              </ul>
              <p className="window-note">
                {answered > 0 && <>{answered}/{Math.max(answered, devices.current.size)} {ui("answeredOf", lang)} · </>}
                {phase === "ask" ? ui("openUntilRestart", lang) : ui("answersClosed", lang)}
              </p>
            </>
          )}

          {phase === "reveal" && (
            <>
              <div className="eyebrow turf">{ui("matchSays", lang)}: {answerLabel(card, card.reveal.answer, lang)}</div>
              <p className="plain">{fill(t(card.reveal.plain, lang), match.facts)}</p>
              <p className="pippi-call">{ui("pippiCalled", lang)}: {answerLabel(card, card.question.pippi_call, lang)}</p>
              <div className="bar"><i style={{ width: `${(1 - (view.progress ?? 0)) * 100}%` }} /></div>
            </>
          )}
        </section>
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

      {phase === "half" && half && (
        <section className="lower-third half" aria-live="polite">
          <div className="lt-head">
            <Mascot pose="wave" size={88} />
            <div>
              <div className="eyebrow">{ui("halfTime", lang)} · {home.short_name} {half.score.HAR} – {half.score.COP} {away.short_name}</div>
              <h1>{ui("halfCalls", lang)}</h1>
            </div>
          </div>
          <HalfTimeCard match={match} half={half} lang={lang} />
          {clk.halfUntil && <div className="bar"><i style={{ width: `${Math.max(0, (clk.halfUntil - now) / 30_000) * 100}%` }} /></div>}
        </section>
      )}

      {phase === "full" && (
        <section className="lower-third reveal">
          <div className="lt-head"><Mascot pose="wave" size={88} /><h1>{ui("fullTime", lang)}</h1></div>
        </section>
      )}

      <div className="controls" role="group" aria-label="Demo controls">
        <span className="dim">Demo</span>
        <button onClick={() => setClk((c) => ({ ...c, running: !c.running }))}>{clk.running ? "Pause" : "Play"}</button>
        <button onClick={() => setClk((c) => skipAhead(tl, c, Date.now()))}>Next ▸</button>
        <button onClick={() => setClk((c) => ({ ...c, speed: SPEEDS[(SPEEDS.indexOf(c.speed) + 1) % SPEEDS.length] }))} aria-label="Speed">×{clk.speed}</button>
        <button className={clk.mode === "highlights" ? "on" : ""} onClick={() => setMode("highlights")} aria-pressed={clk.mode === "highlights"}>Highlights</button>
        <button className={clk.mode === "full" ? "on" : ""} onClick={() => setMode("full")} aria-pressed={clk.mode === "full"}>Full match</button>
        <label className="dim" htmlFor="cam">Camera</label>
        <select id="cam" value={camera} onChange={(e) => setCamera(e.target.value as CameraId | "tactical")}>
          {CAMERAS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
        <button onClick={() => { answers.current.clear(); setClk((c) => ({ ...startClock(c.mode), speed: c.speed })); setAnswerTick((n) => n + 1); }}>Restart</button>
        {LANGS.map((l) => (
          <button key={l} className={l === lang ? "on" : ""} onClick={() => setLang(l)}>{l.toUpperCase()}</button>
        ))}
        <a href={joinUrl} target="_blank" rel="noreferrer">Open phone ↗</a>
      </div>
    </div>
  );
}

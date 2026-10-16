import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import Mascot from "../components/Mascot";
import AddedBreakdown from "../components/AddedBreakdown";
import HalfTimeCard from "../components/HalfTimeCard";
import Pitch from "../components/Pitch";
import { addedHeadline } from "../lib/addedTime";
import { useRoomChannel } from "../lib/channel";
import { buildHalf, firstHalfCards, HALF_MIN } from "../lib/halfTime";
import { loadTracking, minuteToMs, nearestToBall, positionsAt, type Tracking } from "../lib/tracking";
import { ui } from "../lib/i18n";
import { answerLabel, fill, loadAddedTime, loadMatch, randomRoom, ROOM_RE, scoreAt, t } from "../lib/match";
import { LANGS, type AddedTime, type Card, type Lang, type Match, type Msg, type Phase, type StateMsg } from "../lib/types";

const SEC_PER_MATCH_MIN = 1.2; // demo clock: 1 match minute = 1.2 s
const FULL_TIME_MIN = 90;
/** Full time: 90', or one minute after the last card if a card falls in second-half added time. */
const endMinute = (m: Match) => Math.max(FULL_TIME_MIN, Math.ceil(m.cards[m.cards.length - 1]?.t_in_min ?? 0) + 1);
const ASK_MS = 20_000;
const REVEAL_MS = 14_000;
const ADDED_MS = 16_000;
const HALF_MS = 30_000;
const REPLAY_LEAD_MS = 6_000; // a replay starts this long before the moment and runs in real time through the reveal
const CALM_MS = 600; // during the fast demo clock the pitch updates this often, eased, so it reads as a calm time-lapse

interface Engine {
  minute: number;
  phase: Phase;
  next: number; // index of the next card to fire
  board: number; // index of the next added-time board to show (45', 90')
  halfDone: boolean; // half-time card shown
  card: Card | null;
  deadline: number;
  total_ms: number;
}

export default function Tv() {
  const [params, setParams] = useSearchParams();
  const [match, setMatch] = useState<Match | null>(null);
  const [added, setAdded] = useState<AddedTime | null>(null);
  const [tracking, setTracking] = useState<Tracking | null>(null);
  const follows = useRef(new Map<string, string>()); // device -> player id
  const [error, setError] = useState<string | null>(null);
  const [lang, setLang] = useState<Lang>("en");
  const [speed, setSpeed] = useState(1);
  const [running, setRunning] = useState(true);
  const [answerTick, setAnswerTick] = useState(0);

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
        loadTracking(m).then(setTracking);
        return loadAddedTime(m).then(setAdded);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const [eng, setEng] = useState<Engine>({ minute: 0, phase: "play", next: 0, board: 0, halfDone: false, card: null, deadline: 0, total_ms: 0 });
  const answers = useRef(new Map<string, Map<string, string>>()); // card_id -> device -> option
  const devices = useRef(new Set<string>());

  const cardAnswers = (c: Card | null) => (c ? answers.current.get(c.card_id) : undefined);
  const tally = useMemo(() => {
    const out: Record<string, number> = {};
    cardAnswers(eng.card)?.forEach((opt) => (out[opt] = (out[opt] ?? 0) + 1));
    return out;
    // answerTick is the change signal for the mutable ref above
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eng.card, answerTick]);
  const answered = Object.values(tally).reduce((a, b) => a + b, 0);

  // Match clock + card lifecycle. Cards stay until play resumes; the clock is frozen while a card is up.
  useEffect(() => {
    if (!match || !running) return;
    const id = setInterval(() => {
      setEng((s) => {
        const now = Date.now();
        if (s.phase === "play") {
          const end = endMinute(match);
          const minute = Math.min(end, s.minute + (0.1 / SEC_PER_MATCH_MIN) * speed);
          const nextCard = match.cards[s.next];
          const cardAt = nextCard?.t_in_min ?? Infinity;
          const boardAt = added?.boards[s.board]?.at_min ?? Infinity;
          // Half-time card: after the 45' added-time board, and only if there was a first-half question.
          const boardPending = added?.boards[s.board]?.at_min === HALF_MIN;
          const halfAt = s.halfDone || boardPending || !firstHalfCards(match).length ? Infinity : HALF_MIN;
          if (minute >= Math.min(cardAt, boardAt, halfAt)) {
            // Whichever comes first: a Call-it card, an added-time board (45' / 90'), or half-time.
            if (cardAt <= boardAt && cardAt <= halfAt)
              return { ...s, minute: cardAt, phase: "ask", card: nextCard, deadline: now + ASK_MS, total_ms: ASK_MS };
            if (boardAt <= halfAt)
              return { ...s, minute: boardAt, phase: "added", card: null, deadline: now + ADDED_MS, total_ms: ADDED_MS };
            return { ...s, minute: halfAt, phase: "half", card: null, deadline: now + HALF_MS, total_ms: HALF_MS };
          }
          if (minute >= end) return { ...s, minute: end, phase: "full", card: null };
          return { ...s, minute };
        }
        if (s.phase === "ask" && now >= s.deadline) return { ...s, phase: "reveal", deadline: now + REVEAL_MS, total_ms: REVEAL_MS };
        if (s.phase === "reveal" && now >= s.deadline) return { ...s, phase: "play", card: null, next: s.next + 1 };
        if (s.phase === "added" && now >= s.deadline) return { ...s, phase: "play", board: s.board + 1 };
        if (s.phase === "half" && now >= s.deadline) return { ...s, phase: "play", halfDone: true };
        return s;
      });
    }, 100);
    return () => clearInterval(id);
  }, [match, added, running, speed]);

  const send = useRoomChannel(room, "tv", (m: Msg) => {
    if (m.t === "hello") {
      devices.current.add(m.device);
      setAnswerTick((n) => n + 1);
    } else if (m.t === "follow") {
      // Only known player ids are accepted; the TV keeps a count per player, never who follows.
      if (m.player_id && tracking?.entities.includes(m.player_id)) follows.current.set(m.device, m.player_id);
      else follows.current.delete(m.device);
      setAnswerTick((n) => n + 1);
    } else if (m.t === "answer") {
      devices.current.add(m.device);
      setEng((s) => {
        if (s.phase !== "ask" || s.card?.card_id !== m.card_id) return s;
        // Server-side style validation: only known option ids are accepted.
        if (!s.card.question.options.some((o) => o.id === m.option)) return s;
        const per = answers.current.get(m.card_id) ?? new Map<string, string>();
        per.set(m.device, m.option);
        answers.current.set(m.card_id, per);
        // Everyone locked in -> reveal early.
        if (per.size >= devices.current.size && devices.current.size > 0) return { ...s, phase: "reveal", deadline: Date.now() + REVEAL_MS, total_ms: REVEAL_MS };
        return s;
      });
      setAnswerTick((n) => n + 1);
    }
  });

  // Push state to phones whenever something that matters changes (and once a second for the clock).
  const half = useMemo(
    () => (match && eng.phase === "half" ? buildHalf(match, answers.current, scoreAt(match, HALF_MIN)) : null),
    // answerTick is the change signal for the mutable answers ref
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [match, eng.phase, answerTick],
  );
  const lastSent = useRef("");
  const board = eng.phase === "added" ? (added?.boards[eng.board] ?? null) : null;
  const broadcast = useCallback(() => {
    const msg: StateMsg = { t: "state", phase: eng.phase, minute: Math.floor(eng.minute), card: eng.card, board, half, deadline: eng.deadline, total_ms: eng.total_ms, tally, answered };
    const key = JSON.stringify([msg.phase, msg.minute, msg.card?.card_id, msg.board?.period, msg.half?.rows.length, msg.deadline, msg.tally]);
    if (key !== lastSent.current) {
      lastSent.current = key;
      send(msg);
    }
  }, [eng, board, half, tally, answered, send]);
  useEffect(broadcast, [broadcast]);
  useEffect(() => {
    const id = setInterval(() => {
      lastSent.current = ""; // heartbeat so late joiners catch up
      broadcast();
    }, 1500);
    return () => clearInterval(id);
  }, [broadcast]);

  const now = useNow(eng.phase === "ask" || eng.phase === "reveal" || eng.phase === "added" || eng.phase === "half");

  // Calm time-lapse clock for the pitch while the demo clock runs fast.
  const [calmMinute, setCalmMinute] = useState(0);
  const minuteRef = useRef(0);
  minuteRef.current = eng.minute;
  useEffect(() => {
    const id = setInterval(() => setCalmMinute(minuteRef.current), CALM_MS);
    return () => clearInterval(id);
  }, []);

  if (error) return <div className="center">Could not load the match: {error}</div>;
  if (!match) return <div className="center">…</div>;

  const score = scoreAt(match, eng.minute);
  const home = match.teams[0];
  const away = match.teams[1];
  const card = eng.card;
  const joinUrl = `${location.origin}/play/${room}`;
  const remain = Math.max(0, Math.min(1, (eng.deadline - now) / (eng.total_ms || 1)));
  const team = card ? match.teams.find((x) => x.team_id === card.team_id) : undefined;

  // What the pitch shows: a frozen set-up while the question is open, a real-time replay during the reveal,
  // and a calm time-lapse otherwise.
  const replay = !!tracking && !!card && card.t_ms !== undefined && (eng.phase === "ask" || eng.phase === "reveal");
  let viewMs = tracking ? minuteToMs(tracking, calmMinute) : 0;
  if (replay && card?.t_ms !== undefined) {
    const start = card.t_ms - REPLAY_LEAD_MS;
    viewMs = eng.phase === "ask" ? start : start + (eng.total_ms - Math.max(0, eng.deadline - now));
  }
  const dots = tracking ? positionsAt(tracking, viewMs) : null;
  const ringId = replay && tracking && card?.t_ms !== undefined ? nearestToBall(positionsAt(tracking, card.t_ms), card.team_id) : null;
  const followed: Record<string, number> = {};
  follows.current.forEach((pid) => (followed[pid] = (followed[pid] ?? 0) + 1));

  const skipToNext = () => {
    const upNext = Math.min(match.cards[eng.next]?.t_in_min ?? Infinity, added?.boards[eng.board]?.at_min ?? Infinity, eng.halfDone || !firstHalfCards(match).length ? Infinity : HALF_MIN);
    if (eng.phase === "play" && upNext < Infinity) setEng((s) => ({ ...s, minute: upNext - 0.01 }));
    else if (eng.phase === "added") setEng((s) => ({ ...s, phase: "play", board: s.board + 1 }));
    else if (eng.phase === "half") setEng((s) => ({ ...s, phase: "play", halfDone: true }));
    else if (eng.phase === "ask") setEng((s) => ({ ...s, phase: "reveal", deadline: Date.now() + REVEAL_MS, total_ms: REVEAL_MS }));
    else if (eng.phase === "reveal") setEng((s) => ({ ...s, phase: "play", card: null, next: s.next + 1 }));
  };
  const restart = () => {
    answers.current.clear();
    setEng({ minute: 0, phase: "play", next: 0, board: 0, halfDone: false, card: null, deadline: 0, total_ms: 0 });
    setAnswerTick((n) => n + 1);
  };

  return (
    <div className="tv">
      <Pitch marker={card?.pitch} dots={dots} teams={match.teams} ringId={ringId} followed={followed} easeMs={replay ? 100 : CALM_MS} />

      {/* Scoreboard stays clear of the card (top-left, inside the 5% safe area). */}
      <div className="scoreboard" aria-label="Scoreboard">
        <span className="team" style={{ borderColor: home.kit.primary }}>{home.short_name}</span>
        <span className="score">{score.HAR} – {score.COP}</span>
        <span className="team" style={{ borderColor: away.kit.primary }}>{away.short_name}</span>
        <span className="clock">{Math.floor(eng.minute)}'</span>
      </div>

      <div className="join">
        <QRCodeSVG value={joinUrl} size={96} bgColor="#F6F3EC" fgColor="#0E1A2B" />
        <div>
          <strong>{ui("scan", lang)}</strong>
          <div className="mono">{room}</div>
          <div className="dim">{devices.current.size} {ui("phonesJoined", lang)}</div>
        </div>
      </div>

      {card && eng.phase !== "play" && (
        <section className={`lower-third ${eng.phase}`} aria-live="polite">
          <div className="lt-head">
            <Mascot pose={eng.phase === "ask" ? "asks" : card.reveal.pose} size={88} />
            <div>
              <div className="eyebrow">{ui("callIt", lang)} · {team?.name}</div>
              <h1>{t(card.question.text, lang)}</h1>
            </div>
          </div>

          {eng.phase === "ask" && (
            <>
              <ul className="opts">
                {card.question.options.map((o) => (
                  <li key={o.id}>{t(o.label, lang)}<span className="count">{tally[o.id] ?? 0}</span></li>
                ))}
              </ul>
              <div className="bar"><i style={{ width: `${remain * 100}%` }} /></div>
            </>
          )}

          {eng.phase === "reveal" && (
            <>
              <div className="eyebrow turf">{ui("matchSays", lang)}: {answerLabel(card, card.reveal.answer, lang)}</div>
              <p className="plain">{fill(t(card.reveal.plain, lang), match.facts)}</p>
              <p className="pippi-call">{ui("pippiCalled", lang)}: {answerLabel(card, card.question.pippi_call, lang)}</p>
              <div className="bar"><i style={{ width: `${remain * 100}%` }} /></div>
            </>
          )}
        </section>
      )}

      {eng.phase === "added" && board && (
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
          <div className="bar"><i style={{ width: `${remain * 100}%` }} /></div>
        </section>
      )}

      {eng.phase === "half" && half && (
        <section className="lower-third half" aria-live="polite">
          <div className="lt-head">
            <Mascot pose="wave" size={88} />
            <div>
              <div className="eyebrow">{ui("halfTime", lang)} · {home.short_name} {half.score.HAR} – {half.score.COP} {away.short_name}</div>
              <h1>{ui("halfCalls", lang)}</h1>
            </div>
          </div>
          <HalfTimeCard match={match} half={half} lang={lang} />
          <div className="bar"><i style={{ width: `${remain * 100}%` }} /></div>
        </section>
      )}

      {eng.phase === "full" && (
        <section className="lower-third reveal">
          <div className="lt-head"><Mascot pose="wave" size={88} /><h1>{ui("fullTime", lang)}</h1></div>
        </section>
      )}

      <div className="controls" role="group" aria-label="Demo controls">
        <span className="dim">Demo controls</span>
        <button onClick={() => setRunning((r) => !r)}>{running ? "Pause" : "Play"}</button>
        <button onClick={skipToNext}>Next ▸</button>
        <button onClick={() => setSpeed((s) => (s === 1 ? 4 : 1))}>×{speed}</button>
        <button onClick={restart}>Restart</button>
        {LANGS.map((l) => (
          <button key={l} className={l === lang ? "on" : ""} onClick={() => setLang(l)}>{l.toUpperCase()}</button>
        ))}
        <a href={joinUrl} target="_blank" rel="noreferrer">Open phone ↗</a>
      </div>
    </div>
  );
}

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

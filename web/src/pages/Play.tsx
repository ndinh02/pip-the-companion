import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import AddedBreakdown from "../components/AddedBreakdown";
import HalfTimeCard from "../components/HalfTimeCard";
import WhosThat from "../components/WhosThat";
import { FollowView, GhostRun } from "../components/FollowView";
import { loadTracking, type Tracking } from "../lib/tracking";
import Mascot from "../components/Mascot";
import { addedHeadline } from "../lib/addedTime";
import { deviceId, useRoomChannel } from "../lib/channel";
import { NAME } from "../lib/brand";
import { HALF_MIN, shareText } from "../lib/halfTime";
import { clampMinute, followLine, loadFollow, saveFollow } from "../lib/whoThat";
import { deviceLang, nowKey, ui } from "../lib/i18n";
import { factAt } from "../lib/didYouKnow";
import { avatarOf } from "../lib/avatar";
import { choiceStyle } from "../lib/choices";
import { alertsWanted, buzz, disableAlerts, enableAlerts, keepAwake, resumeSound } from "../lib/buzz";
import { answerLabel, fill, loadMatch, loadPlayers, ROOM_RE, t } from "../lib/match";
import { LANGS, type HalfSummary, type Lang, type Match, type Msg, type PlayersFeed, type StateMsg } from "../lib/types";

export default function Play() {
  const room = (useParams().room ?? "").toUpperCase();
  const valid = ROOM_RE.test(room);
  const [lang, setLang] = useState<Lang>(deviceLang);
  const [match, setMatch] = useState<Match | null>(null);
  const [state, setState] = useState<StateMsg | null>(null);
  const [picked, setPicked] = useState<Record<string, string>>({}); // card_id -> option
  const [deep, setDeep] = useState(false);
  const [half, setHalf] = useState<HalfSummary | null>(null); // kept after half-time so the card can be reopened and shared
  const [showHalf, setShowHalf] = useState(false);
  const [players, setPlayers] = useState<PlayersFeed | null>(null);
  const [showWho, setShowWho] = useState(false);
  const [whoStart, setWhoStart] = useState<string | null>(null); // open "Who's that?" straight on this player
  const [showFollow, setShowFollow] = useState(false);
  const [tracking, setTracking] = useState<Tracking | null>(null);
  const [followId, setFollowId] = useState<string | null>(loadFollow);
  const [copied, setCopied] = useState(false);
  const device = useMemo(deviceId, []);
  const [alerts, setAlerts] = useState(alertsWanted);

  useEffect(() => {
    loadMatch()
      .then((m) => {
        setMatch(m);
        return loadPlayers(m).then(setPlayers);
      })
      .catch(() => undefined);
  }, []);

  const send = useRoomChannel(valid ? room : "INVALID", "phone", (m: Msg) => {
    if (m.t === "state") setState(m);
  });
  useEffect(() => {
    if (valid) send({ t: "hello", device });
  }, [valid, device, send]);

  // Tell the TV which player this phone follows (the TV shows an anonymous count only). Re-sent when the TV appears.
  // Positions are a big file: fetch them only once this phone follows someone.
  useEffect(() => {
    if (match && followId && !tracking) loadTracking(match).then(setTracking);
  }, [match, followId, tracking]);

  const tvSeen = !!state;
  useEffect(() => {
    if (valid && tvSeen) send({ t: "follow", device, player_id: followId });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valid, tvSeen, followId, device]);

  useEffect(() => {
    if (state?.phase === "ask") {
      setShowWho(false);
      setShowFollow(false);
    } // a question always takes over the screen
  }, [state?.phase]);

  useEffect(() => {
    if (state?.half) setHalf(state.half);
  }, [state?.half]);

  useEffect(() => {
    setDeep(false); // collapse "Go deeper" for each new card
  }, [state?.card?.card_id, state?.board?.period]);

  // Wake the viewer when Pip asks (buzz + chime, opt-in), and softly when the match answers.
  const askId = state?.phase === "ask" ? state.card?.card_id : undefined;
  useEffect(() => {
    if (askId) buzz("ask");
  }, [askId]);
  const revealId = state?.phase === "reveal" ? state.card?.card_id : undefined;
  useEffect(() => {
    if (revealId) buzz("reveal");
  }, [revealId]);
  // Sound is locked again after every page load until the next tap; the screen lock drops when the tab is hidden.
  useEffect(() => {
    if (!alerts) return;
    const tap = () => void resumeSound();
    const back = () => void keepAwake();
    void keepAwake();
    window.addEventListener("pointerdown", tap);
    document.addEventListener("visibilitychange", back);
    return () => {
      window.removeEventListener("pointerdown", tap);
      document.removeEventListener("visibilitychange", back);
    };
  }, [alerts]);

  // "Did you know?" facts rotate while the ball is dead (phone's own clock since the question opened).
  const [askAt, setAskAt] = useState(0);
  useEffect(() => {
    if (askId) setAskAt(Date.now());
  }, [askId]);

  // Bar drain: re-render ~10x/s only while a card is up.
  const [now, setNow] = useState(() => Date.now());
  const live = (state?.phase === "ask" && !!picked[state.card?.card_id ?? ""]) || state?.phase === "reveal" || state?.phase === "added" || state?.phase === "half";
  useEffect(() => {
    if (!live) return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [live]);

  if (!valid)
    return (
      <div className="phone center">
        <Mascot pose="thinks" />
        <p>{ui("badRoom", lang)}</p>
      </div>
    );

  const card = state?.card ?? null;
  const mine = card ? picked[card.card_id] : undefined;
  const remain = state ? Math.max(0, Math.min(1, (state.deadline - now) / (state.total_ms || 1))) : 0;
  const dark = (!state || state.phase === "play" || state.phase === "locked") && !showHalf && !showWho && !showFollow; // "Eyes up": nothing moves during open play

  const share = async () => {
    if (!match || !half) return;
    const text = shareText(match, half, lang, {
      title: `${ui("halfTime", lang)} · ${NAME}`, room: ui("halfRoom", lang), match: ui("halfMatch", lang),
      split: ui("halfSplit", lang), word: ui("wordOfMatch", lang),
    });
    try {
      if (navigator.share) await navigator.share({ title: ui("halfCard", lang), text });
      else {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch {
      /* share sheet dismissed: nothing to do */
    }
  };
  const followed = players?.players.find((p) => p.player_id === followId) ?? null;
  const onFollow = (id: string | null) => {
    setFollowId(id);
    saveFollow(id);
  };
  const alertsOptIn = !alerts && (
    <button className="alert-optin" onClick={() => { void enableAlerts(); setAlerts(true); }}>
      <strong>🔔 {ui("alertsOn", lang)}</strong>
      <span className="dim">{ui("alertsHint", lang)}</span>
    </button>
  );
  const nowLine = card ? nowKey(card.trigger) : null;
  const whoButton = players && match && <button className="ghost" onClick={() => { setWhoStart(null); setShowWho(true); }}>{ui("whosThat", lang)}</button>;
  const scorerButton = players && match && state?.scorer && players.players.some((p) => p.player_id === state.scorer) && (
    <button className="scorer-btn" onClick={() => { setWhoStart(state.scorer ?? null); setShowWho(true); }}>⚽ {ui("seeScorer", lang)}</button>
  );
  const fact = card && state?.phase === "ask" ? factAt(card.trigger, now - askAt, lang, card.card_id) : null;
  const halfView = match && half && (
    <main>
      <Mascot pose="wave" size={96} />
      <div className="eyebrow">{ui("halfTime", lang)} · {match.teams[0].short_name} {half.score.HAR} – {half.score.COP} {match.teams[1].short_name}</div>
      <h2>{ui("halfCalls", lang)}</h2>
      <HalfTimeCard match={match} half={half} lang={lang} mine={picked}
        followLine={followed && players ? followLine(match, followed, clampMinute(players, HALF_MIN), lang) : undefined} />
      <button className="ghost" onClick={share}>{copied ? ui("copied", lang) : ui("share", lang)}</button>
      {followed && tracking && <GhostRun match={match} tracking={tracking} p={followed} untilMs={tracking.periods[1].start_ms} lang={lang} />}
      {whoButton}
    </main>
  );

  return (
    <div className={`phone ${dark ? "eyes-up" : ""}`}>
      <header>
        <span className="mono">{room}</span>
        <span className="dim">{state ? state.clock ?? `${state.minute}'` : ""}</span>
        {followed && match && (
          <button className="follow-chip" aria-label={ui("yourPlayer", lang)} onClick={() => { setShowWho(false); setShowFollow(true); }}>★ {followed.team_id} #{followed.shirt_no}</button>
        )}
        {alerts && (
          <button className="alert-chip" aria-label={ui("alertsOff", lang)} title={ui("alertsOff", lang)} onClick={() => { disableAlerts(); setAlerts(false); }}>🔔</button>
        )}
        <div className="langs">
          {LANGS.map((l) => (
            <button key={l} className={l === lang ? "on" : ""} onClick={() => setLang(l)} aria-pressed={l === lang}>{l.toUpperCase()}</button>
          ))}
        </div>
      </header>

      {!state && (
        <main className="center">
          <Mascot pose="thinks" />
          <h2>{ui("waitingTv", lang)}</h2>
          <p className="dim">{ui("waitingTvHint", lang)}</p>
          {alertsOptIn}
        </main>
      )}

      {state && dark && state.phase !== "locked" && !showWho && !showFollow && (
        <main className="center">
          <div className="sleep-dot" aria-hidden="true" />
          <p className="dim">{ui("eyesUp", lang)}</p>
          {scorerButton}
          {alertsOptIn}
          {half && <button className="ghost" onClick={() => setShowHalf(true)}>{ui("halfCard", lang)}</button>}
          {whoButton}
        </main>
      )}

      {showWho && !showFollow && players && match && state && state.phase !== "ask" && (
        <WhosThat key={whoStart ?? "pick"} startId={whoStart} match={match} feed={players} minute={state.minute} lang={lang} followId={followId} onFollow={onFollow} onClose={() => setShowWho(false)} />
      )}

      {showFollow && followed && players && match && state && state.phase !== "ask" && (
        <FollowView match={match} feed={players} tracking={tracking} p={followed} minute={state.minute} lang={lang} onClose={() => setShowFollow(false)} />
      )}

      {showHalf && !showWho && !showFollow && state?.phase === "play" && (
        <>
          {halfView}
          <button className="ghost close" onClick={() => setShowHalf(false)}>{ui("hide", lang)}</button>
        </>
      )}

      {state && state.phase === "half" && !showWho && !showFollow && halfView}

      {state && card && state.phase === "ask" && !mine && (
        <main className="kq wake" key={card.card_id}>
          <div className="kq-head">
            <Mascot pose="asks" size={56} />
            <div>
              <div className="eyebrow">{ui("callIt", lang)}</div>
              <h2>{t(card.question.text, lang)}</h2>
            </div>
          </div>
          {nowLine && <p className="now-line">{ui(nowLine, lang)}</p>}
          <div className={`tiles n${card.question.options.length}`}>
            {card.question.options.map((o, i) => {
              const st = choiceStyle(i);
              return (
                <button
                  key={o.id}
                  className="tile"
                  style={{ background: st.bg, color: st.fg }}
                  onClick={() => {
                    setPicked((p) => ({ ...p, [card.card_id]: o.id }));
                    send({ t: "answer", device, card_id: card.card_id, option: o.id });
                  }}
                >
                  <span className="shape" aria-hidden="true">{st.shape}</span>
                  <span>{t(o.label, lang)}</span>
                </button>
              );
            })}
          </div>
          <p className="dim">{ui("openUntilRestart", lang)}</p>
        </main>
      )}

      {state && card && state.phase === "ask" && mine && (() => {
        // Answered: the whole screen takes the colour of the pick, says it is in, and that the MATCH will decide.
        const i = card.question.options.findIndex((o) => o.id === mine);
        const st = choiceStyle(i);
        return (
          <main className="kq-locked" key={`${card.card_id}-locked`} style={{ background: st.bg, color: st.fg }}>
            <div className="big-shape" aria-hidden="true">{st.shape}</div>
            <div className="eyebrow">✓ {ui("locked", lang)}</div>
            <h2>{answerLabel(card, mine, lang)}</h2>
            <p className="count">{state.joined ? `${state.answered} / ${Math.max(state.answered, state.joined)}` : state.answered} {ui("answeredOf", lang)}</p>
            <p className="verdict">⏳ {ui("waitVerdict", lang)}</p>
            <p className="me">{ui("youAre", lang)} {avatarOf(device)}</p>
            {fact && (
              <section className="fact-card" key={fact}>
                <div className="eyebrow">💡 {ui("didYouKnow", lang)}</div>
                <p>{fact}</p>
              </section>
            )}
          </main>
        );
      })()}

      {state && card && state.phase === "locked" && !showWho && !showFollow && (
        // Play has restarted: answers are closed and the phone goes quiet so eyes go back to the screen.
        <main className="center">
          <div className="sleep-dot" aria-hidden="true" />
          <p>{mine ? `✓ ${ui("locked", lang)}: ${answerLabel(card, mine, lang)}` : ui("tooQuick", lang)}</p>
          <p className="dim">{ui("answersClosed", lang)}</p>
        </main>
      )}

      {state && card && match && state.phase === "reveal" && (
        <main>
          {mine && (
            <div className={`verdict-banner ${mine === card.reveal.answer ? "right" : "wrong"}`} role="status">
              {mine === card.reveal.answer ? `✓ ${ui("calledIt", lang)}` : ui("notThisTime", lang)}
            </div>
          )}
          <Mascot pose={card.reveal.pose} size={96} />
          <div className="eyebrow turf">{ui("matchSays", lang)}: {answerLabel(card, card.reveal.answer, lang)}</div>
          <p className="plain">{fill(t(card.reveal.plain, lang), match.facts)}</p>

          <button className="ghost" onClick={() => setDeep((d) => !d)} aria-expanded={deep}>
            {deep ? ui("hide", lang) : ui("goDeeper", lang)}
          </button>
          {deep && <p className="expert">{fill(t(card.reveal.expert, lang), match.facts)}</p>}

          <section className="tally" aria-label={ui("roomSays", lang)}>
            <div className="eyebrow">{ui("roomSays", lang)}</div>
            {card.question.options.map((o) => {
              const n = state.tally[o.id] ?? 0;
              const pct = state.answered ? (n / state.answered) * 100 : 0;
              return (
                <div className="row" key={o.id}>
                  <span>{t(o.label, lang)}{mine === o.id ? ` · ${ui("you", lang)}` : ""}{card.question.pippi_call === o.id ? " 🐤" : ""}</span>
                  <span className="track"><i style={{ width: `${pct}%` }} /></span>
                  <span className="n">{n}</span>
                </div>
              );
            })}
          </section>
        </main>
      )}

      {state && state.phase === "added" && state.board && (
        <main>
          <Mascot pose="thinks" size={96} />
          <div className="eyebrow">{ui("addedTime", lang)} · {state.board.at_min}'</div>
          <h2>{addedHeadline(state.board.announced_min, lang)}</h2>
          <p className="plain">{ui("addedWhy", lang)}</p>
          <button className="ghost" onClick={() => setDeep((d) => !d)} aria-expanded={deep}>
            {deep ? ui("hide", lang) : ui("goDeeper", lang)}
          </button>
          {deep && <AddedBreakdown board={state.board} lang={lang} />}
          <div className="bar"><i style={{ width: `${remain * 100}%` }} /></div>
        </main>
      )}

      {state?.phase === "full" && (
        <main className="center">
          <Mascot pose="wave" />
          <h2>{ui("fullTime", lang)}</h2>
        </main>
      )}
    </div>
  );
}

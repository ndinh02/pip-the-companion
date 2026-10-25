import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import AddedBreakdown from "../components/AddedBreakdown";
import Crest from "../components/Crest";
import PlayerTab from "../components/PlayerTab";
import { loadTracking, type Tracking } from "../lib/tracking";
import { formatClock } from "../lib/matchClock";
import Mascot, { askPose } from "../components/Mascot";
import { addedHeadline } from "../lib/addedTime";
import { deviceId, useRoomChannel, type RoomStatus } from "../lib/channel";
import { NAME } from "../lib/brand";
import { HALF_MIN, shareText, triggerLabel } from "../lib/halfTime";
import { teamName } from "../lib/whoThat";
import { fmt, ui } from "../lib/i18n";
import { useLang } from "../lib/lang";
import { animalName, avatarOf, AVATARS, nextFreeAnimal } from "../lib/avatar";
import Confetti from "../components/Confetti";
import { choiceStyle } from "../lib/choices";
import { alertsWanted, buzz, disableAlerts, enableAlerts, keepAwake, resumeSound } from "../lib/buzz";
import { answerLabel, fill, loadMatch, loadPlayers, ROOM_RE, scoreAt, t } from "../lib/match";
import { forgetPhoneRoom, inAppBrowser, loadPhoneRoom, savePhoneRoom, type PhoneRoom } from "../lib/phoneRoom";
import { LANGS, type Card, type HalfSummary, type HistoryItem, type Lang, type Match, type Msg, type PlayersFeed, type StateMsg } from "../lib/types";

type Tab = "match" | "player" | "room";
type Sheet = "invite" | "leave" | "animal" | null;

/** The animals in a room, overlapping. */
function People({ list, max = 4 }: { list: string[]; max?: number }) {
  return (
    <span className="q-people" aria-label={list.join(" ")}>
      {list.slice(0, max).map((a, i) => <span key={i}>{a}</span>)}
      {list.length > max && <span className="more">+{list.length - max}</span>}
    </span>
  );
}

function LangSwitch({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  return (
    <span className="q-langs" role="group" aria-label={ui("rmLang", lang)}>
      {LANGS.map((l) => <button key={l} className={l === lang ? "on" : ""} onClick={() => setLang(l)} aria-pressed={l === lang}>{l.toUpperCase()}</button>)}
    </span>
  );
}

/** The phone in a room. Always on top: who plays whom, the score and the match clock, in step with the TV.
 *  Below: Match (the conversation with Pip since kick-off), My player, Room. When Pip asks, the question takes over. */
export default function Play() {
  const room = (useParams().room ?? "").toUpperCase();
  const valid = ROOM_RE.test(room);
  const nav = useNavigate();
  const [lang, setLang] = useLang();
  const [match, setMatch] = useState<Match | null>(null);
  const [players, setPlayers] = useState<PlayersFeed | null>(null);
  const [state, setState] = useState<StateMsg | null>(null);
  const [link, setLink] = useState<RoomStatus>("ok");
  const device = useMemo(deviceId, []);
  const [saved, setSaved] = useState<PhoneRoom | null>(() => (valid ? loadPhoneRoom(room) : null));
  const [draft, setDraft] = useState(() => avatarOf(device)); // the animal offered before joining
  const [inAppOk, setInAppOk] = useState(false);
  const [tab, setTab] = useState<Tab>("match");
  const [sheet, setSheet] = useState<Sheet>(null);
  const [changing, setChanging] = useState<string | null>(null); // card id while the one change of mind is in use
  const [seen, setSeen] = useState<Record<string, boolean>>({}); // outcomes closed with "Got it"
  const askSeen = useRef(new Set<string>()); // questions this phone saw while they were open
  const [half, setHalf] = useState<HalfSummary | null>(null);
  const [viewId, setViewId] = useState<string | null>(null); // a player profile being looked at in "My player"
  const [tracking, setTracking] = useState<Tracking | null>(null);
  const [alerts, setAlerts] = useState(alertsWanted);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef(0);
  const say = (text: string) => {
    setToast(text);
    clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2600);
  };

  useEffect(() => {
    loadMatch()
      .then((m) => {
        setMatch(m);
        return loadPlayers(m).then(setPlayers);
      })
      .catch(() => undefined);
  }, []);

  // Listen before joining too: the animal screen shows who is already in the room.
  const send = useRoomChannel(valid ? room : "INVALID", "phone", (m: Msg) => {
    if (m.t === "state") setState({ ...m, clock_at: m.clock_at ?? Date.now() }); // same-browser demo: no network delay
  }, setLink);

  const update = (f: (p: PhoneRoom) => PhoneRoom) =>
    setSaved((p) => {
      if (!p) return p;
      const next = f(p);
      savePhoneRoom(room, next);
      return next;
    });

  // Say hello with our animal; again whenever the TV does not list it (the TV tab was reopened, or we changed animal).
  const people = state?.people;
  const myAnimal = saved?.animal;
  const lastHello = useRef(0);
  useEffect(() => {
    if (!valid || !myAnimal) return;
    if (lastHello.current && people?.includes(myAnimal)) return;
    if (Date.now() - lastHello.current < 3000) return;
    lastHello.current = Date.now();
    send({ t: "hello", device, animal: myAnimal });
  }, [valid, myAnimal, people, device, send]);

  // Before joining, offer an animal nobody in the room has yet.
  useEffect(() => {
    if (!saved && people?.includes(draft)) setDraft(nextFreeAnimal(draft, people));
  }, [saved, people, draft]);

  // Who this phone follows belongs to this room only: a new room starts with nobody (owner feedback 2026-10-25).
  const followId = saved?.followId ?? null;
  useEffect(() => {
    if (match && (followId || viewId) && !tracking) loadTracking(match).then(setTracking);
  }, [match, followId, viewId, tracking]);
  const tvSeen = !!state;
  useEffect(() => {
    if (valid && saved && tvSeen) send({ t: "follow", device, player_id: followId });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valid, !!saved, tvSeen, followId, device]);

  const askId = state?.phase === "ask" ? state.card?.card_id : undefined;
  useEffect(() => {
    if (!askId) return;
    askSeen.current.add(askId);
    setSheet(null); // a question always takes over the screen
    if (saved) buzz("ask");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [askId]);
  const revealId = state?.phase === "reveal" ? state.card?.card_id : undefined;
  useEffect(() => {
    if (revealId && saved) buzz("reveal");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revealId]);
  useEffect(() => {
    if (state?.half) setHalf(state.half);
  }, [state?.half]);
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

  // The clock counts on the phone between the TV's updates (every 1.5 s), so it never looks frozen.
  const [tick, setTick] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // Keep the conversation scrolled to the newest message as the match goes on.
  const endRef = useRef<HTMLDivElement>(null);
  const historyLen = state?.history?.length ?? 0;
  useEffect(() => {
    if (tab === "match") endRef.current?.scrollIntoView({ block: "end" });
  }, [historyLen, tab, state?.phase]);

  if (!valid)
    return (
      <div className="q-ph q-centered">
        <Mascot pose="thinks" size={110} />
        <h2>{ui("badRoom", lang)}</h2>
        <button className="q-btn" onClick={() => nav("/join")}>{ui("anRetype", lang)}</button>
      </div>
    );

  const host = location.host;
  const joinUrl = `${location.origin}/play/${room}`;
  const roomName = state?.room_name;
  const inRoom = people ?? (saved ? [saved.animal] : []);
  const copyLink = async () => {
    try {
      if (navigator.share) await navigator.share({ title: NAME, url: joinUrl });
      else {
        await navigator.clipboard.writeText(joinUrl);
        say(ui("linkCopied", lang));
      }
    } catch {
      /* share sheet dismissed */
    }
  };

  // ---------- before joining: language, your animal (with the wrong-room and in-app-browser checks) ----------
  if (!saved) {
    const others = people ?? [];
    const join = () => {
      const next: PhoneRoom = { animal: draft, joinedAt: state && state.phase !== "lobby" ? state.minute : 0, picks: {}, changed: {}, catchupSeen: false, followId: null };
      savePhoneRoom(room, next);
      setSaved(next);
      setTab("match");
    };
    if (inAppBrowser() && !inAppOk)
      return (
        <div className="q-ph">
          <div className="q-top"><span /><LangSwitch lang={lang} setLang={setLang} /></div>
          <div className="q-catch"><b>{ui("inAppTitle", lang)}</b><span>{ui("inAppText", lang)}</span></div>
          <div className="q-hero"><Mascot pose="thinks" size={96} /></div>
          <h1>{fmt(ui("anJoin", lang), { code: roomName ?? room })}</h1>
          <div className="q-fill" />
          <button className="q-btn ghost" onClick={() => setInAppOk(true)}>{ui("inAppStay", lang)}</button>
          <button className="q-btn" onClick={copyLink}>{ui("inAppCopy", lang)}</button>
          {toast && <div className="q-toast" role="status">{toast}</div>}
        </div>
      );
    return (
      <div className="q-ph">
        <div className="q-top"><button className="q-back" onClick={() => nav("/join")}>‹ {ui("back", lang)}</button><LangSwitch lang={lang} setLang={setLang} /></div>
        {link === "no-room" && !state && (
          <div className="q-err" role="alert"><b>?</b><span>{fmt(ui("anNotOpen", lang), { code: room })}</span></div>
        )}
        <div className="q-fill q-centered">
          {roomName && <div className="q-roomtag">{roomName} · {room}</div>}
          <div className="q-big-animal" aria-hidden="true">{draft}</div>
          <h1>{fmt(ui("anYou", lang), { name: animalName(draft, lang) })}</h1>
          {others.length > 0 && <div className="q-muted">{ui("anHere", lang)}: <People list={others} max={6} /></div>}
        </div>
        <button className="q-btn ghost" onClick={() => setDraft(nextFreeAnimal(draft, others))}>{ui("anOther", lang)}</button>
        <button className="q-btn" onClick={join}>{fmt(ui("anJoin", lang), { code: room })}</button>
      </div>
    );
  }

  // ---------- joined ----------
  const card = state?.card ?? null;
  const mine = card ? saved.picks[card.card_id] : undefined;
  const onFollow = (id: string | null) => update((p) => ({ ...p, followId: id }));
  const minute = state?.minute ?? 0;
  const phase = state?.phase;
  const started = !!state && phase !== "lobby";
  const score = state?.score ?? (match && started ? scoreAt(match, minute) : { HAR: 0, COP: 0 });
  // Is the room live? "live": updates arriving and the clock running; "paused": the TV clock stands still (pause,
  // half-time); "stale": no update for a while or no connection, so numbers on this phone may be out of date.
  const since = state?.clock_at ? tick - state.clock_at : Infinity;
  const rate = state?.clock_rate ?? 0;
  const fresh: "live" | "paused" | "stale" = link !== "ok" || since > 8000 ? "stale" : rate > 0 ? "live" : "paused";
  const liveClock = state?.clock_min !== undefined && state.clock_base
    ? formatClock(state.clock_min + (fresh === "stale" ? 0 : (Math.max(0, since) / 60_000) * rate), state.clock_base)
    : state?.clock ?? "";
  const before = (c: Card) => c.t_in_min < saved.joinedAt;
  const pick = (optionId: string) => {
    if (!card) return;
    if (mine && changing !== card.card_id) return; // locked: one change only, through the button (owner decision 2026-10-23)
    update((p) => ({
      ...p,
      picks: { ...p.picks, [card.card_id]: optionId },
      changed: changing === card.card_id ? { ...p.changed, [card.card_id]: true } : p.changed,
    }));
    setChanging(null);
    send({ t: "answer", device, card_id: card.card_id, option: optionId });
  };
  const gotIt = () => {
    if (card) setSeen((x) => ({ ...x, [card.card_id]: true }));
    setTab("match");
  };
  const leave = () => {
    send({ t: "bye", device });
    forgetPhoneRoom(room);
    nav("/");
  };
  const home = match?.teams[0];
  const away = match?.teams[1];

  // Always on top: who plays whom, the score and the clock (in step with the TV), then the room and your animal.
  const header = (
    <header className="q-live" aria-label={`${home?.name ?? ""} ${score.HAR} – ${score.COP} ${away?.name ?? ""}`}>
      <div className="q-live-row">
        <span className="q-live-team">{home && <Crest team={home} size={38} />}<b>{home?.short_name}</b></span>
        <span className="q-live-mid">
          <span className="q-live-score">{score.HAR}<i>–</i>{score.COP}</span>
          <span className={`q-live-clock ${started ? fresh : "pre"}`}>
            {!started ? ui("mtPre", lang) : fresh === "live" ? liveClock : `${liveClock} · ${ui(fresh === "paused" ? "lvPaused" : "lvStale", lang)}`}
          </span>
        </span>
        <span className="q-live-team right"><b>{away?.short_name}</b>{away && <Crest team={away} size={38} />}</span>
      </div>
      <div className="q-live-sub">
        <span>{roomName ?? fmt(ui("rmTitle", lang), { code: room })}</span>
        <span>{saved.animal} {animalName(saved.animal, lang)}</span>
      </div>
    </header>
  );
  const tabbar = (
    <nav className="q-tabbar">
      {([["match", "◉", "tabMatch"], ["player", "☆", "tabPlayer"], ["room", "◎", "tabRoom"]] as const).map(([k, icon, label]) => (
        <button key={k} className={tab === k ? "on" : ""} aria-current={tab === k} onClick={() => { setTab(k); setSheet(null); }}>
          <i aria-hidden="true">{icon}</i>{ui(label, lang)}
        </button>
      ))}
    </nav>
  );
  const pipSays = (pose: Parameters<typeof Mascot>[0]["pose"], body: ReactNode, big = false) => (
    <div className="q-row">
      <div className="q-av"><Mascot pose={pose} size={40} /></div>
      <div className={`q-bub ${big ? "big" : ""}`}>{body}</div>
    </div>
  );

  // ---------- full-screen moments: Pip asks, locked in, play restarted, the outcome ----------
  let takeover: ReactNode = null;
  if (card && phase === "ask" && (!mine || changing === card.card_id)) {
    const n = card.question.options.length;
    takeover = (
      <div className="q-screen q-wake" key={card.card_id}>
        {pipSays(askPose(card.trigger), t(card.question.text, lang), true)}
        <div className={`q-picks ${n === 3 ? "n3" : ""} ${mine ? "picked" : ""}`}>
          {card.question.options.map((o, i) => {
            const st = choiceStyle(i);
            return (
              <button key={o.id} className={`q-tile ${mine === o.id ? "on" : ""}`} style={{ background: st.bg, color: st.fg }} onClick={() => pick(o.id)}>
                {t(o.label, lang)}
              </button>
            );
          })}
        </div>
        <div className="q-pick-hint">{changing === card.card_id ? ui("akFinal", lang) : ui("akHint", lang)}</div>
      </div>
    );
  } else if (state && card && phase === "ask" && mine) {
    const i = card.question.options.findIndex((o) => o.id === mine);
    const st = choiceStyle(i);
    const joined = Math.max(state.joined ?? 0, state.answered);
    const allIn = joined > 0 && state.answered >= joined;
    takeover = (
      <div className="q-screen q-lockedin" style={{ background: st.bg, color: st.fg }}>
        <div className="q-lock">
          <div className="q-small">✓ {ui("locked", lang)}</div>
          <div className="q-pickname">{answerLabel(card, mine, lang)}</div>
          <div className={`pip-wait ${allIn ? "all-in" : ""}`}><Mascot pose={allIn ? "watching" : "thinks"} size={120} /></div>
          <h2 className="q-narrow">{allIn ? ui("allIn", lang) : ui("waitOthers", lang)}</h2>
          <div>{fmt(ui("liN", lang), { n: state.answered, m: joined })} <People list={state.answered_by ?? []} max={6} /></div>
        </div>
        {saved.changed[card.card_id]
          ? <div className="q-pick-hint">{ui("lockedFinal", lang)}</div>
          : <button className="q-btn q-change" onClick={() => setChanging(card.card_id)}>{ui("changeOnce", lang)}</button>}
      </div>
    );
  } else if (card && phase === "locked" && !before(card)) {
    const slept = !askSeen.current.has(card.card_id);
    const i = mine ? card.question.options.findIndex((o) => o.id === mine) : -1;
    takeover = (
      <div className="q-screen">
        <div className="q-lock">
          <Mascot pose="watching" size={110} />
          {mine ? (
            <>
              <div className="q-chip-big" style={{ background: choiceStyle(i).bg, color: choiceStyle(i).fg }}>{answerLabel(card, mine, lang)}</div>
              <h2>{ui("lkWatch", lang)}</h2>
            </>
          ) : (
            <>
              <h2>{ui("lkNone", lang)}</h2>
              <p className="q-muted q-narrow">{slept ? ui("lkSlept", lang) : ui("lkNoWorry", lang)}</p>
            </>
          )}
        </div>
      </div>
    );
  } else if (card && match && phase === "reveal" && !seen[card.card_id] && !before(card)) {
    // A question from before this phone joined is in the conversation, not a "you missed it" screen.
    const voided = !!card.reveal.void;
    const right = !voided && !!mine && mine === card.reveal.answer;
    const plain = fill(t(card.reveal.plain, lang), match.facts);
    takeover = (
      <div className="q-screen">
        {right && <Confetti />}
        {voided ? (
          <div className="q-banner learn">{ui("vdBanner", lang)}</div>
        ) : right ? (
          <div className="q-banner right">{ui("mtRight", lang)}</div>
        ) : mine ? (
          <div className="q-banner learn">{ui("rvLearn", lang)}</div>
        ) : (
          <div className="q-banner learn">{ui("rvMissed", lang)}</div>
        )}
        {pipSays(voided ? "thinks" : card.reveal.pose, voided
          ? <>{plain}</>
          : <><div className="q-answer"><span className="q-hl">{answerLabel(card, card.reveal.answer, lang)}</span></div><div className="q-plain">{plain}</div></>)}
        {!voided && (
          <details className="q-card q-deeper">
            <summary>{ui("goDeeper", lang)}</summary>
            <p className="q-muted">{fill(t(card.reveal.expert, lang), match.facts)}</p>
          </details>
        )}
        <div className="q-fill" />
        <button className="q-btn" onClick={gotIt}>{ui("gotIt", lang)}</button>
      </div>
    );
  }

  // ---------- tabs ----------
  let body: ReactNode;
  if (!state) {
    body = (
      <div className="q-fill q-centered">
        <Mascot pose="watching" size={110} />
        <h2>{ui("waitingTv", lang)}</h2>
        {link === "no-room" && <p className="q-muted q-narrow">{fmt(ui("anNotOpen", lang), { code: room })}</p>}
      </div>
    );
  } else if (tab === "player") {
    body = players && match ? (
      <PlayerTab match={match} feed={players} tracking={tracking} minute={minute} lang={lang} followId={followId} onFollow={onFollow} viewId={viewId} onView={setViewId} fresh={fresh} />
    ) : (
      <div className="q-fill q-centered"><Mascot pose="perch" size={110} /></div>
    );
  } else if (tab === "room") {
    body = (
      <>
        <div className="q-roomhead">
          <div>
            <h2>{roomName ?? fmt(ui("rmTitle", lang), { code: room })}</h2>
            <div className="q-muted q-mono">{room}</div>
          </div>
          <button className="q-danger" onClick={() => setSheet("leave")}>{ui("rmLeave", lang)}</button>
        </div>
        <div className="q-card q-spread"><People list={inRoom} max={7} /><span className="q-muted">{fmt(ui("rmHere", lang), { n: inRoom.length })}</span></div>
        <div className="q-list q-push">
          <div><span className="q-ic">文</span>{ui("rmLang", lang)}<span className="q-end"><LangSwitch lang={lang} setLang={setLang} /></span></div>
          <button onClick={() => setSheet("animal")}><span className="q-ic">↺</span>{ui("rmAnimal", lang)}<span className="q-end q-big-emoji">{saved.animal}</span></button>
          <button role="switch" aria-checked={alerts} onClick={() => { if (alerts) { disableAlerts(); setAlerts(false); } else { void enableAlerts(); setAlerts(true); } }}>
            <span className="q-ic">🔔</span>{ui("rmChime", lang)}<span className={`q-toggle ${alerts ? "on" : ""}`} />
          </button>
        </div>
        <button className="q-btn" onClick={() => setSheet("invite")}>⇪ {ui("invite", lang)}</button>
      </>
    );
  } else {
    body = (
      <Conversation match={match} state={state} saved={saved} lang={lang} minute={minute} half={half} inRoom={inRoom}
        onInvite={() => setSheet("invite")} onLeave={leave} onPlayer={() => setTab("player")} say={say} endRef={endRef} />
    );
  }

  // ---------- sheets and overlays ----------
  const taken = (people ?? []).filter((a) => a !== saved.animal);
  const sheetView = sheet && (
    <>
      <div className="q-scrim" onClick={() => setSheet(null)} />
      <div className="q-sheet" role="dialog" aria-modal="true">
        <div className="q-grab" />
        {sheet === "invite" && (
          <>
            <h2>{fmt(ui("shInvite", lang), { code: roomName ?? room })}</h2>
            <div className="q-invite">
              <div className="q-qr"><QRCodeSVG value={joinUrl} size={118} bgColor="#FFFFFF" fgColor="#14202F" /></div>
              <div className="q-stack-tight">
                <b className="q-mono q-bigcode">{room}</b>
                <span className="q-muted">{host}</span>
              </div>
            </div>
            <button className="q-btn ghost" onClick={copyLink}>{ui("shCopy", lang)}</button>
            <button className="q-btn" onClick={() => setSheet(null)}>{ui("shDone", lang)}</button>
          </>
        )}
        {sheet === "leave" && (
          <>
            <h2>{fmt(ui("shLeave", lang), { code: roomName ?? room })}</h2>
            <button className="q-btn ghost q-danger-text" onClick={leave}>{ui("shLeaveGo", lang)}</button>
            <button className="q-btn" onClick={() => setSheet(null)}>{ui("shStay", lang)}</button>
          </>
        )}
        {sheet === "animal" && (
          <>
            <h2>{ui("shAnimal", lang)}</h2>
            <div className="q-animals">
              {AVATARS.map((a) => (
                <button key={a} className={`${a === saved.animal ? "on" : ""} ${taken.includes(a) ? "taken" : ""}`} disabled={taken.includes(a)} aria-label={animalName(a, lang)}
                  onClick={() => { lastHello.current = 0; update((p) => ({ ...p, animal: a })); setSheet(null); }}>
                  {a}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
  // Something between this phone and the TV is broken: say what and how to fix it, never an error code.
  const overlay =
    link === "offline" ? (
      <div className="q-offline" role="status"><span>●</span>{ui("stOffline", lang)}</div>
    ) : link === "no-room" && state ? (
      <div className="q-cover" role="status">
        <Mascot pose="thinks" size={110} />
        <h2>{fmt(ui("ovReconn", lang), { code: room })}</h2>
      </div>
    ) : link === "tv-quiet" ? (
      <div className="q-cover" role="status">
        <Mascot pose="watching" size={110} />
        <h2>{ui("ovQuiet", lang)}</h2>
        <p className="q-narrow">{fmt(ui("ovQuietHow", lang), { host, code: roomName ?? room })}</p>
      </div>
    ) : null;

  return (
    <div className="q-ph q-joined">
      {header}
      {takeover ?? (
        <>
          <div className={`q-body ${tab === "match" ? "chat" : ""}`}>{body}</div>
          {tabbar}
        </>
      )}
      {sheetView}
      {overlay}
      {toast && <div className="q-toast" role="status">{toast}</div>}
    </div>
  );
}

/** The conversation with Pip since kick-off: goals, every question (what you said, what the room said, what really
 *  happened and why). Scroll up for anything earlier. No "x of y questions": it is live, nobody knows how many come. */
function Conversation({ match, state, saved, lang, minute, half, inRoom, onInvite, onLeave, onPlayer, say, endRef }: {
  match: Match | null; state: StateMsg; saved: PhoneRoom; lang: Lang; minute: number; half: HalfSummary | null; inRoom: string[];
  onInvite: () => void; onLeave: () => void; onPlayer: () => void; say: (t: string) => void; endRef: React.RefObject<HTMLDivElement | null>;
}) {
  if (!match) return null;
  if (state.phase === "lobby")
    return (
      <div className="q-fill q-centered">
        <h1>{fmt(ui("lbIn", lang), { name: animalName(saved.animal, lang) })}</h1>
        <div className="q-seats">{inRoom.map((a, k) => <span key={k} className={a === saved.animal ? "me" : ""}>{a}</span>)}</div>
        <p className="q-muted q-narrow">{ui("lbShort", lang)}</p>
        <button className="q-btn" onClick={onInvite}>⇪ {ui("invite", lang)}</button>
      </div>
    );
  const byId = new Map(match.cards.map((c) => [c.card_id, c]));
  const history = (state.history ?? []).map((h) => ({ h, c: byId.get(h.card_id) })).filter((x): x is { h: HistoryItem; c: Card } => !!x.c);
  const goals = match.score_timeline.filter((g) => g.player_id && g.from_min <= minute);
  type Item = { min: number; key: string; node: ReactNode };
  const items: Item[] = [{ min: -1, key: "ko", node: <div className="q-sys">{ui("cvKickoff", lang)}</div> }];
  for (const g of goals) {
    const team = match.teams.find((x) => x.team_id === g.team_id);
    items.push({
      min: g.from_min, key: `g${g.from_min}`,
      node: <div className="q-sys goal">⚽ {Math.floor(g.from_min)}' · {ui("goal", lang)} {team?.name} #{g.player_id!.split("-")[1]} · {g.HAR}–{g.COP}</div>,
    });
  }
  if (minute >= HALF_MIN) items.push({ min: HALF_MIN + 0.01, key: "ht", node: <div className="q-sys">{ui("halfTime", lang)}</div> });
  for (const { h, c } of history) items.push({ min: c.t_in_min, key: c.card_id, node: <CallThread c={c} h={h} match={match} mine={c.t_in_min < saved.joinedAt ? undefined : saved.picks[c.card_id]} before={c.t_in_min < saved.joinedAt} lang={lang} /> });
  // The question that is open right now (its full screen was closed or is coming): a short line, it moves into
  // the history once the match has answered.
  const card = state.card;
  if (card && !history.some((x) => x.c.card_id === card.card_id) && (state.phase === "ask" || state.phase === "locked" || state.phase === "reveal")) {
    const m = saved.picks[card.card_id];
    items.push({
      min: card.t_in_min, key: `now-${card.card_id}`,
      node: (
        <div className="q-row">
          <div className="q-av"><Mascot pose={askPose(card.trigger)} size={40} /></div>
          <div className="q-bub"><b>{t(card.question.text, lang)}</b>{m && <div className="q-muted">{ui("you", lang)}: {answerLabel(card, m, lang)}</div>}</div>
        </div>
      ),
    });
  }
  if (state.phase === "added" && state.board) {
    items.push({
      min: minute + 0.5, key: `add${state.board.period}`,
      node: (
        <details className="q-sys added">
          <summary>⏱ {addedHeadline(state.board.announced_min, lang)}</summary>
          <p>{ui("addedWhy", lang)}</p>
          <div className="q-dark"><AddedBreakdown board={state.board} lang={lang} /></div>
        </details>
      ),
    });
  }
  if (state.phase === "full") items.push({ min: 999, key: "ft", node: <div className="q-sys">{ui("fullTime", lang)} · {ui("hfThanks", lang)}</div> });
  items.sort((a, b) => a.min - b.min);

  const share = async () => {
    if (!half) return;
    const text = shareText(match, half, lang, { title: `${ui("halfTime", lang)} · ${NAME}`, room: ui("halfRoom", lang), match: ui("halfMatch", lang), split: ui("halfSplit", lang), word: ui("wordOfMatch", lang) });
    try {
      if (navigator.share) await navigator.share({ title: NAME, text });
      else {
        await navigator.clipboard.writeText(text);
        say(ui("copied", lang));
      }
    } catch {
      /* dismissed */
    }
  };
  return (
    <div className="q-chat">
      {items.map((it) => <div key={it.key}>{it.node}</div>)}
      {state.phase === "full" ? (
        <div className="q-two">
          {half && <button className="q-btn ghost" onClick={share}>{ui("hfShare", lang)}</button>}
          <button className="q-btn" onClick={onLeave}>{ui("shLeaveGo", lang)}</button>
        </div>
      ) : (
        !saved.followId && <button className="q-btn soft" onClick={onPlayer}>☆ {ui("mtFollow", lang)}</button>
      )}
      <div ref={endRef} />
    </div>
  );
}

/** One question in the conversation: Pip's question, your answer, then what the match said and how the room called it. */
function CallThread({ c, h, match, mine, before, lang }: { c: Card; h: HistoryItem; match: Match; mine?: string; before: boolean; lang: Lang }) {
  const voided = !!c.reveal.void;
  const total = Object.values(h.tally).reduce((a, b) => a + b, 0);
  return (
    <div className="q-thread">
      <div className="q-stamp">{Math.floor(c.t_in_min)}' · {triggerLabel(c.trigger, lang)} · {teamName(match, c.team_id)}</div>
      <div className="q-row">
        <div className="q-av"><Mascot pose={askPose(c.trigger)} size={40} /></div>
        <div className="q-bub">{t(c.question.text, lang)}</div>
      </div>
      {!before && <div className={`q-bub me ${mine ? "" : "none"}`}>{mine ? answerLabel(c, mine, lang) : ui("cvNoAnswer", lang)}</div>}
      <div className="q-row">
        <div className="q-av"><Mascot pose={voided ? "thinks" : c.reveal.pose} size={40} /></div>
        <div className="q-bub">
          <div className="q-result">{voided ? ui("noClear", lang) : <>✓ <span className="q-hl">{answerLabel(c, c.reveal.answer, lang)}</span></>}</div>
          {!voided && mine && <div className="q-muted">{mine === c.reveal.answer ? ui("mtRight", lang) : fmt(ui("mtSaid", lang), { x: answerLabel(c, mine, lang) })}</div>}
          {total > 0 && (
            <div className="q-roomcalls">
              {c.question.options.filter((o) => h.tally[o.id]).map((o) => (
                <div key={o.id} className={!voided && o.id === c.reveal.answer ? "ans" : ""}>
                  <span>{t(o.label, lang)}</span>
                  <span className="q-animals-inline">{(h.by[o.id] ?? []).join(" ")}</span>
                </div>
              ))}
            </div>
          )}
          <details className="q-why">
            <summary>{ui("cvWhy", lang)}</summary>
            <p>{fill(t(c.reveal.plain, lang), match.facts)}</p>
            {!voided && <p className="q-muted">{fill(t(c.reveal.expert, lang), match.facts)}</p>}
          </details>
        </div>
      </div>
    </div>
  );
}

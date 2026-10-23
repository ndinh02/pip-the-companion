import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import AddedBreakdown from "../components/AddedBreakdown";
import PlayerTab from "../components/PlayerTab";
import { loadTracking, type Tracking } from "../lib/tracking";
import { formatClock } from "../lib/matchClock";
import Mascot, { askPose } from "../components/Mascot";
import { addedHeadline } from "../lib/addedTime";
import { deviceId, useRoomChannel, type RoomStatus } from "../lib/channel";
import { NAME } from "../lib/brand";
import { HALF_MIN, shareText, triggerLabel } from "../lib/halfTime";
import { loadFollow, saveFollow, teamName } from "../lib/whoThat";
import { deviceLang, fmt, ui } from "../lib/i18n";
import { animalName, avatarOf, AVATARS, nextFreeAnimal } from "../lib/avatar";
import { kitOf } from "../lib/kit";
import Confetti from "../components/Confetti";
import { choiceStyle } from "../lib/choices";
import { alertsWanted, buzz, disableAlerts, enableAlerts, keepAwake, resumeSound } from "../lib/buzz";
import { answerLabel, fill, loadMatch, loadPlayers, ROOM_RE, scoreAt, t } from "../lib/match";
import { forgetPhoneRoom, inAppBrowser, loadPhoneRoom, savePhoneRoom, type PhoneRoom } from "../lib/phoneRoom";
import { LANGS, type Card, type HalfSummary, type Lang, type Match, type Msg, type PlayersFeed, type StateMsg } from "../lib/types";

type Tab = "match" | "player" | "room";
type Sheet = "invite" | "leave" | "animal" | null;

/** The animals in a room, overlapping like the prototype's "people" row. */
function People({ list, max = 4 }: { list: string[]; max?: number }) {
  return (
    <span className="q-people" aria-label={list.join(" ")}>
      {list.slice(0, max).map((a, i) => <span key={i}>{a}</span>)}
      {list.length > max && <span className="more">+{list.length - max}</span>}
    </span>
  );
}

/** The phone in a room (room prototype, 2026-10-23): pick an animal, then three tabs (Match, My player, Room).
 *  When Pip asks, the question takes over the whole screen, wherever the viewer was. */
export default function Play() {
  const room = (useParams().room ?? "").toUpperCase();
  const valid = ROOM_RE.test(room);
  const nav = useNavigate();
  const [lang, setLang] = useState<Lang>(deviceLang);
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
  const [seen, setSeen] = useState<Record<string, boolean>>({}); // reveals closed with "Got it"
  const askSeen = useRef(new Set<string>()); // questions this phone saw while they were open
  const [half, setHalf] = useState<HalfSummary | null>(null);
  const [showHalf, setShowHalf] = useState(false);
  const [viewId, setViewId] = useState<string | null>(null); // a player profile being looked at in "My player"
  const [tracking, setTracking] = useState<Tracking | null>(null);
  const [followId, setFollowId] = useState<string | null>(loadFollow);
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

  useEffect(() => {
    // Positions are a big file: fetch them only once a profile (with its running path) is shown.
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
    setSheet(null);
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

  // ---------- before joining: your animal (with the wrong-room and in-app-browser checks) ----------
  if (!saved) {
    const others = people ?? [];
    const join = () => {
      const next: PhoneRoom = { animal: draft, joinedAt: state && state.phase !== "lobby" ? state.minute : 0, picks: {}, changed: {}, catchupSeen: false };
      savePhoneRoom(room, next);
      setSaved(next);
      setTab("match");
    };
    if (inAppBrowser() && !inAppOk)
      return (
        <div className="q-ph">
          <div className="q-top"><span className="q-mono">{host}/play/{room}</span></div>
          <div className="q-catch"><b>{ui("inAppTitle", lang)}</b><span>{ui("inAppText", lang)}</span></div>
          <div className="q-hero"><Mascot pose="thinks" size={96} /></div>
          <h1>{fmt(ui("anJoin", lang), { code: room })}</h1>
          <div className="q-fill" />
          <button className="q-btn ghost" onClick={() => setInAppOk(true)}>{ui("inAppStay", lang)}</button>
          <button className="q-btn" onClick={copyLink}>{ui("inAppCopy", lang)}</button>
          {toast && <div className="q-toast" role="status">{toast}</div>}
        </div>
      );
    return (
      <div className="q-ph">
        <div className="q-top"><button className="q-back" onClick={() => nav("/join")}>‹ {ui("back", lang)}</button><span className="q-mono">{fmt(ui("rmTitle", lang), { code: room })}</span></div>
        {link === "no-room" && !state && (
          <div className="q-err" role="alert"><b>?</b><span>{fmt(ui("anNotOpen", lang), { code: room })}</span></div>
        )}
        <div className="q-fill q-centered">
          <div className="q-big-animal" aria-hidden="true">{draft}</div>
          <h1>{fmt(ui("anYou", lang), { name: animalName(draft, lang) })}</h1>
          <p className="q-muted q-narrow">{ui("anNoNames", lang)}</p>
          {others.length > 0 && (
            <>
              <div className="q-small q-muted">{ui("anHere", lang)}: <People list={others} max={6} /></div>
              <p className="q-small q-muted q-narrow">{ui("anCheck", lang)}</p>
            </>
          )}
        </div>
        <button className="q-btn ghost" onClick={() => setDraft(nextFreeAnimal(draft, others))}>{ui("anOther", lang)}</button>
        <button className="q-btn" onClick={join}>{fmt(ui("anJoin", lang), { code: room })}</button>
      </div>
    );
  }

  // ---------- joined ----------
  const card = state?.card ?? null;
  const mine = card ? saved.picks[card.card_id] : undefined;
  const followed = players?.players.find((p) => p.player_id === followId) ?? null;
  const onFollow = (id: string | null) => {
    setFollowId(id);
    saveFollow(id);
  };
  const minute = state?.minute ?? 0;
  // Is the room live? "live": updates arriving and the clock running; "paused": the TV clock stands still (pause,
  // half-time); "stale": no update for a while or no connection, so numbers on this phone may be out of date.
  const since = state?.clock_at ? tick - state.clock_at : Infinity;
  const rate = state?.clock_rate ?? 0;
  const fresh: "live" | "paused" | "stale" = link !== "ok" || since > 8000 ? "stale" : rate > 0 ? "live" : "paused";
  const liveClock = state?.clock_min !== undefined && state.clock_base
    ? formatClock(state.clock_min + (fresh === "stale" ? 0 : (Math.max(0, since) / 60_000) * rate), state.clock_base)
    : state?.clock ?? "";
  const freshWord = ui(fresh === "live" ? "mtLive" : fresh === "paused" ? "lvPaused" : "lvStale", lang);
  const score = match && state && state.phase !== "lobby" ? scoreAt(match, minute) : { HAR: 0, COP: 0 };
  const scoreLine = match ? `${match.teams[0].short_name} ${score.HAR}–${score.COP} ${match.teams[1].short_name}` : "";
  const isDone = (c: Card) =>
    state?.phase === "full" || (c.card_id === card?.card_id ? state?.phase === "reveal" || state?.phase === "play" : c.t_in_min < minute);
  const done = match ? match.cards.filter(isDone) : [];
  const before = (c: Card) => c.t_in_min < saved.joinedAt;
  const myCall = (c: Card) => (before(c) ? undefined : saved.picks[c.card_id]);
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

  const topbar = (
    <div className="q-top">
      <span className="q-mono"><b>{room}</b> · {state && state.phase !== "lobby" ? liveClock : ui("mtPre", lang)}</span>
      <People list={inRoom} />
    </div>
  );
  const tabbar = (
    <nav className="q-tabbar">
      {([["match", "◉", "tabMatch"], ["player", "☆", "tabPlayer"], ["room", "◎", "tabRoom"]] as const).map(([k, icon, label]) => (
        <button key={k} className={tab === k ? "on" : ""} aria-current={tab === k} onClick={() => { setTab(k); setSheet(null); setShowHalf(false); }}>
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
  const callRows = (cards: Card[]) =>
    cards.length ? cards.map((c) => {
      const m = myCall(c);
      const right = !c.reveal.void && m === c.reveal.answer;
      return (
        <div className="q-callrow" key={c.card_id}>
          <span>{Math.floor(c.t_in_min)}' {triggerLabel(c.trigger, lang)}: <b>{c.reveal.void ? ui("noClear", lang) : answerLabel(c, c.reveal.answer, lang)}</b></span>
          <span className={`q-small ${right ? "" : "q-muted"}`}>
            {before(c) ? ui("hfBefore", lang) : !m ? ui("hfNoCall", lang) : right ? ui("hfYouRight", lang) : fmt(ui("hfYouSaid", lang), { x: answerLabel(c, m, lang) })}
          </span>
        </div>
      );
    }) : <span className="q-small q-muted">{ui("hfNone", lang)}</span>;

  // ---------- the screens ----------
  let screen: ReactNode;
  let withTabs = true;
  const phase = state?.phase;
  if (!state) {
    screen = (
      <div className="q-fill q-centered">
        <Mascot pose="watching" size={110} />
        <h2>{ui("waitingTv", lang)}</h2>
        <p className="q-muted q-narrow">{link === "no-room" ? fmt(ui("anNotOpen", lang), { code: room }) : ui("waitingTvHint", lang)}</p>
      </div>
    );
  } else if (card && phase === "ask" && (!mine || changing === card.card_id)) {
    withTabs = false;
    const n = card.question.options.length;
    screen = (
      <div className="q-screen q-wake" key={card.card_id}>
        {topbar}
        <div className="q-stamp q-mono">{Math.floor(card.t_in_min)}' · {triggerLabel(card.trigger, lang)}, {match ? teamName(match, card.team_id) : ""}</div>
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
  } else if (card && phase === "ask" && mine) {
    withTabs = false;
    const i = card.question.options.findIndex((o) => o.id === mine);
    const st = choiceStyle(i);
    const joined = Math.max(state.joined ?? 0, state.answered);
    const allIn = joined > 0 && state.answered >= joined;
    screen = (
      <div className="q-screen q-lockedin" style={{ background: st.bg, color: st.fg }}>
        {topbar}
        <div className="q-lock">
          <div className="q-mono q-small">✓ {ui("locked", lang)}</div>
          <div className="q-pickname">{answerLabel(card, mine, lang)}</div>
          <div className="q-small">{fmt(ui("liN", lang), { n: state.answered, m: joined })} · <People list={state.answered_by ?? []} max={6} /></div>
          <div className={`pip-wait ${allIn ? "all-in" : ""}`}><Mascot pose={allIn ? "watching" : "thinks"} size={120} /></div>
          <h2 className="q-narrow">{allIn ? ui("allIn", lang) : ui("waitOthers", lang)}</h2>
        </div>
        {saved.changed[card.card_id]
          ? <div className="q-pick-hint">{ui("lockedFinal", lang)}</div>
          : <button className="q-btn q-change" onClick={() => setChanging(card.card_id)}>{ui("changeOnce", lang)}</button>}
        <div className="q-pick-hint">{ui("liLater", lang)}</div>
      </div>
    );
  } else if (card && phase === "locked" && !before(card)) {
    withTabs = false;
    const slept = !askSeen.current.has(card.card_id) && !before(card);
    const i = mine ? card.question.options.findIndex((o) => o.id === mine) : -1;
    screen = (
      <div className="q-screen">
        {topbar}
        <div className="q-lock">
          <Mascot pose="watching" size={110} />
          {mine ? (
            <>
              <div className="q-mono q-small q-muted">{ui("lkYour", lang)}</div>
              <div className="q-chip-big" style={{ background: choiceStyle(i).bg, color: choiceStyle(i).fg }}>{answerLabel(card, mine, lang)}</div>
              <h2>{ui("lkWatch", lang)}</h2>
            </>
          ) : (
            <>
              <h2>{ui("lkNone", lang)}</h2>
              <p className="q-muted q-narrow">{slept ? ui("lkSlept", lang) : ui("lkNoWorry", lang)}</p>
            </>
          )}
          <div className="q-small q-muted">{fmt(ui("liN", lang), { n: state.answered, m: Math.max(state.joined ?? 0, state.answered) })} · <People list={state.answered_by ?? []} max={6} /></div>
        </div>
      </div>
    );
  } else if (card && match && phase === "reveal" && !seen[card.card_id] && !before(card)) {
    // A question from before this phone joined is in the catch-up card, not a "you missed it" screen.
    withTabs = false;
    const voided = !!card.reveal.void;
    const right = !voided && !!mine && mine === card.reveal.answer;
    const slept = !askSeen.current.has(card.card_id) && !before(card);
    const pipCall = card.question.pippi_call;
    const plain = fill(t(card.reveal.plain, lang), match.facts);
    screen = voided ? (
      <div className="q-screen">
        {topbar}
        <div className="q-banner learn">{ui("vdBanner", lang)}<small>{ui("vdSmall", lang)}</small></div>
        <div className="q-thread">
          {pipSays("thinks", <>{plain} {mine ? fmt(ui("vdYouSaid", lang), { x: answerLabel(card, mine, lang) }) : ""}</>)}
          <div className="q-row"><div className="q-av hidden" /><div className="q-bub">{ui("vdAgain", lang)}</div></div>
        </div>
        <div className="q-fill" />
        <button className="q-btn" onClick={gotIt}>{ui("gotIt", lang)}</button>
      </div>
    ) : (
      <div className="q-screen">
        {right && <Confetti />}
        {topbar}
        {right ? (
          <div className="q-banner right">{ui("mtRight", lang)}<small>{fmt(ui("rvRightSmall", lang), { n: state.tally[card.reveal.answer] ?? 1, m: Math.max(state.joined ?? 0, state.answered) })}</small></div>
        ) : mine ? (
          <div className="q-banner learn">{ui("rvLearn", lang)}<small>{fmt(ui("rvYouSaid", lang), { x: answerLabel(card, mine, lang) })}</small></div>
        ) : (
          <div className="q-banner learn">{ui("rvMissed", lang)}<small>{slept ? ui("rvMissedSlept", lang) : ui("rvMissedPlain", lang)}</small></div>
        )}
        <div className="q-thread">
          <div className="q-stamp q-mono">{ui("matchSays", lang)}</div>
          {pipSays(card.reveal.pose, <><div className="q-answer"><span className="q-hl">{answerLabel(card, card.reveal.answer, lang)}</span></div><div className="q-plain">{plain}</div></>)}
          <div className="q-row"><div className="q-av hidden" /><div className="q-bub">
            {fmt(ui(pipCall === card.reveal.answer ? "rvPipToo" : "rvPipWent", lang), { x: answerLabel(card, pipCall, lang) })}
          </div></div>
        </div>
        <details className="q-card q-deeper">
          <summary>{ui("goDeeper", lang)}</summary>
          <p className="q-small q-muted">{fill(t(card.reveal.expert, lang), match.facts)}</p>
        </details>
        <div className="q-fill" />
        <button className="q-btn" onClick={gotIt}>{ui("gotIt", lang)}</button>
      </div>
    );
  } else if (tab === "player") {
    screen = (
      <div className="q-screen">
        {topbar}
        {players && match ? (
          <PlayerTab match={match} feed={players} tracking={tracking} minute={minute} lang={lang} followId={followId} onFollow={onFollow} viewId={viewId} onView={setViewId} fresh={fresh} />
        ) : (
          <div className="q-fill q-centered"><Mascot pose="perch" size={110} /><p className="q-muted">{ui("loadingTracking", lang)}</p></div>
        )}
        <div className="q-fill" />
        {tabbar}
      </div>
    );
    withTabs = false;
  } else if (tab === "room") {
    screen = (
      <div className="q-screen">
        {topbar}
        <div className="q-roomhead">
          <h2>{fmt(ui("rmTitle", lang), { code: room })}</h2>
          <button className="q-danger" onClick={() => setSheet("leave")}>{ui("rmLeave", lang)}</button>
        </div>
        <div className="q-card q-stack">
          <div className="q-spread"><People list={inRoom} max={6} /><span className="q-small q-muted">{fmt(ui("rmHere", lang), { n: inRoom.length })}</span></div>
          <span className="q-small q-muted">{fmt(ui("rmYou", lang), { name: animalName(saved.animal, lang) })}</span>
        </div>
        <div className="q-list q-push">
          <button onClick={() => setLang(LANGS[(LANGS.indexOf(lang) + 1) % LANGS.length])}><span className="q-ic">文</span>{ui("rmLang", lang)}<span className="q-end">{lang.toUpperCase()}</span></button>
          <button onClick={() => setSheet("animal")}><span className="q-ic">↺</span>{ui("rmAnimal", lang)}<span className="q-end">{saved.animal}</span></button>
          <button role="switch" aria-checked={alerts} onClick={() => { if (alerts) { disableAlerts(); setAlerts(false); } else { void enableAlerts(); setAlerts(true); } }}>
            <span className="q-ic">🔔</span>{ui("rmChime", lang)}<span className={`q-toggle ${alerts ? "on" : ""}`} />
          </button>
        </div>
        <button className="q-btn" onClick={() => setSheet("invite")}>⇪ {ui("invite", lang)}</button>
        {tabbar}
      </div>
    );
    withTabs = false;
  } else if (phase === "lobby") {
    screen = (
      <div className="q-fill q-centered">
        <h1>{fmt(ui("lbIn", lang), { name: animalName(saved.animal, lang) })}</h1>
        <div className="q-seats">{inRoom.map((a, k) => <span key={k} className={a === saved.animal ? "me" : ""}>{a}</span>)}</div>
        <p className="q-muted q-narrow">{ui("lbText", lang)}</p>
        <button className="q-btn" onClick={() => setSheet("invite")}>⇪ {ui("invite", lang)}</button>
      </div>
    );
  } else if (match && (phase === "half" || phase === "full" || (showHalf && half))) {
    const full = phase === "full";
    const shown = full ? done : done.filter((c) => c.t_in_min <= HALF_MIN);
    const share = async () => {
      if (!half) return void copyLink();
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
    withTabs = !full;
    screen = (
      <>
        <div className="q-hero"><Mascot pose={full ? "wave" : "perch"} size={110} /></div>
        <div className="q-mono q-small q-muted q-center">{full ? ui("fullTime", lang) : ui("halfTime", lang)} · {scoreLine}</div>
        <h2 className="q-center">{full ? ui("hfThanks", lang) : ui("hfDrink", lang)}</h2>
        <div className="q-card q-stack">{callRows(shown)}</div>
        <div className="q-fill" />
        {full ? (
          <>
            <button className="q-btn ghost" onClick={share}>{ui("hfShare", lang)}</button>
            <button className="q-btn" onClick={leave}>{ui("shLeaveGo", lang)}</button>
          </>
        ) : (
          <>
            {half && <button className="q-btn ghost" onClick={share}>{ui("share", lang)}</button>}
            {showHalf && phase !== "half"
              ? <button className="q-btn soft" onClick={() => setShowHalf(false)}>{ui("hide", lang)}</button>
              : <button className="q-btn soft" onClick={() => setTab("player")}>☆ {ui("hfSeePlayer", lang)}</button>}
          </>
        )}
      </>
    );
  } else if (phase === "added" && state.board) {
    screen = (
      <>
        <div className="q-card q-stack">
          <div className="q-spread"><span className="q-mono q-small q-muted">{ui("addedTime", lang)} · {state.board.at_min}'</span><Mascot pose="thinks" size={56} /></div>
          <h2>{addedHeadline(state.board.announced_min, lang)}</h2>
          <p className="q-small">{ui("addedWhy", lang)}</p>
          <details className="q-deeper"><summary>{ui("goDeeper", lang)}</summary><div className="q-dark"><AddedBreakdown board={state.board} lang={lang} /></div></details>
        </div>
        <div className="q-fill" />
      </>
    );
  } else {
    // Match tab, open play: status, the call dots, the last call, and "your player" one tap away.
    const last = done[done.length - 1];
    const missed = match && saved.joinedAt > 1 && !saved.catchupSeen
      ? [
          ...match.score_timeline.filter((g) => g.player_id && g.from_min < saved.joinedAt).map((g) => ({
            min: g.from_min, text: fmt(ui("cuGoal", lang), { x: `${teamName(match, g.team_id ?? "")} #${g.player_id!.split("-")[1]}` }),
          })),
          ...done.filter(before).map((c) => ({ min: Math.floor(c.t_in_min), text: `${triggerLabel(c.trigger, lang)}: ${c.reveal.void ? ui("noClear", lang) : answerLabel(c, c.reveal.answer, lang)}` })),
        ].sort((a, b) => a.min - b.min)
      : null;
    screen = (
      <>
        {missed && (
          <div className="q-catch">
            <b>{fmt(ui("cuTitle", lang), { min: `${saved.joinedAt}'` })}</b>
            {missed.length ? missed.map((e, k) => <span key={k}>· {e.min}' {e.text}</span>) : <span>· {ui("cuNone", lang)}</span>}
            <button className="q-link" onClick={() => update((p) => ({ ...p, catchupSeen: true }))}>{ui("gotIt", lang)}</button>
          </div>
        )}
        <div className="q-card q-status">
          <div className={`q-now q-mono ${fresh}`}><i />{freshWord} · {liveClock} · {scoreLine}</div>
          <b className="q-lead">{ui("mtEyes", lang)}</b>
          <div className="q-dots" aria-hidden="true">
            {(match?.cards ?? []).map((c) => {
              if (!isDone(c)) return <i key={c.card_id} />;
              const m = myCall(c);
              return <i key={c.card_id} className={!m || c.reveal.void ? "m" : m === c.reveal.answer ? "r" : "w"} />;
            })}
          </div>
          <span className="q-small q-muted">{fmt(ui("mtCalls", lang), { n: done.length, m: match?.cards.length ?? 0 })}{alerts ? ` · ${ui("mtChime", lang)}` : ""}</span>
        </div>
        {last && pipSays("watching", (() => {
          const m = myCall(last);
          return <>{ui("mtLast", lang)} <b className="q-hl">{last.reveal.void ? ui("noClear", lang) : answerLabel(last, last.reveal.answer, lang)}</b>. {before(last) ? ui("mtBefore", lang) : !m ? ui("mtNone", lang) : !last.reveal.void && m === last.reveal.answer ? ui("mtRight", lang) : fmt(ui("mtSaid", lang), { x: answerLabel(last, m, lang) })}</>;
        })())}
        <div className="q-fill" />
        {state.scorer && players?.players.some((p) => p.player_id === state.scorer) && (
          <button className="q-btn soft" onClick={() => { setViewId(state.scorer ?? null); setTab("player"); }}>⚽ {ui("mtScorer", lang)}</button>
        )}
        {half && <button className="q-btn soft" onClick={() => setShowHalf(true)}>{ui("mtHalfCard", lang)}</button>}
        {followed && match ? (
          <button className="q-card q-followcard" onClick={() => setTab("player")}>
            <span className="q-shirt" style={{ background: kitOf(followed.player_id, match.teams).primary }}>{followed.shirt_no}</span>
            <span><b>{teamName(match, followed.team_id)} #{followed.shirt_no}</b><span className="q-small q-muted"> · {ui("mtFollowing", lang)}</span></span>
            <span className="q-muted">›</span>
          </button>
        ) : (
          <button className="q-btn soft" onClick={() => setTab("player")}>☆ {ui("mtFollow", lang)}</button>
        )}
      </>
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
            <h2>{fmt(ui("shInvite", lang), { code: room })}</h2>
            <div className="q-invite">
              <div className="q-qr"><QRCodeSVG value={joinUrl} size={118} bgColor="#FFFFFF" fgColor="#14202F" /></div>
              <div className="q-stack-tight">
                <span className="q-small q-muted">{fmt(ui("shOrType", lang), { host })}</span>
                <b className="q-mono q-bigcode">{room}</b>
                <span className="q-small q-muted">{ui("shAnyTime", lang)}</span>
              </div>
            </div>
            <button className="q-btn ghost" onClick={copyLink}>{ui("shCopy", lang)}</button>
            <button className="q-btn" onClick={() => setSheet(null)}>{ui("shDone", lang)}</button>
          </>
        )}
        {sheet === "leave" && (
          <>
            <h2>{fmt(ui("shLeave", lang), { code: room })}</h2>
            <p className="q-muted">{ui("shLeaveText", lang)}</p>
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
                  onClick={() => { lastHello.current = 0; update((p) => ({ ...p, animal: a })); setSheet(null); say(fmt(ui("rmYou", lang), { name: animalName(a, lang) })); }}>
                  {a}
                </button>
              ))}
            </div>
            <button className="q-btn" onClick={() => setSheet(null)}>{ui("shDone", lang)}</button>
          </>
        )}
      </div>
    </>
  );
  // Something between this phone and the TV is broken: say what and how to fix it, never an error code.
  const overlay =
    link === "offline" ? (
      <div className="q-offline" role="status"><span>●</span>{ui("stOffline", lang)}<span className="q-end">{ui("ovTvWorks", lang)}</span></div>
    ) : link === "no-room" && state ? (
      <div className="q-cover" role="status">
        <Mascot pose="thinks" size={110} />
        <h2>{fmt(ui("ovReconn", lang), { code: room })}</h2>
        <p className="q-muted q-small q-narrow">{ui("ovReconnText", lang)}</p>
      </div>
    ) : link === "tv-quiet" ? (
      <div className="q-cover" role="status">
        <Mascot pose="watching" size={110} />
        <h2>{ui("ovQuiet", lang)}</h2>
        <p className="q-muted q-narrow">{fmt(ui("ovQuietText", lang), { code: room })}</p>
        <div className="q-card q-small q-stack-tight q-left"><b>{ui("ovQuietFix", lang)}</b><span className="q-muted">{fmt(ui("ovQuietHow", lang), { host, code: room })}</span></div>
      </div>
    ) : null;

  return (
    <div className="q-ph">
      {screen && (withTabs ? (
        <>
          {topbar}
          {screen}
          {tabbar}
        </>
      ) : screen)}
      {sheetView}
      {overlay}
      {toast && <div className="q-toast" role="status">{toast}</div>}
    </div>
  );
}

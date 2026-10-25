import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Mascot from "../components/Mascot";
import { fmt, ui } from "../lib/i18n";
import { useLang } from "../lib/lang";
import { lastPhoneRoom } from "../lib/phoneRoom";
import { LANGS } from "../lib/types";

/** The phone's front door (room prototype "Start"): join a room, rejoin the last one, or learn how to start one on a TV.
 *  The main buttons sit low, in thumb reach. */
export default function Home() {
  const nav = useNavigate();
  const [lang, setLang] = useLang();
  const [howTv, setHowTv] = useState(false);
  const last = lastPhoneRoom();
  const host = location.host;
  const langs = (
    <span className="q-langs">
      {LANGS.map((l) => <button key={l} className={l === lang ? "on" : ""} onClick={() => setLang(l)} aria-pressed={l === lang}>{l.toUpperCase()}</button>)}
    </span>
  );

  if (howTv)
    return (
      <div className="q-ph">
        <div className="q-top"><button className="q-back" onClick={() => setHowTv(false)}>‹ {ui("back", lang)}</button>{langs}</div>
        <h2>{ui("tvHow", lang)}</h2>
        <div className="q-list">
          <div><span className="q-ic">1</span>{fmt(ui("tvHow1", lang), { host })}</div>
          <div><span className="q-ic">2</span>{ui("tvHow2", lang)}</div>
          <div><span className="q-ic">3</span>{ui("tvHow3", lang)}</div>
        </div>
        <div className="q-fill" />
        <button className="q-btn ghost" onClick={() => nav("/scan")}>{ui("tvHowScan", lang)}</button>
        <button className="q-btn" onClick={() => nav("/join")}>{ui("tvHowCode", lang)}</button>
      </div>
    );

  return (
    <div className="q-ph">
      <div className="q-top"><span className="q-mono">{host}</span>{langs}</div>
      <div className="q-hero"><Mascot pose="wave" size={118} /></div>
      <h1>{ui("stTitle", lang)}</h1>
      <p className="q-muted">{ui("stSub", lang)}</p>
      <div className="q-fill" />
      {last && (
        <button className="q-card q-rejoin" onClick={() => nav(`/play/${last}`)}>
          <span className="q-small q-muted">{ui("stLast", lang)}</span>
          <b className="q-mono">{fmt(ui("stRejoin", lang), { code: last })}</b>
        </button>
      )}
      <button className="q-btn ghost" onClick={() => setHowTv(true)}>{ui("stTv", lang)}</button>
      <button className="q-btn" onClick={() => nav("/join")}>{ui("stJoin", lang)}</button>
      <p className="q-small q-center"><Link className="q-link" to="/tv">{ui("stOnTv", lang)}</Link> · <Link className="q-link" to="/console">Console</Link></p>
    </div>
  );
}

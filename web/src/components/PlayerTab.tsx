import { lazy, Suspense, useEffect, useState } from "react";
import { ANIMAL_LABEL, animalOf } from "../lib/animals";
import { fmt, ui } from "../lib/i18n";
import { kitOf } from "../lib/kit";
import { fastestRun, minuteToMs, positionsAt, trail, type Tracking } from "../lib/tracking";
import { usePortraits } from "../lib/usePortraits";
import {
  clampMinute, describePlayer, goalsBy, km, kmh, matchNotes, minutesPlayed, POSITION_LABEL, STAT_LABEL, stat, statusAt, STATUS,
} from "../lib/whoThat";
import type { Lang, Match, PlayerRow, PlayersFeed } from "../lib/types";
import Pitch from "./Pitch";

const PlayerModel = lazy(() => import("./PlayerModel"));

interface Props {
  match: Match;
  feed: PlayersFeed;
  tracking: Tracking | null;
  minute: number; // the TV's clock: stats are never read past this minute
  lang: Lang;
  followId: string | null;
  onFollow: (id: string | null) => void;
  /** A player being looked at (from the list, or "See who scored"); null = your player, or the list. */
  viewId: string | null;
  onView: (id: string | null) => void;
  /** Whether numbers are still arriving from the TV (see Play): shown under the stats so nobody trusts frozen numbers. */
  fresh: "live" | "paused" | "stale";
}

/** "My player" tab (room prototype, re-audited 2026-10-23): one list to pick from, the full profile in the tab itself
 *  (3D character, all numbers, running path, this match), and Follow / Change / Stop following always one tap away.
 *  Buttons only, no typing (AGENTS.md rule 5). Who you follow stays on this phone; the TV only counts it. */
export default function PlayerTab({ match, feed, tracking, minute, lang, followId, onFollow, viewId, onView, fresh }: Props) {
  const m = clampMinute(feed, minute);
  const followed = feed.players.find((p) => p.player_id === followId) ?? null;
  const viewing = feed.players.find((p) => p.player_id === viewId) ?? null;
  const [picking, setPicking] = useState(false); // "Change player" while following: show the list

  const shown = viewing ?? (picking ? null : followed);
  if (!shown)
    return (
      <PlayerList match={match} feed={feed} m={m} lang={lang} followId={followId}
        onPick={(id) => { setPicking(false); onView(id); }} onCancel={followed && picking ? () => setPicking(false) : undefined} />
    );
  const isMine = shown.player_id === followId;
  return (
    <Profile key={shown.player_id} match={match} feed={feed} tracking={tracking} p={shown} m={m} lang={lang} mine={isMine} following={!!followed} fresh={minute > feed.last_minute ? "ended" : fresh}
      onBack={viewing ? () => onView(null) : undefined}
      onFollow={() => { onFollow(shown.player_id); onView(null); setPicking(false); }}
      onChange={() => { onView(null); setPicking(true); }}
      onStop={() => { onFollow(null); onView(null); setPicking(false); }} />
  );
}

function PlayerList({ match, feed, m, lang, followId, onPick, onCancel }: {
  match: Match; feed: PlayersFeed; m: number; lang: Lang; followId: string | null; onPick: (id: string) => void; onCancel?: () => void;
}) {
  const [team, setTeam] = useState(match.teams[0].team_id);
  const rows = feed.players.filter((p) => p.team_id === team);
  const faces = usePortraits(rows.map((p) => p.player_id), match.teams);
  const order = { GK: 0, DF: 1, MF: 2, FW: 3 };
  const onNow = (p: PlayerRow) => minutesPlayed(p, m) > 0 && statusAt(p, m).kind !== "wentOff";
  const sorted = [...rows].sort((a, b) => Number(onNow(b)) - Number(onNow(a)) || order[a.position] - order[b.position] || a.shirt_no - b.shirt_no);
  return (
    <>
      {onCancel && <button className="q-back q-back-row" onClick={onCancel}>‹ {ui("yourPlayer", lang)}</button>}
      <h2>{ui("plTitle", lang)}</h2>
      <p className="q-small q-muted">{ui("plText", lang)}</p>
      <div className="q-seg" role="tablist" aria-label={ui("pickTeam", lang)}>
        {match.teams.map((t) => (
          <button key={t.team_id} role="tab" aria-selected={team === t.team_id} className={team === t.team_id ? "on" : ""} onClick={() => setTeam(t.team_id)}>
            <i style={{ background: t.kit.primary }} />{t.name}
          </button>
        ))}
      </div>
      <div className="q-players">
        {sorted.map((p) => {
          const kit = kitOf(p.player_id, match.teams);
          const animal = ANIMAL_LABEL[animalOf(p.player_id)];
          const st = statusAt(p, m);
          return (
            <button key={p.player_id} className={`q-prow ${onNow(p) ? "" : "idle"}`} onClick={() => onPick(p.player_id)}>
              <span className="q-face" style={{ background: `radial-gradient(circle at 50% 70%, ${kit.primary}55, var(--q-paper-2) 72%)` }}>
                {faces[p.player_id] ? <img src={faces[p.player_id]} alt="" /> : <span aria-hidden="true">{animal.emoji}</span>}
              </span>
              <span className="q-shirt" style={{ background: kit.primary, color: kit.secondary }}>{p.shirt_no}</span>
              <span className="q-prow-text">
                <b>{animal.emoji} {animal[lang]}{followId === p.player_id ? " ★" : ""}</b>
                <span className="q-small q-muted">{POSITION_LABEL[p.position][lang]} · {STATUS[st.kind][lang]}{st.at !== undefined ? ` ${st.at}'` : ""}</span>
              </span>
              <span className="q-muted" aria-hidden="true">›</span>
            </button>
          );
        })}
      </div>
    </>
  );
}

function Profile({ match, feed, tracking, p, m, lang, mine, following, fresh, onBack, onFollow, onChange, onStop }: {
  match: Match; feed: PlayersFeed; tracking: Tracking | null; p: PlayerRow; m: number; lang: Lang; mine: boolean; following: boolean;
  fresh: "live" | "paused" | "stale" | "ended";
  onBack?: () => void; onFollow: () => void; onChange: () => void; onStop: () => void;
}) {
  const team = match.teams.find((t) => t.team_id === p.team_id);
  const kit = kitOf(p.player_id, match.teams);
  const status = statusAt(p, m);
  const animal = ANIMAL_LABEL[animalOf(p.player_id)];
  const s = (k: Parameters<typeof stat>[1]) => stat(p, k, m);
  const played = minutesPlayed(p, m) > 0;
  const goals = goalsBy(match, p.player_id, m);
  const key: [string, string][] = [
    [STAT_LABEL.distance[lang], `${km(s("distance_m"))} km`],
    [STAT_LABEL.topSpeed[lang], `${kmh(s("top_speed_dmh"))} km/h`],
    p.position === "GK" ? [STAT_LABEL.saves[lang], String(s("saves"))] : [STAT_LABEL.passes[lang], `${s("passes_ok")}/${s("passes")}`],
    goals > 0 ? [STAT_LABEL.goals[lang], String(goals)] : [STAT_LABEL.shots[lang], String(s("shots"))],
  ];
  const all: [string, string][] = [
    [STAT_LABEL.distance[lang], `${km(s("distance_m"))} km`],
    [STAT_LABEL.topSpeed[lang], `${kmh(s("top_speed_dmh"))} km/h`],
    [STAT_LABEL.sprints[lang], String(s("sprints"))],
    [STAT_LABEL.passes[lang], `${s("passes_ok")} / ${s("passes")}`],
    [STAT_LABEL.hardPasses[lang], String(s("hard_ok"))],
    [STAT_LABEL.ballWins[lang], String(s("ball_wins"))],
    [STAT_LABEL.shots[lang], String(s("shots"))],
    ...(goals > 0 ? ([[STAT_LABEL.goals[lang], String(goals)]] as [string, string][]) : []),
    ...(p.position === "GK" ? ([[STAT_LABEL.saves[lang], String(s("saves"))]] as [string, string][]) : []),
  ];
  const notes = matchNotes(match, p, m, lang);
  return (
    <>
      {onBack && <button className="q-back q-back-row" onClick={onBack}>‹ {following ? ui("yourPlayer", lang) : ui("plAll", lang)}</button>}
      <div className="q-card q-hero-card" style={{ background: `linear-gradient(180deg, ${kit.primary}40, var(--q-card) 62%)` }}>
        <Suspense fallback={<div style={{ height: 210 }} />}>
          <PlayerModel playerId={p.player_id} teams={match.teams} height={210} />
        </Suspense>
        <div className="q-pid">
          <span className="q-shirt big" style={{ background: kit.primary, color: kit.secondary }}>{p.shirt_no}</span>
          <div>
            <h2>{team?.name} #{p.shirt_no}</h2>
            <div className="q-small q-muted">{animal.emoji} {animal[lang]} · {POSITION_LABEL[p.position][lang]} · {STATUS[status.kind][lang]}{status.at !== undefined ? ` ${status.at}'` : ""}</div>
          </div>
          {mine && <span className="q-badge">★ {ui("following", lang)}</span>}
        </div>
      </div>
      {!mine && <button className="q-btn" onClick={onFollow}>☆ {following ? ui("plInstead", lang) : ui("follow", lang)}</button>}

      {played ? (
        <div className="q-statgrid">
          {key.map(([k, v]) => <div key={k}><b>{v}</b>{k}</div>)}
        </div>
      ) : null}
      <p className={`q-fresh ${fresh}`} role="status">
        <i aria-hidden="true" />{fmt(ui("stAsOf", lang), { t: `${m}'` })} · {ui(fresh === "live" ? "stLiveTxt" : fresh === "paused" ? "stPausedTxt" : fresh === "ended" ? "stEnded" : "stStaleTxt", lang)}
      </p>
      <p className="q-small">{describePlayer(feed, p, m, team?.name ?? p.team_id, lang)}</p>

      {played && <RunningPath match={match} tracking={tracking} p={p} m={m} lang={lang} />}

      {notes.length > 0 && (
        <details className="q-card q-deeper" open>
          <summary>{ui("thisMatch", lang)} · {m}'</summary>
          <ul className="q-notes">{notes.map((n, i) => <li key={i}><span className="q-mono q-small">{n.min}'</span>{n.text}</li>)}</ul>
        </details>
      )}
      {played && (
        <details className="q-card q-deeper">
          <summary>{ui("allStats", lang)}</summary>
          <dl className="q-allstats">{all.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
          <p className="q-small q-muted">{ui("modelled", lang)}</p>
        </details>
      )}
      <p className="q-small q-muted">{ui("plNote", lang)} {ui("followHint", lang)}</p>
      {mine && (
        <div className="q-two">
          <button className="q-btn ghost" onClick={onChange}>{ui("plChange", lang)}</button>
          <button className="q-btn ghost q-danger-text" onClick={onStop}>{ui("plStop", lang)}</button>
        </div>
      )}
    </>
  );
}

const LEAD_MS = 4000;
const RUN_MS = 7000;

/** Laufweg: where the player has been in the last five minutes, still (the phone stays calm), plus their fastest run
 *  so far, replayed only when asked. */
function RunningPath({ match, tracking, p, m, lang }: { match: Match; tracking: Tracking | null; p: PlayerRow; m: number; lang: Lang }) {
  const [at, setAt] = useState<number | null>(null); // ms into the fastest-run replay; null = the still picture
  useEffect(() => {
    if (at === null) return;
    if (at >= RUN_MS) return void setAt(null);
    const id = setTimeout(() => setAt((a) => (a === null ? null : a + 100)), 100);
    return () => clearTimeout(id);
  }, [at]);
  if (!tracking)
    return <div className="q-card q-small q-muted">{ui("loadingTracking", lang)}</div>;
  const nowMs = minuteToMs(tracking, m);
  const run = fastestRun(tracking, p.player_id, nowMs);
  const replaying = at !== null && run;
  const tMs = replaying ? run.tMs - LEAD_MS + at : nowMs;
  const dots = positionsAt(tracking, tMs);
  const here = dots.some((d) => d.id === p.player_id);
  const path = replaying ? trail(tracking, p.player_id, tMs, Math.round(at / 1000), 0.2) : here ? trail(tracking, p.player_id, tMs, 300, 5) : undefined;
  return (
    <section className="q-card q-path">
      <div className="q-spread"><b>{ui("plPath", lang)}</b><span className="q-mono q-small q-muted">{replaying ? `${(run.kmh).toFixed(1)} km/h` : `${m}'`}</span></div>
      <div className="q-pitch">
        <Pitch fit="contain" dots={dots} teams={match.teams} focusId={p.player_id} selectedId={p.player_id} easeMs={replaying ? 100 : 0} trail={path} />
      </div>
      <span className="q-small q-muted">{replaying ? ui("plFastest", lang) : here ? ui("lastMinutes", lang) : ui("notOnPitch", lang)}</span>
      {run && (
        <button className="q-btn soft" onClick={() => setAt(0)} disabled={at !== null}>▶ {ui("plFastest", lang)} · {run.kmh.toFixed(1)} km/h</button>
      )}
    </section>
  );
}

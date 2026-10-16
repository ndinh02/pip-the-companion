import { useEffect, useState } from "react";
import Pitch from "./Pitch";
import { ui } from "../lib/i18n";
import { fastestRun, minuteToMs, positionsAt, trail, type Tracking } from "../lib/tracking";
import { clampMinute, km, kmh, POSITION_LABEL, stat, STAT_LABEL, teamName } from "../lib/whoThat";
import type { Lang, Match, PlayerRow, PlayersFeed } from "../lib/types";

/** "Your player": a still picture of where they are and where they have been, plus their numbers.
 *  Nothing moves here; the phone stays calm (brief §5.2). */
export function FollowView({ match, feed, tracking, p, minute, lang, onClose }: {
  match: Match; feed: PlayersFeed; tracking: Tracking | null; p: PlayerRow; minute: number; lang: Lang; onClose: () => void;
}) {
  const m = clampMinute(feed, minute);
  const tMs = tracking ? minuteToMs(tracking, m) : 0;
  const dots = tracking ? positionsAt(tracking, tMs) : null;
  const here = dots?.some((d) => d.id === p.player_id);
  return (
    <main className="follow-view">
      <div className="wt-head">
        <button className="ghost" onClick={onClose}>{ui("hide", lang)}</button>
        <h2>★ {ui("yourPlayer", lang)}</h2>
      </div>
      <div className="eyebrow">{teamName(match, p.team_id)} · #{p.shirt_no} · {POSITION_LABEL[p.position][lang]} · {m}'</div>
      {!tracking && <p className="dim">{ui("loadingTracking", lang)}</p>}
      {tracking && dots && (
        <>
          <Pitch fit="contain" dots={dots} teams={match.teams} focusId={p.player_id} selectedId={p.player_id} easeMs={0}
            trail={here ? trail(tracking, p.player_id, tMs, 300, 5) : undefined} />
          <p className="dim small">{here ? ui("lastMinutes", lang) : ui("notOnPitch", lang)}</p>
        </>
      )}
      <dl className="stats">
        <div><dt>{STAT_LABEL.distance[lang]}</dt><dd>{km(stat(p, "distance_m", m))} km</dd></div>
        <div><dt>{STAT_LABEL.sprints[lang]}</dt><dd>{stat(p, "sprints", m)}</dd></div>
        <div><dt>{STAT_LABEL.topSpeed[lang]}</dt><dd>{kmh(stat(p, "top_speed_dmh", m))} km/h</dd></div>
        <div><dt>{STAT_LABEL.passes[lang]}</dt><dd>{stat(p, "passes_ok", m)} / {stat(p, "passes", m)}</dd></div>
      </dl>
    </main>
  );
}

const LEAD_MS = 4000;
const RUN_MS = 7000;

/** Half-time ghost run: the followed player's fastest moment of the half, replayed on demand (never autoplays). */
export function GhostRun({ match, tracking, p, untilMs, lang }: { match: Match; tracking: Tracking; p: PlayerRow; untilMs: number; lang: Lang }) {
  const run = fastestRun(tracking, p.player_id, untilMs);
  const [at, setAt] = useState<number | null>(null); // ms into the replay, null = showing the finished run
  useEffect(() => {
    if (at === null) return;
    if (at >= RUN_MS) {
      setAt(null);
      return;
    }
    const id = setTimeout(() => setAt((a) => (a === null ? null : a + 100)), 100);
    return () => clearTimeout(id);
  }, [at]);
  if (!run) return null;
  const start = run.tMs - LEAD_MS;
  const tMs = at === null ? start + RUN_MS : start + at;
  const shown = Math.round((tMs - start) / 1000);
  return (
    <div className="ghost-run">
      <div className="eyebrow">{ui("ghostRun", lang)} · {teamName(match, p.team_id)} #{p.shirt_no}</div>
      <Pitch fit="contain" dots={positionsAt(tracking, tMs)} teams={match.teams} focusId={p.player_id} selectedId={p.player_id} easeMs={at === null ? 0 : 100}
        trail={trail(tracking, p.player_id, tMs, shown, 0.2)} />
      <p><strong>{run.kmh.toFixed(1)} km/h</strong></p>
      <button className="ghost" onClick={() => setAt(0)} disabled={at !== null}>{ui("replay", lang)}</button>
    </div>
  );
}

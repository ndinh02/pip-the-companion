import { useEffect, useMemo, useState } from "react";
import Pitch from "./Pitch";
import { endMs, msToMinute, positionsAt, speedKmh, trail, type Tracking } from "../lib/tracking";
import { km, kmh, loadFollow, POSITION_LABEL, stat, STAT_LABEL } from "../lib/whoThat";
import type { Match, PlayersFeed } from "../lib/types";

const SPEEDS = [1, 8, 60];
const SPRINT_KMH = 25;

/** Laptop expert view: the whole pitch with its own clock. Click a player (or pick from the list) for live numbers. */
export default function TrackingPanel({ match, tracking, players }: { match: Match; tracking: Tracking; players: PlayersFeed | null }) {
  const end = useMemo(() => endMs(tracking), [tracking]);
  const [tMs, setTMs] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(8);
  const [picked, setPicked] = useState<string | null>(() => loadFollow());

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setTMs((t) => Math.min(end, t + 100 * speed)), 100);
    return () => clearInterval(id);
  }, [playing, speed, end]);
  useEffect(() => {
    if (tMs >= end) setPlaying(false);
  }, [tMs, end]);

  const dots = positionsAt(tracking, tMs);
  const minute = msToMinute(tracking, tMs);
  const m = Math.floor(minute);
  const onPitch = picked ? dots.some((d) => d.id === picked) : false;
  const row = players?.players.find((p) => p.player_id === picked) ?? null;
  const v = picked ? speedKmh(tracking, picked, tMs) : null;
  const team = match.teams.find((t) => picked?.startsWith(`${t.team_id}-`));
  const ids = tracking.entities.filter((e) => e !== "ball");

  return (
    <section className="tracking-panel">
      <div className="tp-pitch">
        <Pitch fit="contain" dots={dots} teams={match.teams} easeMs={speed === 1 ? 100 : 0} onPick={setPicked} selectedId={picked}
          trail={picked && onPitch ? trail(tracking, picked, tMs) : undefined} />
        <div className="tp-controls" role="group" aria-label="Replay controls">
          <button onClick={() => setPlaying((p) => !p)}>{playing ? "Pause" : "Play"}</button>
          {SPEEDS.map((s) => (
            <button key={s} className={s === speed ? "on" : ""} onClick={() => setSpeed(s)} aria-pressed={s === speed}>×{s}</button>
          ))}
          <input type="range" min={0} max={end} step={1000} value={tMs} onChange={(e) => setTMs(Number(e.target.value))} aria-label="Match time" />
          <span className="mono">{m}'{String(Math.floor((minute - m) * 60)).padStart(2, "0")}</span>
        </div>
      </div>

      <div className="tp-side">
        <label className="dim" htmlFor="tp-player">Player</label>
        <select id="tp-player" value={picked ?? ""} onChange={(e) => setPicked(e.target.value || null)}>
          <option value="">Click a player or choose…</option>
          {ids.map((id) => <option key={id} value={id}>{id.replace("-", " #")}</option>)}
        </select>

        {picked && (
          <>
            <h3>{team?.name} · #{picked.split("-")[1]}</h3>
            <div className="dim">{row ? POSITION_LABEL[row.position].en : ""}{onPitch ? "" : " · not on the pitch"}</div>
            <div className={`tp-speed ${v !== null && v > SPRINT_KMH ? "sprint" : ""}`}>
              <strong>{v === null ? "–" : v.toFixed(1)}</strong> km/h
              {v !== null && v > SPRINT_KMH && <span className="tag">sprint</span>}
            </div>
            {row && (
              <dl className="stats">
                <div><dt>{STAT_LABEL.distance.en}</dt><dd>{km(stat(row, "distance_m", m))} km</dd></div>
                <div><dt>{STAT_LABEL.topSpeed.en}</dt><dd>{kmh(stat(row, "top_speed_dmh", m))} km/h</dd></div>
                <div><dt>{STAT_LABEL.sprints.en}</dt><dd>{stat(row, "sprints", m)}</dd></div>
                <div><dt>{STAT_LABEL.passes.en}</dt><dd>{stat(row, "passes_ok", m)} / {stat(row, "passes", m)}</dd></div>
                <div><dt>{STAT_LABEL.hardPasses.en}</dt><dd>{stat(row, "hard_ok", m)}</dd></div>
                <div><dt>{STAT_LABEL.ballWins.en}</dt><dd>{stat(row, "ball_wins", m)}</dd></div>
              </dl>
            )}
            <p className="dim small">Trail = last 30 s. Speed is measured from the tracking; the table is as of minute {m}.</p>
          </>
        )}
      </div>
    </section>
  );
}

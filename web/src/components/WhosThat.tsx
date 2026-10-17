import { lazy, Suspense, useState } from "react";
import { ANIMAL_LABEL, animalOf } from "../lib/animals";
import { ui } from "../lib/i18n";
import { kitOf } from "../lib/kit";
import { usePortraits } from "../lib/usePortraits";
import {
  clampMinute, describePlayer, goalsBy, kmh, km, matchNotes, minutesPlayed, POSITION_LABEL, STAT_LABEL, stat, statusAt, STATUS, teamName,
} from "../lib/whoThat";
import type { Lang, Match, PlayerRow, PlayersFeed } from "../lib/types";

const PlayerModel = lazy(() => import("./PlayerModel"));

interface Props {
  match: Match;
  feed: PlayersFeed;
  minute: number; // the TV's clock: stats are never read past this minute
  lang: Lang;
  followId: string | null;
  onFollow: (id: string | null) => void;
  onClose: () => void;
  /** Open straight on this player's card (e.g. the goal scorer). */
  startId?: string | null;
}

/** "Who's that?": team -> squad (faces and numbers) -> profile. Buttons only, no typing (AGENTS.md rule 5). */
export default function WhosThat({ match, feed, minute, lang, followId, onFollow, onClose, startId }: Props) {
  const start = startId ? feed.players.find((p) => p.player_id === startId) ?? null : null;
  const [team, setTeam] = useState<string | null>(start?.team_id ?? null);
  const [player, setPlayer] = useState<PlayerRow | null>(start);
  const m = clampMinute(feed, minute);
  const back = () => (player ? setPlayer(null) : team ? setTeam(null) : onClose());

  return (
    <main className="whos-that">
      <div className="wt-head">
        <button className="ghost" onClick={back}>{player || team ? `← ${ui("back", lang)}` : ui("hide", lang)}</button>
        <h2>{ui("whosThat", lang)}</h2>
      </div>

      {!team && (
        <>
          <div className="eyebrow">{ui("pickTeam", lang)}</div>
          <div className="team-cards">
            {match.teams.map((t) => {
              const on = feed.players.filter((p) => p.team_id === t.team_id && statusAt(p, m).kind !== "bench" && statusAt(p, m).kind !== "wentOff").length;
              return (
                <button key={t.team_id} className="team-card" onClick={() => setTeam(t.team_id)}
                  style={{ background: `linear-gradient(160deg, ${t.kit.primary}, ${t.kit.primary}cc 55%, #0e1a2b)` }}>
                  <span className="tc-short">{t.short_name}</span>
                  <span className="tc-name">{t.name}</span>
                  <span className="tc-on">{on} {ui("onPitch", lang)}</span>
                </button>
              );
            })}
          </div>
        </>
      )}

      {team && !player && <Squad match={match} feed={feed} team={team} m={m} lang={lang} followId={followId} onPick={setPlayer} />}

      {player && <PlayerProfile match={match} feed={feed} p={player} m={m} lang={lang} followed={followId === player.player_id}
        onFollow={() => onFollow(followId === player.player_id ? null : player.player_id)} />}
    </main>
  );
}

function Squad({ match, feed, team, m, lang, followId, onPick }: {
  match: Match; feed: PlayersFeed; team: string; m: number; lang: Lang; followId: string | null; onPick: (p: PlayerRow) => void;
}) {
  const rows = feed.players.filter((p) => p.team_id === team);
  const faces = usePortraits(rows.map((p) => p.player_id), match.teams);
  const order = { GK: 0, DF: 1, MF: 2, FW: 3 };
  const sorted = [...rows].sort((a, b) => Number(minutesPlayed(b, m) > 0) - Number(minutesPlayed(a, m) > 0) || order[a.position] - order[b.position] || a.shirt_no - b.shirt_no);
  return (
    <>
      <div className="eyebrow">{teamName(match, team)} · {ui("pickPlayer", lang)}</div>
      <div className="squad">
        {sorted.map((p) => {
          const kit = kitOf(p.player_id, match.teams);
          const playing = minutesPlayed(p, m) > 0 && statusAt(p, m).kind !== "wentOff";
          const animal = ANIMAL_LABEL[animalOf(p.player_id)];
          return (
            <button key={p.player_id} className={`face-card ${playing ? "" : "idle"}`} onClick={() => onPick(p)}
              aria-label={`${p.shirt_no}, ${animal[lang]}, ${POSITION_LABEL[p.position][lang]}`}>
              <span className="face" style={{ background: `radial-gradient(circle at 50% 70%, ${kit.primary}55, transparent 70%)` }}>
                {faces[p.player_id] ? <img src={faces[p.player_id]} alt="" /> : <span className="emoji" aria-hidden="true">{animal.emoji}</span>}
              </span>
              <span className="fc-num" style={{ background: kit.primary, color: kit.secondary }}>{p.shirt_no}</span>
              <span className="fc-pos">{p.position}{followId === p.player_id ? " ★" : ""}</span>
            </button>
          );
        })}
      </div>
    </>
  );
}

export function PlayerProfile({ match, feed, p, m, lang, followed, onFollow }: {
  match: Match; feed: PlayersFeed; p: PlayerRow; m: number; lang: Lang; followed: boolean; onFollow: () => void;
}) {
  const team = match.teams.find((t) => t.team_id === p.team_id);
  const kit = kitOf(p.player_id, match.teams);
  const status = statusAt(p, m);
  const s = (k: Parameters<typeof stat>[1]) => stat(p, k, m);
  const played = minutesPlayed(p, m) > 0;
  const goals = goalsBy(match, p.player_id, m);
  const animal = ANIMAL_LABEL[animalOf(p.player_id)];
  const key: [string, string][] = played
    ? [
        goals > 0 ? [STAT_LABEL.goals[lang], String(goals)] : [STAT_LABEL.shots[lang], String(s("shots"))],
        [STAT_LABEL.distance[lang], `${km(s("distance_m"))} km`],
        p.position === "GK" ? [STAT_LABEL.saves[lang], String(s("saves"))] : [STAT_LABEL.topSpeed[lang], `${kmh(s("top_speed_dmh"))}`],
      ]
    : [];
  const more: [string, string][] = played
    ? [
        [STAT_LABEL.topSpeed[lang], `${kmh(s("top_speed_dmh"))} km/h`],
        [STAT_LABEL.sprints[lang], String(s("sprints"))],
        [STAT_LABEL.passes[lang], `${s("passes_ok")} / ${s("passes")}`],
        [STAT_LABEL.hardPasses[lang], String(s("hard_ok"))],
        [STAT_LABEL.ballWins[lang], String(s("ball_wins"))],
        [STAT_LABEL.shots[lang], String(s("shots"))],
        ...(p.position === "GK" ? ([[STAT_LABEL.saves[lang], String(s("saves"))]] as [string, string][]) : []),
      ]
    : [];
  const notes = matchNotes(match, p, m, lang);
  return (
    <section className="profile" aria-live="polite">
      <div className="pf-top" style={{ background: `linear-gradient(180deg, ${kit.primary}66, transparent)` }}>
        <Suspense fallback={<div className="player-model" style={{ height: 200 }} />}>
          <PlayerModel playerId={p.player_id} teams={match.teams} height={200} />
        </Suspense>
        <div className="pf-id">
          <span className="shirt" style={{ background: kit.primary, color: kit.secondary }}>{p.shirt_no}</span>
          <div>
            <h3>{team?.name} · #{p.shirt_no}</h3>
            <div className="dim">{animal.emoji} {animal[lang]} · {POSITION_LABEL[p.position][lang]}</div>
            <div className="dim small">{STATUS[status.kind][lang]}{status.at !== undefined ? ` ${status.at}'` : ""}</div>
          </div>
        </div>
        <button className={`follow-btn ${followed ? "on" : ""}`} onClick={onFollow} aria-pressed={followed}>
          {followed ? `★ ${ui("following", lang)}` : `☆ ${ui("follow", lang)}`}
        </button>
      </div>

      {key.length > 0 && (
        <dl className="key-stats">
          {key.map(([k, v]) => (
            <div key={k}><dd>{v}</dd><dt>{k}</dt></div>
          ))}
        </dl>
      )}
      <p className="plain">{describePlayer(feed, p, m, team?.name ?? p.team_id, lang)}</p>

      {notes.length > 0 && (
        <details className="fold" open>
          <summary>{ui("thisMatch", lang)} · {m}'</summary>
          <ul className="notes">
            {notes.map((n, i) => (
              <li key={i}><span className="n-min">{n.min}'</span>{n.text}</li>
            ))}
          </ul>
        </details>
      )}
      {more.length > 0 && (
        <details className="fold">
          <summary>{ui("allStats", lang)}</summary>
          <dl className="stats">
            {more.map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
          <p className="dim small">{ui("modelled", lang)}</p>
        </details>
      )}
      <p className="dim small">{ui("followHint", lang)}</p>
    </section>
  );
}

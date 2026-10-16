import { useState } from "react";
import { ui } from "../lib/i18n";
import {
  clampMinute, describePlayer, kmh, km, minutesPlayed, POSITION_LABEL, STAT_LABEL, stat, statusAt, STATUS, teamName,
} from "../lib/whoThat";
import type { Lang, Match, PlayerRow, PlayersFeed } from "../lib/types";

interface Props {
  match: Match;
  feed: PlayersFeed;
  minute: number; // the TV's clock: stats are never read past this minute
  lang: Lang;
  followId: string | null;
  onFollow: (id: string | null) => void;
  onClose: () => void;
}

/** "Who's that?": team colour -> shirt number -> player card. Buttons only, no typing (AGENTS.md rule 5). */
export default function WhosThat({ match, feed, minute, lang, followId, onFollow, onClose }: Props) {
  const [team, setTeam] = useState<string | null>(null);
  const [player, setPlayer] = useState<PlayerRow | null>(null);
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
          <div className="team-chips">
            {match.teams.map((t) => (
              <button key={t.team_id} className="team-chip" style={{ borderColor: t.kit.primary }} onClick={() => setTeam(t.team_id)}>
                <i style={{ background: t.kit.primary }} aria-hidden="true" />
                {t.name}
              </button>
            ))}
          </div>
        </>
      )}

      {team && !player && (
        <>
          <div className="eyebrow">{teamName(match, team)} · {ui("pickNumber", lang)}</div>
          <div className="numbers">
            {feed.players.filter((p) => p.team_id === team).map((p) => (
              <button key={p.player_id} className={`num ${minutesPlayed(p, m) > 0 ? "" : "idle"}`} onClick={() => setPlayer(p)}
                aria-label={`${p.shirt_no}, ${POSITION_LABEL[p.position][lang]}`}>
                <b>{p.shirt_no}</b>
                <span>{p.position}</span>
              </button>
            ))}
          </div>
        </>
      )}

      {player && <PlayerCard match={match} feed={feed} p={player} m={m} lang={lang} followed={followId === player.player_id}
        onFollow={() => onFollow(followId === player.player_id ? null : player.player_id)} />}
    </main>
  );
}

function PlayerCard({ match, feed, p, m, lang, followed, onFollow }: {
  match: Match; feed: PlayersFeed; p: PlayerRow; m: number; lang: Lang; followed: boolean; onFollow: () => void;
}) {
  const team = match.teams.find((t) => t.team_id === p.team_id);
  const status = statusAt(p, m);
  const s = (k: Parameters<typeof stat>[1]) => stat(p, k, m);
  const played = minutesPlayed(p, m) > 0;
  const rows: [string, string][] = played
    ? [
        [STAT_LABEL.distance[lang], `${km(s("distance_m"))} km`],
        [STAT_LABEL.topSpeed[lang], `${kmh(s("top_speed_dmh"))} km/h`],
        [STAT_LABEL.sprints[lang], String(s("sprints"))],
        [STAT_LABEL.passes[lang], `${s("passes_ok")} / ${s("passes")}`],
        [STAT_LABEL.hardPasses[lang], String(s("hard_ok"))],
        [STAT_LABEL.ballWins[lang], String(s("ball_wins"))],
        [STAT_LABEL.shots[lang], String(s("shots"))],
        ...(p.position === "GK" ? ([[STAT_LABEL.saves[lang], String(s("saves"))]] as [string, string][]) : []),
      ]
    : [];
  return (
    <section className="player-card" aria-live="polite">
      <div className="pc-head">
        <span className="shirt" style={{ background: team?.kit.primary, color: team?.kit.secondary }}>{p.shirt_no}</span>
        <div>
          <h3>{team?.name} · #{p.shirt_no}</h3>
          <div className="dim">{POSITION_LABEL[p.position][lang]} · {STATUS[status.kind][lang]}{status.at !== undefined ? ` ${status.at}'` : ""}</div>
        </div>
      </div>
      <p className="plain">{describePlayer(feed, p, m, team?.name ?? p.team_id, lang)}</p>
      {rows.length > 0 && (
        <>
          <div className="eyebrow">{ui("soFar", lang)} · {m}'</div>
          <dl className="stats">
            {rows.map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
          <p className="dim small">{ui("modelled", lang)}</p>
        </>
      )}
      <button className={followed ? "ghost on" : "ghost"} onClick={onFollow} aria-pressed={followed}>
        {followed ? `${ui("following", lang)} · ${ui("unfollow", lang)}` : ui("follow", lang)}
      </button>
      <p className="dim small">{ui("followHint", lang)}</p>
    </section>
  );
}

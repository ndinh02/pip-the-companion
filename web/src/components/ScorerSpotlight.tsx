import { ANIMAL_LABEL, animalOf } from "../lib/animals";
import { ui } from "../lib/i18n";
import { clampMinute, describePlayer, goalsBy, kmh, km, POSITION_LABEL, STAT_LABEL, stat } from "../lib/whoThat";
import type { Lang, Match, PlayersFeed } from "../lib/types";

/** The TV's quick profile of a goal scorer: who it is and how their match is going, as of now (no spoilers).
 *  Numbers only (no names, decision D1); every value comes from the players feed or the score timeline. */
export default function ScorerSpotlight({ match, feed, playerId, minute, lang }: {
  match: Match; feed: PlayersFeed; playerId: string; minute: number; lang: Lang;
}) {
  const p = feed.players.find((x) => x.player_id === playerId);
  if (!p) return null;
  const team = match.teams.find((t) => t.team_id === p.team_id);
  const m = clampMinute(feed, minute);
  const animal = ANIMAL_LABEL[animalOf(p.player_id)];
  const goals = Math.max(1, goalsBy(match, p.player_id, Math.ceil(minute))); // the goal just scored always counts
  const facts: [string, string][] = [
    [STAT_LABEL.goals[lang], String(goals)],
    [STAT_LABEL.shots[lang], String(Math.max(goals, stat(p, "shots", m)))],
    [STAT_LABEL.topSpeed[lang], `${kmh(stat(p, "top_speed_dmh", m))} km/h`],
    [STAT_LABEL.distance[lang], `${km(stat(p, "distance_m", m))} km`],
  ];
  return (
    <section className="spotlight" aria-live="polite" style={{ borderLeftColor: team?.kit.primary }}>
      <div className="sp-head">
        <span className="shirt" style={{ background: team?.kit.primary, color: team?.kit.secondary }}>{p.shirt_no}</span>
        <div>
          <div className="eyebrow">{ui("scorer", lang)}</div>
          <h2>{team?.name} · #{p.shirt_no}</h2>
          <div className="dim">{animal.emoji} {animal[lang]} · {POSITION_LABEL[p.position][lang]}</div>
        </div>
      </div>
      <dl className="sp-stats">
        {facts.map(([k, v]) => (
          <div key={k}><dd>{v}</dd><dt>{k}</dt></div>
        ))}
      </dl>
      <p className="plain">{describePlayer(feed, p, m, team?.name ?? p.team_id, lang)}</p>
    </section>
  );
}

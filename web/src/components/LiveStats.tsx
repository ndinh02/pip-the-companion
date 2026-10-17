import { useEffect, useRef, useState } from "react";
import { goalsBy, km, kmh, stat, STAT_LABEL } from "../lib/whoThat";
import type { Lang, Match, PlayerRow } from "../lib/types";

/** Four live numbers for "your player", as of the TV's minute. A number that changed since the last minute flashes,
 *  so the phone shows something happened without asking for attention. */
export default function LiveStats({ p, m, lang, match }: { p: PlayerRow; m: number; lang: Lang; match: Match }) {
  const goals = goalsBy(match, p.player_id, m);
  const items: [string, string, number][] = [
    [STAT_LABEL.distance[lang], `${km(stat(p, "distance_m", m))} km`, stat(p, "distance_m", m)],
    [STAT_LABEL.topSpeed[lang], `${kmh(stat(p, "top_speed_dmh", m))} km/h`, stat(p, "top_speed_dmh", m)],
    p.position === "GK"
      ? [STAT_LABEL.saves[lang], String(stat(p, "saves", m)), stat(p, "saves", m)]
      : [STAT_LABEL.passes[lang], `${stat(p, "passes_ok", m)}/${stat(p, "passes", m)}`, stat(p, "passes_ok", m)],
    goals > 0 ? [STAT_LABEL.goals[lang], String(goals), goals] : [STAT_LABEL.shots[lang], String(stat(p, "shots", m)), stat(p, "shots", m)],
  ];
  const prev = useRef<number[]>([]);
  const [flash, setFlash] = useState<boolean[]>([]);
  useEffect(() => {
    const vals = items.map((i) => i[2]);
    setFlash(vals.map((v, k) => prev.current.length > 0 && v !== prev.current[k]));
    prev.current = vals;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m, p.player_id]);
  return (
    <dl className="live-stats" aria-live="off">
      {items.map(([k, v], i) => (
        <div key={k} className={flash[i] ? "flash" : ""}>
          <dd key={v}>{v}</dd>
          <dt>{k}</dt>
        </div>
      ))}
      <div className="ls-min">{m}'</div>
    </dl>
  );
}

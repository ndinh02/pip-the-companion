import type { Dot } from "../lib/tracking";
import type { Team } from "../lib/types";

interface Props {
  marker?: { x: number; y: number } | null;
  /** Players and ball from tracking. Without it the pitch is empty apart from the marker. */
  dots?: Dot[] | null;
  teams?: Team[];
  /** Player on the ball in a replay. */
  ringId?: string | null;
  /** player id -> number of phones in the room following that player (anonymous count). */
  followed?: Record<string, number>;
  /** How long each move between two updates is eased over, in ms. */
  easeMs?: number;
  /** Console only: click a player, show who is selected and where they have been. */
  onPick?: (id: string) => void;
  selectedId?: string | null;
  trail?: { x: number; y: number }[];
  /** "cover" fills the screen (TV); "contain" shows the whole pitch inside its box (console). */
  fit?: "cover" | "contain";
  /** Fade everyone except this player (phone: "your player"). */
  focusId?: string | null;
}

/** 2D pitch, 105 x 68 m, origin bottom-left like the match data. */
export default function Pitch({ marker, dots, teams, ringId, followed, easeMs = 100, onPick, selectedId, trail, fit = "cover", focusId }: Props) {
  const line = { stroke: "rgba(246,243,236,.35)", strokeWidth: 0.35, fill: "none" } as const;
  const kit = (id: string) => teams?.find((t) => id.startsWith(`${t.team_id}-`))?.kit;
  const move = (d: Dot) => ({ transform: `translate(${d.x}px, ${68 - d.y}px)`, transition: `transform ${easeMs}ms linear` });
  const players = dots?.filter((d) => d.id !== "ball") ?? [];
  const ball = dots?.find((d) => d.id === "ball");
  return (
    <svg className={fit === "cover" ? "pitch" : "pitch-box"} viewBox="-2 -2 109 72" preserveAspectRatio={fit === "cover" ? "xMidYMid slice" : "xMidYMid meet"} aria-hidden="true">
      <rect x="-2" y="-2" width="109" height="72" fill="#0F2E26" />
      <rect x="0" y="0" width="105" height="68" {...line} />
      <line x1="52.5" y1="0" x2="52.5" y2="68" {...line} />
      <circle cx="52.5" cy="34" r="9.15" {...line} />
      <rect x="0" y="13.84" width="16.5" height="40.32" {...line} />
      <rect x="88.5" y="13.84" width="16.5" height="40.32" {...line} />
      <rect x="0" y="24.84" width="5.5" height="18.32" {...line} />
      <rect x="99.5" y="24.84" width="5.5" height="18.32" {...line} />
      {marker && !dots && (
        <g transform={`translate(${marker.x} ${68 - marker.y})`}>
          <circle r="2.2" fill="#FFD23F" className="marker-pulse" />
          <circle r="0.9" fill="#0E1A2B" />
        </g>
      )}
      {trail && trail.length > 1 && (
        <polyline points={trail.map((p) => `${p.x},${68 - p.y}`).join(" ")} fill="none" stroke="#FFD23F" strokeWidth="0.45" strokeLinecap="round" strokeLinejoin="round" opacity="0.8" />
      )}
      {players.map((d) => {
        const k = kit(d.id);
        const n = followed?.[d.id] ?? 0;
        return (
          <g key={d.id} style={{ ...move(d), cursor: onPick ? "pointer" : undefined }} opacity={focusId && focusId !== d.id ? 0.3 : 1} onClick={onPick ? () => onPick(d.id) : undefined}>
            {selectedId === d.id && <circle r="2.4" fill="rgba(255,210,63,.25)" stroke="#FFD23F" strokeWidth="0.3" />}
            {n > 0 && <circle r="2.1" fill="none" stroke="#FFD23F" strokeWidth="0.35" strokeDasharray="0.9 0.5" />}
            {ringId === d.id && <circle r="1.7" fill="none" stroke="#F6F3EC" strokeWidth="0.3" />}
            <circle r="1.05" fill={k?.primary ?? "#888"} stroke={k?.secondary ?? "#fff"} strokeWidth="0.22" />
            <text y="0.42" textAnchor="middle" fontSize="1.15" fontWeight="800" fill={k?.secondary ?? "#fff"}>{d.id.split("-")[1]}</text>
            {n > 1 && <text x="2.4" y="-1.6" fontSize="1.3" fontWeight="800" fill="#FFD23F">×{n}</text>}
          </g>
        );
      })}
      {ball && (
        <g style={move(ball)}>
          <circle r="0.6" fill="#F6F3EC" stroke="#0E1A2B" strokeWidth="0.15" />
        </g>
      )}
    </svg>
  );
}

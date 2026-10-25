import { useId } from "react";
import type { Team } from "../lib/types";

const SHIELD = "M50 4 L92 15 V57 C92 85 73 105 50 116 C27 105 8 85 8 57 V15 Z";

/** The two fictional clubs' crests (owner request 2026-10-25): flat shields in the team colours, no letters so they
 *  read at any size. Harbour Lights: a lighthouse throwing its beams over the waves. Copperfield: a sun rising over
 *  ploughed furrows. Not modelled on any real club (AGENTS.md rule 4). */
export default function Crest({ team, size = 40 }: { team: Pick<Team, "team_id" | "kit" | "name">; size?: number }) {
  const clip = `crest-${useId().replace(/:/g, "")}`;
  const { primary, secondary } = team.kit;
  return (
    <svg className="crest" width={size * 0.84} height={size} viewBox="0 0 100 120" role="img" aria-label={team.name}>
      <defs><clipPath id={clip}><path d={SHIELD} /></clipPath></defs>
      {team.team_id === "HAR" ? (
        <>
          <path d={SHIELD} fill={primary} />
          <g clipPath={`url(#${clip})`}>
            <polygon points="44,40 6,26 6,50" fill={secondary} opacity="0.28" />
            <polygon points="56,40 94,26 94,50" fill={secondary} opacity="0.28" />
            <polygon points="43,92 57,92 54,46 46,46" fill={secondary} />
            <rect x="45" y="62" width="10" height="7" fill={primary} />
            <rect x="44.5" y="37" width="11" height="9" rx="1.5" fill="#FFD23F" />
            <polygon points="42,37 58,37 50,29" fill={secondary} />
            <path d="M8 98 q8 -6 16 0 t16 0 t16 0 t16 0 t16 0 t16 0" stroke={secondary} strokeWidth="4" fill="none" strokeLinecap="round" />
            <path d="M8 109 q8 -6 16 0 t16 0 t16 0 t16 0 t16 0 t16 0" stroke={secondary} strokeWidth="4" fill="none" strokeLinecap="round" opacity="0.7" />
          </g>
          <path d={SHIELD} fill="none" stroke={secondary} strokeWidth="5" />
        </>
      ) : team.team_id === "COP" ? (
        <>
          <path d={SHIELD} fill={primary} />
          <g clipPath={`url(#${clip})`}>
            <path d="M30 68 A20 20 0 0 1 70 68 Z" fill={secondary} />
            {[[-1, 30], [-0.5, 22], [0, 18], [0.5, 22], [1, 30]].map(([k], i) => (
              <line key={i} x1={50 + (k as number) * 22} y1="40" x2={50 + (k as number) * 31} y2="32" stroke={secondary} strokeWidth="4" strokeLinecap="round" />
            ))}
            <rect x="0" y="70" width="100" height="50" fill={secondary} />
            {[6, 26, 50, 74, 94].map((x, i) => (
              <line key={i} x1="50" y1="72" x2={x} y2="118" stroke={primary} strokeWidth="3.2" />
            ))}
          </g>
          <path d={SHIELD} fill="none" stroke={secondary} strokeWidth="5" />
        </>
      ) : (
        <path d={SHIELD} fill={primary} stroke={secondary} strokeWidth="5" />
      )}
    </svg>
  );
}

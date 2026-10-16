import { NAME } from "../lib/brand";
import type { Pose } from "../lib/types";

/** PLACEHOLDER mascot — the owner designs the real Pip (brief §6). Five poses, must read at 120 px. */
export default function Mascot({ pose = "asks", size = 120 }: { pose?: Pose; size?: number }) {
  const eyeY = pose === "wow" ? 52 : 56;
  const eyeR = pose === "wow" ? 9 : 7;
  const wingY = pose === "wave" ? 72 : 82;
  return (
    <svg className={`pippi pippi-${pose}`} width={size} height={size} viewBox="0 0 120 120" role="img" aria-label={`${NAME}, ${pose}`}>
      <rect x="6" y="104" width="108" height="6" rx="3" fill="#F6F3EC" />
      <circle cx="60" cy="66" r="38" fill="#FFD23F" />
      <ellipse cx="30" cy={wingY} rx="9" ry="18" fill="#0E1A2B" transform={pose === "wave" ? "rotate(-35 30 82)" : undefined} />
      <ellipse cx="90" cy="82" rx="9" ry="18" fill="#0E1A2B" />
      <circle cx="46" cy={eyeY} r={eyeR + 3} fill="#fff" />
      <circle cx="74" cy={eyeY} r={eyeR + 3} fill="#fff" />
      <circle cx={pose === "thinks" ? 49 : 46} cy={pose === "thinks" ? eyeY - 3 : eyeY} r={eyeR - 2} fill="#0E1A2B" />
      <circle cx={pose === "thinks" ? 77 : 74} cy={pose === "thinks" ? eyeY - 3 : eyeY} r={eyeR - 2} fill="#0E1A2B" />
      {pose === "oops" ? <path d="M50 84 q10 -8 20 0" stroke="#0E1A2B" strokeWidth="4" fill="none" strokeLinecap="round" /> : <path d="M52 70 L68 70 L60 82 Z" fill="#F08A24" />}
    </svg>
  );
}

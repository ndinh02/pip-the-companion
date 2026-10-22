import { useId, type ReactNode } from "react";
import { NAME } from "../lib/brand";
import type { Pose } from "../lib/types";

/** Pip, drawn from the owner's character sheet: a small penguin who sincerely believes they are a bird.
 *  Black ink, white belly, yellow beak and feet. A chalk "sticker" edge keeps the black readable on navy.
 *  The five data poses (types.ts) come from match cards; the other five are screen-only matchday moments. */
export type MascotPose = Pose | "watching" | "perch" | "corner" | "var" | "sub";

const INK = "#111214";
const BELLY = "#FBFAF6";
const YEL = "#FFD23F";
const CHALK = "#F6F3EC";

/** The "Call it!" pose for a card: corners, VAR checks and substitutions get their own moment. */
export function askPose(trigger: string): MascotPose {
  if (trigger === "corner") return "corner";
  if (trigger === "var") return "var";
  if (trigger === "substitution") return "sub";
  return "asks";
}

const WINGS = {
  downL: "M37 50 C29 60 27 74 30 86 C35 79 39 69 41 59Z",
  downR: "M83 50 C91 60 93 74 90 86 C85 79 81 69 79 59Z",
  upL: "M38 54 C28 46 22 36 22 26 C30 30 37 40 42 48Z",
  upR: "M82 54 C92 46 98 36 98 26 C90 30 83 40 78 48Z",
  outL: "M37 56 C28 58 20 64 15 70 C24 70 32 68 39 64Z",
  outR: "M83 56 C92 58 100 64 105 70 C96 70 88 68 81 64Z",
  pointR: "M82 56 C92 52 101 46 108 39 C107 48 98 58 84 64Z",
  chinR: "M83 50 C88 58 86 68 78 69 C72 70 69 64 71 58 C73 54 77 56 79 58 C80 55 81 52 83 50Z",
  waveR: "M83 54 C91 46 97 36 101 28 C104 34 99 46 85 60Z",
};

type Eyes = "calm" | "happy" | "closed" | "up" | "wide";

function Face({ eyes }: { eyes: Eyes }) {
  const line = { stroke: INK, strokeWidth: 2.4, fill: "none", strokeLinecap: "round" as const };
  return (
    <>
      {eyes === "calm" && <><circle cx="57" cy="46" r="2.7" fill={INK} /><circle cx="70" cy="46" r="2.7" fill={INK} /></>}
      {eyes === "up" && <><circle cx="59" cy="44" r="2.5" fill={INK} /><circle cx="72" cy="44" r="2.5" fill={INK} /></>}
      {eyes === "wide" && (
        <>
          <circle cx="57" cy="45" r="3.4" fill={INK} /><circle cx="70" cy="45" r="3.4" fill={INK} />
          <circle cx="58.2" cy="43.8" r="1" fill={BELLY} /><circle cx="71.2" cy="43.8" r="1" fill={BELLY} />
        </>
      )}
      {eyes === "happy" && <><path d="M54 47 Q57 42.5 60 47" {...line} /><path d="M67 47 Q70 42.5 73 47" {...line} /></>}
      {eyes === "closed" && <><path d="M54 45 Q57 48.5 60 45" {...line} /><path d="M67 45 Q70 48.5 73 45" {...line} /></>}
      <path d="M59 51 Q64.5 47.5 71 51 Q65 56.5 59 51Z" fill={YEL} stroke={INK} strokeWidth="1.4" strokeLinejoin="round" />
    </>
  );
}

/** Body, wings and face, standing with feet on y≈104. */
function Penguin({ wings, eyes, wingClass }: { wings: [string, string]; eyes: Eyes; wingClass?: string }) {
  return (
    <g>
      <path d={wings[0]} fill={INK} />
      <path d="M60 22 C77 22 87 39 87 60 C87 86 79 103 60 103 C41 103 33 86 33 60 C33 39 43 22 60 22Z" fill={INK} />
      <path d="M64 31 C76 33 82 47 82 64 C82 87 75 98 62 98 C50 98 42 87 42 67 C42 47 51 31 64 31Z" fill={BELLY} />
      <path d={wings[1]} fill={INK} className={wingClass} />
      <path d="M56 23 C54 17 56 14 60 13 M61 22 C62 16 65 14 68 15" stroke={INK} strokeWidth="2.6" fill="none" strokeLinecap="round" />
      <ellipse cx="50" cy="104" rx="8" ry="3.6" fill={YEL} stroke={INK} strokeWidth="1.6" />
      <ellipse cx="70" cy="104" rx="8" ry="3.6" fill={YEL} stroke={INK} strokeWidth="1.6" />
      <Face eyes={eyes} />
    </g>
  );
}

/** Accent lines (motion, sparkle) drawn in chalk so they read on navy. */
const Lines = ({ d }: { d: string }) => <path d={d} stroke={CHALK} strokeWidth="2.4" fill="none" strokeLinecap="round" opacity="0.9" />;

function scene(pose: MascotPose): { art: ReactNode; extra?: ReactNode } {
  switch (pose) {
    case "asks":
      return { art: <Penguin wings={[WINGS.downL, WINGS.pointR]} eyes="wide" />, extra: <Lines d="M108 29 l3 -5 M113 36 l6 -1 M112 44 l5 2" /> };
    case "thinks":
      return { art: <Penguin wings={[WINGS.downL, WINGS.chinR]} eyes="up" /> };
    case "wow":
      return {
        art: <g transform="translate(0 -8)"><Penguin wings={[WINGS.upL, WINGS.upR]} eyes="happy" /></g>,
        extra: <Lines d="M46 112 L74 112 M54 106 l0 3 M60 105 l0 4 M66 106 l0 3 M14 30 l7 3 M106 30 l-7 3 M18 18 l5 5 M102 18 l-5 5" />,
      };
    case "oops":
      return { art: <Penguin wings={[WINGS.outL, WINGS.outR]} eyes="closed" />, extra: <Lines d="M10 60 q-3 5 0 10 M110 60 q3 5 0 10 M86 18 l2 -6 M93 22 l5 -4" /> };
    case "wave":
      return { art: <Penguin wings={[WINGS.downL, WINGS.waveR]} eyes="calm" wingClass="pippi-wing" />, extra: <Lines d="M106 18 Q113 22 111 30 M111 12 Q120 19 117 31" /> };
    case "watching":
      return { art: <Penguin wings={[WINGS.downL, WINGS.downR]} eyes="calm" />, extra: <Lines d="M28 110 l4 -3 M88 110 l4 -3 M94 111 l3 -2" /> };
    case "sub":
      return { art: <Penguin wings={[WINGS.upL, WINGS.upR]} eyes="wide" />, extra: <Lines d="M12 34 l8 3 M108 34 l-8 3 M16 20 l6 5 M104 20 l-6 5 M10 50 l8 0 M110 50 l-8 0" /> };
    case "perch":
      return {
        art: (
          <g>
            <path d="M14 82 L14 114 M106 82 L106 114" stroke={INK} strokeWidth="7" strokeLinecap="round" />
            <path d="M14 82 L14 114 M106 82 L106 114" stroke={BELLY} strokeWidth="3.4" strokeLinecap="round" />
            <rect x="10" y="78" width="100" height="7" rx="3.5" fill={BELLY} stroke={INK} strokeWidth="2" />
            <g transform="translate(60 78) scale(0.66) translate(-60 -108)">
              <Penguin wings={[WINGS.outL, WINGS.outR]} eyes="calm" />
            </g>
          </g>
        ),
        extra: <Lines d="M22 91 L98 91 M22 100 L98 100 M30 88 L30 112 M45 88 L45 112 M60 88 L60 112 M75 88 L75 112 M90 88 L90 112 M88 18 l4 -5 M94 24 l6 -2" />,
      };
    case "corner":
      return {
        art: (
          <g>
            <path d="M18 106 L18 34" stroke={INK} strokeWidth="5" strokeLinecap="round" />
            <path d="M18 106 L18 34" stroke={BELLY} strokeWidth="2" strokeLinecap="round" />
            <path d="M19 34 L38 41 L19 48Z" fill={YEL} stroke={INK} strokeWidth="2" strokeLinejoin="round" />
            <g transform="translate(10 0) rotate(-9 60 104)"><Penguin wings={[WINGS.outL, WINGS.downR]} eyes="wide" /></g>
          </g>
        ),
        extra: <Lines d="M104 22 l5 -5 M110 30 l6 -2" />,
      };
    case "var":
      return {
        art: (
          <g>
            <g transform="translate(-12 0)"><Penguin wings={[WINGS.downL, WINGS.downR]} eyes="calm" /></g>
            <rect x="84" y="34" width="32" height="23" rx="3" fill={BELLY} stroke={INK} strokeWidth="2.4" />
            <text x="100" y="49.5" textAnchor="middle" fontSize="10" fontWeight="900" fill={INK} fontFamily="'Be Vietnam Pro', system-ui, sans-serif">VAR</text>
            <path d="M100 57 L100 65 M93 65 L107 65" stroke={INK} strokeWidth="5" strokeLinecap="round" />
            <path d="M100 57 L100 65 M93 65 L107 65" stroke={BELLY} strokeWidth="2" strokeLinecap="round" />
          </g>
        ),
        extra: <Lines d="M24 26 l5 4 M18 38 l6 1" />,
      };
  }
}

export default function Mascot({ pose = "asks", size = 120 }: { pose?: MascotPose; size?: number }) {
  const sticker = `pip-edge-${useId().replace(/:/g, "")}`;
  const { art, extra } = scene(pose);
  return (
    <svg className={`pippi pippi-${pose}`} width={size} height={size} viewBox="0 0 120 120" role="img" aria-label={`${NAME}, ${pose}`}>
      <defs>
        {/* Grows a chalk outline around the whole drawing, like a sticker. */}
        <filter id={sticker} x="-10%" y="-10%" width="120%" height="120%">
          <feMorphology in="SourceAlpha" operator="dilate" radius="2.2" result="grown" />
          <feFlood floodColor={CHALK} />
          <feComposite in2="grown" operator="in" result="edge" />
          <feMerge><feMergeNode in="edge" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      {extra}
      <g filter={`url(#${sticker})`}>{art}</g>
    </svg>
  );
}

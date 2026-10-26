import { NAME } from "../lib/brand";
import type { Pose } from "../lib/types";

/** Pip, a small penguin who sincerely believes they are a bird (character sheet draft 02). The artwork is the owner's
 *  own drawing, one file per pose, copied 1:1 from the room prototype (docs/design-options/pip → public/pip).
 *  Never redraw or generate Pip: add a new pose as a new file from the owner. The five data poses (types.ts) come
 *  from match cards; the other five are screen-only matchday moments. */
export type MascotPose = Pose | "watching" | "perch" | "corner" | "var" | "sub";

/** The "Call it!" pose for a card: corners, VAR checks and substitutions get their own moment. */
export function askPose(trigger: string): MascotPose {
  if (trigger === "corner") return "corner";
  if (trigger === "var") return "var";
  if (trigger === "substitution") return "sub";
  return "asks";
}

// What each drawing shows, for screen readers.
const ALT: Record<MascotPose, string> = {
  asks: "asking the room", thinks: "thinking", wow: "amazed", oops: "surprised", wave: "waving", watching: "watching",
  perch: "perched like a bird", corner: "by the corner flag", var: "checking the replay", sub: "welcoming a new player",
};

/** `size` is the drawing's height in px; the width follows each drawing's own shape. */
export default function Mascot({ pose = "asks", size = 120 }: { pose?: MascotPose; size?: number }) {
  return <img className={`pip-art pip-art-${pose}`} src={`/pip/pip-${pose}.png`} alt={`${NAME}, ${ALT[pose]}`} height={size} style={{ height: size, width: "auto" }} draggable={false} />;
}

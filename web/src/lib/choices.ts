/** Each answer option gets a colour, the same on the phones and the TV, so the room can match a tile on a phone to a
 *  row on the screen at a glance. Muted brand colours from the room prototype (2026-10-23); tiles carry the words, so
 *  colour is never the only cue. Text colours keep at least 4.5:1 contrast. `shape` stays for the 3D and console views. */
export const CHOICE_STYLE = [
  { shape: "▲", bg: "#B4483E", fg: "#FFFFFF" },
  { shape: "◆", bg: "#2F6F7E", fg: "#FFFFFF" },
  { shape: "●", bg: "#C9A13B", fg: "#14202F" },
  { shape: "■", bg: "#3F7A52", fg: "#FFFFFF" },
] as const;

export const choiceStyle = (index: number) => CHOICE_STYLE[index % CHOICE_STYLE.length];

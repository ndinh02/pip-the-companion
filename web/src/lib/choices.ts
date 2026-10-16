/** Each answer option gets a colour and a shape, the same on the phones and the TV (Kahoot-style), so the room can
 *  match a tile on a phone to a row on the screen at a glance, and colour-blind viewers still have the shape.
 *  Text colours keep at least 4.5:1 contrast. */
export const CHOICE_STYLE = [
  { shape: "▲", bg: "#C8352B", fg: "#FFFFFF" },
  { shape: "◆", bg: "#157A8C", fg: "#FFFFFF" },
  { shape: "●", bg: "#F2B33D", fg: "#0E1A2B" },
  { shape: "■", bg: "#277A3E", fg: "#FFFFFF" },
] as const;

export const choiceStyle = (index: number) => CHOICE_STYLE[index % CHOICE_STYLE.length];

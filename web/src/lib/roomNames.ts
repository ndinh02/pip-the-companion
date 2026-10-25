/** Room names the host can pick from on the TV (tap to change). A fixed list, never typed: no free text reaches the
 *  phones (AGENTS.md rule 5). Club-neutral, no real places or clubs. */
export const ROOM_NAMES = [
  "The Sofa Stand", "Kitchen End", "Floodlight Club", "The Back Row", "Corner Flag Café", "Half-Time Huddle",
  "The Living Room Terrace", "Bench Warmers", "The Six-Yard Sofa", "Snack Bar United",
];

export const nextRoomName = (current: string | undefined) =>
  ROOM_NAMES[(ROOM_NAMES.indexOf(current ?? "") + 1) % ROOM_NAMES.length];

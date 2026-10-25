/** What a phone remembers about the room it joined, on this phone only (localStorage): its animal, its own calls and
 *  when it joined. Nothing here leaves the phone except the animal and answers it sends to the TV. A reload, a locked
 *  phone or a server restart keeps it; "Leave room" deletes it. */
export interface PhoneRoom {
  animal: string;
  /** Match minute when this phone joined (0 = before kick-off). Earlier calls are "before you joined". */
  joinedAt: number;
  /** card_id -> option id */
  picks: Record<string, string>;
  /** card_id -> true once the one change of mind is used */
  changed: Record<string, boolean>;
  catchupSeen: boolean;
  /** The player this phone follows in this room (null = nobody; a new room always starts with nobody). */
  followId?: string | null;
}

const key = (room: string) => `pip:phone:${room}`;
const LAST = "pip:phone-last-room";
const KEEP_MS = 6 * 60 * 60 * 1000; // a match evening

function read<T>(k: string): T | null {
  try {
    return JSON.parse(localStorage.getItem(k) ?? "null") as T | null;
  } catch {
    return null;
  }
}
function write(k: string, v: unknown) {
  try {
    localStorage.setItem(k, JSON.stringify(v));
  } catch {
    /* private mode: kept for this page only */
  }
}

export function loadPhoneRoom(room: string): PhoneRoom | null {
  const v = read<PhoneRoom & { at?: number }>(key(room));
  return v && (v.at ?? 0) > Date.now() - KEEP_MS ? v : null;
}
export function savePhoneRoom(room: string, v: PhoneRoom) {
  write(key(room), { ...v, at: Date.now() });
  write(LAST, { room, at: Date.now() });
}
export function forgetPhoneRoom(room: string) {
  try {
    localStorage.removeItem(key(room));
  } catch {
    /* ignore */
  }
}
/** The room this phone was in recently, for "Rejoin" on the start screen. */
export function lastPhoneRoom(): string | null {
  const v = read<{ room: string; at: number }>(LAST);
  return v && v.at > Date.now() - KEEP_MS && loadPhoneRoom(v.room) ? v.room : null;
}

/** Links opened from WhatsApp, Instagram, Facebook and similar open in a small in-app browser. */
export const inAppBrowser = () => /FBAN|FBAV|Instagram|WhatsApp|Line\/|; wv\)|Snapchat|TikTok/i.test(navigator.userAgent);

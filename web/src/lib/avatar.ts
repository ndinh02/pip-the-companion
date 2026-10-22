import type { Lang } from "./types";

/** Every phone in a room is an animal: no names, accounts or typing (AGENTS.md rules 5 and 6). A phone gets one from
 *  its random device id and may pick another that nobody in the room has yet. No penguin: Pip is the penguin.
 *  The server accepts only these (web/server/rooms.mjs keeps the same list). DE/VI are drafts until the owner checks them. */
export const AVATAR_NAME: Record<string, Record<Lang, string>> = {
  "🦊": { en: "Fox", de: "Fuchs", vi: "Cáo" },
  "🐼": { en: "Panda", de: "Panda", vi: "Gấu trúc" },
  "🐨": { en: "Koala", de: "Koala", vi: "Gấu koala" },
  "🐯": { en: "Tiger", de: "Tiger", vi: "Hổ" },
  "🐸": { en: "Frog", de: "Frosch", vi: "Ếch" },
  "🐵": { en: "Monkey", de: "Affe", vi: "Khỉ" },
  "🐰": { en: "Rabbit", de: "Hase", vi: "Thỏ" },
  "🦁": { en: "Lion", de: "Löwe", vi: "Sư tử" },
  "🐮": { en: "Cow", de: "Kuh", vi: "Bò" },
  "🐷": { en: "Pig", de: "Schwein", vi: "Heo" },
  "🐙": { en: "Octopus", de: "Oktopus", vi: "Bạch tuộc" },
  "🦉": { en: "Owl", de: "Eule", vi: "Cú" },
  "🐢": { en: "Turtle", de: "Schildkröte", vi: "Rùa" },
  "🦄": { en: "Unicorn", de: "Einhorn", vi: "Kỳ lân" },
  "🐳": { en: "Whale", de: "Wal", vi: "Cá voi" },
  "🦔": { en: "Hedgehog", de: "Igel", vi: "Nhím" },
};
export const AVATARS = Object.keys(AVATAR_NAME);

export function avatarOf(device: string): string {
  let h = 2166136261;
  for (let i = 0; i < device.length; i++) h = Math.imul(h ^ device.charCodeAt(i), 16777619);
  return AVATARS[(h >>> 0) % AVATARS.length];
}

export const animalName = (a: string, lang: Lang) => AVATAR_NAME[a]?.[lang] ?? a;

/** The next animal after `from` that nobody else in the room has (or `from` itself if all are taken). */
export function nextFreeAnimal(from: string, taken: string[]): string {
  const i = AVATARS.indexOf(from);
  for (let k = 1; k <= AVATARS.length; k++) {
    const a = AVATARS[(i + k) % AVATARS.length];
    if (!taken.includes(a)) return a;
  }
  return from;
}

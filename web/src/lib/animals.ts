import type { Lang } from "./types";

/** Every player is a small, cute animal (owner's choice 2026-10-16). One animal per player for the whole match,
 *  mixed through both teams; the shirt colour shows the team. Club-neutral and no human likeness (AGENTS.md rule 4). */
export type Animal = "penguin" | "bear" | "dog" | "rabbit" | "fox" | "tiger" | "elephant";
export const ANIMALS: Animal[] = ["penguin", "bear", "dog", "rabbit", "fox", "tiger", "elephant"];

export function animalOf(playerId: string): Animal {
  const [team, num] = playerId.split("-");
  const n = Number(num);
  const offset = team === "HAR" ? 0 : 4; // the two teams start the cycle at different animals
  return ANIMALS[(n * 3 + offset) % ANIMALS.length];
}

// DE/VI are drafts until the owner checks them.
export const ANIMAL_LABEL: Record<Animal, Record<Lang, string> & { emoji: string }> = {
  penguin: { en: "Penguin", de: "Pinguin", vi: "Chim cánh cụt", emoji: "🐧" },
  bear: { en: "Bear", de: "Bär", vi: "Gấu", emoji: "🐻" },
  dog: { en: "Dog", de: "Hund", vi: "Chó", emoji: "🐶" },
  rabbit: { en: "Rabbit", de: "Hase", vi: "Thỏ", emoji: "🐰" },
  fox: { en: "Fox", de: "Fuchs", vi: "Cáo", emoji: "🦊" },
  tiger: { en: "Tiger", de: "Tiger", vi: "Hổ", emoji: "🐯" },
  elephant: { en: "Elephant", de: "Elefant", vi: "Voi", emoji: "🐘" },
};

/** Goalkeepers wear their own colour: different from both teams and from each other. */
export const KEEPER_KIT: Record<string, { primary: string; secondary: string }> = {
  HAR: { primary: "#3FAE5A", secondary: "#0E1A2B" },
  COP: { primary: "#7B4FC9", secondary: "#FFFFFF" },
};

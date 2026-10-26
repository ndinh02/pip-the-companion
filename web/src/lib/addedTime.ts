import type { Lang } from "./types";

// DE/VI are drafts until the owner checks them.
export const STOP_LABEL: Record<string, Record<Lang, string>> = {
  goal: { en: "Goals", de: "Tore", vi: "Bàn thắng" },
  sub: { en: "Substitutions", de: "Wechsel", vi: "Thay người" },
  injury: { en: "Injuries", de: "Verletzungen", vi: "Chấn thương" },
  VAR: { en: "VAR checks", de: "VAR-Checks", vi: "Kiểm tra VAR" },
  card: { en: "Cards", de: "Karten", vi: "Thẻ phạt" },
  other: { en: "Other", de: "Sonstiges", vi: "Khác" },
};

export function stopLabel(type: string, lang: Lang): string {
  return (STOP_LABEL[type] ?? STOP_LABEL.other)[lang];
}

/** "3 minutes added" — the number comes from the board data, never from copy. */
export function addedHeadline(minutes: number, lang: Lang): string {
  if (lang === "de") return `${minutes} ${minutes === 1 ? "Minute" : "Minuten"} Nachspielzeit`;
  if (lang === "vi") return `Bù giờ ${minutes} phút`;
  return `${minutes} ${minutes === 1 ? "minute" : "minutes"} added`;
}

/** 95 -> "1:35" */
export function fmtDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

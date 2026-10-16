import type { Card, HalfRow, HalfSummary, I18n, Lang, Match } from "./types";
import { t } from "./match";

/** First half = every card at or before this minute. */
export const HALF_MIN = 45;

// DE/VI are drafts until the owner checks them. No digits, no betting words.
export const GLOSSARY: Record<string, { term: I18n; meaning: I18n }> = {
  corner: {
    term: { en: "Corner kick", de: "Eckstoß", vi: "Phạt góc" },
    meaning: {
      en: "When a defender sends the ball out over their own goal line, the attackers restart from the corner of the pitch.",
      de: "Schlägt ein Verteidiger den Ball über die eigene Torlinie ins Aus, startet der Angriff von der Ecke des Spielfelds neu.",
      vi: "Khi hậu vệ đưa bóng ra ngoài đường biên ngang của chính mình, đội tấn công được đá bóng từ góc sân.",
    },
  },
  free_kick: {
    term: { en: "Free kick", de: "Freistoß", vi: "Đá phạt" },
    meaning: {
      en: "After a foul, the fouled team restarts play from the spot where it happened, and the defenders must stand back.",
      de: "Nach einem Foul setzt die gefoulte Mannschaft das Spiel an der Stelle des Fouls fort, und die Verteidiger müssen Abstand halten.",
      vi: "Sau một pha phạm lỗi, đội bị phạm lỗi đá bóng tại chỗ xảy ra lỗi, còn hậu vệ phải lùi ra xa.",
    },
  },
  var: {
    term: { en: "VAR", de: "VAR", vi: "VAR" },
    meaning: {
      en: "The video referee checks key decisions on replay, but only to fix clear mistakes.",
      de: "Der Video-Schiedsrichter prüft wichtige Entscheidungen per Wiederholung, greift aber nur bei klaren Fehlern ein.",
      vi: "Trọng tài video xem lại các quyết định quan trọng, nhưng chỉ can thiệp khi có sai sót rõ ràng.",
    },
  },
  substitution: {
    term: { en: "Substitution", de: "Einwechslung", vi: "Thay người" },
    meaning: {
      en: "A coach swaps a tired or tactically unsuited player for a fresh one from the bench.",
      de: "Der Trainer ersetzt einen müden oder taktisch ungeeigneten Spieler durch einen frischen von der Bank.",
      vi: "Huấn luyện viên đổi một cầu thủ mệt hoặc không còn phù hợp chiến thuật bằng người mới từ ghế dự bị.",
    },
  },
};

export const TRIGGER_LABEL: Record<string, I18n> = {
  corner: { en: "Corner", de: "Ecke", vi: "Phạt góc" },
  free_kick: { en: "Free kick", de: "Freistoß", vi: "Đá phạt" },
  var: { en: "VAR", de: "VAR", vi: "VAR" },
  substitution: { en: "Substitution", de: "Wechsel", vi: "Thay người" },
};

export function triggerLabel(trigger: string, lang: Lang): string {
  return (TRIGGER_LABEL[trigger] ?? { en: trigger, de: trigger, vi: trigger })[lang];
}

export function firstHalfCards(match: Match): Card[] {
  return match.cards.filter((c) => c.t_in_min <= HALF_MIN);
}

/** Room calls for every first-half question. `answers` is card_id -> device -> option, kept by the TV. */
export function buildHalf(match: Match, answers: Map<string, Map<string, string>>, score: { HAR: number; COP: number }): HalfSummary {
  const rows: HalfRow[] = firstHalfCards(match).map((c) => {
    const tally: Record<string, number> = {};
    answers.get(c.card_id)?.forEach((opt) => (tally[opt] = (tally[opt] ?? 0) + 1));
    return { card_id: c.card_id, tally, answered: Object.values(tally).reduce((a, b) => a + b, 0) };
  });
  return { score, rows };
}

/** The option most of the room picked, "split" on a tie, null if nobody answered. */
export function roomCall(row: HalfRow): string | "split" | null {
  const entries = Object.entries(row.tally);
  if (!entries.length) return null;
  const top = Math.max(...entries.map(([, n]) => n));
  const leaders = entries.filter(([, n]) => n === top);
  return leaders.length === 1 ? leaders[0][0] : "split";
}

/** Word of the match: the term behind the question the room agreed on least; the first question if nobody answered. */
export function wordOfMatch(match: Match, half: HalfSummary): { term: I18n; meaning: I18n } | null {
  let best: { trigger: string; agreement: number } | null = null;
  for (const row of half.rows) {
    const card = match.cards.find((c) => c.card_id === row.card_id);
    if (!card || !GLOSSARY[card.trigger]) continue;
    const agreement = row.answered >= 2 ? Math.max(...Object.values(row.tally)) / row.answered : 1;
    if (!best || agreement < best.agreement) best = { trigger: card.trigger, agreement };
  }
  return best ? GLOSSARY[best.trigger] : null;
}

/** Plain text for the share sheet. Only counts and team names — nothing about individual people. */
export function shareText(
  match: Match, half: HalfSummary, lang: Lang, labels: { title: string; room: string; match: string; split: string; word: string },
): string {
  const [home, away] = match.teams;
  const lines = [`${labels.title} · ${home.short_name} ${half.score.HAR}–${half.score.COP} ${away.short_name}`];
  for (const row of half.rows) {
    const card = match.cards.find((c) => c.card_id === row.card_id);
    if (!card) continue;
    const call = roomCall(row);
    const callText = call === "split" ? labels.split : call ? t(card.question.options.find((o) => o.id === call)?.label ?? card.question.text, lang) : "–";
    const answer = t(card.question.options.find((o) => o.id === card.reveal.answer)?.label ?? card.question.text, lang);
    lines.push(`${Math.floor(card.t_in_min)}' ${triggerLabel(card.trigger, lang)}: ${labels.room} ${callText} · ${labels.match} ${answer}`);
  }
  const word = wordOfMatch(match, half);
  if (word) lines.push(`${labels.word}: ${t(word.term, lang)}`);
  lines.push(location.origin);
  return lines.join("\n");
}

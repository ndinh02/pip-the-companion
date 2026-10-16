import { answerLabel, t } from "../lib/match";
import { ui } from "../lib/i18n";
import { roomCall, triggerLabel, wordOfMatch } from "../lib/halfTime";
import type { HalfSummary, Lang, Match } from "../lib/types";

/** Half-time card: what the room called, what the match said, what Pip called, plus the word of the match.
 *  No points, no ranking, no ticks: being wrong is normal (AGENTS.md rule 3 and 8). */
export default function HalfTimeCard({ match, half, lang, mine, followLine }: { match: Match; half: HalfSummary; lang: Lang; mine?: Record<string, string>; followLine?: string }) {
  const word = wordOfMatch(match, half);
  return (
    <div className="half-card">
      <ul className="half-rows" aria-label={ui("halfCalls", lang)}>
        {half.rows.map((row) => {
          const card = match.cards.find((c) => c.card_id === row.card_id);
          if (!card) return null;
          const call = roomCall(row);
          const room = call === "split" ? ui("halfSplit", lang) : call ? answerLabel(card, call, lang) : ui("halfNoCalls", lang);
          const you = mine?.[row.card_id];
          return (
            <li key={row.card_id}>
              <strong>{Math.floor(card.t_in_min)}' {triggerLabel(card.trigger, lang)}</strong>
              <span>
                {ui("halfRoom", lang)}: <b>{room}</b>
                {you ? <> · {ui("you", lang)}: <b>{answerLabel(card, you, lang)}</b></> : null}
              </span>
              <span>
                {ui("halfMatch", lang)}: <b className="turf">{answerLabel(card, card.reveal.answer, lang)}</b> · {ui("pippiCalled", lang)}: <b>{answerLabel(card, card.question.pippi_call, lang)}</b>
              </span>
            </li>
          );
        })}
      </ul>
      {followLine && (
        <div className="word">
          <div className="eyebrow">★ {ui("yourPlayer", lang)}</div>
          <p>{followLine}</p>
        </div>
      )}
      {word && (
        <div className="word">
          <div className="eyebrow">{ui("wordOfMatch", lang)}</div>
          <strong>{t(word.term, lang)}</strong>
          <p>{t(word.meaning, lang)}</p>
        </div>
      )}
    </div>
  );
}

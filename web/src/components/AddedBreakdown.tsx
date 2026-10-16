import { fmtDuration, stopLabel } from "../lib/addedTime";
import { ui } from "../lib/i18n";
import type { AddedBoard, Lang } from "../lib/types";

/** Where the added time came from: one row per kind of stoppage, bar length = time lost. */
export default function AddedBreakdown({ board, lang }: { board: AddedBoard; lang: Lang }) {
  const longest = Math.max(1, ...board.items.map((i) => i.seconds));
  return (
    <div className="added-breakdown">
      <ul>
        {board.items.map((i) => (
          <li key={i.type}>
            <span className="what">{stopLabel(i.type, lang)} <span className="dim">× {i.count}</span></span>
            <span className="track" aria-hidden="true"><i style={{ width: `${(i.seconds / longest) * 100}%` }} /></span>
            <span className="time">{fmtDuration(i.seconds)}</span>
          </li>
        ))}
      </ul>
      <p className="total">
        {ui("addedLost", lang)}: <strong>{fmtDuration(board.actual_s)}</strong> · {ui("addedRounding", lang)}
      </p>
    </div>
  );
}

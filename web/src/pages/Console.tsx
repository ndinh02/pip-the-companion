import { useEffect, useState } from "react";
import { fmtDuration, stopLabel } from "../lib/addedTime";
import TrackingPanel from "../components/TrackingPanel";
import WorkflowTrace from "../components/WorkflowTrace";
import { fill, loadAddedTime, loadMatch, loadPlayers } from "../lib/match";
import { loadTracking, type Tracking } from "../lib/tracking";
import type { AddedTime, Match, PlayersFeed } from "../lib/types";

/** Operator console — STUB. Will show agent decisions, held-back moments and "Catch me lying" (brief §5.4). */
export default function Console() {
  const [match, setMatch] = useState<Match | null>(null);
  const [added, setAdded] = useState<AddedTime | null>(null);
  const [tracking, setTracking] = useState<Tracking | null>(null);
  const [players, setPlayers] = useState<PlayersFeed | null>(null);
  useEffect(() => {
    loadMatch()
      .then((m) => {
        setMatch(m);
        loadTracking(m).then(setTracking);
        loadPlayers(m).then(setPlayers);
        return loadAddedTime(m).then(setAdded);
      })
      .catch(() => undefined);
  }, []);
  if (!match) return <div className="center">…</div>;
  return (
    <div className="console">
      <h1>Console</h1>
      <p className="dim">Operator view: tracking, the content workflow with its checker, the questions in the match file, added time and held-back moments.</p>
      {tracking && (
        <>
          <h2>Tracking <span className="dim">(synthetic, 5 Hz)</span></h2>
          <TrackingPanel match={match} tracking={tracking} players={players} />
          <h2>Questions</h2>
        </>
      )}
      <table>
        <thead><tr><th>Min</th><th>Trigger</th><th>Question (EN)</th><th>Facts used</th><th>Expert line (EN, filled by code)</th></tr></thead>
        <tbody>
          {match.cards.map((c) => (
            <tr key={c.card_id}>
              <td>{c.t_in_min}'</td>
              <td>{c.trigger}</td>
              <td>{c.question.text.en}</td>
              <td className="mono">{c.reveal.fact_ids.join(", ")}</td>
              <td>{fill(c.reveal.expert.en, match.facts)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <WorkflowTrace matchId={match.match_id} />
      {added && (
        <>
          <h2>Added time <span className="dim">(from stoppages)</span></h2>
          <table>
            <thead><tr><th>Half</th><th>Board</th><th>Counted</th><th>Breakdown</th></tr></thead>
            <tbody>
              {added.boards.map((b) => (
                <tr key={b.period}>
                  <td>{b.period} ({b.at_min}')</td>
                  <td>{b.announced_min} min</td>
                  <td>{fmtDuration(b.actual_s)}</td>
                  <td>{b.items.map((i) => `${stopLabel(i.type, "en")} × ${i.count} = ${fmtDuration(i.seconds)}`).join(" · ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {match.moments_held && (
        <>
          <h2>Held back <span className="dim">({match.moments_held.length})</span></h2>
          <p className="dim">Moments the reader found but did not ask about, and why (brief §5.2 timing policy).</p>
          <table>
            <thead><tr><th>Min</th><th>Trigger</th><th>Team</th><th>Reason</th></tr></thead>
            <tbody>
              {match.moments_held.map((h, i) => (
                <tr key={i}>
                  <td>{h.t_in_min}'</td>
                  <td>{h.trigger}</td>
                  <td>{h.team_id}</td>
                  <td className="mono">{h.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

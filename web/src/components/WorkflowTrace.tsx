import { useEffect, useState } from "react";

interface Attempt { attempt: number; writer: string; note: string; expert_en: string; plain_en: string; facts: Record<string, number>; checker: "pass" | "fail"; errors: string[] }
interface Entry {
  card_id: string; trigger: string; t_in_min: number; team_id: string; question_en: string;
  facts_from_events: Record<string, number>; tool_calls: { tool: string }[]; attempts: Attempt[];
  approved_by: string; approved_expert_en: string; approved_plain_en: string;
}
interface Trace {
  match_id: string; workflow_version: string; writer: string; uses_ai: boolean; max_retries: number;
  cards: Entry[]; shipped_equals_checked: boolean;
  catch_me_lying: { what: string; cards: Entry[]; shipped_equals_checked: boolean };
}

/** Operator view of the content workflow that ran BEFORE the match: facts in, drafts, checker verdicts, what was approved.
 *  "Catch me lying" replays a recorded run with two sabotaged writers. Nothing here runs live. */
export default function WorkflowTrace({ matchId }: { matchId: string }) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [lying, setLying] = useState(false);
  useEffect(() => {
    fetch("/data/agent-trace.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((d: Trace | null) => setTrace(d && d.match_id === matchId ? d : null))
      .catch(() => setTrace(null));
  }, [matchId]);
  if (!trace) return null;
  const sabotaged = new Map(trace.catch_me_lying.cards.map((c) => [c.card_id, c]));
  const rows = trace.cards.map((c) => (lying ? sabotaged.get(c.card_id) ?? c : c));
  return (
    <>
      <h2>Content workflow <span className="dim">(ran before the match)</span></h2>
      <p className="dim">
        Facts from code → writer → checker → up to {trace.max_retries} retries → fixed template. Writer for this match: <b>{trace.writer}</b>
        {trace.uses_ai ? "" : " — no AI model is connected yet; an LLM writer plugs into the same checker."}
      </p>
      <label className="lying-switch">
        <input type="checkbox" checked={lying} onChange={(e) => setLying(e.target.checked)} />
        <span><b>Catch me lying</b> — replay the run with two writers sabotaged on purpose</span>
      </label>
      {lying && <p className="dim">{trace.catch_me_lying.what}</p>}
      <table className="trace">
        <thead><tr><th>Card</th><th>Facts from the match events</th><th>Drafts and checker</th><th>Approved for viewers</th></tr></thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.card_id} className={c.attempts.some((a) => a.checker === "fail") ? "had-fail" : ""}>
              <td><b>{c.card_id}</b><br /><span className="dim">{c.t_in_min}' · {c.team_id}</span></td>
              <td className="mono small">
                {Object.entries(c.facts_from_events).map(([k, v]) => <div key={k}>{k} = {v}</div>)}
                {Object.keys(c.facts_from_events).length === 0 && <span className="dim">none needed</span>}
              </td>
              <td>
                {c.attempts.map((a) => (
                  <div key={a.attempt} className={`attempt ${a.checker}`}>
                    <b>{a.checker === "pass" ? "✓ pass" : "✗ rejected"}</b> · draft {a.attempt} · {a.writer}
                    {a.checker === "fail" && (
                      <>
                        <div className="small">“{a.expert_en}”</div>
                        <ul className="small">{a.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
                      </>
                    )}
                  </div>
                ))}
              </td>
              <td>
                {c.approved_expert_en}
                <div className="dim small">by {c.approved_by}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={trace.shipped_equals_checked && trace.catch_me_lying.shipped_equals_checked ? "turf-text" : "warn-text"}>
        {trace.shipped_equals_checked && trace.catch_me_lying.shipped_equals_checked
          ? "✓ The cards in the match file are exactly the checker-approved ones, in both runs."
          : "✗ The match file differs from the approved cards."}
      </p>
    </>
  );
}

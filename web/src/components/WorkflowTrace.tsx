import { useEffect, useState } from "react";

/* Operator view of the content workflow that ran BEFORE the match. Three recorded runs can be compared:
 * the shipped templates, a single Foundry Local model, and a multi-agent run (writer, fact checker, editor,
 * translator) on Foundry Local. Nothing here runs live: every run is a JSON file made before the match.
 * The trace files are produced by Python and may gain or lose fields, so everything below is read defensively. */

type Facts = Record<string, number | string>;

interface Attempt { attempt: number; writer: string; note: string; expert_en: string; plain_en: string; facts: Facts; checker: string; errors: string[] }
interface Step {
  n: number; agent: string; action: string; to: string | null; verdict: string; notes: string[];
  text: Record<string, string> | null; ms: number | null; via_mcp: boolean;
}
interface Translation { plain: string; expert: string; status: string }
interface Entry {
  card_id: string; trigger: string; t_in_min: number | null; team_id: string; question_en: string; decision: string;
  facts_from_events: Facts; approved_facts: Facts; attempts: Attempt[]; steps: Step[];
  approved_by: string; approved_expert_en: string; approved_plain_en: string;
  translations: Record<string, Translation>;
}
interface Agent { id: string; name: string; kind: string; model: string | null; role: string }
interface Trace {
  match_id: string; workflow_version: string; writer: string; model: string; uses_ai: boolean; max_retries: number | null;
  seconds: number | null; cards: Entry[]; held: number; shipped_equals_checked: boolean | null;
  agents: Agent[]; mcp: { server: string; tools: string[]; calls: number | null } | null;
  catch_me_lying: { what: string; cards: Entry[]; shipped_equals_checked: boolean } | null;
}

type RunId = "templates" | "llm" | "multi";
const RUNS: { id: RunId; label: string; url: string }[] = [
  { id: "templates", label: "Templates (shipped)", url: "/data/agent-trace.json" },
  { id: "llm", label: "Foundry Local (qwen2.5-7b)", url: "/data/agent-trace-llm.json" },
  { id: "multi", label: "Multi-agent (Foundry Local)", url: "/data/agent-trace-multi.json" },
];
type Load = "loading" | "missing" | Trace;

// ---------- defensive readers ----------
type Obj = Record<string, unknown>;
const obj = (v: unknown): Obj => (v && typeof v === "object" && !Array.isArray(v) ? (v as Obj) : {});
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const str = (v: unknown, d = ""): string => (typeof v === "string" ? v : typeof v === "number" ? String(v) : d);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const facts = (v: unknown): Facts => {
  const out: Facts = {};
  for (const [k, x] of Object.entries(obj(v))) if (typeof x === "number" || typeof x === "string") out[k] = x;
  return out;
};

function readAttempt(v: unknown, i: number): Attempt {
  const a = obj(v);
  return {
    attempt: num(a.attempt) ?? i + 1, writer: str(a.writer), note: str(a.note), expert_en: str(a.expert_en),
    plain_en: str(a.plain_en), facts: facts(a.facts), checker: str(a.checker, "fail"), errors: arr(a.errors).map((e) => str(e)),
  };
}
function readStep(v: unknown, i: number): Step {
  const s = obj(v);
  const text = s.text && typeof s.text === "object" ? (Object.fromEntries(Object.entries(obj(s.text)).filter(([, x]) => typeof x === "string")) as Record<string, string>) : null;
  return {
    n: num(s.n) ?? i + 1, agent: str(s.agent, "?"), action: str(s.action, "step"), to: typeof s.to === "string" ? s.to : null,
    verdict: str(s.verdict, "info"), notes: arr(s.notes).map((x) => str(x)).filter(Boolean),
    text: text && Object.keys(text).length ? text : null, ms: num(s.ms), via_mcp: s.via_mcp === true,
  };
}
function readEntry(v: unknown): Entry {
  const c = obj(v);
  const translations: Record<string, Translation> = {};
  for (const [lang, t] of Object.entries(obj(c.translations))) {
    const o = obj(t);
    translations[lang] = { plain: str(o.plain), expert: str(o.expert), status: str(o.status, "unknown") };
  }
  return {
    card_id: str(c.card_id, "?"), trigger: str(c.trigger), t_in_min: num(c.t_in_min), team_id: str(c.team_id),
    question_en: str(c.question_en), decision: str(c.decision), facts_from_events: facts(c.facts_from_events),
    approved_facts: facts(c.approved_facts), attempts: arr(c.attempts).map(readAttempt), steps: arr(c.steps).map(readStep),
    approved_by: str(c.approved_by), approved_expert_en: str(c.approved_expert_en), approved_plain_en: str(c.approved_plain_en),
    translations,
  };
}
function readTrace(v: unknown): Trace | null {
  const d = obj(v);
  if (!Array.isArray(d.cards)) return null;
  const writer = str(d.writer, "unknown");
  const mcp = d.mcp && typeof d.mcp === "object" ? obj(d.mcp) : null;
  const lying = d.catch_me_lying && typeof d.catch_me_lying === "object" ? obj(d.catch_me_lying) : null;
  return {
    match_id: str(d.match_id), workflow_version: str(d.workflow_version), writer,
    model: str(d.model) || (writer.startsWith("llm:") ? writer.slice(4) : writer === "template" ? "none (templates)" : writer),
    uses_ai: d.uses_ai === true, max_retries: num(d.max_retries), seconds: num(d.seconds),
    cards: d.cards.map(readEntry), held: arr(d.held).length,
    shipped_equals_checked: typeof d.shipped_equals_checked === "boolean" ? d.shipped_equals_checked : null,
    agents: arr(d.agents).map((a) => {
      const o = obj(a);
      return { id: str(o.id, "?"), name: str(o.name) || str(o.id, "?"), kind: str(o.kind), model: typeof o.model === "string" ? o.model : null, role: str(o.role) };
    }),
    mcp: mcp ? { server: str(mcp.server), tools: arr(mcp.tools).map((x) => str(x)), calls: num(mcp.calls) } : null,
    catch_me_lying: lying && Array.isArray(lying.cards)
      ? { what: str(lying.what), cards: lying.cards.map(readEntry), shipped_equals_checked: lying.shipped_equals_checked === true }
      : null,
  };
}

async function fetchTrace(url: string): Promise<Trace | "missing"> {
  try {
    const r = await fetch(url);
    if (!r.ok) return "missing";
    // the dev server answers unknown paths with the app shell; that is "missing" too
    if (!(r.headers.get("content-type") ?? "").includes("json")) return "missing";
    return readTrace(await r.json()) ?? "missing";
  } catch {
    return "missing";
  }
}

// ---------- helpers for display ----------
/** Fills {placeholders} from the facts the code supplied. Unknown placeholders stay visible, so a bad draft shows its mistake. */
function fillFacts(text: string, f: Facts): string {
  return text.replace(/\{([a-z0-9_]+)\}/g, (m, id: string) => (id in f ? String(f[id]) : m));
}
function cardFacts(c: Entry): Facts {
  const f: Facts = { ...c.facts_from_events };
  for (const a of c.attempts) Object.assign(f, a.facts);
  return Object.assign(f, c.approved_facts);
}
const short = (s: string, n = 160) => (s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s);
const isFallback = (c: Entry, t: Trace) =>
  t.uses_ai && (c.approved_by === "template" || c.approved_by.includes("fallback") || c.steps.some((s) => s.action === "fallback"));
function firstTry(c: Entry): boolean {
  if (c.attempts.length) return c.attempts[0].checker === "pass";
  return !c.steps.some((s) => s.action === "retry" || s.action === "fallback" || s.action === "recover");
}
function retries(c: Entry): number {
  if (c.attempts.length) return Math.max(0, c.attempts.length - 1);
  return c.steps.filter((s) => s.action === "retry").length;
}
function verdictLabel(v: string): string {
  return v === "pass" ? "✓ pass" : v === "fail" ? "✗ fail" : "• info";
}

// ---------- component ----------
export default function WorkflowTrace({ matchId }: { matchId: string }) {
  const [run, setRun] = useState<RunId>("templates");
  const [loads, setLoads] = useState<Partial<Record<RunId, Load>>>({});
  const [lying, setLying] = useState(false);

  useEffect(() => {
    if (loads[run]) return;
    setLoads((l) => ({ ...l, [run]: "loading" }));
    const url = RUNS.find((r) => r.id === run)!.url;
    fetchTrace(url).then((t) => setLoads((l) => ({ ...l, [run]: t })));
  }, [run, loads]);

  const state = loads[run] ?? "loading";
  const trace = typeof state === "object" ? state : null;

  return (
    <>
      <h2>Content workflow <span className="dim">(ran before the match)</span></h2>
      <div className="run-switch" role="group" aria-label="Choose a recorded run">
        {RUNS.map((r) => (
          <button key={r.id} type="button" aria-pressed={run === r.id} onClick={() => setRun(r.id)}>
            {r.label}
          </button>
        ))}
      </div>
      <p className="run-note">
        The shipped match uses the reviewed templates. The AI runs were made before the match on a laptop with Foundry Local;
        AI never runs during the match.
      </p>
      {state === "loading" && <p className="dim">Loading…</p>}
      {state === "missing" && (
        <p className="run-missing">This run is not available in this build.</p>
      )}
      {trace && (
        <>
          <RunSummary trace={trace} />
          {trace.match_id && trace.match_id !== matchId && (
            <p className="dim small">This run was made for match “{trace.match_id}”, not the one playing now.</p>
          )}
          {run === "multi" || trace.agents.length || trace.cards.some((c) => c.steps.length) ? (
            <MultiRun trace={trace} />
          ) : (
            <TableRun trace={trace} lying={run === "templates" && lying} setLying={run === "templates" ? setLying : null} />
          )}
          <ShippedNote trace={trace} lying={run === "templates" && lying} />
        </>
      )}
    </>
  );
}

function RunSummary({ trace }: { trace: Trace }) {
  const cards = trace.cards.length;
  const first = trace.cards.filter(firstTry).length;
  const retried = trace.cards.reduce((n, c) => n + retries(c), 0);
  const fallbacks = trace.cards.filter((c) => isFallback(c, trace)).length;
  const items: [string, string][] = [
    ["Model", trace.model],
    ["Cards", String(cards)],
    ["Approved first try", `${first} of ${cards}`],
    ["Retries", String(retried)],
    ["Fallbacks to template", String(fallbacks)],
  ];
  if (trace.seconds !== null) items.push(["Time", `${trace.seconds.toFixed(1)} s`]);
  if (trace.mcp?.calls != null) items.push(["MCP tool calls", String(trace.mcp.calls)]);
  return (
    <dl className="run-summary">
      {items.map(([k, v]) => (
        <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
      ))}
    </dl>
  );
}

function ShippedNote({ trace, lying }: { trace: Trace; lying: boolean }) {
  if (!trace.uses_ai) {
    const ok = trace.shipped_equals_checked === true && (!lying || trace.catch_me_lying?.shipped_equals_checked === true);
    return (
      <p className={ok ? "turf-text" : "warn-text"}>
        {ok ? "✓ The cards in the match file are exactly the checker-approved ones." : "✗ The match file differs from the approved cards."}
      </p>
    );
  }
  return (
    <p className="dim">
      This AI run is a recorded trial. Its approved lines passed the same checker, but the match you see plays the reviewed templates.
    </p>
  );
}

/** Templates and the single-model run: one row per card, drafts with checker errors. */
function TableRun({ trace, lying, setLying }: { trace: Trace; lying: boolean; setLying: ((v: boolean) => void) | null }) {
  const sabotaged = new Map((trace.catch_me_lying?.cards ?? []).map((c) => [c.card_id, c]));
  const rows = trace.cards.map((c) => (lying ? sabotaged.get(c.card_id) ?? c : c));
  return (
    <>
      <p className="dim">
        Facts from code → writer → checker → up to {trace.max_retries ?? "?"} retries → fixed template. Writer: <b>{trace.writer}</b>
      </p>
      {setLying && trace.catch_me_lying && (
        <>
          <label className="lying-switch">
            <input type="checkbox" checked={lying} onChange={(e) => setLying(e.target.checked)} />
            <span><b>Catch me lying</b> — replay the run with two writers sabotaged on purpose</span>
          </label>
          {lying && <p className="dim">{trace.catch_me_lying.what}</p>}
        </>
      )}
      <table className="trace">
        <thead><tr><th>Card</th><th>Facts from the match events</th><th>Drafts and checker</th><th>Approved for viewers</th></tr></thead>
        <tbody>
          {rows.map((c) => {
            const f = cardFacts(c);
            return (
              <tr key={c.card_id} className={c.attempts.some((a) => a.checker === "fail") ? "had-fail" : ""}>
                <td><b>{c.card_id}</b><br /><span className="dim">{c.t_in_min ?? "?"}' · {c.team_id}</span></td>
                <td className="mono small">
                  {Object.entries(c.facts_from_events).map(([k, v]) => <div key={k}>{k} = {v}</div>)}
                  {Object.keys(c.facts_from_events).length === 0 && <span className="dim">none needed</span>}
                </td>
                <td><Attempts attempts={c.attempts} facts={f} showPassText={trace.uses_ai} /></td>
                <td>
                  {fillFacts(c.approved_expert_en, f)}
                  <div className="dim small">by {c.approved_by}</div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

function Attempts({ attempts, facts: f, showPassText }: { attempts: Attempt[]; facts: Facts; showPassText: boolean }) {
  if (!attempts.length) return <span className="dim small">no drafts recorded</span>;
  return (
    <>
      {attempts.map((a) => {
        const pass = a.checker === "pass";
        const ff = { ...f, ...a.facts };
        return (
          <div key={a.attempt} className={`attempt ${pass ? "pass" : "fail"}`}>
            <b>{pass ? "✓ pass" : "✗ rejected"}</b> · draft {a.attempt}{a.writer ? ` · ${a.writer}` : ""}
            {(!pass || showPassText) && (
              <>
                {a.plain_en && <div className="small">Plain: “{fillFacts(a.plain_en, ff)}”</div>}
                {a.expert_en && <div className="small">Expert: “{fillFacts(a.expert_en, ff)}”</div>}
                {a.errors.length > 0 && <ul className="small">{a.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}
              </>
            )}
          </div>
        );
      })}
    </>
  );
}

/** Multi-agent run: who does what, then per card the handoffs from agent to agent. */
function MultiRun({ trace }: { trace: Trace }) {
  const names = new Map(trace.agents.map((a) => [a.id, a.name]));
  const nameOf = (id: string | null) => (id ? names.get(id) ?? id : "");
  return (
    <>
      {trace.agents.length > 0 && (
        <>
          <h3 className="trace-h3">Agents</h3>
          <ul className="roster">
            {trace.agents.map((a) => (
              <li key={a.id}>
                <div className="roster-top">
                  <b>{a.name}</b>
                  <span className={`kind-badge ${a.kind === "llm" ? "llm" : "code"}`}>{a.kind === "llm" ? "LLM" : "Code"}</span>
                </div>
                {a.model && <div className="mono small">{a.model}</div>}
                {a.role && <div className="small dim">{a.role}</div>}
              </li>
            ))}
          </ul>
        </>
      )}
      {trace.mcp && (
        <p className="dim small">
          Facts reach the agents through the MCP server <b>{trace.mcp.server || "?"}</b>
          {trace.mcp.tools.length > 0 && <> (tools: <span className="mono">{trace.mcp.tools.join(", ")}</span>)</>}. The writer never types a number itself.
        </p>
      )}
      <h3 className="trace-h3">Cards <span className="dim">({trace.cards.length})</span></h3>
      <div className="mcards">
        {trace.cards.map((c, i) => (
          <MultiCard key={c.card_id + i} card={c} trace={trace} nameOf={nameOf} open={i === 0} />
        ))}
      </div>
      {trace.held > 0 && <p className="dim small">{trace.held} moments were held back and not written up.</p>}
    </>
  );
}

function MultiCard({ card: c, trace, nameOf, open }: { card: Entry; trace: Trace; nameOf: (id: string | null) => string; open: boolean }) {
  const f = cardFacts(c);
  const fell = isFallback(c, trace);
  const hadFail = c.steps.some((s) => s.verdict === "fail") || c.attempts.some((a) => a.checker !== "pass");
  const totalMs = c.steps.reduce((n, s) => n + (s.ms ?? 0), 0);
  return (
    <details className={`mcard${hadFail ? " had-fail" : ""}`} open={open}>
      <summary>
        <span className="mcard-id">{c.card_id}</span>
        {c.t_in_min !== null && <span className="dim small">{c.t_in_min}'</span>}
        <span className={`status-badge ${fell ? "fallback" : "approved"}`}>{fell ? "Fallback to template" : "Approved"}</span>
        {retries(c) > 0 && <span className="status-badge retry">{retries(c)} {retries(c) === 1 ? "retry" : "retries"}</span>}
        <span className="dim small">{c.steps.length} steps{totalMs ? ` · ${(totalMs / 1000).toFixed(1)} s` : ""}</span>
      </summary>
      <div className="mcard-body">
        {c.question_en && <p className="small dim">Question: {c.question_en}</p>}
        <div className="approved-box">
          <div className="small dim">Approved{c.approved_by ? ` by ${c.approved_by}` : ""}</div>
          {c.approved_plain_en && <p><b>Plain:</b> {fillFacts(c.approved_plain_en, f)}</p>}
          {c.approved_expert_en && <p className="expert"><b>Expert:</b> {fillFacts(c.approved_expert_en, f)}</p>}
          {Object.keys(c.translations).length > 0 && (
            <div className="tr-list">
              {Object.entries(c.translations).map(([lang, t]) => (
                <div key={lang} className="tr-row">
                  <span className="lang">{lang.toUpperCase()}</span>
                  <span className={`status-badge ${t.status === "approved" ? "approved" : t.status === "fallback" ? "fallback" : "retry"}`}>
                    {t.status === "approved" ? "approved" : t.status === "fallback" ? "fallback" : t.status}
                  </span>
                  <span className="small">{fillFacts(t.plain, f)}{t.expert && <span className="dim"> · {fillFacts(t.expert, f)}</span>}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        {c.steps.length > 0 && (
          <ol className="handoffs">
            {c.steps.map((s) => (
              <li key={s.n} className={`hs ${s.verdict === "pass" ? "pass" : s.verdict === "fail" ? "fail" : "info"}`}>
                <div className="hs-head">
                  <span className="hs-n">{s.n}</span>
                  <b>{nameOf(s.agent)}</b>
                  <span className="hs-action">{s.action}</span>
                  {s.to && <span className="dim">→ {nameOf(s.to)}</span>}
                  <span className={`verdict ${s.verdict}`}>{verdictLabel(s.verdict)}</span>
                  {s.via_mcp && <span className="mcp-badge" title="Facts fetched through the MCP server">MCP</span>}
                  {s.ms !== null && <span className="dim small hs-ms">{s.ms < 1000 ? `${Math.round(s.ms)} ms` : `${(s.ms / 1000).toFixed(1)} s`}</span>}
                </div>
                {s.notes.length > 0 && <ul className="hs-notes small">{s.notes.map((x, i) => <li key={i}>{x}</li>)}</ul>}
                {s.text && (
                  <div className="hs-text small">
                    {Object.entries(s.text).map(([k, v]) => (
                      <div key={k}><span className="dim">{k.replace("_en", "").replace("_", " ")}:</span> “{short(fillFacts(v, f))}”</div>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
        {c.attempts.length > 0 && (
          <details className="attempts-box">
            <summary className="small">Drafts and checker ({c.attempts.length})</summary>
            <div className="trace"><Attempts attempts={c.attempts} facts={f} showPassText /></div>
          </details>
        )}
      </div>
    </details>
  );
}

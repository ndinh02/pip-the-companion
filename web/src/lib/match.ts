import type { AddedTime, Card, I18n, Lang, Match, PlayersFeed } from "./types";

/** The match the app plays. Replace this file (copy `data/demo-match.json` here) to change the match. */
export const MATCH_URL = "/data/match.json";

export async function loadMatch(): Promise<Match> {
  const res = await fetch(MATCH_URL);
  if (!res.ok) throw new Error(`match file ${MATCH_URL}: HTTP ${res.status}`);
  return (await res.json()) as Match;
}

/** Added-time boards for this match, or null if there is no file or it belongs to another match. */
export async function loadAddedTime(match: Match): Promise<AddedTime | null> {
  try {
    const res = await fetch("/data/added-time.json");
    if (!res.ok) return null;
    const data = (await res.json()) as AddedTime;
    if (data.match_id !== match.match_id) {
      console.warn(`added-time.json is for ${data.match_id}, not ${match.match_id}: explainer skipped`);
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

/** Player stats for "Who's that?", or null if there is no file or it belongs to another match. */
export async function loadPlayers(match: Match): Promise<PlayersFeed | null> {
  try {
    const res = await fetch("/data/players.json");
    if (!res.ok) return null;
    const data = (await res.json()) as PlayersFeed;
    if (data.match_id !== match.match_id) {
      console.warn(`players.json is for ${data.match_id}, not ${match.match_id}: "Who's that?" skipped`);
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

/** Every number viewers see is filled in here from `facts` — never written by an AI. */
export function fill(text: string, facts: Match["facts"]): string {
  return text.replace(/\{([a-z0-9_]+)\}/g, (_, id: string) => (id in facts ? String(facts[id].value) : "?"));
}

export function t(text: I18n, lang: Lang): string {
  return text[lang] ?? text.en;
}

export function answerLabel(card: Card, optionId: string, lang: Lang): string {
  const o = card.question.options.find((x) => x.id === optionId);
  return o ? t(o.label, lang) : optionId;
}

export function scoreAt(match: Match, minute: number): { HAR: number; COP: number } {
  let s = { HAR: 0, COP: 0 };
  for (const e of match.score_timeline) if (minute >= e.from_min) s = { HAR: e.HAR, COP: e.COP };
  return s;
}

export const ROOM_RE = /^[A-Z0-9]{4}$/;
export function randomRoom(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
}

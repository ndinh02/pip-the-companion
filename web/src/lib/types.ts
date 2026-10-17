export type Lang = "en" | "de" | "vi";
export const LANGS: Lang[] = ["en", "de", "vi"];
export type I18n = Record<Lang, string>;
export type Pose = "asks" | "thinks" | "wow" | "oops" | "wave";

export interface Team {
  team_id: string;
  name: string;
  short_name: string;
  kit: { primary: string; secondary: string };
}
export interface Option {
  id: string;
  label: I18n;
}
export interface Card {
  card_id: string;
  moment_id: string;
  trigger: string;
  t_in_min: number;
  /** Exact match time in ms (same clock as tracking); absent in the hand-written mock. */
  t_ms?: number;
  /** Ball went dead (question opens), play restarted (answers close), outcome visible (reveal). Match ms. */
  dead_ms?: number;
  restart_ms?: number;
  reveal_ms?: number;
  /** VAR only: the moment of the pass the check is judged on. */
  frame_ms?: number;
  expected_break_s?: number;
  team_id: string;
  pitch: { x: number; y: number };
  question: { text: I18n; options: Option[]; pippi_call: string };
  reveal: { answer: string; pose: Pose; plain: I18n; expert: I18n; fact_ids: string[] };
}
export interface Match {
  match_id: string;
  venue: string;
  pitch: { length_m: number; width_m: number };
  teams: Team[];
  /** One entry per goal (after the 0-0 kick-off entry). Exact times are absent in the hand-written mock. */
  score_timeline: { from_min: number; HAR: number; COP: number; t_ms?: number; team_id?: string; player_id?: string; restart_ms?: number | null }[];
  facts: Record<string, { value: number; source?: string }>;
  cards: Card[];
  /** Moments the reader found but did not turn into cards (match-reader output only). */
  moments_held?: HeldMoment[];
}
export interface HeldMoment {
  trigger: string;
  t_in_min: number;
  team_id: string;
  reason: string;
}

/** One "added time" board (45' / 90'): why the fourth official shows N minutes. Made by scripts/added_time.py. */
export interface AddedItem {
  type: string; // goal | sub | injury | VAR | card | other
  count: number;
  seconds: number;
}
export interface AddedBoard {
  period: number;
  at_min: number;
  announced_min: number;
  actual_s: number;
  items: AddedItem[];
}
export interface AddedTime {
  match_id: string;
  boards: AddedBoard[];
}

/** Per-player cumulative stats, one value per match minute (array[m] = value at the START of minute m). Made by match-reader. */
export type StatKey = "passes" | "passes_ok" | "hard_ok" | "ball_wins" | "shots" | "saves" | "distance_m" | "top_speed_dmh" | "sprints";
export interface PlayerRow {
  player_id: string;
  team_id: string;
  shirt_no: number;
  position: "GK" | "DF" | "MF" | "FW";
  on_min: number | null;
  off_min: number | null;
  stats: Record<StatKey, number[]>;
}
export interface PlayersFeed {
  match_id: string;
  last_minute: number;
  model: string;
  players: PlayerRow[];
}

/** What the room called in the first half. Card text is looked up by card_id in the match file. */
export interface HalfRow {
  card_id: string;
  tally: Record<string, number>;
  answered: number;
}
export interface HalfSummary {
  score: { HAR: number; COP: number };
  rows: HalfRow[];
}

/** "locked": play has restarted, answers are closed, the outcome is coming. */
export type Phase = "play" | "ask" | "locked" | "reveal" | "added" | "half" | "full";

/** TV -> phones */
export interface StateMsg {
  t: "state";
  phase: Phase;
  minute: number;
  /** "23'", "45+2'" */
  clock: string;
  card: Card | null;
  board: AddedBoard | null;
  half: HalfSummary | null;
  deadline: number;
  total_ms: number;
  tally: Record<string, number>;
  answered: number;
  /** The anonymous animals of the phones that have answered so far, in order (never what they picked). */
  answered_by?: string[];
  /** Phones that joined the room (a count only). */
  joined?: number;
  /** The latest goal's scorer while it is fresh (a few match minutes), so phones can offer their profile. */
  scorer?: string | null;
}
/** phones -> TV */
export type PhoneMsg =
  | { t: "hello"; device: string }
  | { t: "answer"; device: string; card_id: string; option: string }
  /** Which player this phone follows (null = nobody). The TV only shows an anonymous count per player. */
  | { t: "follow"; device: string; player_id: string | null };
export type Msg = StateMsg | PhoneMsg;

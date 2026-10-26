import type { Lang, Match, PlayerRow, PlayersFeed, StatKey } from "./types";

// DE/VI are drafts until the owner checks them. No names: a player is team + shirt number + position (decision D1).
export const POSITION_LABEL: Record<PlayerRow["position"], Record<Lang, string>> = {
  GK: { en: "Goalkeeper", de: "Torwart", vi: "Thủ môn" },
  DF: { en: "Defender", de: "Verteidiger", vi: "Hậu vệ" },
  MF: { en: "Midfielder", de: "Mittelfeldspieler", vi: "Tiền vệ" },
  FW: { en: "Forward", de: "Stürmer", vi: "Tiền đạo" },
};

export const STAT_LABEL = {
  distance: { en: "Distance", de: "Strecke", vi: "Quãng đường" },
  topSpeed: { en: "Top speed", de: "Spitzentempo", vi: "Tốc độ tối đa" },
  sprints: { en: "Sprints", de: "Sprints", vi: "Nước rút" },
  passes: { en: "Passes completed", de: "Angekommene Pässe", vi: "Chuyền thành công" },
  hardPasses: { en: "Hard passes completed", de: "Angekommene schwere Pässe", vi: "Đường chuyền khó thành công" },
  ballWins: { en: "Ball wins", de: "Balleroberungen", vi: "Giành bóng" },
  shots: { en: "Shots", de: "Schüsse", vi: "Cú sút" },
  saves: { en: "Saves", de: "Paraden", vi: "Cứu thua" },
  goals: { en: "Goals", de: "Tore", vi: "Bàn thắng" },
} satisfies Record<string, Record<Lang, string>>;

export const STATUS = {
  starter: { en: "Started the match", de: "Von Beginn an dabei", vi: "Đá chính" },
  cameOn: { en: "Came on at", de: "Eingewechselt", vi: "Vào sân" },
  wentOff: { en: "Went off at", de: "Ausgewechselt", vi: "Rời sân" },
  bench: { en: "On the bench so far", de: "Bisher auf der Bank", vi: "Đang ngồi dự bị" },
} satisfies Record<string, Record<Lang, string>>;

/** The match minute the phone may look at: never later than the TV's clock (no spoilers). */
export function clampMinute(feed: PlayersFeed, minute: number): number {
  return Math.max(0, Math.min(Math.floor(minute), feed.last_minute));
}

export function stat(p: PlayerRow, key: StatKey, minute: number): number {
  const arr = p.stats[key];
  return arr[Math.max(0, Math.min(minute, arr.length - 1))];
}

export function minutesPlayed(p: PlayerRow, minute: number): number {
  if (p.on_min === null) return 0;
  return Math.max(0, Math.min(minute, p.off_min ?? Infinity) - p.on_min);
}

export type Status = "starter" | "cameOn" | "wentOff" | "bench";
export function statusAt(p: PlayerRow, minute: number): { kind: Status; at?: number } {
  if (p.on_min !== null && p.on_min > minute) return { kind: "bench" };
  if (p.on_min === null) return { kind: "bench" };
  if (p.off_min !== null && p.off_min <= minute) return { kind: "wentOff", at: Math.floor(p.off_min) };
  if (p.on_min > 0) return { kind: "cameOn", at: Math.floor(p.on_min) };
  return { kind: "starter" };
}

export const km = (m: number) => (m / 1000).toFixed(1);
export const kmh = (dmh: number) => (dmh / 10).toFixed(1);

// ---- the one plain sentence, chosen by code ------------------------------------------------------------------------
type Fill = { n: number; team: string; v: string; at: number };
const SENTENCES: Record<string, Record<Lang, string>> = {
  gk: {
    en: "Number {n}, the goalkeeper: the only player allowed to use their hands, and only inside their own box.",
    de: "Nummer {n}, der Torwart: der einzige Spieler, der die Hände benutzen darf, und nur im eigenen Strafraum.",
    vi: "Số {n}, thủ môn: cầu thủ duy nhất được dùng tay, và chỉ trong vòng cấm của đội mình.",
  },
  passer: {
    en: "Number {n} has completed the most passes for {team} so far: {v}.",
    de: "Nummer {n} hat bisher die meisten angekommenen Pässe für {team}: {v}.",
    vi: "Số {n} đến giờ có nhiều đường chuyền thành công nhất của {team}: {v}.",
  },
  fastest: {
    en: "Number {n} is the fastest player so far: {v} km/h at top speed.",
    de: "Nummer {n} ist bisher der schnellste Spieler: {v} km/h Spitzentempo.",
    vi: "Số {n} đến giờ là cầu thủ nhanh nhất: tốc độ tối đa {v} km/h.",
  },
  ground: {
    en: "Number {n} has covered the most ground for {team} so far: {v} km.",
    de: "Nummer {n} ist bisher am meisten für {team} gelaufen: {v} km.",
    vi: "Số {n} đến giờ là người chạy nhiều nhất của {team}: {v} km.",
  },
  winner: {
    en: "Number {n} has won the ball back the most often for {team} so far: {v} times.",
    de: "Nummer {n} hat bisher am häufigsten den Ball für {team} erobert: {v} Mal.",
    vi: "Số {n} đến giờ giành lại bóng nhiều nhất cho {team}: {v} lần.",
  },
  DF: {
    en: "Number {n}, a defender: stops the other team's attacks and starts their own.",
    de: "Nummer {n}, ein Verteidiger: stoppt die Angriffe des Gegners und startet eigene.",
    vi: "Số {n}, hậu vệ: chặn các pha tấn công của đối phương và mở ra pha tấn công của đội mình.",
  },
  MF: {
    en: "Number {n}, a midfielder: links defence and attack and keeps the team moving.",
    de: "Nummer {n}, ein Mittelfeldspieler: verbindet Abwehr und Angriff und hält das Spiel in Bewegung.",
    vi: "Số {n}, tiền vệ: nối hàng thủ với hàng công và giữ nhịp cho cả đội.",
  },
  FW: {
    en: "Number {n}, a forward: the player closest to goal, whose job is to score and to create chances.",
    de: "Nummer {n}, ein Stürmer: spielt am nächsten am Tor und soll treffen und Chancen vorbereiten.",
    vi: "Số {n}, tiền đạo: cầu thủ gần khung thành nhất, có nhiệm vụ ghi bàn và tạo cơ hội.",
  },
  bench: {
    en: "Number {n} is on the bench so far and has not played yet.",
    de: "Nummer {n} sitzt bisher auf der Bank und hat noch nicht gespielt.",
    vi: "Số {n} đến giờ ngồi dự bị và chưa ra sân.",
  },
  off: {
    en: "Number {n} went off in minute {at}.",
    de: "Nummer {n} wurde in der {at}. Minute ausgewechselt.",
    vi: "Số {n} rời sân ở phút {at}.",
  },
};

/** Biggest value in `rows` for `key`; null if it is not unique or below `min` (no tie-breaking: "most" must be true). */
function uniqueLeader(rows: PlayerRow[], key: StatKey, minute: number, min: number): PlayerRow | null {
  const sorted = [...rows].sort((a, b) => stat(b, key, minute) - stat(a, key, minute));
  if (!sorted.length || stat(sorted[0], key, minute) < min) return null;
  if (sorted[1] && stat(sorted[1], key, minute) === stat(sorted[0], key, minute)) return null;
  return sorted[0];
}

/** One true sentence about the player, filled from the stats by code. */
export function describePlayer(feed: PlayersFeed, p: PlayerRow, minute: number, teamName: string, lang: Lang): string {
  const fill = (key: string, f: Partial<Fill>) =>
    SENTENCES[key][lang]
      .replace("{n}", String(p.shirt_no))
      .replace("{team}", teamName)
      .replace("{v}", f.v ?? "")
      .replace("{at}", String(f.at ?? ""));
  const status = statusAt(p, minute);
  if (status.kind === "bench") return fill("bench", {});
  if (status.kind === "wentOff") return fill("off", { at: status.at });
  if (p.position === "GK") return fill("gk", {});

  const mates = feed.players.filter((x) => x.team_id === p.team_id && minutesPlayed(x, minute) > 0);
  const everyone = feed.players.filter((x) => minutesPlayed(x, minute) > 0);
  if (uniqueLeader(mates, "passes_ok", minute, 5)?.player_id === p.player_id) return fill("passer", { v: String(stat(p, "passes_ok", minute)) });
  if (uniqueLeader(everyone, "top_speed_dmh", minute, 300)?.player_id === p.player_id) return fill("fastest", { v: kmh(stat(p, "top_speed_dmh", minute)) });
  if (uniqueLeader(mates, "distance_m", minute, 2000)?.player_id === p.player_id) return fill("ground", { v: km(stat(p, "distance_m", minute)) });
  if (uniqueLeader(mates, "ball_wins", minute, 3)?.player_id === p.player_id) return fill("winner", { v: String(stat(p, "ball_wins", minute)) });
  return fill(p.position, {});
}

/** Goals this player has scored up to `minute` (counted from the score timeline, i.e. from the match events). */
export function goalsBy(match: Match, playerId: string, minute: number): number {
  return match.score_timeline.filter((g) => g.player_id === playerId && g.from_min <= minute).length;
}

export function teamName(match: Match, teamId: string): string {
  return match.teams.find((t) => t.team_id === teamId)?.name ?? teamId;
}

/** The one line on the half-time card about the player the viewer follows. */
export function followLine(match: Match, p: PlayerRow, minute: number, lang: Lang): string {
  const name = `${teamName(match, p.team_id)} #${p.shirt_no}`;
  const passes = `${stat(p, "passes_ok", minute)}/${stat(p, "passes", minute)}`;
  const dist = km(stat(p, "distance_m", minute));
  if (lang === "de") return `${name}: ${passes} Pässe angekommen, ${dist} km gelaufen`;
  if (lang === "vi") return `${name}: ${passes} chuyền thành công, chạy ${dist} km`;
  return `${name}: ${passes} passes completed, ${dist} km covered`;
}

// ---- "Follow" lives on this phone only (AGENTS.md rule 6) ---------------------------------------------------------
const FOLLOW_KEY = "pippi:follow";
export function loadFollow(): string | null {
  try {
    return localStorage.getItem(FOLLOW_KEY);
  } catch {
    return null;
  }
}
export function saveFollow(id: string | null): void {
  try {
    if (id) localStorage.setItem(FOLLOW_KEY, id);
    else localStorage.removeItem(FOLLOW_KEY);
  } catch {
    /* storage blocked: following simply lasts until reload */
  }
}

// ---- "This match": short notes about the player, as news, written by code from the stats (no spoilers) ----------
const NOTE = {
  started: { en: "Started the match", de: "Stand in der Startelf", vi: "Đá chính từ đầu" },
  cameOn: { en: "Came on", de: "Eingewechselt", vi: "Vào sân" },
  wentOff: { en: "Went off", de: "Ausgewechselt", vi: "Rời sân" },
  goal: { en: "Scored", de: "Tor erzielt", vi: "Ghi bàn" },
  firstShot: { en: "First shot of their match", de: "Erster Schuss im Spiel", vi: "Cú sút đầu tiên trong trận" },
  topSpeed: { en: "Top speed so far: {v} km/h", de: "Bisheriges Spitzentempo: {v} km/h", vi: "Tốc độ tối đa đến giờ: {v} km/h" },
  ballWins: { en: "{v} ball wins so far", de: "Bisher {v} Balleroberungen", vi: "Đã giành lại bóng {v} lần" },
} satisfies Record<string, Record<Lang, string>>;

/** First minute at which `key` reached `value` (the minute something happened), or null. */
function minuteReached(p: PlayerRow, key: StatKey, value: number, upTo: number): number | null {
  const arr = p.stats[key];
  for (let m = 0; m <= Math.min(upTo, arr.length - 1); m++) if (arr[m] >= value && value > 0) return m;
  return null;
}

export interface Note { min: number; text: string }
/** Newest first. Every note is a fact from the match file or the players feed at or before `minute`. */
export function matchNotes(match: Match, p: PlayerRow, minute: number, lang: Lang): Note[] {
  const notes: Note[] = [];
  const st = statusAt(p, minute);
  if (p.on_min === 0) notes.push({ min: 0, text: NOTE.started[lang] });
  else if (p.on_min !== null && p.on_min <= minute) notes.push({ min: Math.floor(p.on_min), text: NOTE.cameOn[lang] });
  if (st.kind === "wentOff" && st.at !== undefined) notes.push({ min: st.at, text: NOTE.wentOff[lang] });
  for (const g of match.score_timeline) if (g.player_id === p.player_id && g.from_min <= minute) notes.push({ min: Math.floor(g.from_min), text: `⚽ ${NOTE.goal[lang]}` });
  const shot = minuteReached(p, "shots", 1, minute);
  if (shot !== null && !notes.some((n) => n.min === shot && n.text.startsWith("⚽"))) notes.push({ min: shot, text: NOTE.firstShot[lang] });
  const top = stat(p, "top_speed_dmh", minute);
  const topAt = minuteReached(p, "top_speed_dmh", top, minute);
  if (top >= 250 && topAt !== null) notes.push({ min: topAt, text: NOTE.topSpeed[lang].replace("{v}", kmh(top)) });
  const wins = stat(p, "ball_wins", minute);
  const winsAt = minuteReached(p, "ball_wins", wins, minute);
  if (wins >= 3 && winsAt !== null) notes.push({ min: winsAt, text: NOTE.ballWins[lang].replace("{v}", String(wins)) });
  return notes.sort((a, b) => b.min - a.min);
}

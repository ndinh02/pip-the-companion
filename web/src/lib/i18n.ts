import type { Lang } from "./types";

// DE/VI are drafts until the owner checks them.
export const UI = {
  callIt: { en: "Call it!", de: "Sag's an!", vi: "Đoán đi!" },
  eyesUp: { en: "Eyes up — Pip will wake you in the next break.", de: "Augen hoch – Pip weckt dich in der nächsten Pause.", vi: "Ngẩng lên xem nào – Pip sẽ gọi bạn ở quãng nghỉ sau." },
  waitingTv: { en: "Looking for the TV…", de: "Suche den Fernseher …", vi: "Đang tìm TV…" },
  waitingTvHint: { en: "Open /tv in another tab of this browser.", de: "Öffne /tv in einem anderen Tab dieses Browsers.", vi: "Mở /tv ở một tab khác của trình duyệt này." },
  locked: { en: "Locked in", de: "Eingeloggt", vi: "Đã chốt" },
  lockedWait: { en: "Waiting for the match to answer…", de: "Warten, bis das Spiel antwortet …", vi: "Đang chờ trận đấu trả lời…" },
  matchSays: { en: "The match says", de: "Das Spiel sagt", vi: "Trận đấu cho biết" },
  pippiCalled: { en: "Pip called", de: "Pip tippte auf", vi: "Pip đoán" },
  roomSays: { en: "The room called", de: "Der Raum sagte", vi: "Cả nhà đoán" },
  goDeeper: { en: "Go deeper", de: "Mehr Details", vi: "Xem sâu hơn" },
  hide: { en: "Hide", de: "Ausblenden", vi: "Ẩn" },
  fullTime: { en: "Full time", de: "Abpfiff", vi: "Hết giờ" },
  scan: { en: "Scan to join the room", de: "Scannen und dem Raum beitreten", vi: "Quét để vào phòng" },
  phonesJoined: { en: "phones joined", de: "Handys verbunden", vi: "điện thoại đã vào" },
  badRoom: { en: "That room code doesn't look right.", de: "Dieser Raumcode sieht nicht richtig aus.", vi: "Mã phòng này có vẻ chưa đúng." },
  sleeping: { en: "Pip is watching the game", de: "Pip schaut das Spiel", vi: "Pip đang xem trận" },
  addedTime: { en: "Added time", de: "Nachspielzeit", vi: "Bù giờ" },
  addedWhy: {
    en: "Referees add the time lost while the ball was dead: goals, substitutions, injuries, VAR checks and cards.",
    de: "Der Schiedsrichter fügt die Zeit hinzu, die bei Spielunterbrechungen verloren ging: Tore, Wechsel, Verletzungen, VAR-Prüfungen und Karten.",
    vi: "Trọng tài cộng thêm thời gian mất đi khi bóng chết: bàn thắng, thay người, chấn thương, VAR và thẻ phạt.",
  },
  addedLost: { en: "Time lost", de: "Verlorene Zeit", vi: "Thời gian mất" },
  addedRounding: { en: "The board rounds to whole minutes.", de: "Die Anzeigetafel rundet auf ganze Minuten.", vi: "Bảng điện tử làm tròn theo phút." },
  halfTime: { en: "Half-time", de: "Halbzeit", vi: "Nghỉ giữa hiệp" },
  halfCalls: { en: "What the room called", de: "Das sagte der Raum", vi: "Cả nhà đã đoán" },
  halfRoom: { en: "Room", de: "Raum", vi: "Cả nhà" },
  halfMatch: { en: "Match", de: "Spiel", vi: "Trận" },
  halfSplit: { en: "Split", de: "Geteilt", vi: "Chia đều" },
  halfNoCalls: { en: "No calls", de: "Keine Antworten", vi: "Chưa ai đoán" },
  wordOfMatch: { en: "Word of the match", de: "Wort des Spiels", vi: "Từ của trận" },
  share: { en: "Share", de: "Teilen", vi: "Chia sẻ" },
  copied: { en: "Copied", de: "Kopiert", vi: "Đã sao chép" },
  halfCard: { en: "Half-time card", de: "Halbzeitkarte", vi: "Thẻ giữa hiệp" },
  whosThat: { en: "Who's that?", de: "Wer ist das?", vi: "Ai đấy?" },
  pickTeam: { en: "Which team?", de: "Welche Mannschaft?", vi: "Đội nào?" },
  pickNumber: { en: "Shirt number", de: "Rückennummer", vi: "Số áo" },
  back: { en: "Back", de: "Zurück", vi: "Quay lại" },
  follow: { en: "Follow this player", de: "Diesem Spieler folgen", vi: "Theo dõi cầu thủ này" },
  following: { en: "Following", de: "Du folgst", vi: "Đang theo dõi" },
  unfollow: { en: "Stop following", de: "Nicht mehr folgen", vi: "Bỏ theo dõi" },
  yourPlayer: { en: "Your player", de: "Dein Spieler", vi: "Cầu thủ của bạn" },
  followHint: { en: "Stays on this phone only.", de: "Bleibt nur auf diesem Handy.", vi: "Chỉ lưu trên điện thoại này." },
  modelled: {
    en: "Distance, top speed and sprints are computed from synthetic tracking data. All data in this demo is synthetic.",
    de: "Strecke, Spitzentempo und Sprints werden aus synthetischen Trackingdaten berechnet. Alle Daten in dieser Demo sind synthetisch.",
    vi: "Quãng đường, tốc độ tối đa và số lần nước rút được tính từ dữ liệu theo dõi giả lập. Mọi dữ liệu trong bản demo đều là dữ liệu giả lập.",
  },
  soFar: { en: "so far", de: "bisher", vi: "đến giờ" },
  lastMinutes: { en: "Where they have been, last five minutes", de: "Laufwege der letzten fünf Minuten", vi: "Di chuyển trong năm phút gần nhất" },
  ghostRun: { en: "Fastest run of the half", de: "Schnellster Lauf der Halbzeit", vi: "Pha bứt tốc nhanh nhất hiệp" },
  replay: { en: "Replay", de: "Wiederholen", vi: "Xem lại" },
  notOnPitch: { en: "Not on the pitch right now.", de: "Gerade nicht auf dem Platz.", vi: "Hiện không có mặt trên sân." },
  loadingTracking: { en: "Loading positions…", de: "Positionen werden geladen …", vi: "Đang tải vị trí…" },
  // What is happening during the stoppage (said on the TV and on phones that already answered). No outcome in here.
  nowVar: { en: "VAR is checking the replay. The goal waits.", de: "Der VAR prüft die Wiederholung. Das Tor wartet.", vi: "VAR đang xem lại. Bàn thắng đang chờ." },
  nowCorner: { en: "Players are packing the box for the corner.", de: "Die Spieler drängen sich im Strafraum für die Ecke.", vi: "Cầu thủ đang dồn vào vòng cấm chờ phạt góc." },
  nowFreeKick: { en: "The wall is lining up for the free kick.", de: "Die Mauer stellt sich für den Freistoß auf.", vi: "Hàng rào đang xếp cho cú đá phạt." },
  nowSub: { en: "A player is walking off, a fresh one is waiting.", de: "Ein Spieler geht vom Platz, ein frischer wartet.", vi: "Một cầu thủ rời sân, người mới đang chờ vào." },
  skippingWait: { en: "Fast-forwarding the wait", de: "Wartezeit im Schnelldurchlauf", vi: "Tua nhanh lúc chờ" },
  scorer: { en: "Goal scorer", de: "Tor erzielt von", vi: "Người ghi bàn" },
  seeScorer: { en: "Goal! See who scored", de: "Tor! Sieh dir an, wer getroffen hat", vi: "Vào! Xem ai ghi bàn" },
  didYouKnow: { en: "Did you know?", de: "Schon gewusst?", vi: "Bạn có biết?" },
  goal: { en: "GOAL!", de: "TOR!", vi: "VÀO!" },
  answeredOf: { en: "answered", de: "haben geantwortet", vi: "đã trả lời" },
  pipThinks: { en: "Pip thinks", de: "Pip tippt auf", vi: "Pip nghĩ là" },
  roomSoFar: { en: "The room so far", de: "Der Raum bisher", vi: "Cả nhà đến giờ" },
  alertsOn: { en: "Buzz me when Pip asks", de: "Vibrieren, wenn Pip fragt", vi: "Rung khi Pip hỏi" },
  alertsHint: { en: "Your phone buzzes (and chimes, if not on silent) when a question opens. The screen stays awake.", de: "Dein Handy vibriert (und klingt, wenn nicht stumm), sobald eine Frage kommt. Der Bildschirm bleibt an.", vi: "Điện thoại sẽ rung (và kêu, nếu không để im lặng) khi có câu hỏi. Màn hình sẽ luôn sáng." },
  alertsOff: { en: "Alerts off", de: "Hinweise aus", vi: "Tắt báo" },
  openUntilRestart: { en: "Open until play restarts", de: "Offen, bis das Spiel weitergeht", vi: "Mở đến khi trận đấu tiếp tục" },
  answersClosed: { en: "Play is on: answers are locked. Watch!", de: "Es geht weiter: Antworten sind gesperrt. Schau hin!", vi: "Bóng đã lăn: đã khóa câu trả lời. Xem nào!" },
  tooQuick: { en: "Too quick this time. No call needed.", de: "Diesmal ging es zu schnell. Kein Problem.", vi: "Lần này nhanh quá. Không sao cả." },
  skippingTo: { en: "Skipping to", de: "Weiter zu", vi: "Tua đến" },
  you: { en: "You", de: "Du", vi: "Bạn" },
} satisfies Record<string, Record<Lang, string>>;

export function ui(key: keyof typeof UI, lang: Lang): string {
  return UI[key][lang];
}

export function deviceLang(): Lang {
  const l = (navigator.language || "en").slice(0, 2);
  return l === "de" || l === "vi" ? l : "en";
}

/** The "what's happening now" line for a stoppage, or null when there is none for this kind of moment. */
export function nowKey(trigger: string): keyof typeof UI | null {
  return ({ var: "nowVar", corner: "nowCorner", free_kick: "nowFreeKick", substitution: "nowSub" } as const)[trigger as "var"] ?? null;
}

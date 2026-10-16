import type { Lang } from "./types";

/** "Did you know?" rule facts that fill a stoppage. Each one is about the rules (IFAB Laws of the Game), never about
 *  what will happen next, so nothing here can spoil the answer. No match numbers: those only ever come from code.
 *  DE/VI are drafts until the owner checks them. */
type Fact = Record<Lang, string>;

const FACTS: Record<string, Fact[]> = {
  var: [
    {
      en: "VAR can only step in for four things: goals, penalties, straight red cards and mistaken identity.",
      de: "Der VAR darf nur bei vier Dingen eingreifen: Tore, Elfmeter, glatte Rote Karten und Verwechslungen.",
      vi: "VAR chỉ can thiệp bốn tình huống: bàn thắng, phạt đền, thẻ đỏ trực tiếp và nhầm người.",
    },
    {
      en: "Offside is judged at the moment the pass is played, not when the ball arrives.",
      de: "Abseits zählt in dem Moment, in dem der Pass gespielt wird, nicht wenn der Ball ankommt.",
      vi: "Việt vị được tính ngay lúc bóng được chuyền đi, không phải lúc bóng tới chân.",
    },
    {
      en: "For handball, the arm starts at the bottom of the armpit. The shoulder doesn't count.",
      de: "Beim Handspiel beginnt der Arm unten an der Achsel. Die Schulter zählt nicht.",
      vi: "Với lỗi chạm tay, cánh tay tính từ dưới nách trở xuống. Vai thì không tính.",
    },
    {
      en: "The referee has the final say. VAR only advises, and can invite the referee to watch the screen.",
      de: "Das letzte Wort hat der Schiedsrichter. Der VAR berät nur und kann ihn an den Bildschirm bitten.",
      vi: "Trọng tài chính quyết định cuối cùng. VAR chỉ góp ý và có thể mời trọng tài xem màn hình.",
    },
  ],
  corner: [
    {
      en: "You can score straight from a corner. Nobody else has to touch the ball.",
      de: "Man kann direkt aus einer Ecke ein Tor erzielen. Niemand sonst muss den Ball berühren.",
      vi: "Có thể ghi bàn trực tiếp từ quả phạt góc, không cần ai chạm bóng.",
    },
    {
      en: "Nobody can be offside straight from a corner kick.",
      de: "Direkt nach einem Eckstoß kann niemand im Abseits stehen.",
      vi: "Không ai bị việt vị khi nhận bóng trực tiếp từ quả phạt góc.",
    },
    {
      en: "Defenders must stand ten yards from the corner arc until the ball is kicked.",
      de: "Verteidiger müssen zehn Yards vom Eckviertelkreis entfernt stehen, bis der Ball gespielt ist.",
      vi: "Hậu vệ phải đứng cách cung phạt góc mười thước Anh cho tới khi bóng được đá.",
    },
  ],
  free_kick: [
    {
      en: "The wall must stand ten yards from the ball. The referee's spray line marks the spot.",
      de: "Die Mauer muss zehn Yards vom Ball entfernt stehen. Die Sprühlinie des Schiedsrichters zeigt die Stelle.",
      vi: "Hàng rào phải đứng cách bóng mười thước Anh. Vạch sơn xịt của trọng tài đánh dấu chỗ đó.",
    },
    {
      en: "Attackers can't stand right next to a wall of three or more defenders.",
      de: "Angreifer dürfen nicht direkt neben einer Mauer aus drei oder mehr Verteidigern stehen.",
      vi: "Cầu thủ tấn công không được đứng sát hàng rào có từ ba hậu vệ trở lên.",
    },
    {
      en: "On an indirect free kick, the referee raises an arm: another player must touch the ball before a goal counts.",
      de: "Beim indirekten Freistoß hebt der Schiedsrichter den Arm: Ein weiterer Spieler muss den Ball berühren, sonst zählt das Tor nicht.",
      vi: "Với quả đá phạt gián tiếp, trọng tài giơ tay: phải có cầu thủ khác chạm bóng thì bàn thắng mới được tính.",
    },
  ],
  substitution: [
    {
      en: "A player who has been taken off can't come back on in the same match.",
      de: "Wer ausgewechselt wurde, darf im selben Spiel nicht zurück auf den Platz.",
      vi: "Cầu thủ đã bị thay ra không được vào sân lại trong cùng trận.",
    },
    {
      en: "The new player can only come on once the other player has left the pitch.",
      de: "Der neue Spieler darf erst aufs Feld, wenn der andere den Platz verlassen hat.",
      vi: "Cầu thủ mới chỉ được vào sân khi người kia đã rời sân.",
    },
  ],
};

export const FACT_EVERY_MS = 25_000; // real time each fact stays up
const FACTS_PER_STOP = 2; // a stoppage shows at most two facts, then the second one stays

/** The fact to show `elapsedMs` (real time) into a stoppage, or null when there are none for this kind of moment.
 *  `seed` (the card id) picks where in the list to start, so different stoppages show different facts. */
export function factAt(trigger: string, elapsedMs: number, lang: Lang, seed = ""): string | null {
  const list = FACTS[trigger];
  if (!list?.length) return null;
  const start = [...seed].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 997, 0);
  const step = Math.min(FACTS_PER_STOP - 1, Math.floor(Math.max(0, elapsedMs) / FACT_EVERY_MS));
  return list[(start + step) % list.length][lang];
}

/** Every fact, for the copy check. */
export const ALL_FACTS = FACTS;

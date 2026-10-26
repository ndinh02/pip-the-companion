# Language review: German (de) and Vietnamese (vi)

Reviewed 2026-10-26 by Claude acting as DE/VI localization reviewer. EN stays canonical and untouched; only `de`/`vi` values changed. No keys, placeholders or code changed.

## Summary

- **Scope:** 464 strings per language: 373 in `web/src/lib/` (`i18n.ts`, `avatar.ts`, `animals.ts`, `halfTime.ts`, `whoThat.ts`, `addedTime.ts`, `didYouKnow.ts`; no other `web/src` file has DE/VI copy) and 91 in `match-reader/templates/cards.json`.
- **Changed:** 88 DE, 85 VI (173 edits). Animal names (`avatar.ts`, `animals.ts`) were fine and are unchanged.
- **Main themes:**
  1. **Betting register in German.** "tippen auf / getippt" (Pip tippte auf, Pip tippt auf, Richtig getippt!) is Tippspiel language even though it gets past the whole-word filter. It is now "Pip sagte", "Pip meint" and "Du lagst richtig!". In Vietnamese, "thử vận may" (try your luck) became "thử dứt điểm".
  2. **"Locked in" = "Eingeloggt"**, which reads as "logged in" in an app. It is now "Antwort steht".
  3. **Broken minute labels.** The code adds ` 63'` after `STATUS.cameOn/wentOff`. That gave "Eingewechselt in der 63'" and "Vào sân phút 63'". The labels are now "Eingewechselt", "Ausgewechselt", "Vào sân" and "Rời sân".
  4. **Wrong corner terms in German.** "Nahpfosten/Fernpfosten" is not used in German football. Broadcast German says "erster/zweiter Pfosten", and the options and all reveals now use that.
  5. **Wrong VAR margin wording.** "Không việt vị {var_margin_cm} cm" read as "not offside by X cm", and "Nicht im Abseits, um X cm" was broken German. Both are rewritten.
  6. **One word per term.** "Room" in Vietnamese was both "cả nhà" and "cả phòng"; it is now "cả phòng" everywhere, matching the "Phòng" tab. "VAR check" is now "VAR-Check". "Moments" is now "pha bóng". An answer the user picks is now "câu trả lời"; "đáp án" stays only for the match's answer ("Không có đáp án rõ ràng"). Pairs with the same EN text now share one DE/VI text (calledIt/mtRight, learnTitle/rvLearn, pickFollow/plTitle, alertsOn/rmChime).
  7. **False friends.** "Halbzeitkarte"/"Spielkarte" (ticket, playing card) and "thẻ" (yellow/red card) for the share card. "TV đang im lặng" / "Der Fernseher ist still" mean "sound off", but EN means "no signal". "Pip sẽ gọi điện thoại" means "Pip will phone you".
  8. **Grading people (rule 8).** The glossary said a subbed-off player was "taktisch ungeeignet" / "không còn phù hợp", which judges the player. It now says "aus taktischen Gründen" / "vì lý do chiến thuật".
- `cards.json` changed, so `data/demo-match.json` and `web/public/data/match.json` were regenerated with the given command.

## Verification

- `cd web && npm run check:copy`: pass (9 cards × 3 languages, 1392 strings, no betting language)
- `npx tsc --noEmit`: pass
- `npm run build`: pass
- `match-reader: python3 -m unittest discover -s tests`: pass (63 tests, OK, 1 skipped)
- `node scripts/check-copy.mjs data/demo-match.json`: pass

## Every change

| File | Key / path | Lang | Old | New | Why |
|---|---|---|---|---|---|
| i18n.ts | `eyesUp` | de | Augen hoch – Pip weckt dich in der nächsten Pause. | Schau aufs Spiel – Pip weckt dich in der nächsten Pause. | "Augen hoch" is a literal calque; says what to look at |
| i18n.ts | `eyesUp` | vi | Ngẩng lên xem nào – Pip sẽ gọi bạn ở quãng nghỉ sau. | Ngẩng lên xem trận nào – Pip sẽ gọi bạn ở quãng nghỉ sau. | Clearer: look up at the match |
| i18n.ts | `locked` | de | Eingeloggt | Antwort steht | "Eingeloggt" reads as "logged in" inside an app |
| i18n.ts | `lockedWait` | de | Warten, bis das Spiel antwortet … | Warten auf die Antwort des Spiels … | Smoother |
| i18n.ts | `pippiCalled` | de | Pip tippte auf | Pip sagte | "tippen auf" is Tippspiel/betting register |
| i18n.ts | `roomSays` | vi | Cả nhà đoán | Cả phòng đoán | One term for "the room": cả phòng |
| i18n.ts | `goDeeper` | vi | Xem sâu hơn | Tìm hiểu thêm | Literal; natural VI for "learn more" |
| i18n.ts | `fullTime` | vi | Hết giờ | Hết trận | "Hết giờ" = time is up; full time is "hết trận" |
| i18n.ts | `addedWhy` | de | Der Schiedsrichter fügt die Zeit hinzu, die bei Spielunterbrechungen verloren ging: Tore, Wechsel, Verletzungen, VAR-Prüfungen und Karten. | Der Schiedsrichter lässt die Zeit nachspielen, die bei Unterbrechungen verloren ging: Tore, Wechsel, Verletzungen, VAR-Checks und Karten. | Football idiom "nachspielen lassen"; one term VAR-Check |
| i18n.ts | `addedWhy` | vi | Trọng tài cộng thêm thời gian mất đi khi bóng chết: bàn thắng, thay người, chấn thương, VAR và thẻ phạt. | Trọng tài cộng thêm thời gian mất đi khi bóng chết: bàn thắng, thay người, chấn thương, kiểm tra VAR và thẻ phạt. | Matches the added-time list label "Kiểm tra VAR" |
| i18n.ts | `addedLost` | vi | Thời gian mất | Thời gian bị mất | Grammatical |
| i18n.ts | `addedRounding` | de | Die Anzeigetafel rundet auf ganze Minuten. | Die Tafel zeigt nur ganze Minuten. | "rundet auf" means "rounds up", which is not what EN says |
| i18n.ts | `addedRounding` | vi | Bảng điện tử làm tròn theo phút. | Bảng báo bù giờ chỉ hiện số phút tròn. | Clearer which board and what rounding |
| i18n.ts | `halfCalls` | vi | Cả nhà đã đoán | Cả phòng đã đoán | One term for "the room" |
| i18n.ts | `halfRoom` | vi | Cả nhà | Cả phòng | One term for "the room" |
| i18n.ts | `wordOfMatch` | vi | Từ của trận | Thuật ngữ của trận | Literal; it shows a football term (glossary) |
| i18n.ts | `halfCard` | de | Halbzeitkarte | Halbzeit-Übersicht | "Karte" reads as a ticket or a yellow/red card |
| i18n.ts | `halfCard` | vi | Thẻ giữa hiệp | Tóm tắt giữa hiệp | "Thẻ" in football = yellow/red card |
| i18n.ts | `whosThat` | vi | Ai đấy? | Đó là ai? | Neutral (not regional) phrasing |
| i18n.ts | `ghostRun` | vi | Pha bứt tốc nhanh nhất hiệp | Pha bứt tốc nhanh nhất của hiệp | Grammar |
| i18n.ts | `nowVar` | de | Der VAR prüft die Wiederholung. Das Tor wartet. | Der VAR schaut sich die Bilder an. Das Tor muss warten. | More natural broadcast German |
| i18n.ts | `nowVar` | vi | VAR đang xem lại. Bàn thắng đang chờ. | VAR đang xem lại. Bàn thắng chờ xác nhận. | A goal cannot "wait" in VI; "awaits confirmation" |
| i18n.ts | `nowCorner` | de | Die Spieler drängen sich im Strafraum für die Ecke. | Vor der Ecke füllt sich der Strafraum. | Smoother, shorter |
| i18n.ts | `nowFreeKick` | vi | Hàng rào đang xếp cho cú đá phạt. | Các cầu thủ đang xếp hàng rào cho quả đá phạt. | Natural VI; "quả đá phạt" used everywhere else |
| i18n.ts | `nowSub` | de | Ein Spieler geht vom Platz, ein frischer wartet. | Ein Spieler geht vom Platz, ein neuer steht bereit. | Smoother |
| i18n.ts | `skippingWait` | vi | Tua nhanh lúc chờ | Tua nhanh đoạn chờ | Natural VI |
| i18n.ts | `scorer` | de | Tor erzielt von | Torschütze | Standard label |
| i18n.ts | `seeScorer` | de | Tor! Sieh dir an, wer getroffen hat | Tor! Wer hat getroffen? | Shorter, matches "See who scored" (mtScorer) |
| i18n.ts | `pickFollow` | de | Such dir einen Spieler aus | Wähle einen Spieler, dem du folgst | Same EN as plTitle: one DE wording |
| i18n.ts | `pickFollowHint` | de | Figur und Live-Werte warten hier zwischen den Momenten auf dich. | Seine Figur und seine Live-Werte warten hier zwischen den Momenten auf dich. | "Their" was dropped |
| i18n.ts | `pickFollowHint` | vi | Nhân vật và số liệu trực tiếp sẽ chờ bạn ở đây giữa các khoảnh khắc. | Nhân vật và số liệu trực tiếp của cầu thủ sẽ chờ bạn ở đây giữa các pha bóng. | "Moments" = "pha bóng" everywhere else |
| i18n.ts | `learnTitle` | de | Diesmal nicht. Hier ist der Grund | Diesmal nicht. Das ist der Grund | Same EN as rvLearn: one DE wording; less literal |
| i18n.ts | `learnTitle` | vi | Lần này chưa đúng. Đây là lý do | Lần này chưa trúng. Lý do đây | Same EN as rvLearn/notThisTime: one VI wording |
| i18n.ts | `gotIt` | de | Verstanden | Alles klar | Warmer, less military |
| i18n.ts | `gotIt` | vi | Đã hiểu | Hiểu rồi | Warmer, conversational |
| i18n.ts | `pickPlayer` | de | tippe auf ein Gesicht | tippe auf einen Spieler | Mistranslation: EN says "a player" |
| i18n.ts | `pipThinks` | de | Pip tippt auf | Pip meint | "tippen auf" is Tippspiel/betting register |
| i18n.ts | `roomSoFar` | vi | Cả nhà đến giờ | Cả phòng đến giờ | One term for "the room" |
| i18n.ts | `alertsOn` | de | Signalton, wenn Pip fragt | Ton, wenn Pip fragt | Same EN as rmChime: one DE wording |
| i18n.ts | `alertsOff` | de | Hinweise aus | Ton aus | Matches the chime toggle |
| i18n.ts | `alertsOff` | vi | Tắt báo | Tắt chuông | Matches "Báo chuông" |
| i18n.ts | `openUntilRestart` | vi | Mở đến khi trận đấu tiếp tục | Mở đến khi bóng lăn lại | Natural football phrasing |
| i18n.ts | `answersClosed` | de | Es geht weiter: Antworten sind gesperrt. Schau hin! | Es geht weiter: Antworten geschlossen. Schau hin! | Same term as lkWatch |
| i18n.ts | `waitVerdict` | vi | Cả nhà chờ trận đấu phân xử… | Cả phòng chờ trận đấu trả lời… | "phân xử" evokes refereeing; "trả lời" matches lockedWait |
| i18n.ts | `calledIt` | de | Richtig getippt! | Du lagst richtig! | "getippt" is betting register; matches tvCalledIt "lagen richtig" |
| i18n.ts | `hlIntro` | vi | Mình xem đoạn mở màn, rồi tua tới những khoảnh khắc quan trọng. Mỗi lần tua đều được báo ở đây. | Chúng ta xem đoạn mở màn, rồi tua tới những khoảnh khắc quan trọng. Mỗi lần tua đều được báo ở đây. | "Mình" is Pip's "I"; here EN means "we" |
| i18n.ts | `mVar` | vi | VAR kiểm tra | một lần kiểm tra VAR | Noun phrase like the other items ("một quả phạt góc") |
| i18n.ts | `mAdded` | vi | giờ bù | bù giờ | Same term as addedTime |
| i18n.ts | `shoutIt` | de | Antworte am Handy oder ruf es einfach! | Antworte am Handy oder ruf's einfach laut! | "ruf es" alone is unclear |
| i18n.ts | `changeOnce` | vi | Đổi đáp án (một lần) | Đổi câu trả lời (một lần) | "đáp án" = the correct answer; the user's answer is "câu trả lời" |
| i18n.ts | `lockedFinal` | de | Eingeloggt. Keine Änderung mehr. | Antwort steht. Keine Änderung mehr. | Same as "locked" |
| i18n.ts | `stNoRoom` | de | Verbinde wieder mit dem Raum … | Verbinde neu mit dem Raum … | Natural |
| i18n.ts | `stTvQuiet` | de | Der Fernseher ist still. Öffne Pip dort erneut, der Raum bleibt erhalten. | Der Fernseher meldet sich nicht mehr. Öffne Pip dort neu, der Raum bleibt erhalten. | "still" = silent (sound); EN means no signal |
| i18n.ts | `stTvQuiet` | vi | TV đang im lặng. Hãy mở lại Pip trên TV, phòng vẫn được giữ. | TV không phản hồi. Hãy mở lại Pip trên TV, phòng vẫn được giữ. | "im lặng" = sound off; EN means no signal |
| i18n.ts | `stSub` | de | Pip stellt dem Raum in jeder Pause eine kurze Frage. Kein Konto, keine Namen. | In jeder Pause stellt Pip allen im Raum eine kurze Frage. Kein Konto, keine Namen. | "dem Raum eine Frage stellen" is a calque |
| i18n.ts | `scPoint` | de | Halte die Kamera auf den QR-Code am Fernseher oder auf das Handy eines Freundes. | Halte die Kamera auf den QR-Code am Fernseher oder auf ein anderes Handy. | Avoids gendered "Freund" |
| i18n.ts | `anCheck` | de | Die Ecke deines Fernsehers zeigt dieselben Tiere. Wenn nicht, prüf den Code. | In der Ecke des Fernsehers siehst du dieselben Tiere. Wenn nicht, prüf den Code. | Natural word order |
| i18n.ts | `anCheck` | vi | Góc TV của bạn hiện đúng những con vật này. Nếu không, hãy kiểm tra mã. | Góc TV cũng hiện đúng những con vật này. Nếu không, hãy kiểm tra lại mã. | Smoother |
| i18n.ts | `anNotOpen` | de | Raum {code} ist auf keinem Fernseher offen. Prüf den Code am Fernseher. | Raum {code} ist noch auf keinem Fernseher offen. Prüf den Code am Fernseher. | "yet" was dropped |
| i18n.ts | `inAppTitle` | vi | Bạn đang ở trình duyệt bên trong một ứng dụng khác. | Bạn đang mở trong trình duyệt của một ứng dụng khác. | Natural |
| i18n.ts | `inAppText` | de | Pip läuft hier, aber Ton und wacher Bildschirm klappen am besten im normalen Browser. | Pip läuft auch hier, aber Ton und dauerhaft eingeschalteter Bildschirm klappen am besten im normalen Browser. | "wacher Bildschirm" is not idiomatic |
| i18n.ts | `lbText` | vi | Trận đấu bắt đầu trên TV khi giao bóng. Pip sẽ gọi điện thoại của bạn ở quãng nghỉ đầu tiên. | Trận đấu bắt đầu trên TV khi giao bóng. Pip sẽ báo lên điện thoại của bạn ở quãng nghỉ đầu tiên. | "gọi điện thoại" = make a phone call |
| i18n.ts | `mtCalls` | vi | {n} trên {m} câu đến giờ | {n}/{m} câu hỏi đến giờ | Natural; same N/M style as other VI counts |
| i18n.ts | `mtChime` | de | dein Handy gibt einen Ton | dein Handy meldet sich mit einem Ton | Natural |
| i18n.ts | `mtChime` | vi | điện thoại sẽ báo | điện thoại sẽ báo chuông | Matches "Báo chuông" |
| i18n.ts | `mtRight` | de | Richtig gesagt! | Du lagst richtig! | Same EN as calledIt: one DE wording |
| i18n.ts | `mtNone` | de | Bei dieser hast du nichts gesagt. | Hier hast du nicht geantwortet. | Natural |
| i18n.ts | `mtNone` | vi | Câu này bạn chưa chọn. | Câu này bạn không trả lời. | "chưa" implies you still can |
| i18n.ts | `plTitle` | de | Wähle einen Spieler zum Folgen | Wähle einen Spieler, dem du folgst | Same EN as pickFollow: one DE wording; less clunky |
| i18n.ts | `plText` | de | Die Live-Zahlen warten hier zwischen den Momenten. | Seine Live-Werte warten hier zwischen den Momenten auf dich. | "Werte" is the stat term everywhere else |
| i18n.ts | `plNote` | de | Die Zahlen ändern sich zwischen den Momenten, nie während Pip fragt. | Die Werte ändern sich zwischen den Momenten, nie während Pip fragt. | One stat term: Werte |
| i18n.ts | `plPath` | vi | Đường chạy | Đường di chuyển | "Đường chạy" = running track; matches lastMinutes "Di chuyển" |
| i18n.ts | `stAsOf` | de | Werte Stand {t} | Werte, Stand {t} | Punctuation |
| i18n.ts | `stEnded` | de | Endstand der Werte | endgültige Werte | "Endstand" reads as final score |
| i18n.ts | `tvCallsOnPhones` | vi | Các lựa chọn của cả phòng có trên điện thoại. | Các lựa chọn của cả phòng nằm trên điện thoại. | Natural |
| i18n.ts | `lbShort` | de | Pip fragt den Raum in der ersten Pause. | In der ersten Pause fragt Pip alle im Raum. | "den Raum fragen" is a calque |
| i18n.ts | `rmChime` | vi | Báo khi Pip hỏi | Báo chuông khi Pip hỏi | Same EN as alertsOn: one VI wording |
| i18n.ts | `shOrType` | de | Oder eingeben auf {host} | Oder auf {host} eingeben | Word order |
| i18n.ts | `akFinal` | vi | Chọn đáp án mới. Lần này là chốt. | Chọn câu trả lời mới. Lần này là chốt. | "đáp án" = correct answer |
| i18n.ts | `liN` | vi | {n} trên {m} người đã trả lời | {n}/{m} người đã trả lời | Same N/M style as tvAllIn |
| i18n.ts | `lkWatch` | vi | Đã khóa đáp án. Xem chuyện gì xảy ra nhé! | Đã khóa câu trả lời. Xem chuyện gì xảy ra nhé! | Same term as answersClosed |
| i18n.ts | `lkNone` | de | Für diese Frage ist Schluss. | Antworten für diese Frage geschlossen. | Same term as lkWatch; "Schluss" sounds abrupt |
| i18n.ts | `rvRightSmall` | vi | {n} trên {m} người trong phòng cũng vậy | {n}/{m} người trong phòng cũng vậy | Same N/M style |
| i18n.ts | `rvLearn` | de | Diesmal nicht. Darum: | Diesmal nicht. Das ist der Grund | Same EN as learnTitle: one DE wording |
| i18n.ts | `rvMissedPlain` | vi | Chuyện đã xảy ra | Đây là những gì đã xảy ra | Natural |
| i18n.ts | `rvPipWent` | de | Ich war für {x}. Auf zur nächsten! | Ich hatte {x}. Auf zur nächsten! | "war für" = was in favour of (opinion) |
| i18n.ts | `hfDrink` | de | Zeit für ein Getränk. Hier sind deine Antworten. | Zeit für was zu trinken. Hier sind deine Antworten. | Literal; colloquial German |
| i18n.ts | `hfThanks` | vi | Cảm ơn đã cùng xem. | Cảm ơn bạn đã cùng xem. | Needs a subject to sound warm |
| i18n.ts | `hfBefore` | de | vor deiner Zeit | bevor du da warst | "vor deiner Zeit" = before you were born/your era |
| i18n.ts | `hfShare` | de | Unsere Spielkarte teilen | Unsere Spiel-Übersicht teilen | "Spielkarte" = playing card |
| i18n.ts | `hfShare` | vi | Chia sẻ thẻ trận đấu | Chia sẻ tóm tắt trận đấu | "Thẻ" in football = yellow/red card |
| i18n.ts | `ovReconn` | de | Verbinde wieder mit Raum {code} … | Verbinde neu mit Raum {code} … | Same as stNoRoom |
| i18n.ts | `ovQuiet` | de | Der Fernseher ist still | Der Fernseher meldet sich nicht mehr | Same as stTvQuiet |
| i18n.ts | `ovQuiet` | vi | TV đang im lặng | TV không phản hồi | Same as stTvQuiet |
| i18n.ts | `ovQuietFix` | vi | Cách sửa trên TV: | Để sửa trên TV: | Natural |
| halfTime.ts | `corner` | de | Schlägt ein Verteidiger den Ball über die eigene Torlinie ins Aus, startet der Angriff von der Ecke des Spielfelds neu. | Spielt ein Verteidiger den Ball über die eigene Torlinie ins Aus, geht es für die Angreifer mit einer Ecke von der Eckfahne weiter. | "der Angriff startet neu" is unidiomatic |
| halfTime.ts | `corner` | vi | Khi hậu vệ đưa bóng ra ngoài đường biên ngang của chính mình, đội tấn công được đá bóng từ góc sân. | Khi hậu vệ đưa bóng ra ngoài đường biên ngang phần sân nhà, đội tấn công được đá bóng từ góc sân. | "của chính mình" is ambiguous |
| halfTime.ts | `substitution` | de | Einwechslung | Spielerwechsel | Covers both on and off; TRIGGER uses "Wechsel" |
| halfTime.ts | `substitution` | de | Der Trainer ersetzt einen müden oder taktisch ungeeigneten Spieler durch einen frischen von der Bank. | Der Trainer ersetzt einen müden Spieler oder wechselt aus taktischen Gründen einen frischen Spieler von der Bank ein. | "ungeeignet" grades a player (rule 8) |
| halfTime.ts | `substitution` | vi | Huấn luyện viên đổi một cầu thủ mệt hoặc không còn phù hợp chiến thuật bằng người mới từ ghế dự bị. | Huấn luyện viên thay một cầu thủ đã mệt, hoặc vì lý do chiến thuật, bằng người mới từ ghế dự bị. | "không còn phù hợp" grades a player (rule 8) |
| whoThat.ts | `passes` | de | Pässe angekommen | Angekommene Pässe | Label word order |
| whoThat.ts | `hardPasses` | de | Schwere Pässe angekommen | Angekommene schwere Pässe | Label word order |
| whoThat.ts | `saves` | vi | Cú cản phá | Cứu thua | Standard VI stat term |
| whoThat.ts | `cameOn` | de | Eingewechselt in der | Eingewechselt | Code appends " 63'": "in der 63'" is broken German |
| whoThat.ts | `wentOff` | de | Ausgewechselt in der | Ausgewechselt | Code appends " 63'": "in der 63'" is broken German |
| whoThat.ts | `cameOn` | vi | Vào sân phút | Vào sân | Code appends " 63'": "phút 63'" doubles the minute |
| whoThat.ts | `wentOff` | vi | Rời sân phút | Rời sân | Code appends " 63'": "phút 63'" doubles the minute |
| whoThat.ts | `passer` | de | Nummer {n} hat bisher die meisten Pässe für {team} gespielt, die ankamen: {v}. | Nummer {n} hat bisher die meisten angekommenen Pässe für {team}: {v}. | Clunky relative clause |
| whoThat.ts | `fastest` | vi | Số {n} đến giờ là cầu thủ nhanh nhất: {v} km/h ở tốc độ tối đa. | Số {n} đến giờ là cầu thủ nhanh nhất: tốc độ tối đa {v} km/h. | Word order |
| whoThat.ts | `ground` | vi | Số {n} đến giờ chạy nhiều nhất của {team}: {v} km. | Số {n} đến giờ là người chạy nhiều nhất của {team}: {v} km. | Grammar |
| whoThat.ts | `FW` | de | Nummer {n}, ein Stürmer: der Spieler am nächsten zum Tor, der trifft und Chancen vorbereitet. | Nummer {n}, ein Stürmer: spielt am nächsten am Tor und soll treffen und Chancen vorbereiten. | "der trifft" claims he scores; EN says it is his job |
| whoThat.ts | `topSpeed` | vi | Tốc độ cao nhất đến giờ: {v} km/h | Tốc độ tối đa đến giờ: {v} km/h | Same term as STAT_LABEL topSpeed |
| addedTime.ts | `VAR` | de | VAR-Prüfungen | VAR-Checks | One term (mVar "VAR-Check") |
| didYouKnow.ts | `fact: VAR can only` | de | Der VAR darf nur bei vier Dingen eingreifen: Tore, Elfmeter, glatte Rote Karten und Verwechslungen. | Der VAR darf nur in vier Fällen eingreifen: bei Toren, Elfmetern, glatten Roten Karten und Spielerverwechslungen. | Grammar ("bei" + dative) |
| didYouKnow.ts | `fact: For handball` | de | Beim Handspiel beginnt der Arm unten an der Achsel. Die Schulter zählt nicht. | Beim Handspiel zählt der Arm erst ab der Unterkante der Achsel. Die Schulter zählt nicht. | Clearer rule wording |
| didYouKnow.ts | `fact: Defenders must stand ten` | vi | Hậu vệ phải đứng cách cung phạt góc mười thước Anh cho tới khi bóng được đá. | Hậu vệ phải đứng cách cung phạt góc mười yard (hơn chín mét) cho tới khi bóng được đá. | "thước Anh" is archaic; VI media use metres |
| didYouKnow.ts | `fact: The wall must stand` | de | Die Mauer muss zehn Yards vom Ball entfernt stehen. Die Sprühlinie des Schiedsrichters zeigt die Stelle. | Die Mauer muss zehn Yards vom Ball entfernt stehen. Die Linie aus dem Freistoßspray markiert die Stelle. | "Freistoßspray" is the German term |
| didYouKnow.ts | `fact: The wall must stand` | vi | Hàng rào phải đứng cách bóng mười thước Anh. Vạch sơn xịt của trọng tài đánh dấu chỗ đó. | Hàng rào phải đứng cách bóng mười yard (hơn chín mét). Vạch sơn xịt của trọng tài đánh dấu chỗ đó. | "thước Anh" is archaic |
| cards.json | `corner.question.options.near.label` | de | Nahpfosten | Erster Pfosten | "Nahpfosten" is not used; broadcast German says erster/zweiter Pfosten |
| cards.json | `corner.question.options.far.label` | de | Fernpfosten | Zweiter Pfosten | Same |
| cards.json | `corner.question.options.short.label` | vi | Ngắn | Đá ngắn | Matches the reveal "Đá ngắn!"; "Ngắn" alone is unclear |
| cards.json | `corner.reveal.short.plain.0` | de | Kurz! <team> spielte zu einem nahen Mitspieler, statt zu flanken. | Kurz! <team> passte zu einem Mitspieler in der Nähe, statt zu flanken. | "nahen Mitspieler" = close friend |
| cards.json | `corner.reveal.short.plain.2` | vi | Chuyền ngắn! Bóng ở lại gần cờ góc, <team> triển khai pha bóng từ đó. | Phạt góc ngắn! Bóng ở lại gần cờ góc, <team> triển khai pha bóng từ đó. | Corner short = đá/phạt góc ngắn, not a pass |
| cards.json | `corner.reveal.short.expert` | vi | Hôm nay <team> đã đá ngắn {corners_short}/{corners_total} quả phạt góc. Trung bình giải khoảng {league_short_share_pct}%. | Hôm nay <team> đã đá ngắn {corners_short}/{corners_total} quả phạt góc. Trung bình toàn giải là khoảng {league_short_share_pct}%. | Grammar |
| cards.json | `corner.reveal.near.expert` | vi | Hôm nay <team> đã đá ngắn {corners_short}/{corners_total} quả phạt góc. Trung bình giải khoảng {league_short_share_pct}%. | Hôm nay <team> đã đá ngắn {corners_short}/{corners_total} quả phạt góc. Trung bình toàn giải là khoảng {league_short_share_pct}%. | Grammar |
| cards.json | `corner.reveal.far.expert` | vi | Hôm nay <team> đã đá ngắn {corners_short}/{corners_total} quả phạt góc. Trung bình giải khoảng {league_short_share_pct}%. | Hôm nay <team> đã đá ngắn {corners_short}/{corners_total} quả phạt góc. Trung bình toàn giải là khoảng {league_short_share_pct}%. | Grammar |
| cards.json | `corner.reveal.central.expert` | vi | Hôm nay <team> đã đá ngắn {corners_short}/{corners_total} quả phạt góc. Trung bình giải khoảng {league_short_share_pct}%. | Hôm nay <team> đã đá ngắn {corners_short}/{corners_total} quả phạt góc. Trung bình toàn giải là khoảng {league_short_share_pct}%. | Grammar |
| cards.json | `corner.reveal.near.plain.0` | de | Nahpfosten! Der Ball kam auf den Pfosten, der der Eckfahne am nächsten ist. | Erster Pfosten! Der Ball kam an den Pfosten, der der Eckfahne am nächsten ist. | New option term; "an den Pfosten" |
| cards.json | `corner.reveal.near.plain.1` | de | Nahpfosten! <team> zielte auf den Pfosten, der der Ecke am nächsten ist. | Erster Pfosten! <team> zielte auf den Pfosten nahe der Ecke. | New option term; shorter |
| cards.json | `corner.reveal.near.plain.2` | de | Es ist der Nahpfosten! Die Hereingabe landete vor dem Pfosten, der dem Schützen am nächsten ist. | Erster Pfosten also! Die Hereingabe landete vor dem Pfosten, der dem Schützen am nächsten ist. | "Es ist der …" is a calque of "it is" |
| cards.json | `corner.reveal.near.plain.2` | vi | Là cột gần! Quả tạt rơi trước cột gần người đá nhất. | Cột gần đấy! Quả tạt rơi trước cột gần người đá nhất. | "Là cột gần!" is a calque of "it is" |
| cards.json | `corner.reveal.far.plain.0` | de | Fernpfosten! Der Ball flog zum Pfosten, der am weitesten von der Eckfahne entfernt ist. | Zweiter Pfosten! Der Ball flog zum Pfosten, der am weitesten von der Eckfahne entfernt ist. | New option term |
| cards.json | `corner.reveal.far.plain.1` | de | Fernpfosten! <team> schlug ihn quer durch den Strafraum. | Zweiter Pfosten! <team> schlug den Ball quer durch den Strafraum. | New option term; "ihn" had no referent |
| cards.json | `corner.reveal.far.plain.2` | de | Es ist der Fernpfosten! Die Hereingabe flog am nahen Pfosten vorbei auf die andere Seite. | Zweiter Pfosten also! Die Hereingabe flog am ersten Pfosten vorbei auf die andere Seite. | Calque; new option term |
| cards.json | `corner.reveal.far.plain.2` | vi | Là cột xa! Quả tạt bay qua cột gần sang phía bên kia. | Cột xa đấy! Quả tạt bay qua cột gần sang phía bên kia. | Calque of "it is" |
| cards.json | `corner.reveal.central.plain.0` | vi | Giữa! <team> đưa quả phạt góc vào khoảng trống trước khung thành. | Khu giữa! <team> đưa quả phạt góc vào khoảng trống trước khung thành. | "Giữa!" alone is unclear as an exclamation |
| cards.json | `corner.reveal.void.plain.0` | vi | Hàng thủ đánh đầu đẩy bóng đi trước khi nó tới được ai. | Hàng thủ đánh đầu phá bóng trước khi nó tới chân ai. | Football term "phá bóng" |
| cards.json | `corner.reveal.void.expert` | de | Keine Hereingabe erreichte eine Zone: Ein Verteidiger klärte aus dem Torraum, oder die Ecke wurde neu getreten. | Die Hereingabe erreichte keine der Zonen: Ein Verteidiger klärte im Torraum, oder die Ecke wurde neu getreten. | Natural |
| cards.json | `corner.reveal.void.expert` | vi | Không quả tạt nào tới được khu vực: hậu vệ phá bóng từ trong khu vòng cấm nhỏ, hoặc quả phạt góc được đá lại. | Quả tạt không tới được khu vực nào: hậu vệ phá bóng ngay trong vòng cấm nhỏ, hoặc quả phạt góc được đá lại. | Natural; "khu vòng cấm nhỏ" redundant |
| cards.json | `free_kick.question.text.1` | de | Freistoß für <team>. Was probieren sie? | Freistoß für <team>. Was haben sie vor? | Natural |
| cards.json | `free_kick.question.options.cross.label` | vi | Tạt | Tạt bóng | "Tạt" alone is clipped; matches reveals |
| cards.json | `free_kick.reveal.shoot.plain.0` | vi | Sút! <team> sút thẳng vào khung thành. | Sút! <team> dứt điểm thẳng vào khung thành. | Avoids "Sút … sút" |
| cards.json | `free_kick.reveal.shoot.plain.4` | vi | Sút! <team> thử vận may vào khung thành từ quả đá phạt. | Sút! <team> thử dứt điểm từ quả đá phạt. | "thử vận may" = try one's luck (gambling connotation) |
| cards.json | `free_kick.reveal.void.plain.0` | de | Das Spiel wurde gestoppt, bevor der Ball jemanden erreichte, also gab es kein Ergebnis. | Das Spiel wurde gestoppt, bevor der Ball jemanden erreichte, also gibt es nichts zu prüfen. | "Ergebnis" = match score; EN says nothing to check |
| cards.json | `free_kick.reveal.void.expert` | de | Der Freistoß erreichte keine Option: Er wurde neu ausgeführt, oder das Spiel wurde vorher gestoppt. | Der Freistoß passte zu keiner Antwort: Er wurde neu ausgeführt, oder das Spiel wurde vorher gestoppt. | "erreichte keine Option" is a calque |
| cards.json | `free_kick.reveal.void.expert` | vi | Quả đá phạt không tới được lựa chọn nào: được đá lại, hoặc trận đấu dừng trước khi bóng đi xa. | Quả đá phạt không khớp với lựa chọn nào: được đá lại, hoặc trận đấu dừng trước khi bóng đi xa. | Calque |
| cards.json | `substitution.question.text.1` | de | Wechsel bei <team>. Was bedeutet er? | Wechsel bei <team>. Was heißt das? | Natural |
| cards.json | `substitution.question.text.1` | vi | <team> thay người. Điều đó có nghĩa là gì? | Thay người bên phía <team>. Điều đó có ý nghĩa gì? | Varies from text[0]; natural |
| cards.json | `substitution.question.text.4` | vi | <team> thay người để tạo thay đổi. Họ nghĩ gì? | <team> thay người để làm mới lối chơi. Họ tính gì đây? | "thay … thay đổi" repetition; natural |
| cards.json | `substitution.question.options.attack.label` | de | Angreifen | Offensive | Natural label; reveals start with it |
| cards.json | `substitution.question.options.defend.label` | de | Verteidigen | Defensive | Same |
| cards.json | `substitution.question.options.fresh.label` | vi | Thêm sức | Tiếp sức | Idiomatic for "fresh legs" |
| cards.json | `substitution.reveal.attack.plain.0` | de | Angreifen! Ein Stürmer kommt, also hat <team> mehr Optionen im Angriff. | Offensive! Ein Stürmer kommt, also hat <team> mehr Optionen im Angriff. | New option label |
| cards.json | `substitution.reveal.attack.plain.1` | de | Angreifen! Ein Stürmer kommt, <team> will mehr Chancen herausspielen. | Offensive! Ein Stürmer kommt, <team> will mehr Chancen herausspielen. | New option label |
| cards.json | `substitution.reveal.defend.plain.0` | de | Verteidigen! Ein Verteidiger kommt, also hat <team> mehr Absicherung hinten. | Defensive! Ein Verteidiger kommt, also hat <team> hinten mehr Absicherung. | New option label; word order |
| cards.json | `substitution.reveal.defend.plain.1` | de | Verteidigen! Ein Verteidiger ist drin, <team> stärkt die Abwehrreihe. | Defensive! Ein Verteidiger kommt rein, <team> stärkt die Abwehrreihe. | New option label |
| cards.json | `substitution.reveal.defend.plain.0` | vi | Phòng ngự! Một hậu vệ vào sân, nên <team> chắc chắn hơn ở phía sau. | Phòng ngự! Một hậu vệ vào sân, nên <team> chắc chắn hơn ở hàng thủ. | Football term |
| cards.json | `substitution.reveal.defend.plain.2` | vi | An toàn trước! <team> đưa một hậu vệ vào để chắc chắn hơn. | An toàn là trên hết! <team> đưa một hậu vệ vào để chắc chắn hơn. | Idiom |
| cards.json | `substitution.reveal.fresh.plain.0` | vi | Thêm sức! Một tiền vệ vào sân để giữ nhịp độ. | Tiếp sức! Một tiền vệ vào sân để giữ nhịp độ. | New option label |
| cards.json | `substitution.reveal.fresh.plain.1` | vi | Thêm sức! Một tiền vệ vào sân, <team> giữ cho khu giữa sân luôn sôi động. | Tiếp sức! Một tiền vệ vào sân, <team> giữ cho khu giữa sân luôn sôi động. | New option label |
| cards.json | `var.question.text.0` | de | Der VAR prüft. Was wird geprüft? | Der VAR prüft. Worum geht es? | "prüft … geprüft" repetition |
| cards.json | `var.question.text.0` | vi | VAR đang kiểm tra. Họ xem điều gì? | VAR đang kiểm tra. Họ đang xem tình huống gì? | Natural |
| cards.json | `var.reveal.offside:overturned.plain.0` | vi | Việt vị. Lúc đường chuyền được thực hiện, tiền đạo đứng trước hậu vệ cuối cùng. Bàn thắng bị hủy. | Việt vị. Lúc đường chuyền được thực hiện, cầu thủ tấn công đứng trước hậu vệ cuối cùng. Bàn thắng bị hủy. | EN "attacker" = cầu thủ tấn công (not only forwards) |
| cards.json | `var.reveal.offside:overturned.plain.1` | vi | Việt vị! Lúc chuyền bóng, tiền đạo đứng trước hậu vệ cuối cùng, nên không có bàn thắng. | Việt vị! Lúc chuyền bóng, cầu thủ tấn công đứng trước hậu vệ cuối cùng, nên không có bàn thắng. | Same |
| cards.json | `var.reveal.offside:overturned.expert` | de | Abseits um {var_margin_cm} cm, bewertet im Bild des Passes. | Abseits um {var_margin_cm} cm, gemessen im Moment der Ballabgabe. | "im Bild des Passes" is a calque |
| cards.json | `var.reveal.offside:stands.plain.0` | de | Abseits-Prüfung. Der Angreifer stand auf einer Höhe oder dahinter, das Tor zählt. | Abseits-Check. Der Angreifer stand auf gleicher Höhe mit dem letzten Verteidiger oder dahinter, das Tor zählt. | "auf einer Höhe" had no reference point; one term VAR-Check |
| cards.json | `var.reveal.offside:stands.plain.0` | vi | Kiểm tra việt vị. Tiền đạo ngang hoặc sau hậu vệ cuối cùng, nên bàn thắng được công nhận. | Kiểm tra việt vị. Cầu thủ tấn công đứng ngang hoặc sau hậu vệ cuối cùng, nên bàn thắng được công nhận. | Attacker term; missing verb |
| cards.json | `var.reveal.offside:stands.plain.1` | vi | Không việt vị! Tiền đạo không đứng trước hậu vệ cuối cùng, nên bàn thắng được công nhận. | Không việt vị! Cầu thủ tấn công không đứng trước hậu vệ cuối cùng, nên bàn thắng được công nhận. | Attacker term |
| cards.json | `var.reveal.offside:stands.expert` | de | Nicht im Abseits, um {var_margin_cm} cm, bewertet im Bild des Passes. | Kein Abseits, mit {var_margin_cm} cm Luft, gemessen im Moment der Ballabgabe. | "Nicht im Abseits, um X cm" is broken |
| cards.json | `var.reveal.offside:stands.expert` | vi | Không việt vị {var_margin_cm} cm, xét theo khung hình lúc chuyền bóng. | Không việt vị, còn cách {var_margin_cm} cm, xét theo khung hình lúc chuyền bóng. | "Không việt vị X cm" reads as "not offside by X cm" (wrong) |
| cards.json | `var.reveal.foul:stands.plain.0` | de | Foul-Prüfung. Kein klares Foul gefunden, das Tor zählt. | Foul-Check. Kein klares Foul gefunden, das Tor zählt. | One term VAR-Check |
| cards.json | `var.reveal.foul:stands.plain.1` | de | Kein Foul! Der Video-Schiedsrichter sah nichts Klares, das Tor zählt. | Kein Foul! Der Video-Schiedsrichter sah kein klares Vergehen, das Tor zählt. | "nichts Klares" is unidiomatic |
| cards.json | `var.reveal.foul:overturned.plain.1` | vi | Có phạm lỗi! Pha triển khai có điều không được phép, nên bàn thắng bị hủy. | Có phạm lỗi! Trong pha triển khai có tình huống không hợp lệ, nên bàn thắng bị hủy. | Natural |

## Open points for the owner

1. **German "Raum" for the group of people.** "Raum" is right for the object (room code, tab, "Raum starten"). Used for people ("Der Raum sagte", "Das sagte der Raum", "{n} von {m} im Raum auch") it is understandable but a little technical. Option: use "die Runde" for the people sense. Not changed, so the term stays consistent with the tab.
2. **Vietnamese "cả phòng" vs "cả nhà".** "Cả nhà" (the whole household) is warmer for a living room, but "phòng" is the app's object. I unified on "cả phòng". Switching back is a one-word change in 6 strings.
3. **"Call it!" = "Sag's an!" / "Đoán đi!".** Both are fine. "Đoán" means "guess", which suits newcomers. "Sag's an!" pairs with the tagline "Zusammen ansagen". Alternative DE: "Was meinst du?"
4. **Substitution options in DE** are now "Offensive / Defensive / Frische Beine". Alternative: "Mehr Angriff / Mehr Abwehr / Frische Beine".
5. **"zehn Yards" (DE) / "mười yard (hơn chín mét)" (VI)** in the rule facts. German fans usually say "9,15 Meter", but the copy avoids digits. Keep the yards, or allow the digits in the static rule facts?
6. **"Pip" as "ich" (DE) / "mình" (VI)** in reveal lines. Kept. "Mình" is used only for Pip; `hlIntro` ("We watch…") was changed to "Chúng ta" so "mình" never means "we".
7. **Generic masculine in DE** ("ein Stürmer", "dein Spieler", "Torschütze"). Kept as standard football German. The animal pattern "Dein Tier: {name}" is kept, so no article is needed.
8. **Southern vs northern VI words**: "Heo" (pig) is kept; the northern form is "Lợn". "Ai đấy?" became the neutral "Đó là ai?".
9. **`followLine` in `whoThat.ts`** builds "… Pässe angekommen, … km gelaufen" in a code template literal. I did not touch it because it is code. It reads acceptably, but it does not match the new label "Angekommene Pässe".
10. **"Highlights"** stays "Highlights" in DE (common usage) and "Điểm nhấn" in VI. "Tóm tắt" would also work in VI, but it is now used for the half-time recap.

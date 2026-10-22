import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { hasRoomServer } from "../lib/channel";
import { deviceLang, fmt, ui } from "../lib/i18n";
import type { Lang } from "../lib/types";

// Room codes use these characters only (lib/match.ts randomRoom): no I, O, 0 or 1 to mix up.
const CODE_CHAR = /[ABCDEFGHJKLMNPQRSTUVWXYZ2-9]/g;

/** Type the four characters from the TV (room prototype "Type code") with the phone's own keyboard (iOS / Android).
 *  The field keeps only room-code characters, so it is never free text.
 *  A code with no open room gets a plain-words error and the QR as a second way in. */
export default function Join() {
  const nav = useNavigate();
  const [lang] = useState<Lang>(deviceLang);
  const [code, setCode] = useState("");
  const [state, setState] = useState<"typing" | "looking" | "none">("typing");

  const check = async (c: string) => {
    setState("looking");
    try {
      // 404 = no TV has opened this room. Anything else (or no room server: the single-device demo) = go and see.
      if ((await hasRoomServer()) && (await fetch(`/api/rooms/${c}/state`, { cache: "no-store" })).status === 404) return setState("none");
    } catch {
      /* offline or no server: let the room screen say what is wrong */
    }
    nav(`/play/${c}`);
  };
  const field = useRef<HTMLInputElement>(null);
  const type = (raw: string) => {
    setCode((raw.toUpperCase().match(CODE_CHAR) ?? []).join("").slice(0, 4));
    setState("typing");
  };
  // The fourth character starts the check.
  useEffect(() => {
    if (code.length === 4 && state === "typing") void check(code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);
  const retry = () => {
    setCode("");
    setState("typing");
    field.current?.focus();
  };

  return (
    <div className="q-ph">
      <div className="q-top"><button className="q-back" onClick={() => nav("/")}>‹ {ui("back", lang)}</button></div>
      <h2>{ui("jnTitle", lang)}</h2>
      {/* The four boxes show the code; a real text field on top of them opens the system keyboard in capitals. */}
      <label className="q-code" aria-live="polite">
        {[0, 1, 2, 3].map((i) => <span key={i} className={code[i] ? "on" : i === code.length ? "caret" : ""}>{code[i] ?? ""}</span>)}
        <input
          ref={field}
          className="q-code-input"
          value={code}
          onChange={(e) => type(e.target.value)}
          aria-label={ui("jnTitle", lang)}
          autoFocus
          inputMode="text"
          autoCapitalize="characters"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="go"
          maxLength={4}
        />
      </label>
      {state === "none" ? (
        <>
          <div className="q-err" role="alert"><b>!</b><span>{fmt(ui("jnNoRoom", lang), { code })}</span></div>
          <button className="q-btn soft" onClick={retry}>{ui("jnRetry", lang)}</button>
        </>
      ) : state === "looking" ? (
        <p className="q-small q-muted">{fmt(ui("jnLooking", lang), { code })}</p>
      ) : (
        <p className="q-small q-muted">{ui("jnScan", lang)}</p>
      )}
      <div className="q-fill" />
      <button className="q-btn ghost" onClick={() => nav("/scan")}>{ui("scOr", lang)}</button>
    </div>
  );
}

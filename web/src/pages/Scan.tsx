import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fmt, ui } from "../lib/i18n";
import { useLang } from "../lib/lang";
import { ROOM_RE } from "../lib/match";

/** The room code inside a Pip link ("https://…/play/ABCD"), or null. Only the four-character code is kept: the rest of
 *  the text (from a QR or the clipboard) is never shown, stored or sent anywhere. */
export function roomFromLink(text: string): string | null {
  const m = text.trim().match(/\/play\/([A-Za-z0-9]{4})(?![A-Za-z0-9])/);
  const code = m?.[1].toUpperCase() ?? "";
  return ROOM_RE.test(code) ? code : null;
}

type Detect = (video: HTMLVideoElement) => Promise<string | null>;

/** Reads QR codes from the video: the browser's own reader where there is one (Chrome on Android), otherwise jsQR,
 *  loaded only here (Safari on iPhone has no built-in reader). Frames stay on the phone. */
async function makeDetector(): Promise<Detect> {
  const BD = (window as unknown as { BarcodeDetector?: new (o: { formats: string[] }) => { detect: (s: CanvasImageSource) => Promise<{ rawValue: string }[]> } }).BarcodeDetector;
  if (BD) {
    try {
      const d = new BD({ formats: ["qr_code"] });
      return async (v) => (await d.detect(v))[0]?.rawValue ?? null;
    } catch {
      /* listed but not working: use jsQR */
    }
  }
  const jsQR = (await import("jsqr")).default;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  return async (v) => {
    if (!ctx || !v.videoWidth) return null;
    const scale = Math.min(1, 640 / Math.max(v.videoWidth, v.videoHeight)); // smaller frames read faster
    canvas.width = Math.round(v.videoWidth * scale);
    canvas.height = Math.round(v.videoHeight * scale);
    ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
    const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
    return jsQR(img.data, img.width, img.height, { inversionAttempts: "dontInvert" })?.data ?? null;
  };
}

const GIVE_UP_MS = 15_000; // no Pip code seen this long: offer the other ways in

/** Scan the TV's QR (room prototype "Scan QR"). When the camera is blocked, missing, or finds nothing, it falls back
 *  ("QR not found") to pasting an invite link a friend copied (Room → Invite → Copy invite link) or typing the code. */
export default function Scan() {
  const nav = useNavigate();
  const [lang] = useLang();
  const video = useRef<HTMLVideoElement>(null);
  const [found, setFound] = useState<string | null>(null);
  const [notPip, setNotPip] = useState(false);
  const [trouble, setTrouble] = useState<null | "camera" | "slow">(null);
  const [pasteMsg, setPasteMsg] = useState<string | null>(null);

  useEffect(() => {
    if (trouble === "camera") return;
    let stream: MediaStream | null = null;
    let stopped = false;
    let timer = 0;
    const started = Date.now();
    (async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("no camera API (needs https)");
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        if (stopped) return;
        const v = video.current!;
        v.srcObject = stream;
        await v.play();
        const detect = await makeDetector();
        const tick = async () => {
          if (stopped) return;
          try {
            const text = await detect(v);
            if (text) {
              const code = roomFromLink(text);
              setNotPip(!code);
              if (code) setFound(code);
            }
          } catch {
            /* a bad frame: try the next one */
          }
          if (Date.now() - started > GIVE_UP_MS) setTrouble((t) => t ?? "slow");
          timer = window.setTimeout(tick, 200);
        };
        void tick();
      } catch {
        if (!stopped) setTrouble("camera"); // permission denied, no camera, or not https
      }
    })();
    return () => {
      stopped = true;
      clearTimeout(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [trouble === "camera"]); // eslint-disable-line react-hooks/exhaustive-deps

  const paste = async () => {
    try {
      const code = roomFromLink(await navigator.clipboard.readText());
      if (code) return nav(`/play/${code}`);
    } catch {
      /* clipboard blocked: say so below */
    }
    setPasteMsg(ui("scPasteNone", lang));
  };

  return (
    <div className="q-ph q-scan">
      <div className="q-top"><button className="q-back" onClick={() => nav(-1)}>‹ {ui("back", lang)}</button><span className="q-mono">{ui("scCamera", lang)}</span></div>
      <div className={`q-camera ${trouble ? "small" : ""}`}>
        {trouble !== "camera" && <video ref={video} playsInline muted aria-hidden="true" />}
        <div className={`q-frame ${trouble ? "dashed" : ""}`}>{trouble === "camera" && <span>{ui("scNoCamera", lang)}</span>}</div>
        {(found || notPip) && trouble !== "camera" && (
          found
            ? <button className="q-found" onClick={() => nav(`/play/${found}`)}>{fmt(ui("scFound", lang), { code: found })}</button>
            : <div className="q-found">{ui("scNotPip", lang)}</div>
        )}
      </div>
      {trouble ? (
        <>
          <div className="q-card q-stack-tight">
            <b>{ui("scTrouble", lang)}</b>
            <span className="q-small q-muted">· {ui("scTip1", lang)}</span>
            <span className="q-small q-muted">· {ui("scTip2", lang)}</span>
          </div>
          {pasteMsg && <div className="q-err" role="alert"><b>!</b><span>{pasteMsg}</span></div>}
          <button className="q-btn ghost q-on-dark" onClick={paste}>{ui("scPaste", lang)}</button>
          <button className="q-btn q-light" onClick={() => nav("/join")}>{ui("scType", lang)}</button>
        </>
      ) : (
        <>
          <p className="q-small q-center q-scan-hint">{ui("scPoint", lang)}</p>
          <p className="q-small q-center q-scan-hint">{ui("scPrivate", lang)}</p>
        </>
      )}
    </div>
  );
}

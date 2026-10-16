import { useEffect, useRef } from "react";
import type { Msg } from "./types";

/** Single-device demo mode: TV and phones talk through BroadcastChannel (same browser, same origin).
 *  Later: Azure Web PubSub or polling (OPEN question 3) — keep this file as the only transport. */
export function useRoomChannel(room: string, onMessage: (m: Msg) => void) {
  const chan = useRef<BroadcastChannel | null>(null);
  const handler = useRef(onMessage);
  handler.current = onMessage;

  useEffect(() => {
    const c = new BroadcastChannel(`pippi:${room}`);
    c.onmessage = (e: MessageEvent<Msg>) => {
      if (e.data && typeof e.data === "object" && "t" in e.data) handler.current(e.data);
    };
    chan.current = c;
    return () => {
      c.close();
      chan.current = null;
    };
  }, [room]);

  return (m: Msg) => chan.current?.postMessage(m);
}

export function deviceId(): string {
  try {
    let id = sessionStorage.getItem("pippi:device");
    if (!id) {
      id = Math.random().toString(36).slice(2, 10);
      sessionStorage.setItem("pippi:device", id);
    }
    return id;
  } catch {
    return Math.random().toString(36).slice(2, 10);
  }
}

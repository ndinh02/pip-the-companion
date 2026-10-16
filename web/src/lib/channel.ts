import { useCallback, useEffect, useRef } from "react";
import type { Msg, StateMsg } from "./types";

/** The ONE transport boundary between the shared screen and the phones.
 *
 *  - Hosted (our Node server, see web/server/rooms.mjs): HTTP polling, so phones on any network can join.
 *  - Local `npm run dev` (no server): single-device demo mode over BroadcastChannel (same browser only).
 *
 *  Screens call `useRoomChannel(room, role, onMessage)` and get a stable `send`. They never see which mode runs. */
export type Role = "tv" | "phone";

const TV_POLL_MS = 700; // how often the screen collects answers
const PHONE_POLL_MS = 1000; // how often a phone asks what is on screen

let serverCheck: Promise<boolean> | null = null;
/** True when the page is served by our Node server (it answers /healthz with "ok"; the Vite dev server does not). */
function hasRoomServer(): Promise<boolean> {
  serverCheck ??= fetch("/healthz", { cache: "no-store" })
    .then(async (r) => r.ok && (await r.text()).trim() === "ok")
    .catch(() => false);
  return serverCheck;
}

const tokenKey = (room: string) => `pip:tv-token:${room}`;
function readToken(room: string): string | null {
  try {
    return sessionStorage.getItem(tokenKey(room));
  } catch {
    return null;
  }
}
function saveToken(room: string, token: string) {
  try {
    sessionStorage.setItem(tokenKey(room), token);
  } catch {
    /* private mode: the token lives as long as this page */
  }
}

/** The screen's deadline is in its own clock. Over the network we send "ms left" instead, and the phone turns it
 *  back into its own clock (minus how old the state is), so device clocks do not need to agree. */
type Wire = StateMsg & { remaining_ms?: number };

export function useRoomChannel(room: string, role: Role, onMessage: (m: Msg) => void) {
  const handler = useRef(onMessage);
  handler.current = onMessage;
  const sender = useRef<(m: Msg) => void>(() => undefined);

  useEffect(() => {
    let stopped = false;
    let cleanup = () => undefined as void;

    hasRoomServer().then((remote) => {
      if (stopped) return;
      if (!remote) {
        // ---- single-device mode -------------------------------------------------------------------------------
        const c = new BroadcastChannel(`pip:${room}`);
        c.onmessage = (e: MessageEvent<Msg>) => {
          if (e.data && typeof e.data === "object" && "t" in e.data) handler.current(e.data);
        };
        sender.current = (m) => c.postMessage(m);
        cleanup = () => c.close();
        return;
      }

      const base = `/api/rooms/${encodeURIComponent(room)}`;
      const timers: number[] = [];
      if (role === "tv") {
        // ---- shared screen: claim the room, publish state, collect phone messages --------------------------------
        let token = readToken(room);
        let after = 0;
        let latest: StateMsg | null = null;
        let posting = false;
        const open = async () => {
          const r = await fetch(`${base}/open`, { method: "POST", headers: token ? { "x-room-token": token } : {} });
          if (r.status === 409) {
            // Another screen is live in this room: start a fresh one rather than fight over it.
            location.replace("/tv");
            return false;
          }
          if (!r.ok) return false;
          token = (await r.json()).token as string;
          saveToken(room, token);
          return true;
        };
        const publish = async () => {
          if (posting || !latest || !token) return;
          posting = true;
          const state = latest;
          latest = null;
          const wire: Wire = { ...state, remaining_ms: Math.max(0, state.deadline - Date.now()) };
          try {
            const r = await fetch(`${base}/state`, {
              method: "POST",
              headers: { "Content-Type": "application/json", "x-room-token": token },
              body: JSON.stringify(wire),
            });
            if (r.status === 403 || r.status === 404) await open(); // server restarted or woke up: reclaim
          } catch {
            latest ??= state; // offline for a moment: try again with the newest state
          } finally {
            posting = false;
            if (latest) void publish();
          }
        };
        void open();
        sender.current = (m) => {
          if (m.t !== "state") return;
          latest = m;
          void publish();
        };
        timers.push(
          window.setInterval(async () => {
            if (!token) return;
            try {
              const r = await fetch(`${base}/inbox?after=${after}`, { headers: { "x-room-token": token }, cache: "no-store" });
              if (r.status === 403 || r.status === 404) return void (await open());
              if (!r.ok) return;
              const data = (await r.json()) as { seq: number; msgs: Msg[] };
              after = data.seq;
              data.msgs.forEach((msg) => handler.current(msg));
            } catch {
              /* network blip: next poll */
            }
          }, TV_POLL_MS),
        );
      } else {
        // ---- phone: poll the screen's state, post answers ------------------------------------------------------
        let v = -1;
        sender.current = (m) => {
          if (m.t === "state") return;
          void fetch(`${base}/msg`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(m) }).catch(() => undefined);
        };
        const poll = async () => {
          try {
            const r = await fetch(`${base}/state?v=${v}`, { cache: "no-store" });
            if (r.status !== 200) return;
            const data = (await r.json()) as { v: number; state: Wire; age_ms: number };
            v = data.v;
            const { remaining_ms, ...state } = data.state;
            if (remaining_ms !== undefined) state.deadline = Date.now() + remaining_ms - data.age_ms;
            handler.current(state);
          } catch {
            /* network blip: next poll */
          }
        };
        void poll();
        timers.push(window.setInterval(poll, PHONE_POLL_MS));
      }
      cleanup = () => timers.forEach((t) => clearInterval(t));
    });

    return () => {
      stopped = true;
      cleanup();
      sender.current = () => undefined;
    };
  }, [room, role]);

  // Stable identity: screens can list `send` in effect dependencies without re-sending on every render.
  return useCallback((m: Msg) => sender.current(m), []);
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

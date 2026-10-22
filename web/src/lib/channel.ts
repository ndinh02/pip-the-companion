import { useCallback, useEffect, useRef } from "react";
import type { Msg, StateMsg } from "./types";

/** The ONE transport boundary between the shared screen and the phones.
 *
 *  - Hosted (our Node server, see web/server/rooms.mjs): HTTP polling, so phones on any network can join.
 *  - Local `npm run dev` (no server): single-device demo mode over BroadcastChannel (same browser only).
 *
 *  Screens call `useRoomChannel(room, role, onMessage)` and get a stable `send`. They never see which mode runs. */
export type Role = "tv" | "phone";
/** What a phone can tell about its link to the room (shown as a one-line bar, never as an error code).
 *  ok · offline (no network) · no-room (server restarted or the TV has not opened it yet) · tv-quiet (the TV tab
 *  was closed or lost its connection; the room is kept, owner decision 2026-10-23). */
export type RoomStatus = "ok" | "offline" | "no-room" | "tv-quiet";
const TV_QUIET_MS = 10_000; // the TV checks in every 0.7 s; ten silent seconds means it is gone

const TV_POLL_MS = 700; // how often the screen collects answers
const TV_ALARM_AFTER = 3; // failed tries in a row (about 2 s) before the TV shows its alarm
const PHONE_POLL_MS = 1000; // how often a phone asks what is on screen

let serverCheck: Promise<boolean> | null = null;
/** True when the page is served by our Node server (it answers /healthz with "ok"; the Vite dev server does not). */
/** True when the room server runs (hosted app); false in the single-device demo (Vite dev, tabs of one browser). */
export function hasRoomServer(): Promise<boolean> {
  serverCheck ??= fetch("/healthz", { cache: "no-store" })
    .then(async (r) => r.ok && (await r.text()).trim() === "ok")
    .catch(() => false);
  return serverCheck;
}

// The TV's room key lives in localStorage so a closed or reloaded TV tab can take its room back (owner decision
// 2026-10-23: OK under the privacy rule; it is a room key on the TV device, not an account or a tracker).
const tokenKey = (room: string) => `pip:tv-token:${room}`;
const LAST_ROOM_KEY = "pip:tv-last-room";
const RESUME_WITHIN_MS = 3 * 60 * 60 * 1000; // the server forgets an idle room after 4 h
function readToken(room: string): string | null {
  try {
    return localStorage.getItem(tokenKey(room));
  } catch {
    return null;
  }
}
function saveToken(room: string, token: string) {
  try {
    localStorage.setItem(tokenKey(room), token);
    localStorage.setItem(LAST_ROOM_KEY, JSON.stringify({ room, at: Date.now() }));
  } catch {
    /* private mode: the token lives as long as this page */
  }
}
/** The room this TV device ran recently, so opening /tv again resumes it instead of making a new code. */
export function lastTvRoom(): string | null {
  try {
    const v = JSON.parse(localStorage.getItem(LAST_ROOM_KEY) ?? "null") as { room?: string; at?: number } | null;
    return v?.room && v.at && Date.now() - v.at < RESUME_WITHIN_MS ? v.room : null;
  } catch {
    return null;
  }
}
// The key is shared by every tab on this device, so a second TV tab must not take over a room another tab is
// running (two screens would fight over the phones). The running tab stamps its room every poll.
const liveKey = (room: string) => `pip:tv-live:${room}`;
const LIVE_MS = 3_000;
const TAB = Math.random().toString(36).slice(2, 10);
function roomBusyHere(room: string): boolean {
  try {
    const v = JSON.parse(localStorage.getItem(liveKey(room)) ?? "null") as { tab?: string; at?: number } | null;
    return !!v && v.tab !== TAB && Date.now() - (v.at ?? 0) < LIVE_MS;
  } catch {
    return false;
  }
}
function clearLive(room: string) {
  try {
    const v = JSON.parse(localStorage.getItem(liveKey(room)) ?? "null") as { tab?: string } | null;
    if (v?.tab === TAB) localStorage.removeItem(liveKey(room));
  } catch {
    /* ignore */
  }
}
function stampLive(room: string) {
  try {
    localStorage.setItem(liveKey(room), JSON.stringify({ tab: TAB, at: Date.now() }));
  } catch {
    /* ignore */
  }
}
/** Called while the TV runs, so "recent" means "recently on screen", not "recently created". */
function touchLastRoom(room: string) {
  try {
    localStorage.setItem(LAST_ROOM_KEY, JSON.stringify({ room, at: Date.now() }));
  } catch {
    /* ignore */
  }
}

/** The screen's deadline is in its own clock. Over the network we send "ms left" instead, and the phone turns it
 *  back into its own clock (minus how old the state is), so device clocks do not need to agree. */
type Wire = StateMsg & { remaining_ms?: number };

export function useRoomChannel(room: string, role: Role, onMessage: (m: Msg) => void, onStatus?: (s: RoomStatus) => void) {
  const handler = useRef(onMessage);
  handler.current = onMessage;
  const statusHandler = useRef(onStatus);
  statusHandler.current = onStatus;
  const sender = useRef<(m: Msg) => void>(() => undefined);

  useEffect(() => {
    let stopped = false;
    let cleanup = () => undefined as void;
    let cleanupExtra = () => undefined as void;
    // Messages sent before we know which transport to use (e.g. a phone's first "hello") wait here, then go out.
    const early: Msg[] = [];
    sender.current = (m) => void early.push(m);
    const flushEarly = () => early.splice(0).forEach((m) => sender.current(m));

    hasRoomServer().then((remote) => {
      if (stopped) return;
      if (!remote) {
        // ---- single-device mode -------------------------------------------------------------------------------
        const c = new BroadcastChannel(`pip:${room}`);
        c.onmessage = (e: MessageEvent<Msg>) => {
          if (e.data && typeof e.data === "object" && "t" in e.data) handler.current(e.data);
        };
        sender.current = (m) => c.postMessage(m);
        flushEarly();
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
        // The TV is the alarm: after a few failed tries in a row it says so on screen; one good answer clears it.
        let failures = 0;
        let tvStatus: RoomStatus | null = null;
        const tvReport = (s: RoomStatus) => {
          if (s !== tvStatus) statusHandler.current?.((tvStatus = s));
        };
        const reached = () => {
          failures = 0;
          tvReport("ok");
        };
        const missed = () => {
          failures += 1;
          if (failures >= TV_ALARM_AFTER) tvReport("offline");
        };
        const open = async () => {
          if (roomBusyHere(room)) {
            location.replace("/tv?fresh=1"); // another TV tab on this device runs this room
            return false;
          }
          let r: Response;
          try {
            r = await fetch(`${base}/open`, { method: "POST", headers: token ? { "x-room-token": token } : {} });
          } catch {
            missed(); // server unreachable (down, or no network): keep trying from the poll
            return false;
          }
          if (r.status === 409) {
            // Another screen is live in this room: start a fresh one rather than fight over it.
            location.replace("/tv?fresh=1");
            return false;
          }
          if (!r.ok) {
            missed();
            return false;
          }
          reached();
          const next = (await r.json()).token as string;
          if (next !== token) after = 0; // a new room on the server (it restarted): its message numbers start again
          token = next;
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
            if (r.status === 403 || r.status === 404) {
              reached(); // the server answered, so it is up: reclaim the room
              await open();
            } else if (r.ok) reached();
            else missed();
          } catch {
            latest ??= state; // offline for a moment: try again with the newest state
            missed();
          } finally {
            posting = false;
            if (latest) void publish();
          }
        };
        void open();
        const leaving = () => clearLive(room); // a closed or reloaded tab can take its room straight back
        window.addEventListener("pagehide", leaving);
        cleanupExtra = () => window.removeEventListener("pagehide", leaving);
        sender.current = (m) => {
          if (m.t !== "state") return;
          latest = m;
          void publish();
        };
        flushEarly();
        timers.push(
          window.setInterval(async () => {
            if (!token) return void (await open()); // never claimed (server was down at start): keep trying
            try {
              const r = await fetch(`${base}/inbox?after=${after}`, { headers: { "x-room-token": token }, cache: "no-store" });
              if (r.status === 403 || r.status === 404) {
                reached();
                return void (await open());
              }
              if (!r.ok) {
                missed();
                return;
              }
              reached();
              const data = (await r.json()) as { seq: number; msgs: Msg[] };
              if (data.seq < after) {
                after = 0; // the server's count went backwards: it restarted under us. Read from the start next time.
                return;
              }
              after = data.seq;
              touchLastRoom(room);
              stampLive(room);
              data.msgs.forEach((msg) => handler.current(msg));
            } catch {
              missed(); // network blip or outage: the next poll tries again
            }
          }, TV_POLL_MS),
        );
      } else {
        // ---- phone: poll the screen's state, post answers ------------------------------------------------------
        let v = -1;
        let status: RoomStatus | null = null;
        const report = (s: RoomStatus) => {
          if (s !== status) statusHandler.current?.((status = s));
        };
        // Messages that did not get through (no network, or the server restarted) are sent again on the next good
        // poll. Only the newest of each kind is kept: an old answer must not overwrite a newer one.
        const unsent = new Map<string, Msg>();
        const post = async (m: Msg) => {
          const k = m.t === "answer" ? `answer:${m.card_id}` : m.t;
          try {
            const r = await fetch(`${base}/msg`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(m) });
            if (r.ok) unsent.delete(k);
            else if (r.status === 404 || r.status >= 500) unsent.set(k, m);
          } catch {
            unsent.set(k, m);
          }
        };
        sender.current = (m) => {
          if (m.t === "state") return;
          void post(m);
        };
        flushEarly();
        const poll = async () => {
          try {
            const r = await fetch(`${base}/state?v=${v}`, { cache: "no-store" });
            if (r.status === 404) return report("no-room");
            if (r.status !== 200 && r.status !== 204) return;
            const tvAge = Number(r.headers.get("x-tv-age") ?? 0);
            report(tvAge > TV_QUIET_MS ? "tv-quiet" : "ok");
            if (unsent.size) [...unsent.values()].forEach((m) => void post(m));
            if (r.status !== 200) return;
            const data = (await r.json()) as { v: number; state: Wire; age_ms: number };
            v = data.v;
            const { remaining_ms, ...state } = data.state;
            if (remaining_ms !== undefined) state.deadline = Date.now() + remaining_ms - data.age_ms;
            handler.current(state);
          } catch {
            report("offline"); // next poll tries again
          }
        };
        void poll();
        timers.push(window.setInterval(poll, PHONE_POLL_MS));
      }
      cleanup = () => {
        timers.forEach((t) => clearInterval(t));
        cleanupExtra();
      };
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

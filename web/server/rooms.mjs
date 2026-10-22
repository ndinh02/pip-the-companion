// Rooms over plain HTTP polling (OPEN question 3, decided 2026-10-16: polling).
// Memory only: rooms vanish after ROOM_IDLE_MS without a TV, or when the app restarts. Nothing is written to disk.
//
//   POST /api/rooms/:code/open            TV claims a room            -> { token }
//   POST /api/rooms/:code/state   (TV)    TV publishes what is on screen (needs the token)
//   GET  /api/rooms/:code/state?v=N       phones poll; 204 if nothing new since version N. Both carry x-tv-age
//                                         (ms since the TV last checked in) so phones can say "the TV has gone quiet".
//   POST /api/rooms/:code/msg             phones send hello / answer / follow (validated, no free text)
//   GET  /api/rooms/:code/inbox?after=N (TV)  TV collects phone messages (needs the token)
import { randomBytes, timingSafeEqual } from "node:crypto";

export const ROOM_RE = /^[A-Z0-9]{4}$/;
const DEVICE_RE = /^[a-z0-9]{4,16}$/;
const ID_RE = /^[a-z0-9][a-z0-9_-]{0,39}$/; // card ids, option ids
const PLAYER_RE = /^[A-Z]{2,4}-[0-9]{1,2}$/;
const ROOM_IDLE_MS = 4 * 60 * 60 * 1000;
const TV_TAKEOVER_MS = 2 * 60 * 1000; // a room whose TV has been silent this long can be claimed again
const MAX_ROOMS = 500;
const MAX_INBOX = 500;
const MAX_STATE_BYTES = 16_000;
const MAX_MSG_BYTES = 512;

const rooms = new Map(); // code -> { token, state, version, updated, tvSeen, inbox: [{seq, msg}], seq }

function sweep(now = Date.now()) {
  for (const [code, r] of rooms) if (now - r.tvSeen > ROOM_IDLE_MS) rooms.delete(code);
}
setInterval(sweep, 10 * 60 * 1000).unref();

// ---- rate limit: per client IP, token bucket ------------------------------------------------------------------
const buckets = new Map();
function allowed(ip, now = Date.now()) {
  const b = buckets.get(ip) ?? { tokens: 40, at: now };
  b.tokens = Math.min(40, b.tokens + ((now - b.at) / 1000) * 15); // 15 requests/s sustained, bursts of 40
  b.at = now;
  buckets.set(ip, b);
  if (buckets.size > 10_000) buckets.clear();
  if (b.tokens < 1) return false;
  b.tokens -= 1;
  return true;
}

function sameToken(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  return timingSafeEqual(Buffer.from(a), Buffer.from(b));
}

/** Phone messages: only the three known shapes, only known-format ids. Anything else is dropped. */
export function validPhoneMsg(m) {
  if (!m || typeof m !== "object" || !DEVICE_RE.test(m.device ?? "")) return null;
  if (m.t === "hello") return { t: "hello", device: m.device };
  if (m.t === "answer" && ID_RE.test(m.card_id ?? "") && ID_RE.test(m.option ?? ""))
    return { t: "answer", device: m.device, card_id: m.card_id, option: m.option };
  if (m.t === "follow" && (m.player_id === null || PLAYER_RE.test(m.player_id ?? "")))
    return { t: "follow", device: m.device, player_id: m.player_id };
  return null;
}

async function readJson(req, limit) {
  let size = 0;
  const chunks = [];
  for await (const c of req) {
    size += c.length;
    if (size > limit) throw Object.assign(new Error("too large"), { status: 413 });
    chunks.push(c);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8") || "null");
  } catch {
    throw Object.assign(new Error("bad json"), { status: 400 });
  }
}

const json = (res, status, body, headers) => {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers });
  res.end(body === undefined ? "" : JSON.stringify(body));
};

/** Handles /api/rooms/... ; returns false for any other path. `headers` = security headers to add. */
export async function handleRooms(req, res, url, headers) {
  const m = url.pathname.match(/^\/api\/rooms\/([^/]+)\/(open|state|msg|inbox)$/);
  if (!m) return false;
  const send = (s, b, extra) => json(res, s, b, extra ? { ...headers, ...extra } : headers);
  const ip = (req.headers["x-forwarded-for"]?.split(",")[0] ?? req.socket.remoteAddress ?? "?").trim();
  if (!allowed(ip)) return send(429, { error: "slow down" }), true;
  const [, code, action] = m;
  if (!ROOM_RE.test(code)) return send(400, { error: "bad room code" }), true;
  const now = Date.now();
  const room = rooms.get(code);
  const isTv = room && sameToken(req.headers["x-room-token"], room.token);

  try {
    if (action === "open" && req.method === "POST") {
      if (room && !isTv && now - room.tvSeen < TV_TAKEOVER_MS) return send(409, { error: "room in use" }), true;
      if (!room && rooms.size >= MAX_ROOMS) sweep(now);
      if (!room && rooms.size >= MAX_ROOMS) return send(503, { error: "too many rooms" }), true;
      const token = isTv ? room.token : randomBytes(18).toString("base64url");
      rooms.set(code, { token, state: null, version: 0, updated: now, tvSeen: now, inbox: [], seq: 0, ...(isTv ? room : {}), tvSeen: now });
      return send(200, { token }), true;
    }
    if (action === "state" && req.method === "POST") {
      if (!isTv) return send(403, { error: "not this room's screen" }), true;
      const state = await readJson(req, MAX_STATE_BYTES);
      if (!state || state.t !== "state") return send(400, { error: "bad state" }), true;
      room.state = state;
      room.version += 1;
      room.updated = now;
      room.tvSeen = now;
      return send(204), true;
    }
    if (action === "state" && req.method === "GET") {
      if (!room || !room.state) return send(404, { error: "no screen in this room yet" }), true;
      const v = Number(url.searchParams.get("v") ?? -1);
      const tvAge = { "x-tv-age": String(now - room.tvSeen) };
      if (v === room.version) return send(204, undefined, tvAge), true;
      return send(200, { v: room.version, state: room.state, age_ms: now - room.updated }, tvAge), true;
    }
    if (action === "msg" && req.method === "POST") {
      if (!room) return send(404, { error: "no screen in this room yet" }), true;
      const msg = validPhoneMsg(await readJson(req, MAX_MSG_BYTES));
      if (!msg) return send(400, { error: "bad message" }), true;
      room.seq += 1;
      room.inbox.push({ seq: room.seq, msg });
      if (room.inbox.length > MAX_INBOX) room.inbox.splice(0, room.inbox.length - MAX_INBOX);
      return send(204), true;
    }
    if (action === "inbox" && req.method === "GET") {
      if (!isTv) return send(403, { error: "not this room's screen" }), true;
      room.tvSeen = now;
      const after = Number(url.searchParams.get("after") ?? 0);
      return send(200, { seq: room.seq, msgs: room.inbox.filter((e) => e.seq > after).map((e) => e.msg) }), true;
    }
    return send(405, { error: "method not allowed" }), true;
  } catch (e) {
    return send(e.status ?? 500, { error: e.status ? e.message : "error" }), true;
  }
}

export const _test = { rooms, buckets };

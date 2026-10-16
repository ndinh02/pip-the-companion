// Run: node --test web/server
process.env.PIP_NO_LISTEN = "1";
process.env.DIST_DIR = new URL("../dist", import.meta.url).pathname;
import test from "node:test";
import assert from "node:assert/strict";

const { server } = await import("./server.mjs");
const { _test } = await import("./rooms.mjs");
await new Promise((r) => server.listen(0, r));
const base = `http://127.0.0.1:${server.address().port}`;
test.after(() => server.close());

const post = (p, body, token) =>
  fetch(base + p, { method: "POST", headers: { "Content-Type": "application/json", ...(token ? { "x-room-token": token } : {}) }, body: JSON.stringify(body) });

test("a TV opens a room, publishes state; a phone reads it and sends an answer the TV collects", async () => {
  _test.buckets.clear();
  const { token } = await (await post("/api/rooms/ABCD/open", {})).json();
  assert.ok(token.length > 10);
  assert.equal((await post("/api/rooms/ABCD/state", { t: "state", phase: "play", minute: 3 }, token)).status, 204);
  const got = await (await fetch(base + "/api/rooms/ABCD/state")).json();
  assert.equal(got.state.minute, 3);
  assert.equal((await fetch(`${base}/api/rooms/ABCD/state?v=${got.v}`)).status, 204, "nothing new -> 204");
  assert.equal((await post("/api/rooms/ABCD/msg", { t: "answer", device: "abc123", card_id: "c1-var", option: "offside" })).status, 204);
  const inbox = await (await fetch(base + "/api/rooms/ABCD/inbox?after=0", { headers: { "x-room-token": token } })).json();
  assert.deepEqual(inbox.msgs, [{ t: "answer", device: "abc123", card_id: "c1-var", option: "offside" }]);
});

test("only the room's screen can publish state or read the inbox; a busy room cannot be taken over", async () => {
  _test.buckets.clear();
  const { token } = await (await post("/api/rooms/WXYZ/open", {})).json();
  assert.equal((await post("/api/rooms/WXYZ/state", { t: "state" }, "wrong")).status, 403);
  assert.equal((await post("/api/rooms/WXYZ/state", { t: "state" })).status, 403);
  assert.equal((await fetch(base + "/api/rooms/WXYZ/inbox")).status, 403);
  assert.equal((await post("/api/rooms/WXYZ/open", {})).status, 409);
  assert.equal((await post("/api/rooms/WXYZ/open", {}, token)).status, 200, "the same screen can reopen");
});

test("no free text: unknown message shapes, extra text and bad ids are rejected", async () => {
  _test.buckets.clear();
  await post("/api/rooms/QQQQ/open", {});
  for (const bad of [
    { t: "chat", device: "abc123", text: "hello" },
    { t: "answer", device: "abc123", card_id: "c1-var", option: "<script>" },
    { t: "answer", device: "ABC 123", card_id: "c1", option: "x" },
    { t: "follow", device: "abc123", player_id: "Messi" },
  ]) assert.equal((await post("/api/rooms/QQQQ/msg", bad)).status, 400, JSON.stringify(bad));
  const big = { t: "hello", device: "abc123", pad: "x".repeat(2000) };
  assert.equal((await post("/api/rooms/QQQQ/msg", big)).status, 413);
  assert.equal((await post("/api/rooms/bad!/msg", { t: "hello", device: "abc123" })).status, 400);
  assert.equal((await post("/api/rooms/NONE/msg", { t: "hello", device: "abc123" })).status, 404);
});

test("rate limit: a flood from one address is slowed down", async () => {
  _test.buckets.clear();
  const codes = await Promise.all(Array.from({ length: 80 }, () => fetch(base + "/api/rooms/ZZZZ/state").then((r) => r.status)));
  assert.ok(codes.includes(429));
  _test.buckets.clear();
});

test("the app and its security headers still work", async () => {
  const r = await fetch(base + "/tv");
  assert.equal(r.status, 200);
  assert.match(r.headers.get("content-security-policy"), /connect-src 'self'/);
  assert.equal((await fetch(base + "/api/nothing")).status, 404);
});

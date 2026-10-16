// Pip web server for Azure App Service (Linux, Node 22). No dependencies.
// Serves the built app from ./dist with security headers, gzip and a single-page-app fallback.
// Rooms for separate phones live under /api/rooms (rooms.mjs).
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";
import { handleRooms } from "./rooms.mjs";

const here = fileURLToPath(new URL(".", import.meta.url));
// On App Service the build sits next to this file (server/dist); locally it is web/dist.
const ROOT = resolve(process.env.DIST_DIR ?? join(here, "dist"));
const PORT = Number(process.env.PORT ?? 8080);

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".txt": "text/plain; charset=utf-8",
};
const COMPRESS = new Set([".html", ".js", ".css", ".json", ".svg", ".txt"]);

const SECURITY_HEADERS = {
  "Content-Security-Policy":
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
  "Cross-Origin-Opener-Policy": "same-origin",
  "Strict-Transport-Security": "max-age=31536000",
};

const gzCache = new Map(); // path -> gzipped bytes (the data files are large and never change between deploys)

async function fileFor(urlPath) {
  // Only files inside ROOT; anything else (or a missing file) falls back to the app shell.
  let decoded;
  try {
    decoded = decodeURIComponent(urlPath);
  } catch {
    return null;
  }
  const full = normalize(join(ROOT, decoded));
  if (full !== ROOT && !full.startsWith(ROOT + sep)) return null;
  try {
    const s = await stat(full);
    return s.isFile() ? full : null;
  } catch {
    return null;
  }
}

function send(res, status, headers, body) {
  res.writeHead(status, { ...SECURITY_HEADERS, ...headers });
  res.end(body);
}

export const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", "http://x");
  if (url.pathname.startsWith("/api/")) {
    if (await handleRooms(req, res, url, SECURITY_HEADERS)) return;
    return send(res, 404, { "Content-Type": "text/plain" }, "not found");
  }
  if (req.method !== "GET" && req.method !== "HEAD") return send(res, 405, { Allow: "GET, HEAD" }, "");
  const path = url.pathname;
  if (path === "/healthz") return send(res, 200, { "Content-Type": "text/plain" }, "ok");

  let file = path === "/" ? join(ROOT, "index.html") : await fileFor(path);
  if (!file) {
    // Missing data or asset files are real 404s; every other path is a screen of the app (/tv, /play/ABCD, ...).
    if (path.startsWith("/data/") || path.startsWith("/assets/")) return send(res, 404, { "Content-Type": "text/plain" }, "not found");
    file = join(ROOT, "index.html");
  }
  const ext = extname(file);
  const headers = {
    "Content-Type": TYPES[ext] ?? "application/octet-stream",
    // Built assets have content hashes in their names; data and the app shell must always be fresh.
    "Cache-Control": path.startsWith("/assets/") ? "public, max-age=31536000, immutable" : "no-cache",
    Vary: "Accept-Encoding",
  };
  try {
    let body = await readFile(file);
    if (COMPRESS.has(ext) && /\bgzip\b/.test(req.headers["accept-encoding"] ?? "")) {
      if (!gzCache.has(file)) gzCache.set(file, gzipSync(body));
      body = gzCache.get(file);
      headers["Content-Encoding"] = "gzip";
    }
    headers["Content-Length"] = body.length;
    send(res, 200, headers, req.method === "HEAD" ? undefined : body);
  } catch {
    send(res, 500, { "Content-Type": "text/plain" }, "error");
  }
});

if (process.env.PIP_NO_LISTEN !== "1") server.listen(PORT, () => console.log(`Pip server on :${PORT}, serving ${ROOT}`));

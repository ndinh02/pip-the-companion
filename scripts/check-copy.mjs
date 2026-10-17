// Checks viewer-facing copy. Rule that never changes: NO BETTING LANGUAGE anywhere a viewer can read (AGENTS.md).
// 1. The match file: banned words, placeholders, lengths, no hard-coded numbers.
// 2. Every other viewer-facing string: the app's UI text (all `en:/de:/vi:` strings in web/src) and every card
//    template variant (match-reader/templates) — banned words and empty strings.
// Run: cd web && npm run check:copy
import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
// Default: the file the app plays. Pass another path to check it instead: node check-copy.mjs ../data/demo-match.json
const file = process.argv[2] ?? join(here, "../web/public/data/match.json");
const match = JSON.parse(readFileSync(file, "utf8"));
const banned = JSON.parse(readFileSync(join(here, "banned-words.json"), "utf8"));
const LANGS = ["en", "de", "vi"];
const MAX_LEN = 200;
const errors = [];

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const bannedRegex = Object.fromEntries(
  LANGS.map((l) => [l, new RegExp(`(?<![\\p{L}])(${banned[l].map(escape).join("|")})(?![\\p{L}])`, "iu")]),
);

function checkText(where, lang, text, allowedPlaceholders) {
  if (typeof text !== "string" || !text.trim()) return errors.push(`${where}.${lang}: empty`);
  if (text.length > MAX_LEN) errors.push(`${where}.${lang}: ${text.length} chars > ${MAX_LEN}`);
  const hit = text.match(bannedRegex[lang]);
  if (hit) errors.push(`${where}.${lang}: banned word "${hit[1]}"`);
  for (const m of text.matchAll(/\{([a-z0-9_]+)\}/g)) {
    if (!allowedPlaceholders.has(m[1])) errors.push(`${where}.${lang}: placeholder {${m[1]}} not in fact_ids`);
    if (!(m[1] in match.facts)) errors.push(`${where}.${lang}: placeholder {${m[1]}} not in facts`);
  }
  // A bare digit in copy means a number the code did not supply.
  if (/\d/.test(text.replace(/\{[a-z0-9_]+\}/g, ""))) errors.push(`${where}.${lang}: hard-coded number in "${text}"`);
}

for (const card of match.cards) {
  const ids = new Set(card.reveal.fact_ids);
  for (const id of ids) if (!(id in match.facts)) errors.push(`${card.card_id}: unknown fact_id ${id}`);
  const optionIds = card.question.options.map((o) => o.id);
  if (!optionIds.includes(card.reveal.answer)) errors.push(`${card.card_id}: answer not among options`);
  if (!optionIds.includes(card.question.pippi_call)) errors.push(`${card.card_id}: pippi_call not among options`);
  for (const l of LANGS) {
    checkText(`${card.card_id}.question.text`, l, card.question.text[l], new Set());
    for (const o of card.question.options) checkText(`${card.card_id}.option.${o.id}`, l, o.label[l], new Set());
    checkText(`${card.card_id}.reveal.plain`, l, card.reveal.plain[l], ids);
    checkText(`${card.card_id}.reveal.expert`, l, card.reveal.expert[l], ids);
  }
}

// ---- 2. UI strings and templates: banned words everywhere ----------------------------------------------------------
let uiCount = 0;
function checkPlain(where, lang, text) {
  uiCount++;
  if (typeof text !== "string" || !text.trim()) return errors.push(`${where}.${lang}: empty`);
  const hit = text.match(bannedRegex[lang]);
  if (hit) errors.push(`${where}.${lang}: banned word "${hit[1]}" in "${text}"`);
}
function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(name)) out.push(p);
  }
  return out;
}
const src = join(here, "../web/src");
for (const f of walk(src)) {
  const text = readFileSync(f, "utf8");
  // translated strings are written as  en: "…", de: "…", vi: "…"  (double quotes, no template literals)
  for (const m of text.matchAll(/\b(en|de|vi):\s*"((?:[^"\\]|\\.)*)"/g)) {
    const line = text.slice(0, m.index).split("\n").length;
    checkPlain(`${f.slice(src.length + 1)}:${line}`, m[1], m[2]);
  }
}
const tplDir = join(here, "../match-reader/templates");
for (const name of readdirSync(tplDir).filter((n) => n.endsWith(".json"))) {
  const visit = (node, path) => {
    if (Array.isArray(node)) node.forEach((v, i) => visit(v, `${path}[${i}]`));
    else if (node && typeof node === "object") {
      for (const [k, v] of Object.entries(node)) {
        if (LANGS.includes(k) && typeof v === "string") checkPlain(`templates/${name}${path}`, k, v);
        else visit(v, `${path}.${k}`);
      }
    }
  };
  visit(JSON.parse(readFileSync(join(tplDir, name), "utf8")), "");
}

if (errors.length) {
  console.error(`✗ copy check failed (${errors.length})\n` + errors.map((e) => "  - " + e).join("\n"));
  process.exit(1);
}
console.log(`✓ copy check passed: ${match.cards.length} cards × ${LANGS.length} languages, ${uiCount} UI and template strings, no betting language`);

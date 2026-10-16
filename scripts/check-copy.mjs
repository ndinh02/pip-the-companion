// Checks the match file's viewer-facing copy: banned betting words, placeholders, lengths.
// Run: cd web && npm run check:copy
import { readFileSync } from "node:fs";
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

if (errors.length) {
  console.error(`✗ copy check failed (${errors.length})\n` + errors.map((e) => "  - " + e).join("\n"));
  process.exit(1);
}
console.log(`✓ copy check passed: ${match.cards.length} cards × ${LANGS.length} languages`);

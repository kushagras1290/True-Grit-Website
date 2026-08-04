#!/usr/bin/env node

/**
 * Fills `page_content_translations` (migration 0067) for every published CMS
 * page, in every advertised language.
 *
 * WHY. The table was empty. The homepage, About, Delivery, Returns, Privacy,
 * Terms, Help and Standards are all CMS pages whose copy lives in a block tree,
 * so switching to Hindi translated the chrome around them and left the actual
 * page body — headings, paragraphs, FAQ answers, call-to-action labels — in
 * English. Eight pages across ninety-nine locales is 792 rows, well inside D1's
 * free-plan daily write budget, so unlike the entity backfill this one runs to
 * completion in a single pass.
 *
 * WHAT IS TRANSLATED. Only the values under keys the API already treats as
 * customer copy (`services/translation.py::_TRANSLATABLE_KEYS`). Ids, types,
 * hrefs, slugs, image URLs, booleans and numbers pass through byte-identical,
 * so a translated page keeps exactly the shape the storefront knows how to
 * render and every link keeps pointing where it did.
 *
 * USAGE
 *   node scripts/backfill-page-translations.mjs
 *   node scripts/backfill-page-translations.mjs --locales=hi,ta --dry-run
 */

import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const DATABASE = "truegrit-dev";
const WRANGLER = path.resolve("node_modules/wrangler/bin/wrangler.js");
const CACHE_DIR = path.resolve("node_modules/.cache/truegrit-page-i18n");
const SQL_DIR = path.resolve("node_modules/.cache/truegrit-page-sql");
// The definitive language list; the storefront's own locales.ts is a
// re-export shim with no literal definitions of its own.
const LOCALES_FILE = path.resolve("packages/i18n/src/locales.ts");
const UPDATED_BY = "usr_admin";
const TRANSLATION_CONCURRENCY = 8;
const BATCH_CHARACTER_BUDGET = 1200;

/** Mirrors `_TRANSLATABLE_KEYS` in the API's translation service. */
const TRANSLATABLE_KEYS = new Set([
  "heading",
  "subheading",
  "text",
  "title",
  "label",
  "description",
  "question",
  "answer",
  "quote",
  "attribution",
  "intro",
  "eyebrow",
  "consentText",
  "imageAlt",
  "message",
]);
/** Arrays of bare strings that are themselves copy (`rich_text.paragraphs`). */
const TRANSLATABLE_STRING_LIST_KEYS = new Set(["paragraphs"]);

const GOOGLE_LOCALE = new Map([
  ["zh-Hans", "zh-CN"],
  ["zh-Hant", "zh-TW"],
  ["nb", "no"],
  ["ks", "ur"],
  ["brx", "hi"],
  ["mni", "bn"],
]);

function parseArguments(argv) {
  const options = { locales: "all", dryRun: false };
  for (const argument of argv) {
    const [flag, value = ""] = argument.split("=");
    if (flag === "--locales") options.locales = value;
    else if (flag === "--dry-run") options.dryRun = true;
    else throw new Error(`Unknown argument: ${argument}`);
  }
  return options;
}

function localeCodes(selector) {
  const source = fs.readFileSync(LOCALES_FILE, "utf8");
  const all = [...source.matchAll(/\{\s*code:\s*"([^"]+)"/g)]
    .map((match) => match[1])
    .filter((code) => code !== "en");
  if (selector === "all") return all;
  const wanted = selector
    .split(",")
    .map((code) => code.trim())
    .filter(Boolean);
  for (const code of wanted) if (!all.includes(code)) throw new Error(`Unknown locale: ${code}`);
  return wanted;
}

function wrangler(args, maxBuffer = 128 * 1024 * 1024) {
  return execFileSync(process.execPath, [WRANGLER, ...args], { encoding: "utf8", maxBuffer });
}

function d1Query(sql) {
  const output = wrangler(["d1", "execute", DATABASE, "--remote", "--json", "--command", sql]);
  const start = output.indexOf("[");
  if (start < 0) throw new Error(`Unexpected wrangler output:\n${output.slice(0, 400)}`);
  return JSON.parse(output.slice(start))[0]?.results ?? [];
}

const sqlText = (value) => `'${String(value).replaceAll("'", "''")}'`;
const hash = (text) => crypto.createHash("sha1").update(text).digest("hex").slice(0, 16);
const isCopy = (value) => typeof value === "string" && /\p{L}/u.test(value) && value.trim() !== "";

/** Walk the block tree, applying `visit` to every customer-facing string. */
function walkCopy(node, visit, key = null) {
  if (Array.isArray(node)) {
    if (key && TRANSLATABLE_STRING_LIST_KEYS.has(key)) {
      return node.map((entry) => (isCopy(entry) ? visit(entry) : entry));
    }
    return node.map((entry) => walkCopy(entry, visit));
  }
  if (node && typeof node === "object") {
    const result = {};
    for (const [childKey, value] of Object.entries(node)) {
      if (TRANSLATABLE_KEYS.has(childKey) && isCopy(value)) result[childKey] = visit(value);
      else result[childKey] = walkCopy(value, visit, childKey);
    }
    return result;
  }
  return node;
}

const shield = (source) => source.replaceAll("True Grit", "__TGBRAND__");
const unshield = (source) => source.replaceAll("__TGBRAND__", "True Grit").trim();
const escapeHtml = (source) =>
  source
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
const decodeHtml = (source) =>
  source
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&");

async function requestPlain(target, english) {
  const url = new URL("https://translate.googleapis.com/translate_a/single");
  url.searchParams.set("client", "gtx");
  url.searchParams.set("sl", "en");
  url.searchParams.set("tl", GOOGLE_LOCALE.get(target) ?? target);
  url.searchParams.set("dt", "t");
  url.searchParams.set("q", shield(english));
  const response = await fetch(url, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) return english;
  const payload = await response.json();
  return unshield(payload[0].map((segment) => segment[0]).join("")) || english;
}

async function requestBatch(target, batch, attempt = 1) {
  const body = batch
    .map(
      (entry, index) =>
        `<span id="t${String(index).padStart(4, "0")}">${escapeHtml(shield(entry))}</span>`,
    )
    .join("");
  const url = new URL("https://translate.googleapis.com/translate_a/single");
  url.searchParams.set("client", "gtx");
  url.searchParams.set("sl", "en");
  url.searchParams.set("tl", GOOGLE_LOCALE.get(target) ?? target);
  url.searchParams.set("dt", "t");
  url.searchParams.set("q", body);
  try {
    const response = await fetch(url, {
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) throw new Error(`${response.status}`);
    const payload = await response.json();
    const combined = payload[0].map((segment) => segment[0]).join("");
    const matches = [...combined.matchAll(/<span id=['"]t(\d{4})['"]>([\s\S]*?)<\/span>/g)];
    if (matches.length !== batch.length) throw new Error("marker count mismatch");
    const result = new Array(batch.length);
    for (const match of matches) {
      const index = Number(match[1]);
      result[index] = unshield(decodeHtml(match[2])) || batch[index];
    }
    return result;
  } catch (error) {
    if (batch.length > 1) {
      const middle = Math.ceil(batch.length / 2);
      return [
        ...(await requestBatch(target, batch.slice(0, middle))),
        ...(await requestBatch(target, batch.slice(middle))),
      ];
    }
    if (attempt >= 3) return [await requestPlain(target, batch[0]).catch(() => batch[0])];
    await new Promise((resolve) => setTimeout(resolve, 400 * 2 ** attempt));
    return requestBatch(target, batch, attempt + 1);
  }
}

function batched(values) {
  const batches = [];
  let current = [];
  let size = 0;
  for (const value of values) {
    if (current.length > 0 && size + value.length + 32 > BATCH_CHARACTER_BUDGET) {
      batches.push(current);
      current = [];
      size = 0;
    }
    current.push(value);
    size += value.length + 32;
  }
  if (current.length > 0) batches.push(current);
  return batches;
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  const locales = localeCodes(options.locales);
  fs.mkdirSync(CACHE_DIR, { recursive: true });
  fs.mkdirSync(SQL_DIR, { recursive: true });

  const pages = d1Query(
    "SELECT p.id AS page_id, p.slug, v.content_json FROM pages p" +
      " JOIN page_versions v ON v.id = p.published_version_id" +
      " WHERE p.status = 'published'",
  );
  if (pages.length === 0) {
    process.stdout.write("No published pages.\n");
    return;
  }

  const parsed = pages.map((page) => ({
    pageId: page.page_id,
    slug: page.slug,
    content: JSON.parse(page.content_json),
  }));

  // Every distinct string across every page, gathered once.
  const sources = new Set();
  for (const page of parsed) walkCopy(page.content, (text) => (sources.add(text), text));
  process.stdout.write(
    `${parsed.length} published pages, ${sources.size} distinct strings of copy\n`,
  );

  const existing = new Set(
    d1Query("SELECT page_id || '|' || locale AS pair FROM page_content_translations").map(
      (row) => row.pair,
    ),
  );

  const now = new Date().toISOString();
  let written = 0;

  for (const locale of locales) {
    const todo = parsed.filter((page) => !existing.has(`${page.pageId}|${locale}`));
    if (todo.length === 0) {
      process.stdout.write(`${locale}: already complete\n`);
      continue;
    }

    const cacheFile = path.join(CACHE_DIR, `${locale}.json`);
    let cache = {};
    if (fs.existsSync(cacheFile)) {
      try {
        cache = JSON.parse(fs.readFileSync(cacheFile, "utf8"));
      } catch {
        cache = {};
      }
    }
    const pending = [...sources].filter((text) => !(hash(text) in cache));
    if (pending.length > 0) {
      const batches = batched(pending);
      for (let index = 0; index < batches.length; index += TRANSLATION_CONCURRENCY) {
        const slice = batches.slice(index, index + TRANSLATION_CONCURRENCY);
        const results = await Promise.all(slice.map((batch) => requestBatch(locale, batch)));
        slice.forEach((batch, batchIndex) => {
          batch.forEach((english, entryIndex) => {
            cache[hash(english)] = results[batchIndex][entryIndex];
          });
        });
        fs.writeFileSync(cacheFile, JSON.stringify(cache));
      }
    }

    const values = todo.map((page) => {
      const translated = walkCopy(page.content, (text) => cache[hash(text)] ?? text);
      return (
        `(${sqlText(page.pageId)}, ${sqlText(locale)}, ${sqlText(JSON.stringify(translated))},` +
        ` 1, ${sqlText(now)}, ${sqlText(UPDATED_BY)})`
      );
    });

    if (options.dryRun) {
      process.stdout.write(`${locale}: would write ${values.length} pages (dry run)\n`);
      written += values.length;
      continue;
    }

    const file = path.join(SQL_DIR, `${locale}.sql`);
    fs.writeFileSync(
      file,
      "INSERT OR REPLACE INTO page_content_translations\n" +
        "  (page_id, locale, content_json, auto_translated, updated_at, updated_by)\n" +
        `VALUES\n${values.join(",\n")};\n`,
    );
    wrangler(["d1", "execute", DATABASE, "--remote", "--yes", "--file", file]);
    fs.rmSync(file, { force: true });
    written += values.length;
    process.stdout.write(`${locale}: wrote ${values.length} pages\n`);
  }

  process.stdout.write(`\nDone. ${written} page translations written.\n`);
}

await main();

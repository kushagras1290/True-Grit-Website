#!/usr/bin/env node

/**
 * Fills `entity_translations` (migration 0068) for database-sourced content.
 *
 * WHY THIS EXISTS. The storefront chrome has been translated into every
 * advertised language for a while, but the table backing product names,
 * category names, article and recipe titles held nothing except navigation
 * labels. So switching to Hindi translated the buttons and left 1,496 product
 * names, 216 categories, 352 articles and 552 recipes in English — the
 * "some text translates, some doesn't" this script closes.
 *
 * BUDGET. D1 on the Workers Free plan allows 100,000 written rows per day,
 * resetting at 00:00 UTC, and one entity in one locale is one row. The full
 * matrix is roughly 2,600 entities x 99 locales = ~260,000 rows, so a complete
 * backfill spans several days. `--max-rows` stops cleanly under a budget and
 * `--locales` chooses which languages get filled first; everything already
 * written is skipped on the next run, so re-running simply continues.
 *
 * USAGE
 *   node scripts/backfill-entity-translations.mjs --locales=indian --max-rows=90000
 *   node scripts/backfill-entity-translations.mjs --locales=hi,ta,bn --types=product
 *   node scripts/backfill-entity-translations.mjs --locales=all --dry-run
 *
 * Translations are cached on disk per locale, so a re-run after an interrupted
 * pass costs no network calls for work already done.
 */

import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const CACHE_DIR = path.resolve("node_modules/.cache/truegrit-entity-i18n");
const SQL_DIR = path.resolve("node_modules/.cache/truegrit-entity-sql");
// The definitive language list; the storefront's own locales.ts is a
// re-export shim with no literal definitions of its own.
const LOCALES_FILE = path.resolve("packages/i18n/src/locales.ts");
/**
 * Byte budget for a single INSERT.
 *
 * D1 rejects an oversized statement with `SQLITE_TOOBIG`, and rows here vary
 * hugely in size — a product name is 30 characters, a category's hero
 * description several hundred — so batching by row count blows the limit as
 * soon as a chunk lands on long rows. Budgeting by bytes is stable whatever the
 * mix. 20 KB was measured against the remote database: 60 KB is rejected,
 * 20 KB accepted, and the file as a whole may hold many such statements.
 */
const STATEMENT_BYTE_BUDGET = Number(process.env.TG_STATEMENT_BYTES ?? 20_000);
/** Statements per wrangler invocation. Keeps 100k rows from becoming thousands
 *  of process launches, while staying a modest upload. */
const STATEMENTS_PER_FILE = Number(process.env.TG_STATEMENTS_PER_FILE ?? 20);
const TRANSLATION_CONCURRENCY = 8;
/** Google's endpoint truncates long payloads; this is the batch budget the
 *  storefront catalogue generator already proved out. */
const BATCH_CHARACTER_BUDGET = 1200;
const CLOUDFLARE_BATCH_POLL_MS = Number(process.env.TG_CF_BATCH_POLL_MS ?? 10_000);
const CLOUDFLARE_ACCOUNT_ID = process.env.CLOUDFLARE_ACCOUNT_ID ?? "";
let cloudflareApiToken = process.env.CLOUDFLARE_API_TOKEN ?? "";
const CLOUDFLARE_TRANSLATION_MODEL = "@cf/meta/m2m100-1.2b";
const CLOUDFLARE_LLM_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
const CLOUDFLARE_BATCH_URL = (model) =>
  `https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/run/${model}?queueRequest=true`;

/** M2M100 covers most advertised locales. These codes were probed against the
 * live model on 2026-08-09 and rejected by the model itself, so they use the
 * multilingual LLM batch path below instead of being silently mapped to a
 * different language. */
const CLOUDFLARE_LLM_LOCALES = new Map([
  ["as", "Assamese"],
  ["kok", "Konkani"],
  ["sat", "Santali (Ol Chiki script)"],
  ["ks", "Kashmiri"],
  ["eu", "Basque"],
  ["doi", "Dogri"],
  ["mai", "Maithili"],
  ["sa", "Sanskrit"],
  ["brx", "Bodo"],
  ["te", "Telugu"],
  ["tk", "Turkmen"],
  ["mni", "Manipuri (Meitei Mayek script)"],
  ["ky", "Kyrgyz"],
  ["tg", "Tajik"],
  ["mt", "Maltese"],
  ["rw", "Kinyarwanda"],
  ["ny", "Chichewa"],
  ["ug", "Uyghur"],
]);
const CLOUDFLARE_LOCALE = new Map([
  ["zh-Hans", "zh"],
  ["zh-Hant", "zh"],
  ["nb", "no"],
  ["fil", "tl"],
]);

/**
 * Which columns are worth translating, per entity type.
 *
 * Mirrors `TRANSLATABLE_FIELDS` in
 * `apps/api/src/truegrit_api/services/entity_translation.py`. Keep the two in
 * step: this script writes the rows, that registry decides what the admin UI
 * and the auto-translate endpoint consider translatable.
 */
const ENTITY_SPECS = {
  product: {
    query: `SELECT p.id, p.name, p.short_description, p.storage_guidance,
      p.harvest_note, p.growing_method, p.seo_title, p.seo_description,
      p.image_alt, f.name AS farm_name, f.region
      FROM products p LEFT JOIN farms f ON f.id = p.farm_id
      WHERE p.status = 'published'`,
    fields: [
      "name",
      "short_description",
      "storage_guidance",
      "harvest_note",
      "growing_method",
      "seo_title",
      "seo_description",
      "image_alt",
      "farm_name",
      "region",
    ],
  },
  category: {
    query: `SELECT id, name, short_description, hero_eyebrow, hero_title, hero_description,
      hero_image_alt, thumbnail_image_alt, seo_title, seo_description
      FROM categories WHERE status = 'published'`,
    fields: [
      "name",
      "short_description",
      "hero_eyebrow",
      "hero_title",
      "hero_description",
      "hero_image_alt",
      "thumbnail_image_alt",
      "seo_title",
      "seo_description",
    ],
  },
  article: {
    query: `SELECT a.id, a.title, a.excerpt, a.hero_image_alt, a.seo_title, a.seo_description,
      v.content_json FROM articles a JOIN article_versions v ON v.id = a.published_version_id
      WHERE a.status = 'published'`,
    fields: ["title", "excerpt", "hero_image_alt", "seo_title", "seo_description", "content_json"],
  },
  recipe: {
    query: `SELECT r.id, r.title, r.excerpt, r.hero_image_alt, r.seo_title, r.seo_description,
      v.content_json FROM recipes r JOIN recipe_versions v ON v.id = r.published_version_id
      WHERE r.status = 'published'`,
    fields: ["title", "excerpt", "hero_image_alt", "seo_title", "seo_description", "content_json"],
  },
  farm: {
    query: `SELECT id, name, farmer_name, region, story_json, methods_json, hero_image_alt,
      seo_title, seo_description FROM farms WHERE status = 'published'`,
    fields: [
      "name",
      "farmer_name",
      "region",
      "story_json",
      "methods_json",
      "hero_image_alt",
      "seo_title",
      "seo_description",
    ],
  },
  bundle: {
    query: "SELECT id, name, description FROM bundles WHERE status = 'active'",
    fields: ["name", "description"],
  },
};

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
  "summary",
  "body",
  "pullQuote",
]);
const TRANSLATABLE_STRING_LIST_KEYS = new Set(["paragraphs", "steps", "methods"]);

const GOOGLE_LOCALE = new Map([
  ["zh-Hans", "zh-CN"],
  ["zh-Hant", "zh-TW"],
  ["nb", "no"],
  ["ks", "ur"],
  ["brx", "hi"],
  ["mni", "bn"],
]);

function parseArguments(argv) {
  const options = {
    locales: "indian",
    types: Object.keys(ENTITY_SPECS).join(","),
    maxRows: 90_000,
    dryRun: false,
    database: "truegrit-dev",
    env: "",
    config: "apps/api/wrangler.jsonc",
    refreshAuto: false,
    updatedBy: "usr_admin",
    translator: "google",
  };
  for (const argument of argv) {
    const [flag, value = ""] = argument.split("=");
    if (flag === "--locales") options.locales = value;
    else if (flag === "--types") options.types = value;
    else if (flag === "--max-rows") options.maxRows = Number(value);
    else if (flag === "--database") options.database = value;
    else if (flag === "--env") options.env = value;
    else if (flag === "--config") options.config = value;
    else if (flag === "--refresh-auto") options.refreshAuto = true;
    else if (flag === "--updated-by") options.updatedBy = value;
    else if (flag === "--translator") options.translator = value;
    else if (flag === "--dry-run") options.dryRun = true;
    else throw new Error(`Unknown argument: ${argument}`);
  }
  if (!Number.isFinite(options.maxRows) || options.maxRows <= 0) {
    throw new Error("--max-rows must be a positive number");
  }
  if (!new Set(["google", "cloudflare"]).has(options.translator)) {
    throw new Error("--translator must be google or cloudflare");
  }
  return options;
}

/** Locale metadata is declared once, in the storefront. Parsing it here keeps
 *  the language list from drifting into a second hand-maintained copy. */
function localeDefinitions() {
  const source = fs.readFileSync(LOCALES_FILE, "utf8");
  return [...source.matchAll(/\{\s*code:\s*"([^"]+)"[^}]*?group:\s*"(indian|world)"/gs)].map(
    (match) => ({ code: match[1], group: match[2] }),
  );
}

function resolveLocales(selector) {
  const all = localeDefinitions().filter((locale) => locale.code !== "en");
  if (selector === "all") return all.map((locale) => locale.code);
  if (selector === "indian" || selector === "world") {
    return all.filter((locale) => locale.group === selector).map((locale) => locale.code);
  }
  const wanted = new Set(
    selector
      .split(",")
      .map((code) => code.trim())
      .filter(Boolean),
  );
  const known = new Set(all.map((locale) => locale.code));
  for (const code of wanted) if (!known.has(code)) throw new Error(`Unknown locale: ${code}`);
  return [...wanted];
}

/**
 * Wrangler is invoked through its JS entrypoint rather than the `npx` wrapper.
 *
 * Running it through a shell re-splits the SQL on its own spaces (wrangler then
 * reports `Unknown arguments: id,, name,,`), and recent Node refuses to
 * `execFile` a Windows `.cmd` without one (EINVAL). Spawning `node` with the
 * entrypoint sidesteps both: no shell, so arguments containing spaces and
 * quotes arrive intact on every platform.
 */
const WRANGLER = path.resolve("node_modules/wrangler/bin/wrangler.js");

function wrangler(args, maxBuffer) {
  return execFileSync(process.execPath, [WRANGLER, ...args], { encoding: "utf8", maxBuffer });
}

let runtimeOptions;

function d1Args() {
  return [
    "d1",
    "execute",
    runtimeOptions.database,
    "--remote",
    "--config",
    runtimeOptions.config,
    ...(runtimeOptions.env ? ["--env", runtimeOptions.env] : []),
  ];
}

function d1Query(sql) {
  const output = wrangler([...d1Args(), "--json", "--command", sql], 256 * 1024 * 1024);
  // wrangler prefixes the JSON with banner lines on some versions; take the
  // payload from the first bracket so both shapes parse.
  const start = output.indexOf("[");
  if (start < 0) throw new Error(`Unexpected wrangler output:\n${output.slice(0, 400)}`);
  const parsed = JSON.parse(output.slice(start));
  return parsed[0]?.results ?? [];
}

function d1ExecuteFile(file) {
  wrangler([...d1Args(), "--yes", "--file", file], 64 * 1024 * 1024);
}

const sqlText = (value) => `'${String(value).replaceAll("'", "''")}'`;

function shield(source) {
  return source
    .replaceAll("True Grit", "__TGBRAND__")
    .replaceAll("Vikas Farms", "__VIKASFARMS__")
    .replaceAll("Kathiya", "__KATHIYA__")
    .replaceAll("Banshi", "__BANSHI__")
    .replaceAll("Paigambari", "__PAIGAMBARI__");
}

function unshield(source) {
  return source
    .replaceAll("__TGBRAND__", "True Grit")
    .replaceAll("__VIKASFARMS__", "Vikas Farms")
    .replaceAll("__KATHIYA__", "Kathiya")
    .replaceAll("__BANSHI__", "Banshi")
    .replaceAll("__PAIGAMBARI__", "Paigambari")
    .trim();
}

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
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
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
    if (attempt >= 3) {
      // One stubborn string must not sink the run: English is the storefront's
      // designed fallback and renders correctly, just untranslated.
      return [await requestPlain(target, batch[0]).catch(() => batch[0])];
    }
    await new Promise((resolve) => setTimeout(resolve, 400 * 2 ** attempt));
    return requestBatch(target, batch, attempt + 1);
  }
}

function batched(values) {
  const batches = [];
  let current = [];
  let size = 0;
  for (const value of values) {
    const cost = value.length + 32;
    if (current.length > 0 && size + cost > BATCH_CHARACTER_BUDGET) {
      batches.push(current);
      current = [];
      size = 0;
    }
    current.push(value);
    size += cost;
  }
  if (current.length > 0) batches.push(current);
  return batches;
}

function cacheFileFor(locale) {
  return path.join(CACHE_DIR, `${locale}.json`);
}

function loadCache(locale) {
  const file = cacheFileFor(locale);
  if (!fs.existsSync(file)) return {};
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return {};
  }
}

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function refreshCloudflareToken() {
  const output = execFileSync(process.execPath, [WRANGLER, "auth", "token"], {
    encoding: "utf8",
    maxBuffer: 1024 * 1024,
  });
  const token = output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .findLast((line) => /^[A-Za-z0-9_.-]{40,}$/.test(line));
  if (!token) throw new Error("Wrangler did not return a refreshed Cloudflare token");
  cloudflareApiToken = token;
}

async function cloudflareRequest(model, input, attempt = 1) {
  if (!CLOUDFLARE_ACCOUNT_ID || !cloudflareApiToken) {
    throw new Error(
      "Cloudflare translation requires CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN",
    );
  }
  const response = await fetch(CLOUDFLARE_BATCH_URL(model), {
    method: "POST",
    headers: {
      accept: "application/json",
      authorization: `Bearer ${cloudflareApiToken}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(input),
    signal: AbortSignal.timeout(30_000),
  });
  const payload = await response.json();
  if (response.status === 401 && attempt === 1) {
    refreshCloudflareToken();
    return cloudflareRequest(model, input, attempt + 1);
  }
  if (!response.ok || !payload.success) {
    throw new Error(
      `Cloudflare AI ${response.status}: ${JSON.stringify(payload.errors ?? payload).slice(0, 800)}`,
    );
  }
  return payload.result;
}

async function cloudflareBatch(model, requests, locale) {
  const queued = await cloudflareRequest(model, { requests });
  if (!queued.request_id) throw new Error(`${locale}: Cloudflare AI returned no request_id`);
  process.stdout.write(`${locale}: queued Cloudflare batch ${queued.request_id}\n`);
  for (;;) {
    await wait(CLOUDFLARE_BATCH_POLL_MS);
    const result = await cloudflareRequest(model, { request_id: queued.request_id });
    if (Array.isArray(result.responses)) return result.responses;
    if (Array.isArray(result.results)) {
      return result.results.map((entry) => ({
        success: entry.success,
        external_reference: entry.external_reference,
        result: entry.result,
      }));
    }
    if (!new Set(["queued", "running"]).has(result.status)) {
      throw new Error(`${locale}: unexpected Cloudflare batch status ${JSON.stringify(result)}`);
    }
    process.stdout.write(`\r  ${locale}: Cloudflare batch ${result.status}   `);
  }
}

async function cloudflareBatches(model, requests, locale, requestsPerBatch) {
  const chunks = [];
  for (let index = 0; index < requests.length; index += requestsPerBatch) {
    chunks.push(requests.slice(index, index + requestsPerBatch));
  }
  const responses = await Promise.all(
    chunks.map((chunk, index) =>
      cloudflareBatch(model, chunk, `${locale} ${index + 1}/${chunks.length}`),
    ),
  );
  return responses.flat();
}

function llmBatches(values) {
  const batches = [];
  let current = [];
  let size = 0;
  for (const value of values) {
    const cost = value.length + 8;
    if (current.length > 0 && (current.length >= 20 || size + cost > 3_500)) {
      batches.push(current);
      current = [];
      size = 0;
    }
    current.push(value);
    size += cost;
  }
  if (current.length > 0) batches.push(current);
  return batches;
}

function parseLlmTranslations(response, expected, locale, index) {
  const text = response?.result?.response;
  if (typeof text !== "string") {
    throw new Error(`${locale}: LLM batch ${index} returned no text`);
  }
  const match = /\{[\s\S]*\}/.exec(text);
  if (!match) throw new Error(`${locale}: LLM batch ${index} returned no JSON object`);
  const parsed = JSON.parse(match[0]);
  if (!Array.isArray(parsed.translations) || parsed.translations.length !== expected) {
    throw new Error(
      `${locale}: LLM batch ${index} returned ${parsed.translations?.length ?? 0}/${expected} strings`,
    );
  }
  return parsed.translations.map((translation) => {
    if (typeof translation !== "string" || !translation.trim()) {
      throw new Error(`${locale}: LLM batch ${index} returned an empty translation`);
    }
    return unshield(translation);
  });
}

async function translateAllCloudflare(locale, pending, cache) {
  if (pending.length === 0) return cache;
  const language = CLOUDFLARE_LLM_LOCALES.get(locale);
  if (!language) {
    const responses = await cloudflareBatches(
      CLOUDFLARE_TRANSLATION_MODEL,
      pending.map((english) => ({
        text: shield(english),
        source_lang: "en",
        target_lang: CLOUDFLARE_LOCALE.get(locale) ?? locale,
        external_reference: hash(english),
      })),
      locale,
      250,
    );
    for (const response of responses) {
      const translated = response?.result?.translated_text;
      if (!response.success || typeof translated !== "string" || !translated.trim()) {
        throw new Error(`${locale}: Cloudflare translation failed for ${response.external_reference}`);
      }
      cache[response.external_reference] = unshield(translated);
    }
  } else {
    const batches = llmBatches(pending);
    const responses = await cloudflareBatches(
      CLOUDFLARE_LLM_MODEL,
      batches.map((batch, index) => ({
        messages: [
          {
            role: "user",
            content:
              `Translate every string in this JSON array from English into ${language}. ` +
              "Preserve array length and order. Return only a JSON object with one key, " +
              "translations, whose value is the translated string array. Do not translate " +
              "True Grit, Vikas Farms, Kathiya, Banshi, or Paigambari. Input: " +
              JSON.stringify(batch.map(shield)),
          },
        ],
        temperature: 0,
        max_tokens: 4096,
        external_reference: String(index),
      })),
      locale,
      50,
    );
    const byIndex = new Map(responses.map((response) => [Number(response.external_reference), response]));
    for (let index = 0; index < batches.length; index += 1) {
      const response = byIndex.get(index);
      if (!response?.success) throw new Error(`${locale}: LLM batch ${index} failed`);
      const translations = parseLlmTranslations(response, batches[index].length, locale, index);
      batches[index].forEach((english, entryIndex) => {
        cache[hash(english)] = translations[entryIndex];
      });
    }
  }
  fs.writeFileSync(cacheFileFor(locale), JSON.stringify(cache));
  process.stdout.write(`\r  ${locale}: translated ${pending.length}/${pending.length} new strings   \n`);
  return cache;
}

/**
 * Translate every distinct source string for one locale, reusing the cache.
 *
 * Keyed by a hash of the English text, not by entity id, so the same product
 * name appearing on two records costs one call and two catalogue reads.
 */
async function translateAll(locale, sources, cache) {
  const pending = [...new Set(sources)].filter(
    (text) => runtimeOptions.translator === "cloudflare" || !(hash(text) in cache),
  );
  if (pending.length === 0) return cache;
  if (runtimeOptions.translator === "cloudflare") {
    return translateAllCloudflare(locale, pending, cache);
  }
  const batches = batched(pending);
  let done = 0;
  for (let index = 0; index < batches.length; index += TRANSLATION_CONCURRENCY) {
    const slice = batches.slice(index, index + TRANSLATION_CONCURRENCY);
    const results = await Promise.all(slice.map((batch) => requestBatch(locale, batch)));
    slice.forEach((batch, batchIndex) => {
      batch.forEach((english, entryIndex) => {
        cache[hash(english)] = results[batchIndex][entryIndex];
      });
    });
    done += slice.reduce((total, batch) => total + batch.length, 0);
    fs.writeFileSync(cacheFileFor(locale), JSON.stringify(cache));
    process.stdout.write(`\r  ${locale}: translated ${done}/${pending.length} new strings   `);
  }
  process.stdout.write("\n");
  return cache;
}

const hash = (text) => crypto.createHash("sha1").update(text).digest("hex").slice(0, 16);
const isCopy = (value) => typeof value === "string" && /\p{L}/u.test(value) && value.trim() !== "";

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

function entitySources(fields) {
  const sources = [];
  for (const [field, value] of Object.entries(fields)) {
    if (typeof value === "string" && isCopy(value)) sources.push(value);
    else if (field === "content" || field === "story_content") {
      walkCopy(value, (text) => (sources.push(text), text));
    } else if (Array.isArray(value)) {
      value.forEach((entry) => {
        if (isCopy(entry)) sources.push(entry);
      });
    } else if (field === "ingredients" && value && typeof value === "object") {
      for (const ingredient of Object.values(value)) {
        if (!ingredient || typeof ingredient !== "object") continue;
        for (const text of Object.values(ingredient)) if (isCopy(text)) sources.push(text);
      }
    }
  }
  return sources;
}

function translatedEntityFields(fields, cache) {
  const translate = (text) => cache[hash(text)] ?? text;
  const translated = {};
  for (const [field, value] of Object.entries(fields)) {
    if (typeof value === "string") translated[field] = isCopy(value) ? translate(value) : value;
    else if (field === "content" || field === "story_content") {
      translated[field] = walkCopy(value, translate);
    } else if (Array.isArray(value)) {
      translated[field] = value.map((entry) => (isCopy(entry) ? translate(entry) : entry));
    } else if (field === "ingredients" && value && typeof value === "object") {
      translated[field] = Object.fromEntries(
        Object.entries(value).map(([id, ingredient]) => [
          id,
          Object.fromEntries(
            Object.entries(ingredient).map(([key, text]) => [
              key,
              isCopy(text) ? translate(text) : text,
            ]),
          ),
        ]),
      );
    } else translated[field] = value;
  }
  return translated;
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  runtimeOptions = options;
  const locales = resolveLocales(options.locales);
  const types = options.types
    .split(",")
    .map((type) => type.trim())
    .filter(Boolean);
  for (const type of types) if (!ENTITY_SPECS[type]) throw new Error(`Unknown type: ${type}`);

  fs.mkdirSync(CACHE_DIR, { recursive: true });
  fs.mkdirSync(SQL_DIR, { recursive: true });

  // 1. Read the English source rows once; they are the same for every locale.
  const entities = [];
  for (const type of types) {
    const spec = ENTITY_SPECS[type];
    const rows = d1Query(spec.query);
    for (const row of rows) {
      const fields = {};
      for (const field of spec.fields) {
        const value = row[field];
        if (field === "content_json" && typeof value === "string") {
          fields.content = JSON.parse(value);
        } else if (field === "story_json" && typeof value === "string") {
          fields.story_content = JSON.parse(value);
        } else if (field === "methods_json" && typeof value === "string") {
          fields.methods = JSON.parse(value);
        } else if (typeof value === "string" && value.trim()) fields[field] = value.trim();
      }
      if (Object.keys(fields).length > 0) entities.push({ type, id: row.id, fields });
    }
    process.stdout.write(`${type}: ${rows.length} published rows\n`);
  }
  if (types.includes("recipe")) {
    const ingredients = d1Query(
      "SELECT ri.recipe_id, ri.id, ri.label, ri.quantity_text FROM recipe_ingredients ri" +
        " JOIN recipes r ON r.id = ri.recipe_id WHERE r.status = 'published'",
    );
    const recipes = new Map(
      entities.filter((entity) => entity.type === "recipe").map((entity) => [entity.id, entity]),
    );
    for (const ingredient of ingredients) {
      const recipe = recipes.get(ingredient.recipe_id);
      if (!recipe) continue;
      recipe.fields.ingredients ??= {};
      recipe.fields.ingredients[ingredient.id] = {
        label: ingredient.label,
        quantity_text: ingredient.quantity_text || "",
      };
    }
  }
  if (entities.length === 0) {
    process.stdout.write("Nothing to translate.\n");
    return;
  }

  // 2. Skip pairs already stored, so a resumed run costs nothing for them.
  const existing = new Map(
    d1Query(
      `SELECT entity_type || '|' || entity_id || '|' || locale AS pair, auto_translated FROM entity_translations` +
        ` WHERE entity_type IN (${types.map((type) => `'${type}'`).join(", ")})`,
    ).map((row) => [row.pair, Number(row.auto_translated)]),
  );
  process.stdout.write(`${existing.size} entity/locale pairs already stored\n`);

  const allSources = entities.flatMap((entity) => entitySources(entity.fields));
  let written = 0;
  const now = new Date().toISOString();

  for (const locale of locales) {
    const todo = entities.filter((entity) => {
      const state = existing.get(`${entity.type}|${entity.id}|${locale}`);
      return state === undefined || (options.refreshAuto && state === 1);
    });
    if (todo.length === 0) {
      process.stdout.write(`${locale}: already complete\n`);
      continue;
    }
    if (written + todo.length > options.maxRows) {
      const remaining = options.maxRows - written;
      process.stdout.write(
        `\nStopping before ${locale}: ${todo.length} rows needed, ${remaining} left in this run's` +
          ` budget (--max-rows=${options.maxRows}).\nRe-run after 00:00 UTC to continue; finished` +
          ` locales are skipped automatically.\n`,
      );
      break;
    }

    const cache = await translateAll(locale, allSources, loadCache(locale));

    const values = todo.map((entity) => {
      const translated = translatedEntityFields(entity.fields, cache);
      return (
        `(${sqlText(entity.type)}, ${sqlText(entity.id)}, ${sqlText(locale)},` +
        ` ${sqlText(JSON.stringify(translated))}, 1, ${sqlText(now)}, ${sqlText(options.updatedBy)})`
      );
    });

    if (options.dryRun) {
      process.stdout.write(`${locale}: would write ${values.length} rows (dry run)\n`);
      written += values.length;
      continue;
    }

    const statements = [];
    let chunk = [];
    let chunkBytes = 0;
    const flushChunk = () => {
      if (chunk.length === 0) return;
      statements.push(
        "INSERT OR REPLACE INTO entity_translations\n" +
          "  (entity_type, entity_id, locale, fields_json, auto_translated, updated_at, updated_by)\n" +
          `VALUES\n${chunk.join(",\n")};`,
      );
      chunk = [];
      chunkBytes = 0;
    };
    for (const value of values) {
      if (chunk.length > 0 && chunkBytes + value.length > STATEMENT_BYTE_BUDGET) flushChunk();
      chunk.push(value);
      chunkBytes += value.length + 2;
    }
    flushChunk();

    for (let index = 0; index < statements.length; index += STATEMENTS_PER_FILE) {
      const slice = statements.slice(index, index + STATEMENTS_PER_FILE);
      const file = path.join(SQL_DIR, `${locale}-${index}.sql`);
      fs.writeFileSync(file, `${slice.join("\n")}\n`);
      d1ExecuteFile(file);
      fs.rmSync(file, { force: true });
      process.stdout.write(
        `\r  ${locale}: sent ${Math.min(index + slice.length, statements.length)}/${statements.length} statements   `,
      );
    }
    process.stdout.write("\n");
    written += values.length;
  }

  process.stdout.write(`\nDone. ${written} rows written this run.\n`);
}

await main();

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

const DATABASE = "truegrit-dev";
const CACHE_DIR = path.resolve("node_modules/.cache/truegrit-entity-i18n");
const SQL_DIR = path.resolve("node_modules/.cache/truegrit-entity-sql");
// The definitive language list; the storefront's own locales.ts is a
// re-export shim with no literal definitions of its own.
const LOCALES_FILE = path.resolve("packages/i18n/src/locales.ts");
const UPDATED_BY = "usr_admin";
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
    table: "products",
    fields: ["name", "short_description"],
    where: "status = 'published'",
  },
  category: {
    table: "categories",
    fields: ["name", "short_description", "hero_eyebrow", "hero_title", "hero_description"],
    where: "status = 'published'",
  },
  article: { table: "articles", fields: ["title", "excerpt"], where: "status = 'published'" },
  recipe: { table: "recipes", fields: ["title", "excerpt"], where: "status = 'published'" },
  farm: { table: "farms", fields: ["name", "region"], where: "status = 'published'" },
  bundle: { table: "bundles", fields: ["name", "description"], where: "status = 'active'" },
};

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
  };
  for (const argument of argv) {
    const [flag, value = ""] = argument.split("=");
    if (flag === "--locales") options.locales = value;
    else if (flag === "--types") options.types = value;
    else if (flag === "--max-rows") options.maxRows = Number(value);
    else if (flag === "--dry-run") options.dryRun = true;
    else throw new Error(`Unknown argument: ${argument}`);
  }
  if (!Number.isFinite(options.maxRows) || options.maxRows <= 0) {
    throw new Error("--max-rows must be a positive number");
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

function d1Query(sql) {
  const output = wrangler(
    ["d1", "execute", DATABASE, "--remote", "--json", "--command", sql],
    256 * 1024 * 1024,
  );
  // wrangler prefixes the JSON with banner lines on some versions; take the
  // payload from the first bracket so both shapes parse.
  const start = output.indexOf("[");
  if (start < 0) throw new Error(`Unexpected wrangler output:\n${output.slice(0, 400)}`);
  const parsed = JSON.parse(output.slice(start));
  return parsed[0]?.results ?? [];
}

function d1ExecuteFile(file) {
  wrangler(["d1", "execute", DATABASE, "--remote", "--yes", "--file", file], 64 * 1024 * 1024);
}

const sqlText = (value) => `'${String(value).replaceAll("'", "''")}'`;

function shield(source) {
  return source.replaceAll("True Grit", "__TGBRAND__");
}

function unshield(source) {
  return source.replaceAll("__TGBRAND__", "True Grit").trim();
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

/**
 * Translate every distinct source string for one locale, reusing the cache.
 *
 * Keyed by a hash of the English text, not by entity id, so the same product
 * name appearing on two records costs one call and two catalogue reads.
 */
async function translateAll(locale, sources, cache) {
  const pending = [...new Set(sources)].filter((text) => !(hash(text) in cache));
  if (pending.length === 0) return cache;
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

async function main() {
  const options = parseArguments(process.argv.slice(2));
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
    const columns = ["id", ...spec.fields].join(", ");
    const rows = d1Query(`SELECT ${columns} FROM ${spec.table} WHERE ${spec.where}`);
    for (const row of rows) {
      const fields = {};
      for (const field of spec.fields) {
        const value = row[field];
        if (typeof value === "string" && value.trim()) fields[field] = value.trim();
      }
      if (Object.keys(fields).length > 0) entities.push({ type, id: row.id, fields });
    }
    process.stdout.write(`${type}: ${rows.length} published rows\n`);
  }
  if (entities.length === 0) {
    process.stdout.write("Nothing to translate.\n");
    return;
  }

  // 2. Skip pairs already stored, so a resumed run costs nothing for them.
  const existing = new Set(
    d1Query(
      `SELECT entity_type || '|' || entity_id || '|' || locale AS pair FROM entity_translations` +
        ` WHERE entity_type IN (${types.map((type) => `'${type}'`).join(", ")})`,
    ).map((row) => row.pair),
  );
  process.stdout.write(`${existing.size} entity/locale pairs already stored\n`);

  const allSources = entities.flatMap((entity) => Object.values(entity.fields));
  let written = 0;
  const now = new Date().toISOString();

  for (const locale of locales) {
    const todo = entities.filter(
      (entity) => !existing.has(`${entity.type}|${entity.id}|${locale}`),
    );
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
      const translated = {};
      for (const [field, english] of Object.entries(entity.fields)) {
        translated[field] = cache[hash(english)] ?? english;
      }
      return (
        `(${sqlText(entity.type)}, ${sqlText(entity.id)}, ${sqlText(locale)},` +
        ` ${sqlText(JSON.stringify(translated))}, 1, ${sqlText(now)}, ${sqlText(UPDATED_BY)})`
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

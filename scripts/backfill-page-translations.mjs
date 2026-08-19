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

const WRANGLER = path.resolve("node_modules/wrangler/bin/wrangler.js");
const CACHE_DIR = path.resolve("node_modules/.cache/truegrit-page-i18n");
const SQL_DIR = path.resolve("node_modules/.cache/truegrit-page-sql");
const TOKEN_LOCK = path.resolve("node_modules/.cache/truegrit-cloudflare-token.lock");
const WRANGLER_CONFIG =
  process.env.TG_WRANGLER_CONFIG ??
  path.join(
    process.env.XDG_CONFIG_HOME ?? path.join(process.env.APPDATA ?? "", "xdg.config"),
    ".wrangler/config/default.toml",
  );
// The definitive language list; the storefront's own locales.ts is a
// re-export shim with no literal definitions of its own.
const LOCALES_FILE = path.resolve("packages/i18n/src/locales.ts");
const TRANSLATION_CONCURRENCY = 8;
const BATCH_CHARACTER_BUDGET = 1200;
const CLOUDFLARE_BATCH_POLL_MS = Number(process.env.TG_CF_BATCH_POLL_MS ?? 10_000);
const CLOUDFLARE_SYNC_CONCURRENCY = Number(process.env.TG_CF_SYNC_CONCURRENCY ?? 4);
const CLOUDFLARE_TRANSLATION_MODE = process.env.TG_CF_TRANSLATION_MODE ?? "sync";
const CLOUDFLARE_ACCOUNT_ID = process.env.CLOUDFLARE_ACCOUNT_ID ?? "";
let cloudflareApiToken = process.env.CLOUDFLARE_API_TOKEN ?? "";
const CLOUDFLARE_TRANSLATION_MODEL = "@cf/meta/m2m100-1.2b";
const CLOUDFLARE_LLM_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
const CLOUDFLARE_LLM_MODEL_BY_LOCALE = new Map([
  ["sat", "@cf/meta/llama-4-scout-17b-16e-instruct"],
]);
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
  const options = {
    locales: "all",
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
    else if (flag === "--database") options.database = value;
    else if (flag === "--env") options.env = value;
    else if (flag === "--config") options.config = value;
    else if (flag === "--refresh-auto") options.refreshAuto = true;
    else if (flag === "--updated-by") options.updatedBy = value;
    else if (flag === "--translator") options.translator = value;
    else if (flag === "--dry-run") options.dryRun = true;
    else throw new Error(`Unknown argument: ${argument}`);
  }
  if (!new Set(["google", "cloudflare"]).has(options.translator)) {
    throw new Error("--translator must be google or cloudflare");
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
  const output = wrangler([...d1Args(), "--json", "--command", sql]);
  const start = output.indexOf("[");
  if (start < 0) throw new Error(`Unexpected wrangler output:\n${output.slice(0, 400)}`);
  return JSON.parse(output.slice(start))[0]?.results ?? [];
}

async function d1Import(file) {
  for (let attempt = 1; ; attempt += 1) {
    try {
      return wrangler([...d1Args(), "--yes", "--file", file]);
    } catch (error) {
      if (attempt >= 6) throw error;
      await wait(Math.min(15_000, 1_500 * 2 ** (attempt - 1)));
    }
  }
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

const shield = (source) =>
  source.replaceAll("True Grit", "[[[9001]]]").replaceAll("Vikas Farms", "[[[9002]]]");
function unshield(source) {
  const objectWrapped = /^\{"k\d+":\s*"([\s\S]*)\}$/.exec(source.trim());
  if (objectWrapped) source = objectWrapped[1].replace(/"$/, "");
  return source
    .replace(/tgbrand/gi, "True Grit")
    .replace(/_+\s*(?:tgbrand|true\s*grit)\s*_+/gi, "True Grit")
    .replace(/_+\s*(true\s*grit)\b|\b(true\s*grit)\s*_+/gi, "True Grit")
    .replace(/_+\s*vikas\s*farms\s*_+/gi, "Vikas Farms")
    .replace(/_+\s*(vikas\s*farms)\b|\b(vikas\s*farms)\s*_+/gi, "Vikas Farms")
    .replace(/\[{2,4}9001\]{2,4}/g, "True Grit")
    .replace(/\[{2,4}9002\]{2,4}/g, "Vikas Farms")
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

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function configuredCloudflareToken() {
  if (!fs.existsSync(WRANGLER_CONFIG)) return "";
  const match = /oauth_token\s*=\s*"([^"]+)"/.exec(fs.readFileSync(WRANGLER_CONFIG, "utf8"));
  return match?.[1] ?? "";
}

function waitSync(milliseconds) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds);
}

function refreshCloudflareToken() {
  const reuseConfiguredToken = () => {
    const configured = configuredCloudflareToken();
    if (!configured || configured === cloudflareApiToken) return false;
    cloudflareApiToken = configured;
    return true;
  };
  if (reuseConfiguredToken()) return;

  let lock;
  for (;;) {
    try {
      lock = fs.openSync(TOKEN_LOCK, "wx");
      break;
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
      if (reuseConfiguredToken()) return;
      const age = Date.now() - fs.statSync(TOKEN_LOCK).mtimeMs;
      if (age > 180_000) fs.rmSync(TOKEN_LOCK, { force: true });
      else waitSync(1_000);
    }
  }

  try {
    if (reuseConfiguredToken()) return;
    const output = execFileSync(process.execPath, [WRANGLER, "auth", "token"], {
      encoding: "utf8",
      maxBuffer: 1024 * 1024,
      timeout: 120_000,
    });
    const token = output
      .split(/\r?\n/)
      .map((line) => line.trim())
      .findLast((line) => /^[A-Za-z0-9_.-]{40,}$/.test(line));
    if (!token) throw new Error("Wrangler did not return a refreshed Cloudflare token");
    cloudflareApiToken = token;
  } finally {
    fs.closeSync(lock);
    fs.rmSync(TOKEN_LOCK, { force: true });
  }
}

async function cloudflareRequest(model, input, attempt = 1) {
  if (!CLOUDFLARE_ACCOUNT_ID || !cloudflareApiToken) {
    throw new Error(
      "Cloudflare translation requires CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN",
    );
  }
  const response = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/run/${model}?queueRequest=true`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        authorization: `Bearer ${cloudflareApiToken}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(input),
      signal: AbortSignal.timeout(30_000),
    },
  );
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

async function cloudflareSyncRequest(model, input, attempt = 1) {
  if (!CLOUDFLARE_ACCOUNT_ID || !cloudflareApiToken) {
    throw new Error(
      "Cloudflare translation requires CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN",
    );
  }
  for (let currentAttempt = attempt; ; currentAttempt += 1) {
    try {
      const response = await fetch(
        `https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/run/${model}`,
        {
          method: "POST",
          headers: {
            accept: "application/json",
            authorization: `Bearer ${cloudflareApiToken}`,
            "content-type": "application/json",
          },
          body: JSON.stringify(input),
          signal: AbortSignal.timeout(model === CLOUDFLARE_TRANSLATION_MODEL ? 30_000 : 120_000),
        },
      );
      const payload = await response.json();
      if (response.status === 401) {
        refreshCloudflareToken();
        continue;
      }
      if (!response.ok || !payload.success) {
        if (response.status === 429 || response.status >= 500) {
          await wait(
            Math.min(30_000, 750 * 2 ** Math.min(currentAttempt, 5)) + Math.random() * 500,
          );
          continue;
        }
        throw new Error(
          `Cloudflare AI ${response.status}: ${JSON.stringify(payload.errors ?? payload).slice(0, 800)}`,
        );
      }
      return payload.result;
    } catch (error) {
      if (String(error).includes("Cloudflare AI ")) throw error;
      if (model !== CLOUDFLARE_TRANSLATION_MODEL && currentAttempt >= 2) throw error;
      await wait(Math.min(30_000, 750 * 2 ** Math.min(currentAttempt, 5)) + Math.random() * 500);
    }
  }
}

async function mapConcurrent(values, concurrency, visit) {
  const result = new Array(values.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(concurrency, values.length) }, async () => {
    for (;;) {
      const index = next;
      next += 1;
      if (index >= values.length) return;
      result[index] = await visit(values[index], index);
    }
  });
  await Promise.all(workers);
  return result;
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
  }
}

async function cloudflareBatches(model, requests, locale, requestsPerBatch) {
  const chunks = [];
  for (let index = 0; index < requests.length; index += requestsPerBatch) {
    chunks.push(requests.slice(index, index + requestsPerBatch));
  }
  return (
    await Promise.all(
      chunks.map((chunk, index) =>
        cloudflareBatch(model, chunk, `${locale} ${index + 1}/${chunks.length}`),
      ),
    )
  ).flat();
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
  const raw =
    response?.result?.response ??
    response?.response ??
    response?.result?.choices?.[0]?.message?.content ??
    response?.choices?.[0]?.message?.content;
  let parsed = raw;
  if (typeof raw === "string") {
    const match = /\{[\s\S]*\}/.exec(raw);
    if (!match) throw new Error(`${locale}: LLM batch ${index} returned no JSON object`);
    parsed = JSON.parse(match[0]);
  }
  if (!parsed || typeof parsed !== "object") {
    throw new Error(`${locale}: LLM batch ${index} returned no JSON object`);
  }
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

async function translateLlmBatch(locale, language, batch, label) {
  const model = CLOUDFLARE_LLM_MODEL_BY_LOCALE.get(locale) ?? CLOUDFLARE_LLM_MODEL;
  try {
    const result = await cloudflareSyncRequest(model, {
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
    });
    return parseLlmTranslations(result, batch.length, locale, label);
  } catch (error) {
    if (batch.length === 1) {
      const fallback = await cloudflareSyncRequest(model, {
        messages: [
          {
            role: "user",
            content:
              `Translate this text from English into ${language}. Return only the translated ` +
              "text, with no explanation or quotation marks. Do not translate True Grit, " +
              "Vikas Farms, Kathiya, Banshi, or Paigambari. Text: " +
              shield(batch[0]),
          },
        ],
        temperature: 0,
        max_tokens: 4096,
      });
      const plain =
        fallback?.response ??
        fallback?.result?.response ??
        fallback?.choices?.[0]?.message?.content ??
        fallback?.result?.choices?.[0]?.message?.content;
      if (typeof plain === "string" && plain.trim()) return [unshield(plain)];
      throw error;
    }
    const middle = Math.ceil(batch.length / 2);
    return [
      ...(await translateLlmBatch(locale, language, batch.slice(0, middle), `${label}a`)),
      ...(await translateLlmBatch(locale, language, batch.slice(middle), `${label}b`)),
    ];
  }
}

async function translateCloudflare(locale, pending, cache) {
  const language = CLOUDFLARE_LLM_LOCALES.get(locale);
  if (!language) {
    if (CLOUDFLARE_TRANSLATION_MODE === "sync") {
      const results = await mapConcurrent(pending, CLOUDFLARE_SYNC_CONCURRENCY, (english) =>
        cloudflareSyncRequest(CLOUDFLARE_TRANSLATION_MODEL, {
          text: shield(english),
          source_lang: "en",
          target_lang: CLOUDFLARE_LOCALE.get(locale) ?? locale,
        }),
      );
      pending.forEach((english, index) => {
        const translated = results[index]?.translated_text;
        if (typeof translated !== "string" || !translated.trim()) {
          throw new Error(`${locale}: Cloudflare translation returned an empty string`);
        }
        cache[hash(english)] = unshield(translated);
      });
      return cache;
    }
    const responses = await cloudflareBatches(
      CLOUDFLARE_TRANSLATION_MODEL,
      pending.map((english) => ({
        text: shield(english),
        source_lang: "en",
        target_lang: CLOUDFLARE_LOCALE.get(locale) ?? locale,
        external_reference: hash(english),
      })),
      locale,
      50,
    );
    for (const response of responses) {
      const translated = response?.result?.translated_text;
      if (!response.success || typeof translated !== "string" || !translated.trim()) {
        throw new Error(
          `${locale}: Cloudflare translation failed for ${response.external_reference}`,
        );
      }
      cache[response.external_reference] = unshield(translated);
    }
    return cache;
  }

  const batches = llmBatches(pending);
  if (CLOUDFLARE_TRANSLATION_MODE === "sync") {
    const results = await mapConcurrent(
      batches,
      Math.min(6, CLOUDFLARE_SYNC_CONCURRENCY),
      (batch, index) => translateLlmBatch(locale, language, batch, index),
    );
    for (let index = 0; index < batches.length; index += 1) {
      const translations = results[index];
      batches[index].forEach((english, entryIndex) => {
        cache[hash(english)] = translations[entryIndex];
      });
    }
    return cache;
  }
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
            "True Grit or Vikas Farms. Input: " +
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
  const byIndex = new Map(
    responses.map((response) => [Number(response.external_reference), response]),
  );
  for (let index = 0; index < batches.length; index += 1) {
    const response = byIndex.get(index);
    if (!response?.success) throw new Error(`${locale}: LLM batch ${index} failed`);
    const translations = parseLlmTranslations(response, batches[index].length, locale, index);
    batches[index].forEach((english, entryIndex) => {
      cache[hash(english)] = translations[entryIndex];
    });
  }
  return cache;
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  runtimeOptions = options;
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

  const existing = new Map(
    d1Query(
      "SELECT page_id || '|' || locale AS pair, auto_translated FROM page_content_translations",
    ).map((row) => [row.pair, Number(row.auto_translated)]),
  );

  const now = new Date().toISOString();
  let written = 0;

  for (const locale of locales) {
    const todo = parsed.filter((page) => {
      const state = existing.get(`${page.pageId}|${locale}`);
      return state === undefined || (options.refreshAuto && state === 1);
    });
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
      if (options.translator === "cloudflare") {
        cache = await translateCloudflare(locale, pending, cache);
        fs.writeFileSync(cacheFile, JSON.stringify(cache));
      } else {
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
    }

    const values = todo.map((page) => {
      const translated = walkCopy(page.content, (text) => cache[hash(text)] ?? text);
      return (
        `(${sqlText(page.pageId)}, ${sqlText(locale)}, ${sqlText(JSON.stringify(translated))},` +
        ` 1, ${sqlText(now)}, ${sqlText(options.updatedBy)})`
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
    await d1Import(file);
    fs.rmSync(file, { force: true });
    written += values.length;
    process.stdout.write(`${locale}: wrote ${values.length} pages\n`);
  }

  process.stdout.write(`\nDone. ${written} page translations written.\n`);
}

await main();

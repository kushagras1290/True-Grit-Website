#!/usr/bin/env node

/**
 * Generates the admin panel's per-locale catalogues.
 *
 * One file per language, not one file for all of them. The admin has ~1,300
 * strings; bundling ninety-nine languages into a single module would add
 * several megabytes to a single-page app that loads before the operator can do
 * anything. Vite code-splits a dynamic `import()` per file, so an operator
 * working in Tamil downloads Tamil.
 *
 * Cached on disk per locale, so a re-run only fetches strings that are new.
 */

import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const I18N_ROOT = path.resolve("apps/admin/src/lib/i18n");
const SOURCES_FILE = path.join(I18N_ROOT, "source-strings.ts");
const CATALOGUE_DIR = path.join(I18N_ROOT, "catalogues");
const INDEX_FILE = path.join(I18N_ROOT, "generated-catalogues.ts");
const LOCALES_FILE = path.resolve("packages/i18n/src/locales.ts");
const CACHE_DIR = path.resolve("node_modules/.cache/truegrit-admin-i18n");
const CONCURRENCY = 10;
const BATCH_CHARACTER_BUDGET = 1200;

const GOOGLE_LOCALE = new Map([
  ["zh-Hans", "zh-CN"],
  ["zh-Hant", "zh-TW"],
  ["nb", "no"],
  ["ks", "ur"],
  ["brx", "hi"],
  ["mni", "bn"],
]);

function sourceStrings() {
  const text = fs.readFileSync(SOURCES_FILE, "utf8");
  const source = ts.createSourceFile(SOURCES_FILE, text, ts.ScriptTarget.Latest, true);
  const values = [];
  const visit = (node) => {
    if (ts.isArrayLiteralExpression(node)) {
      for (const element of node.elements) {
        if (ts.isStringLiteralLike(element)) values.push(element.text);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return values;
}

function localeCodes() {
  const text = fs.readFileSync(LOCALES_FILE, "utf8");
  return [...text.matchAll(/\{\s*code:\s*"([^"]+)"/g)]
    .map((match) => match[1])
    .filter((code) => code !== "en");
}

const shield = (value) => value.replaceAll("True Grit", "__TGBRAND__");

function unshield(value, english) {
  let result = value.replaceAll("__TGBRAND__", "True Grit");
  for (const match of english.matchAll(/\{(\w+)\}/g)) {
    result = result.replaceAll(`__TGPH_${match[1].toUpperCase()}__`, `{${match[1]}}`);
  }
  return result.trim();
}

const shieldAll = (value) =>
  shield(value).replace(/\{(\w+)\}/g, (_, name) => `__TGPH_${name.toUpperCase()}__`);

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const decodeHtml = (value) =>
  value
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&");

function placeholdersIntact(value, english) {
  const expected = [...english.matchAll(/\{(\w+)\}/g)].map((match) => match[1]);
  return expected.every((name) => value.includes(`{${name}}`));
}

async function requestPlain(target, english) {
  const url = new URL("https://translate.googleapis.com/translate_a/single");
  url.searchParams.set("client", "gtx");
  url.searchParams.set("sl", "en");
  url.searchParams.set("tl", GOOGLE_LOCALE.get(target) ?? target);
  url.searchParams.set("dt", "t");
  url.searchParams.set("q", shieldAll(english));
  const response = await fetch(url, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) return english;
  const payload = await response.json();
  const value = unshield(payload[0].map((segment) => segment[0]).join(""), english) || english;
  return placeholdersIntact(value, english) ? value : english;
}

async function requestBatch(target, batch, attempt = 1) {
  const body = batch
    .map(
      (english, index) =>
        `<span id="t${String(index).padStart(4, "0")}">${escapeHtml(shieldAll(english))}</span>`,
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
    if (!response.ok) throw new Error(String(response.status));
    const payload = await response.json();
    const combined = payload[0].map((segment) => segment[0]).join("");
    const matches = [...combined.matchAll(/<span id=['"]t(\d{4})['"]>([\s\S]*?)<\/span>/g)];
    if (matches.length !== batch.length) throw new Error("marker count mismatch");
    const result = new Array(batch.length);
    for (const match of matches) {
      const index = Number(match[1]);
      const english = batch[index];
      const value = unshield(decodeHtml(match[2]), english) || english;
      // A mangled placeholder would render `__TGPH_COUNT__` to an operator.
      // English is the designed fallback and reads correctly.
      result[index] = placeholdersIntact(value, english) ? value : english;
    }
    return result;
  } catch {
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

const sources = sourceStrings();
const targets = localeCodes();
fs.mkdirSync(CACHE_DIR, { recursive: true });
fs.mkdirSync(CATALOGUE_DIR, { recursive: true });
process.stdout.write(`${sources.length} source strings, ${targets.length} locales\n`);

let cursor = 0;
let completed = 0;

async function worker() {
  while (cursor < targets.length) {
    const target = targets[cursor++];
    const cacheFile = path.join(CACHE_DIR, `${target}.json`);
    let cache = {};
    if (fs.existsSync(cacheFile)) {
      try {
        cache = JSON.parse(fs.readFileSync(cacheFile, "utf8"));
      } catch {
        cache = {};
      }
    }
    const pending = sources.filter((english) => !cache[english]);
    for (const batch of batched(pending)) {
      const values = await requestBatch(target, batch);
      batch.forEach((english, index) => {
        cache[english] = values[index];
      });
      fs.writeFileSync(cacheFile, JSON.stringify(cache));
    }

    // A batched request can return fewer entries than it was given (observed
    // against the live endpoint). Left unrepaired, a dropped string simply
    // never gets a chunk entry and falls back to English forever, even after
    // the source text it belongs to is retranslatable — `requestPlain` always
    // returns a usable value, so this closes the gap unconditionally.
    const stillMissing = sources.filter((english) => !cache[english]);
    if (stillMissing.length > 0) {
      process.stdout.write(
        `  ${target}: repairing ${stillMissing.length} string(s) dropped by the batch translator\n`,
      );
      for (const english of stillMissing) cache[english] = await requestPlain(target, english);
      fs.writeFileSync(cacheFile, JSON.stringify(cache));
    }

    // Entries identical to English carry no information and would double the
    // chunk for languages that share vocabulary with it (proper nouns, "OK").
    const entries = sources
      .filter((english) => cache[english] && cache[english] !== english)
      .map((english) => `  ${JSON.stringify(english)}: ${JSON.stringify(cache[english])},`);
    fs.writeFileSync(
      path.join(CATALOGUE_DIR, `${target}.ts`),
      `/** Generated by scripts/generate-admin-translations.mjs. */\n` +
        `const CATALOGUE: Readonly<Record<string, string>> = {\n${entries.join("\n")}\n};\n\n` +
        `export default CATALOGUE;\n`,
    );
    completed += 1;
    process.stdout.write(`Translated ${target} (${completed}/${targets.length})\n`);
  }
}

await Promise.all(Array.from({ length: Math.min(CONCURRENCY, targets.length) }, () => worker()));

fs.writeFileSync(
  INDEX_FILE,
  `/**
 * Generated by scripts/generate-admin-translations.mjs.
 *
 * Each locale is a dynamic import so Vite emits it as its own chunk: an
 * operator working in Tamil downloads Tamil, not all ninety-nine languages.
 */
import type { Catalogue } from "@truegrit/i18n";

export const ADMIN_CATALOGUE_LOADERS: Readonly<
  Record<string, () => Promise<{ default: Catalogue }>>
> = {
${targets.map((code) => `  ${JSON.stringify(code)}: () => import("./catalogues/${code}"),`).join("\n")}
};
`,
);
process.stdout.write(`Wrote ${INDEX_FILE} and ${targets.length} catalogue chunks\n`);

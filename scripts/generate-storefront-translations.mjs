#!/usr/bin/env node

/**
 * Generates the complete machine-translated storefront catalogue.
 *
 * Existing hand-authored core catalogues stay authoritative. This generator
 * fills the literal full-site catalogue for every locale and the core catalogue
 * for newly added locales. Results are deterministic TypeScript and are checked
 * by the normal i18n test suite before release.
 */

import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const I18N_ROOT = path.resolve("apps/storefront/app/lib/i18n");
const OUTPUT_FILE = path.join(I18N_ROOT, "generated-catalogues.ts");
const CACHE_DIR = path.resolve("node_modules/.cache/truegrit-i18n");
const CONCURRENCY = 12;
const GOOGLE_LOCALE = new Map([
  ["zh-Hans", "zh-CN"],
  ["zh-Hant", "zh-TW"],
  ["nb", "no"],
  // The lightweight generation endpoint does not expose these three tags.
  // Their established hand-authored core catalogues remain authoritative;
  // the closest same-script regional locale fills newly discovered literal
  // copy until the endpoint adds the language itself.
  ["ks", "ur"],
  ["brx", "hi"],
  ["mni", "bn"],
]);

function objectEntries(file, variableName) {
  const sourceText = fs.readFileSync(file, "utf8");
  const source = ts.createSourceFile(file, sourceText, ts.ScriptTarget.Latest, true);
  let object;
  function unwrap(expression) {
    let current = expression;
    while (ts.isAsExpression(current) || ts.isSatisfiesExpression(current)) {
      current = current.expression;
    }
    return current;
  }
  function visit(node) {
    if (
      ts.isVariableDeclaration(node) &&
      node.name.getText(source) === variableName &&
      node.initializer &&
      ts.isObjectLiteralExpression(unwrap(node.initializer))
    ) {
      object = unwrap(node.initializer);
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  if (!object) throw new Error(`Could not find ${variableName} in ${file}`);
  return object.properties.flatMap((property) => {
    if (!ts.isPropertyAssignment(property) || !ts.isStringLiteralLike(property.initializer)) {
      return [];
    }
    const key = ts.isComputedPropertyName(property.name)
      ? null
      : property.name.getText(source).replace(/^["']|["']$/g, "");
    return key ? [[key, property.initializer.text]] : [];
  });
}

function localeCodes() {
  const sourceText = fs.readFileSync(path.join(I18N_ROOT, "locales.ts"), "utf8");
  return [...sourceText.matchAll(/\{\s*code:\s*"([^"]+)"/g)].map((match) => match[1]);
}

function chunks(entries) {
  const result = [];
  let current = [];
  let size = 0;
  for (const entry of entries) {
    const addition = entry[1].length + 14;
    if (current.length > 0 && size + addition > 1200) {
      result.push(current);
      current = [];
      size = 0;
    }
    current.push(entry);
    size += addition;
  }
  if (current.length > 0) result.push(current);
  return result;
}

function shield(source) {
  return source
    .replaceAll("True Grit", "__TGBRAND__")
    .replace(/\{(\w+)\}/g, (_, name) => `__TGPH_${name.toUpperCase()}__`);
}

function unshield(source, english) {
  let result = source.replaceAll("__TGBRAND__", "True Grit");
  for (const match of english.matchAll(/\{(\w+)\}/g)) {
    result = result.replaceAll(`__TGPH_${match[1].toUpperCase()}__`, `{${match[1]}}`);
  }
  return result.trim();
}

function escapeHtml(source) {
  return source
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function decodeHtml(source) {
  return source
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&");
}

async function requestPlainTranslation(target, english) {
  const url = new URL("https://translate.googleapis.com/translate_a/single");
  url.searchParams.set("client", "gtx");
  url.searchParams.set("sl", "en");
  url.searchParams.set("tl", GOOGLE_LOCALE.get(target) ?? target);
  url.searchParams.set("dt", "t");
  url.searchParams.set("q", shield(english));
  const response = await fetch(url, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) return english;
  const payload = await response.json();
  const translated = payload[0].map((segment) => segment[0]).join("");
  return unshield(translated, english) || english;
}

async function requestTranslation(target, batch, attempt = 1) {
  const body = batch
    .map(
      ([, value], index) =>
        `<span id="t${String(index).padStart(4, "0")}">${escapeHtml(shield(value))}</span>`,
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
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    const payload = await response.json();
    const combined = payload[0].map((segment) => segment[0]).join("");
    const matches = [...combined.matchAll(/<span id=['"]t(\d{4})['"]>([\s\S]*?)<\/span>/g)];
    if (matches.length === 0 && batch.length === 1) {
      const [key, english] = batch[0];
      return [[key, await requestPlainTranslation(target, english)]];
    }
    if (matches.length !== batch.length) {
      throw new Error(`expected ${batch.length} markers, received ${matches.length}`);
    }
    if (matches.length === 1 && batch.length === 1) {
      const [key, english] = batch[0];
      const value = unshield(decodeHtml(matches[0][2]), english);
      if (!value) return [[key, await requestPlainTranslation(target, english)]];
    }
    return matches.map((match) => {
      const index = Number(match[1]);
      const [key, english] = batch[index];
      const value = unshield(decodeHtml(match[2]), english);
      if (!value) throw new Error(`blank translation for ${key}`);
      const expectedPlaceholders = [...english.matchAll(/\{(\w+)\}/g)].map((item) => item[1]);
      if (expectedPlaceholders.some((name) => !value.includes(`{${name}}`))) {
        throw new Error(`placeholder changed for ${key}`);
      }
      return [key, value];
    });
  } catch (error) {
    if (batch.length > 1 && error instanceof Error && error.message.startsWith("expected ")) {
      const middle = Math.ceil(batch.length / 2);
      return [
        ...(await requestTranslation(target, batch.slice(0, middle))),
        ...(await requestTranslation(target, batch.slice(middle))),
      ];
    }
    if (attempt >= 4) {
      if (batch.length > 1) {
        const middle = Math.ceil(batch.length / 2);
        return [
          ...(await requestTranslation(target, batch.slice(0, middle))),
          ...(await requestTranslation(target, batch.slice(middle))),
        ];
      }
      throw new Error(`${target}: ${error instanceof Error ? error.message : String(error)}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 350 * 2 ** attempt));
    return requestTranslation(target, batch, attempt + 1);
  }
}

async function translate(target, entries, existing, checkpoint) {
  const translated = { ...existing };
  const pending = entries.filter(([key]) => !translated[key]);
  // A nearly complete cache is normally left with the handful of strings
  // whose punctuation made the HTML marker endpoint split a span. Finish
  // those as plain requests in parallel instead of recursively retrying an
  // HTML shape the endpoint has already rejected.
  if (pending.length <= 24) {
    for (let index = 0; index < pending.length; index += CONCURRENCY) {
      const batch = pending.slice(index, index + CONCURRENCY);
      const values = await Promise.all(
        batch.map(([, english]) => requestPlainTranslation(target, english)),
      );
      batch.forEach(([key], valueIndex) => {
        translated[key] = values[valueIndex];
      });
      checkpoint(translated);
    }
    return translated;
  }
  for (const batch of chunks(pending)) {
    for (const [key, value] of await requestTranslation(target, batch)) {
      translated[key] = value;
    }
    checkpoint(translated);
  }
  return translated;
}

function renderRecord(record, indent = "  ") {
  return Object.entries(record)
    .map(([key, value]) => `${indent}${JSON.stringify(key)}: ${JSON.stringify(value)},`)
    .join("\n");
}

fs.mkdirSync(CACHE_DIR, { recursive: true });
const coreEntries = objectEntries(path.join(I18N_ROOT, "messages.ts"), "EN_MESSAGES");
const literalEntries = objectEntries(path.join(I18N_ROOT, "raw-messages.ts"), "RAW_EN_MESSAGES");
const existingCoreCodes = new Set(
  fs
    .readdirSync(path.join(I18N_ROOT, "catalog"), { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".ts"))
    .map((entry) => entry.name.replace(/\.ts$/, "")),
);
const targets = localeCodes().filter((code) => code !== "en");
const results = new Map();
let cursor = 0;

async function worker() {
  while (cursor < targets.length) {
    const target = targets[cursor++];
    const cacheFile = path.join(CACHE_DIR, `${target}.json`);
    let cached = {};
    if (fs.existsSync(cacheFile)) {
      try {
        cached = JSON.parse(fs.readFileSync(cacheFile, "utf8"));
      } catch {
        cached = {};
      }
    }
    const literalComplete = literalEntries.every(([key]) => cached.literal?.[key]);
    const needsCore = !existingCoreCodes.has(target);
    const coreComplete = !needsCore || coreEntries.every(([key]) => cached.core?.[key]);
    const result = {
      literal: cached.literal ?? {},
      core: cached.core ?? {},
    };
    const checkpoint = () => fs.writeFileSync(cacheFile, JSON.stringify(result));
    if (!literalComplete) {
      result.literal = await translate(target, literalEntries, result.literal, (partial) => {
        result.literal = partial;
        checkpoint();
      });
    }
    if (!coreComplete) {
      result.core = await translate(target, coreEntries, result.core, (partial) => {
        result.core = partial;
        checkpoint();
      });
    }
    fs.writeFileSync(cacheFile, JSON.stringify(result));
    results.set(target, result);
    process.stdout.write(`Translated ${target} (${results.size}/${targets.length})\n`);
  }
}

await Promise.all(Array.from({ length: Math.min(CONCURRENCY, targets.length) }, () => worker()));

const generatedCore = targets
  .filter((code) => !existingCoreCodes.has(code))
  .map(
    (code) => `  ${JSON.stringify(code)}: {\n${renderRecord(results.get(code).core, "    ")}\n  },`,
  )
  .join("\n");
const generatedLiterals = targets
  .map(
    (code) =>
      `  ${JSON.stringify(code)}: {\n${renderRecord(results.get(code).literal, "    ")}\n  },`,
  )
  .join("\n");

fs.writeFileSync(
  OUTPUT_FILE,
  `/** Generated by scripts/generate-storefront-translations.mjs. */
import type { LocaleMessages } from "./messages";

export const GENERATED_CORE_CATALOGUES: Readonly<Record<string, LocaleMessages>> = {
${generatedCore}
};

export const GENERATED_LITERAL_CATALOGUES: Readonly<Record<string, LocaleMessages>> = {
${generatedLiterals}
};
`,
);
process.stdout.write(`Wrote ${OUTPUT_FILE}\n`);

#!/usr/bin/env node

/**
 * Fails when storefront copy would render untranslated.
 *
 * WHY THIS WAS REWRITTEN. The previous version walked JSX *text nodes* only.
 * That is a small fraction of where copy actually lives, so it reported a clean
 * tree while `{busy ? "Saving…" : "Save"}`, `aria-label={`Show ${name}`}`,
 * `seoMeta({ title: "Checkout" })`, status enums rendered straight from the
 * database, and every prose prop on `ContactForm` all shipped in English in all
 * ninety-nine languages. A green audit that misses the actual bug is worse than
 * no audit, because it is quoted as evidence.
 *
 * The check is now defined by the tool that does the work: run the localizer in
 * `--check` mode, and fail if it would rewrite a file or regenerate the source
 * catalogue. That makes the audit and the fix the same definition of "covered",
 * so they cannot drift apart.
 *
 * Also verifies that every advertised locale has a complete catalogue, which is
 * what `apps/storefront/app/lib/i18n/i18n.test.ts` asserts at test time — kept
 * here too so `pnpm lint`-style pipelines catch it without running vitest.
 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const I18N = path.resolve("apps/storefront/app/lib/i18n");

let failed = false;

function section(title) {
  process.stdout.write(`\n== ${title}\n`);
}

section("Unwrapped literals and source catalogue freshness");
try {
  const output = execFileSync(
    process.execPath,
    [path.resolve("scripts/localize-storefront-jsx.mjs"), "--check"],
    { encoding: "utf8" },
  );
  process.stdout.write(output);
} catch (error) {
  process.stdout.write(error.stdout ?? "");
  process.stdout.write(error.stderr ?? "");
  failed = true;
}

section("Locale coverage");
// The definitive language list lives in the shared package now — the
// storefront's own `locales.ts` is a re-export shim with no literal
// definitions of its own for this regex to find.
const localeSource = fs.readFileSync(path.resolve("packages/i18n/src/locales.ts"), "utf8");
const advertised = [...localeSource.matchAll(/\{\s*code:\s*"([^"]+)"/g)]
  .map((match) => match[1])
  .filter((code) => code !== "en");

const generated = fs.readFileSync(path.join(I18N, "generated-catalogues.ts"), "utf8");
const handAuthored = new Set(
  fs
    .readdirSync(path.join(I18N, "catalog"), { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".ts"))
    .map((entry) => entry.name.replace(/\.ts$/, "")),
);
// Prettier unquotes keys that are valid identifiers, so `hi: {` and
// `"zh-Hans": {` both appear in this file. Match either shape.
const literalBlocks = new Set(
  [...generated.matchAll(/^ {2}(?:"([\w-]+)"|([A-Za-z_$][\w$]*)):\s*\{/gm)].map(
    (match) => match[1] ?? match[2],
  ),
);

const missing = advertised.filter((code) => !literalBlocks.has(code) && !handAuthored.has(code));
if (missing.length > 0) {
  process.stdout.write(`Locales with no generated catalogue: ${missing.join(", ")}\n`);
  failed = true;
} else {
  process.stdout.write(`OK: all ${advertised.length} advertised locales have a catalogue.\n`);
}

if (failed) {
  process.stdout.write("\nStorefront i18n audit FAILED.\n");
  process.exitCode = 1;
} else {
  process.stdout.write("\nStorefront i18n audit passed.\n");
}

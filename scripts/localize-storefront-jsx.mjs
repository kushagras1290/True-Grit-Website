#!/usr/bin/env node

/**
 * Wraps literal storefront JSX copy in `LocalizedText` and regenerates the
 * deterministic English source catalogue used by those wrappers.
 *
 * This intentionally handles text nodes only. String-valued props are added
 * to the source catalogue too, but reusable components translate those via
 * `useLocalizeText`; one-off native attributes remain visible to the audit.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const ROOT = path.resolve("apps/storefront/app");
const RAW_CATALOGUE = path.join(ROOT, "lib/i18n/raw-messages.ts");
const TRANSLATABLE_ATTRIBUTES = new Set([
  "alt",
  "aria-label",
  "description",
  "eyebrow",
  "heading",
  "label",
  "placeholder",
  "title",
]);
const TRANSLATABLE_OBJECT_PROPERTIES = new Set([
  "body",
  "description",
  "eyebrow",
  "heading",
  "label",
  "meta",
  "placeholder",
  "text",
  "title",
]);
const IGNORED_FILES = new Set(["language-suggestion.tsx"]);
const NON_TRANSLATABLE = new Set(["G", "TG", "f", "True Grit", "TRUE GRIT", "VITE_API_URL"]);

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) return walk(target);
    return entry.isFile() && target.endsWith(".tsx") ? [target] : [];
  });
}

function normalized(value) {
  return value.replace(/\s+/g, " ").trim();
}

function decoded(value) {
  return value
    .replaceAll("&amp;", "&")
    .replaceAll("&apos;", "'")
    .replaceAll("&#39;", "'")
    .replaceAll("&quot;", '"')
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)));
}

function isTranslatable(value) {
  return /\p{L}/u.test(value) && !NON_TRANSLATABLE.has(value) && !/^https?:\/\//.test(value);
}

function insideLocalizedText(node, source) {
  let current = node.parent;
  while (current) {
    if (
      ts.isJsxElement(current) &&
      current.openingElement.tagName.getText(source) === "LocalizedText"
    ) {
      return true;
    }
    current = current.parent;
  }
  return false;
}

const allSources = new Set();
let changedFiles = 0;

for (const file of walk(ROOT)) {
  if (
    IGNORED_FILES.has(path.basename(file)) ||
    file === path.join(ROOT, "lib/i18n/localized-text.tsx")
  ) {
    continue;
  }
  let sourceText = fs.readFileSync(file, "utf8");
  const source = ts.createSourceFile(
    file,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const replacements = [];

  function visit(node) {
    if (ts.isJsxText(node)) {
      const value = decoded(normalized(node.text));
      if (isTranslatable(value)) {
        allSources.add(value);
        if (!insideLocalizedText(node, source)) {
          const raw = sourceText.slice(node.pos, node.end);
          const leading = raw.match(/^\s*/)?.[0] ?? "";
          const trailing = raw.match(/\s*$/)?.[0] ?? "";
          const core = raw.slice(leading.length, raw.length - trailing.length).replace(/\s+/g, " ");
          replacements.push({
            start: node.pos,
            end: node.end,
            value: `${leading}<LocalizedText>${core}</LocalizedText>${trailing}`,
          });
        }
      }
    }
    if (
      ts.isJsxAttribute(node) &&
      TRANSLATABLE_ATTRIBUTES.has(node.name.text) &&
      node.initializer &&
      ts.isStringLiteral(node.initializer)
    ) {
      const value = decoded(normalized(node.initializer.text));
      if (isTranslatable(value)) allSources.add(value);
    }
    if (
      ts.isPropertyAssignment(node) &&
      TRANSLATABLE_OBJECT_PROPERTIES.has(node.name.getText(source).replace(/["']/g, "")) &&
      ts.isStringLiteralLike(node.initializer)
    ) {
      const value = decoded(normalized(node.initializer.text));
      if (isTranslatable(value)) allSources.add(value);
    }
    ts.forEachChild(node, visit);
  }
  visit(source);

  if (replacements.length === 0) continue;
  for (const replacement of replacements.sort((a, b) => b.start - a.start)) {
    sourceText =
      sourceText.slice(0, replacement.start) +
      replacement.value +
      sourceText.slice(replacement.end);
  }

  if (
    !sourceText.includes('from "../lib/i18n/localized-text"') &&
    !sourceText.includes('from "./lib/i18n/localized-text"')
  ) {
    const target = path.join(ROOT, "lib/i18n/localized-text");
    let relative = path.relative(path.dirname(file), target).replaceAll("\\", "/");
    if (!relative.startsWith(".")) relative = `./${relative}`;
    const imports = [...source.statements].filter(ts.isImportDeclaration);
    const insertion = imports.length > 0 ? imports.at(-1).end : 0;
    sourceText = `${sourceText.slice(0, insertion)}\nimport { LocalizedText } from "${relative}";${sourceText.slice(insertion)}`;
  }

  fs.writeFileSync(file, sourceText);
  changedFiles += 1;
}

const entries = [...allSources]
  .sort((a, b) => a.localeCompare(b, "en"))
  .map((source) => {
    const key = `literal.${crypto.createHash("sha1").update(source).digest("hex").slice(0, 12)}`;
    return `  ${JSON.stringify(key)}: ${JSON.stringify(source)},`;
  });

const catalogue = `/**
 * Generated English source catalogue for literal storefront UI copy.
 * Run \`node scripts/localize-storefront-jsx.mjs\` after adding JSX copy.
 */
const RAW_EN_MESSAGES = {
${entries.join("\n")}
} as const;

export default RAW_EN_MESSAGES;
`;
fs.writeFileSync(RAW_CATALOGUE, catalogue);

process.stdout.write(
  `Localized ${allSources.size} source strings across ${changedFiles} changed files.\n`,
);

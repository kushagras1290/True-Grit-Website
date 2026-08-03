#!/usr/bin/env node

/**
 * Reports storefront-owned JSX copy that is still rendered as a literal.
 *
 * Database/CMS fields are expressions and therefore never appear here. Keeping
 * this audit parser-based avoids the false positives produced by grepping
 * TypeScript operators, comments, class names, and test descriptions.
 */

import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const ROOT = path.resolve("apps/storefront/app");
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
const IGNORED_FILES = new Set(["language-suggestion.tsx"]);
const LOCALLY_TRANSLATED_PROP_COMPONENTS = new Set([
  "CopyBlock",
  "IndexLink",
  "PageBanner",
  "PhoneVerifier",
  "RecommendedProducts",
  "Section",
  "StaticHero",
  "SupportCta",
]);
const NON_TRANSLATABLE = new Set(["G", "TG", "f", "True Grit", "TRUE GRIT", "VITE_API_URL"]);

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) return walk(target);
    return entry.isFile() && target.endsWith(".tsx") ? [target] : [];
  });
}

function isWords(value) {
  return /\p{L}/u.test(value) && !/^https?:\/\//.test(value);
}

const findings = [];
for (const file of walk(ROOT)) {
  if (IGNORED_FILES.has(path.basename(file))) continue;
  const sourceText = fs.readFileSync(file, "utf8");
  const source = ts.createSourceFile(
    file,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );

  function report(node, kind, value) {
    const normalized = value.replace(/\s+/g, " ").trim();
    if (!isWords(normalized) || NON_TRANSLATABLE.has(normalized)) return;
    const { line } = source.getLineAndCharacterOfPosition(node.getStart(source));
    findings.push({
      file: path.relative(process.cwd(), file).replaceAll("\\", "/"),
      line: line + 1,
      kind,
      value: normalized,
    });
  }

  function visit(node) {
    const insideLocalizedText = (candidate) => {
      let current = candidate.parent;
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
    };
    if (ts.isJsxText(node) && !insideLocalizedText(node)) report(node, "text", node.text);
    if (
      ts.isJsxAttribute(node) &&
      TRANSLATABLE_ATTRIBUTES.has(node.name.text) &&
      node.initializer &&
      ts.isStringLiteral(node.initializer)
    ) {
      let owner = node.parent;
      while (owner && !ts.isJsxOpeningLikeElement(owner)) owner = owner.parent;
      const tagName =
        owner && ts.isJsxOpeningLikeElement(owner) ? owner.tagName.getText(source) : "";
      if (!LOCALLY_TRANSLATED_PROP_COMPONENTS.has(tagName)) {
        report(node, node.name.text, node.initializer.text);
      }
    }
    ts.forEachChild(node, visit);
  }

  visit(source);
}

for (const finding of findings) {
  process.stdout.write(
    `${finding.file}:${finding.line} [${finding.kind}] ${JSON.stringify(finding.value)}\n`,
  );
}
process.stdout.write(`\n${findings.length} untranslated JSX literals\n`);
if (findings.length > 0) process.exitCode = 1;

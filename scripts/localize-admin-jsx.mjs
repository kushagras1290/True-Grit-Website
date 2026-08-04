#!/usr/bin/env node

/**
 * Wraps literal admin-panel JSX copy in `<T>` and regenerates the English
 * source list the admin catalogue is built from.
 *
 * The same two shapes the storefront localizer handles, for the same reason:
 * a text node and a children expression (`{busy ? "Saving…" : "Save"}`) render
 * identically and are equally invisible to a naive grep.
 *
 * `--check` reports without writing and exits non-zero, for CI.
 */

import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const ROOT = path.resolve("apps/admin/src");
const SOURCES_FILE = path.join(ROOT, "lib/i18n/source-strings.ts");
const CHECK_ONLY = process.argv.includes("--check");

const TRANSLATABLE_ATTRIBUTES = new Set([
  "alt",
  "aria-label",
  "description",
  "emptyMessage",
  "heading",
  "hint",
  "label",
  "message",
  "placeholder",
  "subtitle",
  "title",
]);

const TRANSLATABLE_OBJECT_PROPERTIES = new Set([
  "description",
  "heading",
  "hint",
  "label",
  "message",
  "placeholder",
  "subtitle",
  "title",
]);

const SOURCE_TEXT_CALLERS = new Set(["t", "format"]);
const NON_TRANSLATABLE = new Set(["True Grit", "TRUE GRIT", "VITE_API_URL"]);

/** Files that must not be rewritten: the i18n plumbing itself, and tests. */
const SKIP = /(?:[\\/]lib[\\/]i18n[\\/]|\.test\.tsx?$|test-setup\.ts$)/;

const MODIFIED_CLASS_TOKEN =
  /^-?(?:[a-z][a-z0-9]*:)*[a-z][a-zA-Z0-9]*(?:-[a-zA-Z0-9.[\]#%/()_-]+)+$/;
const BARE_CLASS_TOKEN =
  /^(?:flex|grid|block|inline|hidden|absolute|relative|sticky|fixed|isolate|truncate|uppercase|lowercase|capitalize|italic|underline|group|peer|contents|table|border|rounded|shadow|blur|filter|antialiased|grow|shrink|transition|invisible|visible)$/;

function isClassNameString(value) {
  const tokens = value.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return false;
  return tokens.every((token) => MODIFIED_CLASS_TOKEN.test(token) || BARE_CLASS_TOKEN.test(token));
}

const normalized = (value) => value.replace(/\s+/g, " ").trim();

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
  if (!/\p{L}/u.test(value)) return false;
  if (NON_TRANSLATABLE.has(value)) return false;
  if (/^https?:\/\//.test(value)) return false;
  if (isClassNameString(value)) return false;
  if (!/\s/.test(value) && /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(value)) return false;
  return true;
}

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) return walk(target);
    if (!entry.isFile() || !/\.tsx?$/.test(target) || SKIP.test(target)) return [];
    return [target];
  });
}

function insideT(node, source) {
  let current = node.parent;
  while (current) {
    if (ts.isJsxElement(current) && current.openingElement.tagName.getText(source) === "T") {
      return true;
    }
    current = current.parent;
  }
  return false;
}

/** True when a string literal renders directly as JSX children. */
function rendersAsChildren(node) {
  let current = node;
  let parent = current.parent;
  while (parent) {
    if (ts.isJsxExpression(parent)) return !ts.isJsxAttribute(parent.parent);
    if (ts.isParenthesizedExpression(parent)) {
      current = parent;
      parent = parent.parent;
      continue;
    }
    if (ts.isConditionalExpression(parent) && parent.condition !== current) {
      current = parent;
      parent = parent.parent;
      continue;
    }
    if (
      ts.isBinaryExpression(parent) &&
      [
        ts.SyntaxKind.AmpersandAmpersandToken,
        ts.SyntaxKind.BarBarToken,
        ts.SyntaxKind.QuestionQuestionToken,
      ].includes(parent.operatorToken.kind)
    ) {
      current = parent;
      parent = parent.parent;
      continue;
    }
    return false;
  }
  return false;
}

const allSources = new Set();
const unwrapped = [];
let changedFiles = 0;

for (const file of walk(ROOT)) {
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
        if (!insideT(node, source)) {
          const raw = sourceText.slice(node.pos, node.end);
          const leading = raw.match(/^\s*/)?.[0] ?? "";
          const trailing = raw.match(/\s*$/)?.[0] ?? "";
          const core = raw.slice(leading.length, raw.length - trailing.length).replace(/\s+/g, " ");
          replacements.push({
            start: node.pos,
            end: node.end,
            value: `${leading}<T>${core}</T>${trailing}`,
          });
        }
      }
    }

    if (ts.isStringLiteralLike(node) && !ts.isJsxText(node) && rendersAsChildren(node)) {
      const value = decoded(normalized(node.text));
      if (isTranslatable(value)) {
        // Collected on every pass, regardless of whether it is already
        // wrapped — a second run must see the same source strings the first
        // run did, or the catalogue silently loses entries every time this
        // script runs again after `<T>` has already been applied.
        allSources.add(value);
        if (!insideT(node, source)) {
          replacements.push({
            start: node.getStart(source),
            end: node.end,
            value: `<T>{${node.getText(source)}}</T>`,
          });
        }
      }
    }

    if (
      ts.isJsxAttribute(node) &&
      TRANSLATABLE_ATTRIBUTES.has(node.name.getText(source)) &&
      node.initializer
    ) {
      const collect = (expression) => {
        if (ts.isStringLiteralLike(expression)) {
          const value = decoded(normalized(expression.text));
          if (isTranslatable(value)) allSources.add(value);
          return;
        }
        if (ts.isConditionalExpression(expression)) {
          collect(expression.whenTrue);
          collect(expression.whenFalse);
        }
      };
      if (ts.isStringLiteral(node.initializer)) collect(node.initializer);
      else if (ts.isJsxExpression(node.initializer) && node.initializer.expression) {
        collect(node.initializer.expression);
      }
    }

    if (
      ts.isPropertyAssignment(node) &&
      TRANSLATABLE_OBJECT_PROPERTIES.has(node.name.getText(source).replace(/["']/g, "")) &&
      ts.isStringLiteralLike(node.initializer)
    ) {
      const value = decoded(normalized(node.initializer.text));
      if (isTranslatable(value)) allSources.add(value);
    }

    if (
      ts.isCallExpression(node) &&
      SOURCE_TEXT_CALLERS.has(node.expression.getText(source)) &&
      node.arguments.length > 0 &&
      ts.isStringLiteralLike(node.arguments[0])
    ) {
      const value = decoded(normalized(node.arguments[0].text));
      if (isTranslatable(value)) allSources.add(value);
    }

    ts.forEachChild(node, visit);
  }
  visit(source);

  if (replacements.length === 0) continue;

  if (CHECK_ONLY) {
    const relative = path.relative(process.cwd(), file).replaceAll("\\", "/");
    for (const replacement of replacements) {
      const { line } = source.getLineAndCharacterOfPosition(replacement.start);
      unwrapped.push(`${relative}:${line + 1}`);
    }
    changedFiles += 1;
    continue;
  }

  for (const replacement of replacements.sort((a, b) => b.start - a.start)) {
    sourceText =
      sourceText.slice(0, replacement.start) +
      replacement.value +
      sourceText.slice(replacement.end);
  }
  if (!/^import \{[^}]*\bT\b[^}]*\} from "[^"]*lib\/i18n";$/m.test(sourceText)) {
    let relative = path
      .relative(path.dirname(file), path.join(ROOT, "lib/i18n"))
      .replaceAll("\\", "/");
    if (!relative.startsWith(".")) relative = `./${relative}`;
    const imports = [...source.statements].filter(ts.isImportDeclaration);
    const insertion = imports.length > 0 ? imports.at(-1).end : 0;
    sourceText = `${sourceText.slice(0, insertion)}\nimport { T } from "${relative}";${sourceText.slice(insertion)}`;
  }
  fs.writeFileSync(file, sourceText);
  changedFiles += 1;
}

const sorted = [...allSources].sort((a, b) => a.localeCompare(b, "en"));
const output = `/**
 * Generated English source strings for admin-panel copy.
 * Run \`node scripts/localize-admin-jsx.mjs\` after adding UI copy.
 */
const ADMIN_SOURCE_STRINGS = [
${sorted.map((value) => `  ${JSON.stringify(value)},`).join("\n")}
] as const;

export default ADMIN_SOURCE_STRINGS;
`;

if (CHECK_ONLY) {
  // Parsed via the TypeScript AST, like the storefront's check — a regex over
  // the rendered file is fragile against whatever escaping JSON.stringify
  // chose for a given string (quotes, backslashes, surrogate pairs).
  const existing = new Set();
  if (fs.existsSync(SOURCES_FILE)) {
    const currentText = fs.readFileSync(SOURCES_FILE, "utf8");
    const currentSource = ts.createSourceFile(
      SOURCES_FILE,
      currentText,
      ts.ScriptTarget.Latest,
      true,
    );
    const collect = (node) => {
      if (ts.isArrayLiteralExpression(node)) {
        for (const element of node.elements) {
          if (ts.isStringLiteralLike(element)) existing.add(element.text);
        }
      }
      ts.forEachChild(node, collect);
    };
    collect(currentSource);
  }
  const expected = new Set(sorted);
  const stale =
    existing.size !== expected.size || [...expected].some((value) => !existing.has(value));
  for (const location of unwrapped) process.stdout.write(`${location} untranslated literal\n`);
  if (stale) process.stdout.write("lib/i18n/source-strings.ts is out of date\n");
  if (unwrapped.length > 0 || stale) {
    process.stdout.write(
      `\n${unwrapped.length} unwrapped literal(s). Run: node scripts/localize-admin-jsx.mjs\n`,
    );
    process.exitCode = 1;
  } else {
    process.stdout.write(`OK: ${allSources.size} admin source strings, nothing unwrapped.\n`);
  }
} else {
  fs.mkdirSync(path.dirname(SOURCES_FILE), { recursive: true });
  fs.writeFileSync(SOURCES_FILE, output);
  process.stdout.write(
    `Localized ${allSources.size} admin source strings across ${changedFiles} changed files.\n`,
  );
}

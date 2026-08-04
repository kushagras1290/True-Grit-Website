#!/usr/bin/env node

/**
 * Wraps literal storefront JSX copy in `LocalizedText` and regenerates the
 * deterministic English source catalogue used by those wrappers.
 *
 * Two shapes of literal are rewritten in place:
 *
 *   * text nodes            — `<p>Save</p>`
 *   * children expressions  — `{busy ? "Saving…" : "Save"}`
 *
 * The second is the reason this script exists in its current form: a ternary
 * inside JSX renders exactly like a text node and is invisible to a text-node
 * walker, so every "Submitting…"/"Submit" button in the storefront shipped
 * untranslated while the audit reported a clean tree.
 *
 * String-valued props are collected into the catalogue but never rewritten:
 * reusable components translate their own prose props with `useLocalizeText`,
 * which keeps the call sites readable and the translation in one place.
 * Interpolated copy is collected from `useLocalizeFormat` call sites, whose
 * first argument is the placeholder-bearing source string.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const ROOT = path.resolve("apps/storefront/app");
const RAW_CATALOGUE = path.join(ROOT, "lib/i18n/raw-messages.ts");

/**
 * `--check` reports what would change and writes nothing, exiting non-zero if
 * anything would. That is the CI guard: a pull request that adds a literal
 * without running this script fails, which is the only thing that keeps
 * "everything is translated" true a month from now.
 */
const CHECK_ONLY = process.argv.includes("--check");

/** Props whose value is prose the visitor reads. Native attributes and the
 *  storefront's own component props share one list — both end up as text. */
const TRANSLATABLE_ATTRIBUTES = new Set([
  "alt",
  "aria-description",
  "aria-label",
  "ariaLabel",
  "body",
  "caption",
  "cta",
  "defaultSubject",
  "description",
  "emptyMessage",
  "errorMessage",
  "eyebrow",
  "heading",
  "hint",
  "imageAlt",
  "label",
  "legend",
  "message",
  "messagePlaceholder",
  "note",
  "placeholder",
  "submitLabel",
  "subtitle",
  "successMessage",
  "summary",
  "tagline",
  "text",
  "title",
]);

/** Object keys that carry prose in page data tables and status maps. */
const TRANSLATABLE_OBJECT_PROPERTIES = new Set([
  "answer",
  "blurb",
  "body",
  "caption",
  "copy",
  "cta",
  "description",
  "detail",
  "eyebrow",
  "heading",
  "helper",
  "helperText",
  "hint",
  "label",
  "legend",
  "message",
  "meta",
  "note",
  "placeholder",
  "prompt",
  "question",
  "subtitle",
  "summary",
  "text",
  "title",
]);

/** Functions whose first argument is English source text. */
const SOURCE_TEXT_CALLERS = new Set(["localize", "format", "localizeFormat", "formatSource"]);

/**
 * Functions whose string arguments are copy the visitor eventually reads.
 *
 * `setError("Could not place your order.")` lands in `{localize(error)}`, so
 * the literal needs to be in the catalogue even though it never appears in
 * JSX. `messageFrom` is `phone-auth`'s fallback helper, same story.
 */
const MESSAGE_ARGUMENT_CALLERS = /^(?:set[A-Z]\w*Error|messageFrom)$/;

const IGNORED_FILES = new Set();
const NON_TRANSLATABLE = new Set(["G", "TG", "f", "True Grit", "TRUE GRIT", "VITE_API_URL"]);

/**
 * Utility-class strings look like prose to a parser and never to a reader.
 *
 * Classified by the *whole* string, not by spotting a keyword anywhere in it.
 * A substring test rejects real copy: "collectives that grow the market"
 * contains `grow`, "ships on fixed dispatch days" contains `fixed`, and
 * "flexible ways to cook" starts a word with `flex`. Every one of those is a
 * sentence a customer reads, and every one was silently dropped from the
 * catalogue before this became a whole-string test.
 */
const MODIFIED_CLASS_TOKEN =
  /^-?(?:[a-z][a-z0-9]*:)*[a-z][a-zA-Z0-9]*(?:-[a-zA-Z0-9.[\]#%/()_-]+)+$/;
const BARE_CLASS_TOKEN =
  /^(?:flex|grid|block|inline|hidden|absolute|relative|sticky|fixed|isolate|truncate|uppercase|lowercase|capitalize|italic|underline|group|peer|contents|table|border|rounded|shadow|blur|filter|antialiased|grow|shrink|transition|invisible|visible)$/;

function isClassNameString(value) {
  const tokens = value.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return false;
  return tokens.every((token) => MODIFIED_CLASS_TOKEN.test(token) || BARE_CLASS_TOKEN.test(token));
}

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
  if (!/\p{L}/u.test(value)) return false;
  if (NON_TRANSLATABLE.has(value)) return false;
  if (/^https?:\/\//.test(value)) return false;
  if (isClassNameString(value)) return false;
  // `width=device-width, initial-scale=1` and friends: machine directives that
  // happen to contain letters.
  if (/^[a-z-]+=[^\s]+(?:,\s*[a-z-]+=[^\s]+)*$/i.test(value)) return false;
  // A bare identifier or slug is a value, not a sentence.
  if (!/\s/.test(value) && /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(value)) return false;
  return true;
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

/**
 * True when `node` is a string literal that renders directly as JSX children.
 *
 * Only pass-through operators may sit between the literal and the expression
 * container. A literal inside a call, a template, an object or an arrow body is
 * an argument or a value — rewriting it to an element would change what the
 * code means, not just what language it renders in.
 */
function rendersAsChildren(node) {
  let current = node;
  let parent = current.parent;
  while (parent) {
    if (ts.isJsxExpression(parent)) {
      // An attribute value is not children, and cannot hold an element.
      return !ts.isJsxAttribute(parent.parent);
    }
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

/** `setError("…")`, including the string arm of `cond ? err.message : "…"`. */
function collectMessageArguments(node, source) {
  if (!ts.isCallExpression(node)) return;
  if (!MESSAGE_ARGUMENT_CALLERS.test(node.expression.getText(source))) return;
  const consider = (expression) => {
    if (ts.isStringLiteralLike(expression)) {
      const value = decoded(normalized(expression.text));
      if (isTranslatable(value)) allSources.add(value);
      return;
    }
    if (ts.isConditionalExpression(expression)) {
      consider(expression.whenTrue);
      consider(expression.whenFalse);
      return;
    }
    if (ts.isBinaryExpression(expression)) {
      consider(expression.left);
      consider(expression.right);
    }
  };
  for (const argument of node.arguments) consider(argument);
}

/**
 * `const ORDER_STATUS = { pending_payment: "Pending payment", … }`.
 *
 * These tables are keyed by a database token, so the key never matches the
 * prose-key list; the *values* are the copy. SCREAMING_SNAKE is this
 * codebase's convention for a module-level lookup table, which makes it a
 * reliable signal — and `isTranslatable` still rejects class-name blobs and
 * slugs, so a constant holding CSS or route fragments contributes nothing.
 */
function collectLabelTable(node, source) {
  if (!ts.isVariableDeclaration(node) || !node.initializer) return;
  if (!/^[A-Z][A-Z0-9_]*$/.test(node.name.getText(source))) return;
  let initializer = node.initializer;
  while (ts.isAsExpression(initializer) || ts.isSatisfiesExpression(initializer)) {
    initializer = initializer.expression;
  }
  if (!ts.isObjectLiteralExpression(initializer)) return;
  for (const property of initializer.properties) {
    if (!ts.isPropertyAssignment(property) || !ts.isStringLiteralLike(property.initializer)) {
      continue;
    }
    const value = decoded(normalized(property.initializer.text));
    if (isTranslatable(value)) allSources.add(value);
  }
}

let changedFiles = 0;
let wrappedText = 0;
let wrappedExpressions = 0;
/** Locations of literals `--check` found still unwrapped. */
const unwrapped = [];

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
          wrappedText += 1;
        }
      }
    }

    // `{busy ? "Saving…" : "Save"}` and friends. The literal is preserved
    // verbatim inside the wrapper, so quoting and escaping never change.
    if (ts.isStringLiteralLike(node) && !ts.isJsxText(node) && rendersAsChildren(node)) {
      const value = decoded(normalized(node.text));
      if (isTranslatable(value)) {
        // Collected on every pass regardless of whether it is already
        // wrapped. Gating this on `!insideLocalizedText` — as an earlier
        // version did — meant re-running the script after wrapping a string
        // stopped seeing it at all, silently dropping it from the regenerated
        // catalogue on the very next extraction.
        allSources.add(value);
        if (!insideLocalizedText(node, source)) {
          replacements.push({
            start: node.getStart(source),
            end: node.end,
            value: `<LocalizedText>{${node.getText(source)}}</LocalizedText>`,
          });
          wrappedExpressions += 1;
        }
      }
    }

    if (
      ts.isJsxAttribute(node) &&
      TRANSLATABLE_ATTRIBUTES.has(node.name.getText(source)) &&
      node.initializer
    ) {
      // Both `heading="…"` and `heading={draft ? "…" : "…"}`. The conditional
      // form is how a route picks between two headings, and skipping it left
      // pairs like "Revise your post"/"Revise your recipe" out of every
      // catalogue while their sibling literals were translated.
      const collectAttributeText = (expression) => {
        if (ts.isStringLiteralLike(expression)) {
          const value = decoded(normalized(expression.text));
          if (isTranslatable(value)) allSources.add(value);
          return;
        }
        if (ts.isConditionalExpression(expression)) {
          collectAttributeText(expression.whenTrue);
          collectAttributeText(expression.whenFalse);
          return;
        }
        if (ts.isBinaryExpression(expression)) {
          collectAttributeText(expression.left);
          collectAttributeText(expression.right);
          return;
        }
        if (ts.isParenthesizedExpression(expression)) collectAttributeText(expression.expression);
      };
      if (ts.isStringLiteral(node.initializer)) collectAttributeText(node.initializer);
      else if (ts.isJsxExpression(node.initializer) && node.initializer.expression) {
        collectAttributeText(node.initializer.expression);
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

    // `format("Reviews for {product}", { product })` — the placeholder-bearing
    // source string is the catalogue entry.
    if (
      ts.isCallExpression(node) &&
      SOURCE_TEXT_CALLERS.has(node.expression.getText(source)) &&
      node.arguments.length > 0 &&
      ts.isStringLiteralLike(node.arguments[0])
    ) {
      const value = decoded(normalized(node.arguments[0].text));
      if (isTranslatable(value)) allSources.add(value);
    }

    collectMessageArguments(node, source);
    collectLabelTable(node, source);

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

  // Any relative depth, and any named-import shape — matching the exact
  // specifier is what previously produced a duplicate import in a file that
  // reached the module by a shorter path.
  if (!/^import\s*\{[^}]*\}\s*from\s*"[^"]*i18n\/localized-text";$/m.test(sourceText)) {
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

// Non-JSX modules hold prose too: status tables, reason lists and the copy
// passed to `seoMeta`. They are collected, never rewritten — the component
// that renders the value is what translates it.
/** Files inside `lib/i18n` that hold English source rather than translations. */
const I18N_SOURCE_MODULES = new Set(["status-labels.ts"]);

function collectFromModules(directory, insideCatalogueDirectory = false) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      // The i18n directory holds the catalogues themselves; walking it whole
      // would feed translated strings back in as if they were English source.
      collectFromModules(target, insideCatalogueDirectory || entry.name === "i18n");
      continue;
    }
    if (!entry.isFile() || !target.endsWith(".ts") || target.endsWith(".test.ts")) continue;
    if (insideCatalogueDirectory && !I18N_SOURCE_MODULES.has(path.basename(target))) continue;
    const text = fs.readFileSync(target, "utf8");
    const module = ts.createSourceFile(target, text, ts.ScriptTarget.Latest, true);
    const visit = (node) => {
      if (
        ts.isPropertyAssignment(node) &&
        TRANSLATABLE_OBJECT_PROPERTIES.has(node.name.getText(module).replace(/["']/g, "")) &&
        ts.isStringLiteralLike(node.initializer)
      ) {
        const value = decoded(normalized(node.initializer.text));
        if (isTranslatable(value)) allSources.add(value);
      }
      if (
        ts.isCallExpression(node) &&
        SOURCE_TEXT_CALLERS.has(node.expression.getText(module)) &&
        node.arguments.length > 0 &&
        ts.isStringLiteralLike(node.arguments[0])
      ) {
        const value = decoded(normalized(node.arguments[0].text));
        if (isTranslatable(value)) allSources.add(value);
      }
      collectMessageArguments(node, module);
      collectLabelTable(node, module);
      ts.forEachChild(node, visit);
    };
    visit(module);
  }
}
collectFromModules(ROOT);

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

if (CHECK_ONLY) {
  // Compare entries, not bytes. Prettier reformats the generated file after
  // this script writes it (long strings get wrapped), so a byte comparison
  // reports every formatted catalogue as stale and the check never passes.
  const currentEntries = new Map();
  if (fs.existsSync(RAW_CATALOGUE)) {
    const currentText = fs.readFileSync(RAW_CATALOGUE, "utf8");
    const currentSource = ts.createSourceFile(
      RAW_CATALOGUE,
      currentText,
      ts.ScriptTarget.Latest,
      true,
    );
    const collect = (node) => {
      if (ts.isPropertyAssignment(node) && ts.isStringLiteralLike(node.initializer)) {
        currentEntries.set(
          node.name.getText(currentSource).replace(/^["']|["']$/g, ""),
          node.initializer.text,
        );
      }
      ts.forEachChild(node, collect);
    };
    collect(currentSource);
  }
  const expectedEntries = new Map(
    [...allSources].map((value) => [
      `literal.${crypto.createHash("sha1").update(value).digest("hex").slice(0, 12)}`,
      value,
    ]),
  );
  const catalogueStale =
    currentEntries.size !== expectedEntries.size ||
    [...expectedEntries].some(([key, value]) => currentEntries.get(key) !== value);
  for (const location of unwrapped) {
    process.stdout.write(`${location} untranslated literal\n`);
  }
  if (catalogueStale) {
    process.stdout.write("lib/i18n/raw-messages.ts is out of date\n");
  }
  if (unwrapped.length > 0 || catalogueStale) {
    process.stdout.write(
      `\n${unwrapped.length} unwrapped literal(s)` +
        `${catalogueStale ? " and a stale source catalogue" : ""}.\n` +
        "Run: node scripts/localize-storefront-jsx.mjs\n" +
        "Then: node scripts/generate-storefront-translations.mjs\n",
    );
    process.exitCode = 1;
  } else {
    process.stdout.write(`OK: ${allSources.size} source strings, nothing unwrapped.\n`);
  }
} else {
  fs.writeFileSync(RAW_CATALOGUE, catalogue);
  process.stdout.write(
    `Localized ${allSources.size} source strings across ${changedFiles} changed files ` +
      `(${wrappedText} text nodes, ${wrappedExpressions} children expressions).\n`,
  );
}

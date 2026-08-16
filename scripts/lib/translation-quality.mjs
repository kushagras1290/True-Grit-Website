/**
 * Mechanical quality checks for machine-translated catalogue strings.
 *
 * WHY THIS EXISTS. `backfill-entity-translations.mjs` sent most locales through
 * `@cf/meta/m2m100-1.2b`, a small 2020-era translation model, and wrote whatever
 * came back. Production picked up strings like "रसोई के लिए रसोई के लिए रसोई"
 * ("kitchen for kitchen for kitchen"), "_KKathiya ग्रीनहाउस" (a half-repaired
 * brand placeholder next to "greenhouse") and titles where the brand itself had
 * been translated. Every one of those is detectable without knowing the target
 * language, and none of them should ever have reached the database.
 *
 * WHAT THIS CANNOT DO. These are mechanical checks, not a meaning check. A
 * fluent, correctly-scripted, correctly-shaped translation that simply says the
 * wrong thing -- "Daliya" rendered as "डैडी - टॉयलेट" ("Daddy - Toilet") -- is
 * invisible here. Detecting that needs a round-trip or a stronger model, which
 * is why the accompanying purge removes the whole M2M100 generation rather than
 * trying to keep the rows that happen to pass these gates.
 */

/** Issue codes, ordered roughly by how conclusive each one is. */
export const TRANSLATION_ISSUES = Object.freeze({
  EMPTY: "empty",
  PLACEHOLDER_LEAK: "placeholder-leak",
  BRAND_LOST: "brand-lost",
  BRAND_MANGLED: "brand-mangled",
  REPETITION: "repetition",
  SCRIPT_MISMATCH: "script-mismatch",
  LENGTH_ANOMALY: "length-anomaly",
});

/**
 * Terms the pipeline shields and therefore expects back verbatim. A brand that
 * survives as Latin text inside another script is correct and intended; a brand
 * that has been translated, transliterated or chewed up is not.
 */
const PROTECTED_TERMS = Object.freeze([
  "True Grit",
  "Vikas Farms",
  "Kathiya",
  "Banshi",
  "Paigambari",
]);

/**
 * Debris left when M2M100 mangles a `[[[9003]]]` shield marker. `unshield()` in
 * the backfill repairs many of these, so anything still present at write time
 * means the repair missed and the value is unusable.
 */
const PLACEHOLDER_DEBRIS = /\[{2,}\s*900\d|900\d\s*\]{2,}|tgbrand|\[\[\[|\]\]\]/i;

function escapeForRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Shield scars around a brand: `_ True Grit_`, `__Banshi`, and the doubled
 * initial in `_KKathiya` that production is serving today.
 *
 * Built per term rather than as one alternation because the doubled-initial
 * shape needs the term's own first letter, which a shared pattern cannot
 * backreference into an alternation branch.
 */
const BRAND_SCARS = PROTECTED_TERMS.map((term) => {
  const escaped = escapeForRegExp(term);
  const initial = escapeForRegExp(term[0]);
  return new RegExp(`_+\\s*${initial}?${escaped}|${escaped}\\s*_+|\\b${initial}${escaped}`, "i");
});

/**
 * Dominant script per locale, as a character class. Locales written in Latin
 * are absent: there is nothing to distinguish them from untranslated English.
 */
const LOCALE_SCRIPT = new Map([
  ["hi", "\\u0900-\\u097F"],
  ["mr", "\\u0900-\\u097F"],
  ["ne", "\\u0900-\\u097F"],
  ["sa", "\\u0900-\\u097F"],
  ["kok", "\\u0900-\\u097F"],
  ["mai", "\\u0900-\\u097F"],
  ["doi", "\\u0900-\\u097F"],
  ["brx", "\\u0900-\\u097F"],
  ["bn", "\\u0980-\\u09FF"],
  ["as", "\\u0980-\\u09FF"],
  ["pa", "\\u0A00-\\u0A7F"],
  ["gu", "\\u0A80-\\u0AFF"],
  ["or", "\\u0B00-\\u0B7F"],
  ["ta", "\\u0B80-\\u0BFF"],
  ["te", "\\u0C00-\\u0C7F"],
  ["kn", "\\u0C80-\\u0CFF"],
  ["ml", "\\u0D00-\\u0D7F"],
  ["ur", "\\u0600-\\u06FF"],
  ["ar", "\\u0600-\\u06FF"],
  ["fa", "\\u0600-\\u06FF"],
  ["ks", "\\u0600-\\u06FF"],
  ["sd", "\\u0600-\\u06FF"],
  ["sat", "\\u1C50-\\u1C7F"],
  ["mni", "\\uABC0-\\uABFF"],
  ["zh-Hans", "\\u4E00-\\u9FFF"],
  ["zh-Hant", "\\u4E00-\\u9FFF"],
  ["ja", "\\u3040-\\u30FF\\u4E00-\\u9FFF"],
  ["ko", "\\uAC00-\\uD7AF"],
  ["ru", "\\u0400-\\u04FF"],
  ["uk", "\\u0400-\\u04FF"],
  ["bg", "\\u0400-\\u04FF"],
  ["el", "\\u0370-\\u03FF"],
  ["he", "\\u0590-\\u05FF"],
  ["th", "\\u0E00-\\u0E7F"],
]);

/**
 * Share of letters that must be in the target script. Deliberately lenient:
 * a correct title legitimately keeps the brand, a variety name and often a unit
 * in Latin, so only a value that is overwhelmingly Latin is treated as a miss.
 */
const MIN_TARGET_SCRIPT_RATIO = 0.3;

/** Scripts that pack more meaning per character than English. */
const COMPACT_SCRIPTS = new Set(["zh-Hans", "zh-Hant", "ja", "ko"]);

const MIN_LENGTH_RATIO = 0.35;
const MIN_LENGTH_RATIO_COMPACT = 0.15;
const MAX_LENGTH_RATIO = 2.6;
/** Below this, ratio checks are noise: "Oils" -> a four-letter word is normal. */
const LENGTH_CHECK_MIN_SOURCE = 12;

/** Longest run of identical adjacent tokens that can still be deliberate. */
const MAX_TOKEN_RUN = 2;
/** Longest phrase length checked for back-to-back duplication. */
const MAX_PHRASE_LENGTH = 4;

function tokenise(value) {
  return value.split(/\s+/u).filter(Boolean);
}

/**
 * True when the text loops: the same token three times running, or the same
 * short phrase repeated immediately after itself.
 *
 * Both shapes come out of the same decoder failure. "व्यंजन व्यंजन व्यंजन" is
 * the token form; "रसोई के लिए रसोई के लिए" is the phrase form, which a
 * token-only check misses because no single token is adjacent to itself.
 */
function hasRepetitionLoop(value) {
  const tokens = tokenise(value);
  let run = 1;
  for (let index = 1; index < tokens.length; index += 1) {
    run = tokens[index] === tokens[index - 1] ? run + 1 : 1;
    if (run > MAX_TOKEN_RUN) return true;
  }
  for (let size = 2; size <= MAX_PHRASE_LENGTH; size += 1) {
    for (let start = 0; start + size * 2 <= tokens.length; start += 1) {
      const first = tokens.slice(start, start + size).join(" ");
      const second = tokens.slice(start + size, start + size * 2).join(" ");
      if (first === second) return true;
    }
  }
  return false;
}

function targetScriptRatio(value, locale) {
  const range = LOCALE_SCRIPT.get(locale);
  if (!range) return null;
  const letters = value.match(/\p{L}/gu);
  if (!letters?.length) return null;
  const inScript = value.match(new RegExp(`[${range}]`, "gu"));
  return (inScript?.length ?? 0) / letters.length;
}

/**
 * Inspects one translated value against its English source.
 *
 * @param {{ source: string, translated: string, locale: string }} input
 * @returns {{ ok: boolean, issues: string[] }}
 */
export function inspectTranslation({ source, translated, locale }) {
  const issues = [];
  const value = typeof translated === "string" ? translated.trim() : "";
  const english = typeof source === "string" ? source.trim() : "";

  if (!value) return { ok: false, issues: [TRANSLATION_ISSUES.EMPTY] };

  if (PLACEHOLDER_DEBRIS.test(value)) issues.push(TRANSLATION_ISSUES.PLACEHOLDER_LEAK);
  if (BRAND_SCARS.some((scar) => scar.test(value))) {
    issues.push(TRANSLATION_ISSUES.BRAND_MANGLED);
  }

  for (const term of PROTECTED_TERMS) {
    if (english.includes(term) && !value.includes(term)) {
      issues.push(TRANSLATION_ISSUES.BRAND_LOST);
      break;
    }
  }

  if (hasRepetitionLoop(value)) issues.push(TRANSLATION_ISSUES.REPETITION);

  const ratio = targetScriptRatio(value, locale);
  if (ratio !== null && ratio < MIN_TARGET_SCRIPT_RATIO) {
    issues.push(TRANSLATION_ISSUES.SCRIPT_MISMATCH);
  }

  if (english.length >= LENGTH_CHECK_MIN_SOURCE) {
    const lengthRatio = value.length / english.length;
    const floor = COMPACT_SCRIPTS.has(locale) ? MIN_LENGTH_RATIO_COMPACT : MIN_LENGTH_RATIO;
    if (lengthRatio < floor || lengthRatio > MAX_LENGTH_RATIO) {
      issues.push(TRANSLATION_ISSUES.LENGTH_ANOMALY);
    }
  }

  return { ok: issues.length === 0, issues };
}

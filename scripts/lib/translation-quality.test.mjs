/**
 * Run with: node --test scripts/lib/
 *
 * The corrupted values below are verbatim from www.truegritin.com on
 * 2026-08-16, so a regression here means the site could serve them again.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { TRANSLATION_ISSUES, inspectTranslation } from "./translation-quality.mjs";

function issuesFor(source, translated, locale) {
  return inspectTranslation({ source, translated, locale }).issues;
}

describe("inspectTranslation", () => {
  it("rejects the decoder loops that reached production", () => {
    // /recipes/til-ladoo, Hindi: "kitchen for kitchen for kitchen for kitchen".
    assert.ok(
      issuesFor("Til Ladoo Recipe", "रसोई के लिए रसोई के लिए रसोई के लिए रसोई", "hi").includes(
        TRANSLATION_ISSUES.REPETITION,
      ),
    );

    // /recipes/til-ladoo-recipe, Hindi: "Til Ladoo recipe recipe recipe".
    assert.ok(
      issuesFor("Til Ladoo Recipe Recipe", "Til Ladoo व्यंजन व्यंजन व्यंजन", "hi").includes(
        TRANSLATION_ISSUES.REPETITION,
      ),
    );
  });

  it("catches a phrase repeated back to back, not just a repeated word", () => {
    // No single token sits next to a copy of itself here.
    assert.ok(
      issuesFor("Storage guidance for flour", "आटा भंडारण आटा भंडारण", "hi").includes(
        TRANSLATION_ISSUES.REPETITION,
      ),
    );
  });

  it("flags shield scars left over from a mangled brand placeholder", () => {
    // /product/kathiya-wheat-flour, Hindi.
    const issues = issuesFor("Kathiya Wheat Flour", "_KKathiya ग्रीनहाउस", "hi");
    assert.ok(issues.includes(TRANSLATION_ISSUES.BRAND_MANGLED));
  });

  it("flags a brand that did not survive translation", () => {
    // "ट्रिब्रेंड" is the model's attempt at rendering the brand name.
    assert.ok(
      issuesFor(
        "Whole Masoor Curry Recipe - True Grit",
        "Whole Masoor Curry Recipe - ट्रिब्रेंड",
        "hi",
      ).includes(TRANSLATION_ISSUES.BRAND_LOST),
    );
  });

  it("flags leaked placeholder debris", () => {
    assert.ok(
      issuesFor("True Grit Sesame Oil", "[[[9001]]] तिल का तेल", "hi").includes(
        TRANSLATION_ISSUES.PLACEHOLDER_LEAK,
      ),
    );
  });

  it("flags a value left in English for a non-Latin locale", () => {
    assert.ok(
      issuesFor("Cold Pressed Sesame Oil", "Cold Pressed Sesame Oil", "ta").includes(
        TRANSLATION_ISSUES.SCRIPT_MISMATCH,
      ),
    );
  });

  it("accepts a correct translation that keeps the brand in Latin script", () => {
    const result = inspectTranslation({
      source: "Black Gram Sattu — Buy Online. True Grit",
      translated: "काला चना सत्तू — ऑनलाइन खरीदें. True Grit",
      locale: "hi",
    });
    assert.deepEqual(result.issues, []);
    assert.equal(result.ok, true);
  });

  it("does not punish compact scripts for being short", () => {
    assert.deepEqual(issuesFor("Cold Pressed Sesame Oil", "冷压芝麻油", "zh-Hans"), []);
  });

  it("leaves Latin-script locales alone rather than guessing", () => {
    assert.deepEqual(issuesFor("Cold Pressed Sesame Oil", "Kaltgepresstes Sesamöl", "de"), []);
  });

  it("treats an empty translation as conclusively broken", () => {
    const result = inspectTranslation({ source: "Sesame Oil", translated: "   ", locale: "hi" });
    assert.deepEqual(result.issues, [TRANSLATION_ISSUES.EMPTY]);
    assert.equal(result.ok, false);
  });

  it("skips the length ratio on short sources where it would be noise", () => {
    assert.ok(!issuesFor("Oils", "तेल", "hi").includes(TRANSLATION_ISSUES.LENGTH_ANOMALY));
  });
});

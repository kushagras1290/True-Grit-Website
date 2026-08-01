/**
 * Guards the claim made in `messages.ts` and `messages.server.ts`: every
 * registered locale is a complete translation, not a partial one that merely
 * compiles. `LocaleMessages` is `Partial<...>` at the type level so a new
 * English string can ship immediately without breaking every catalogue at
 * once — but "temporarily partial while translators catch up" must not
 * quietly become "permanently partial because nobody noticed". This test is
 * that notice.
 */

import { describe, expect, it } from "vitest";

import { CATALOGUES } from "./messages.server";
import { EN_MESSAGES, type MessageKey } from "./messages";
import { LOCALES } from "./locales";

const ENGLISH_KEYS = Object.keys(EN_MESSAGES) as MessageKey[];

describe("i18n catalogues", () => {
  it("registers a locale entry for every non-English locale in the registry", () => {
    const nonEnglish = LOCALES.filter((locale) => locale.code !== "en").map((l) => l.code);
    const registered = Object.keys(CATALOGUES);
    for (const code of nonEnglish) {
      expect(registered, `LOCALES defines "${code}" but CATALOGUES has no entry for it`).toContain(
        code,
      );
    }
    // And the reverse: no catalogue for a locale that was later removed from
    // the registry, which would be dead code nobody is exercising.
    for (const code of registered) {
      expect(nonEnglish, `CATALOGUES has "${code}" but it is not in LOCALES`).toContain(code);
    }
  });

  it.each(Object.entries(CATALOGUES))(
    "%s translates every English source key",
    (_code, catalogue) => {
      const missing = ENGLISH_KEYS.filter((key) => catalogue[key] === undefined);
      expect(missing, `missing keys: ${missing.join(", ")}`).toEqual([]);
    },
  );

  it.each(Object.entries(CATALOGUES))("%s has no blank translations", (_code, catalogue) => {
    const blank = Object.entries(catalogue)
      .filter(([, value]) => typeof value === "string" && value.trim() === "")
      .map(([key]) => key);
    expect(blank, `blank keys: ${blank.join(", ")}`).toEqual([]);
  });

  it.each(Object.entries(CATALOGUES))(
    "%s does not leave a {placeholder} unresolved by a typo",
    (_code, catalogue) => {
      // Every {name} in a translated string must also appear in the English
      // source for that key -- otherwise `translate()` silently prints the
      // literal "{name}" because nothing ever supplies it.
      const badKeys: string[] = [];
      for (const [key, value] of Object.entries(catalogue)) {
        if (typeof value !== "string") continue;
        const englishTemplate = EN_MESSAGES[key as MessageKey];
        const translatedPlaceholders = [...value.matchAll(/\{(\w+)\}/g)].map((m) => m[1]);
        const englishPlaceholders = new Set(
          [...englishTemplate.matchAll(/\{(\w+)\}/g)].map((m) => m[1]),
        );
        if (translatedPlaceholders.some((name) => !englishPlaceholders.has(name))) {
          badKeys.push(key);
        }
      }
      expect(badKeys, `keys with an unknown placeholder: ${badKeys.join(", ")}`).toEqual([]);
    },
  );
});

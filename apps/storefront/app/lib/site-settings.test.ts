import { describe, expect, it } from "vitest";

import { normalizeSiteSettings } from "./site-settings";

describe("normalizeSiteSettings", () => {
  it("keeps English-only i18n mode explicit and defaults it off", () => {
    expect(normalizeSiteSettings({}).i18n.englishOnly).toBe(false);
    expect(normalizeSiteSettings({ i18n: { englishOnly: true } }).i18n.englishOnly).toBe(true);
  });
});

import { describe, expect, it } from "vitest";

import { resolveLocale } from "./resolve.server";

function request({
  path = "/shop",
  headers = {},
  cf,
}: {
  path?: string;
  headers?: Record<string, string>;
  cf?: Record<string, unknown>;
} = {}): Request {
  const result = new Request(`https://truegrit.example${path}`, { headers });
  if (cf) Object.assign(result, { cf });
  return result;
}

describe("resolveLocale", () => {
  it("honours explicit query and saved choices before automatic sources", () => {
    expect(
      resolveLocale(
        request({
          path: "/shop?lang=ta",
          headers: { cookie: "truegrit_lang=fr", "accept-language": "de" },
        }),
      ),
    ).toMatchObject({ locale: { code: "ta" }, source: "query" });

    expect(
      resolveLocale(request({ headers: { cookie: "truegrit_lang=fr", "accept-language": "de" } })),
    ).toMatchObject({ locale: { code: "fr" }, source: "cookie" });
  });

  it("honours a stated browser language over the country the request came from", () => {
    expect(
      resolveLocale(
        request({
          headers: { "accept-language": "fr-FR;q=0.7, de-DE;q=0.9, en;q=0.8" },
          cf: { country: "IN", region: "Tamil Nadu", regionCode: "IN-TN" },
        }),
      ),
    ).toMatchObject({ locale: { code: "de" }, source: "header" });

    expect(
      resolveLocale(
        request({
          headers: { "accept-language": "en-GB,en;q=0.9" },
          cf: { country: "DE" },
        }),
      ),
    ).toMatchObject({ locale: { code: "en" }, source: "header" });
  });

  it("answers a browser asking for English in English, wherever it dialled in from", () => {
    // The regression this ordering exists for: an Indian IP used to force
    // Hindi over an explicit `en-US`, and because the catalogue copy is only
    // partly translated the reader got `<html lang="hi">` around English text.
    expect(
      resolveLocale(
        request({
          headers: { "accept-language": "en-US,en;q=0.9" },
          cf: { country: "IN", region: "Uttar Pradesh", regionCode: "IN-UP" },
        }),
      ),
    ).toMatchObject({ locale: { code: "en" }, source: "header" });
  });

  it("falls back to country geography when the browser states no usable preference", () => {
    expect(resolveLocale(request({ cf: { country: "DE" } }))).toMatchObject({
      locale: { code: "de" },
      source: "geo",
    });

    expect(
      resolveLocale(request({ headers: { "accept-language": "xx-ZZ" }, cf: { country: "US" } })),
    ).toMatchObject({ locale: { code: "en" }, source: "geo" });
  });

  it("distinguishes Traditional and Simplified Chinese explicit choices", () => {
    expect(resolveLocale(request({ path: "/shop?lang=zh-TW" }))).toMatchObject({
      locale: { code: "zh-Hant" },
      source: "query",
    });
    expect(resolveLocale(request({ path: "/shop?lang=zh-CN" }))).toMatchObject({
      locale: { code: "zh-Hans" },
      source: "query",
    });
  });

  it("uses Indian state geography when available", () => {
    expect(
      resolveLocale(
        request({
          headers: { "accept-language": "xx-ZZ" },
          cf: { country: "IN", region: "Karnataka", regionCode: "IN-KA" },
        }),
      ),
    ).toMatchObject({ locale: { code: "kn" }, source: "geo" });

    // Nagaland maps to English rather than Hindi, and with no usable header
    // the state mapping is still what decides it.
    expect(
      resolveLocale(
        request({
          headers: { "accept-language": "xx-ZZ" },
          cf: { country: "IN", region: "Nagaland", regionCode: "IN-NL" },
        }),
      ),
    ).toMatchObject({ locale: { code: "en" }, source: "geo" });

    // A Hindi-speaking browser in a non-Hindi state is taken at its word.
    expect(
      resolveLocale(
        request({
          headers: { "accept-language": "hi-IN" },
          cf: { country: "IN", region: "Nagaland", regionCode: "IN-NL" },
        }),
      ),
    ).toMatchObject({ locale: { code: "hi" }, source: "header" });
  });
});

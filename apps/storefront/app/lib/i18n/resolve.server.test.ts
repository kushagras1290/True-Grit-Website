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

  it("honours the browser's weighted language list, including English", () => {
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

  it("distinguishes Traditional and Simplified Chinese browser regions", () => {
    expect(
      resolveLocale(request({ headers: { "accept-language": "zh-TW,zh;q=0.8" } })),
    ).toMatchObject({ locale: { code: "zh-Hant" }, source: "header" });
    expect(resolveLocale(request({ headers: { "accept-language": "zh-CN" } }))).toMatchObject({
      locale: { code: "zh-Hans" },
      source: "header",
    });
  });

  it("uses geography only when the browser supplies no supported language", () => {
    expect(
      resolveLocale(
        request({
          headers: { "accept-language": "xx-ZZ" },
          cf: { country: "IN", region: "Karnataka", regionCode: "IN-KA" },
        }),
      ),
    ).toMatchObject({ locale: { code: "kn" }, source: "geo" });
  });
});

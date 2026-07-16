import { describe, expect, it } from "vitest";

import { resolveCountry } from "./geo.server";

function request(headers: Record<string, string> = {}): Request {
  return new Request("https://truegrit.example/shop", { headers });
}

describe("resolveCountry", () => {
  it("reads the Cloudflare country header", () => {
    expect(resolveCountry(request({ "cf-ipcountry": "US" }))).toBe("US");
    expect(resolveCountry(request({ "CF-IPCountry": "gb" }))).toBe("GB");
  });

  it("ignores Cloudflare's unknown/Tor sentinels", () => {
    expect(resolveCountry(request({ "cf-ipcountry": "XX" }))).toBe("IN");
    expect(resolveCountry(request({ "cf-ipcountry": "T1" }))).toBe("IN");
  });

  it("lets the tg_country cookie override the header", () => {
    expect(
      resolveCountry(request({ "cf-ipcountry": "US", cookie: "tg_session=abc; tg_country=ae" })),
    ).toBe("AE");
  });

  it("falls back to India when nothing is known", () => {
    expect(resolveCountry(request())).toBe("IN");
  });
});

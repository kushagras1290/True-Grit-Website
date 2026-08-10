import { describe, expect, it } from "vitest";

import { resolveCountry, resolveRegion } from "./geo.server";

function request(headers: Record<string, string> = {}, cf?: Record<string, unknown>): Request {
  const req = new Request("https://truegrit.example/shop", { headers });
  if (cf) Object.assign(req, { cf });
  return req;
}

describe("resolveCountry", () => {
  it("reads the canonical Workers-runtime cf country", () => {
    expect(resolveCountry(request({}, { country: "DE" }))).toBe("DE");
    expect(resolveCountry(request({ "cf-ipcountry": "US" }, { country: "de" }))).toBe("DE");
  });

  it("reads the Cloudflare country header", () => {
    expect(resolveCountry(request({ "cf-ipcountry": "US" }))).toBe("US");
    expect(resolveCountry(request({ "CF-IPCountry": "gb" }))).toBe("GB");
  });

  it("ignores Cloudflare's unknown/Tor sentinels", () => {
    expect(resolveCountry(request({ "cf-ipcountry": "XX" }))).toBe("IN");
    expect(resolveCountry(request({ "cf-ipcountry": "T1" }))).toBe("IN");
  });

  it("lets the tg_country cookie override the Worker geo and header", () => {
    expect(
      resolveCountry(
        request(
          { "cf-ipcountry": "US", cookie: "tg_session=abc; tg_country=ae" },
          { country: "DE" },
        ),
      ),
    ).toBe("AE");
  });

  it("falls back to India when nothing is known", () => {
    expect(resolveCountry(request())).toBe("IN");
  });
});

describe("resolveRegion", () => {
  it("reads region/regionCode from the Workers-runtime cf property", () => {
    expect(resolveRegion(request({}, { region: "Punjab", regionCode: "IN-PB" }))).toEqual({
      region: "Punjab",
      regionCode: "IN-PB",
    });
  });

  it("returns nulls when cf is absent, matching a lower-tier account or local dev", () => {
    expect(resolveRegion(request())).toEqual({ region: null, regionCode: null });
  });

  it("lets the tg_region cookie override cf for local testing", () => {
    expect(
      resolveRegion(
        request({ cookie: "tg_region=Karnataka" }, { region: "Punjab", regionCode: "IN-PB" }),
      ),
    ).toEqual({ region: "Karnataka", regionCode: "Karnataka" });
  });
});

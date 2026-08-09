import { describe, expect, it } from "vitest";
import countryLocaleMap from "country-locale-map";

import { matchCountryLocale, matchIndiaRegionLocale } from "./geo-locale";

describe("matchCountryLocale", () => {
  it("maps a country to its dominant language", () => {
    expect(matchCountryLocale("DE")?.code).toBe("de");
    expect(matchCountryLocale("de")?.code).toBe("de");
  });

  it("uses a supported default for India and formerly unmapped countries", () => {
    expect(matchCountryLocale("IN")?.code).toBe("hi");
    expect(matchCountryLocale("PK")?.code).toBe("ur");
    expect(matchCountryLocale("KE")?.code).toBe("sw");
    expect(matchCountryLocale("PH")?.code).toBe("fil");
  });

  it("maps every ISO country to a shipped storefront language", () => {
    for (const country of countryLocaleMap.getAllCountries()) {
      expect(matchCountryLocale(country.alpha2), country.name).not.toBeNull();
    }
  });

  it("returns null for invalid and absent country codes", () => {
    expect(matchCountryLocale("ZZ")).toBeNull();
    expect(matchCountryLocale(null)).toBeNull();
  });
});

describe("matchIndiaRegionLocale", () => {
  it("maps each state the user asked for by name", () => {
    expect(matchIndiaRegionLocale("Punjab", null)?.code).toBe("pa");
    expect(matchIndiaRegionLocale("Jammu and Kashmir", null)?.code).toBe("ks");
    expect(matchIndiaRegionLocale("Madhya Pradesh", null)?.code).toBe("hi");
    expect(matchIndiaRegionLocale("Karnataka", null)?.code).toBe("kn");
    expect(matchIndiaRegionLocale("Tamil Nadu", null)?.code).toBe("ta");
  });

  it("is case-insensitive and trims whitespace on the region name", () => {
    expect(matchIndiaRegionLocale("  punjab  ", null)?.code).toBe("pa");
    expect(matchIndiaRegionLocale("TAMIL NADU", null)?.code).toBe("ta");
  });

  it("falls back to the ISO-3166-2 region code when no name is given", () => {
    expect(matchIndiaRegionLocale(null, "IN-PB")?.code).toBe("pa");
    expect(matchIndiaRegionLocale(null, "PB")?.code).toBe("pa");
    expect(matchIndiaRegionLocale(undefined, "in-ka")?.code).toBe("kn");
  });

  it("prefers the region name over the code when both are present", () => {
    // A mismatched pair should not happen in practice, but the name is what
    // Cloudflare documents as the more complete field.
    expect(matchIndiaRegionLocale("Karnataka", "IN-PB")?.code).toBe("kn");
  });

  it("returns null for a state with no single dominant language in this catalogue", () => {
    expect(matchIndiaRegionLocale("Nagaland", "IN-NL")).toBeNull();
  });

  it("returns null when neither region nor regionCode is known", () => {
    expect(matchIndiaRegionLocale(null, null)).toBeNull();
    expect(matchIndiaRegionLocale("Atlantis", "XX-YY")).toBeNull();
  });
});

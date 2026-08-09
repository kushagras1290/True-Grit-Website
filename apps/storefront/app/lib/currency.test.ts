import { describe, expect, it } from "vitest";
import countryToCurrency from "country-to-currency";

import { currencyForCountry, formatDisplayMoney, INR } from "./currency";

describe("currencyForCountry", () => {
  it("maps India and invalid countries to INR", () => {
    expect(currencyForCountry("IN").code).toBe("INR");
    expect(currencyForCountry("ZZ").code).toBe("INR");
    expect(currencyForCountry("").code).toBe("INR");
  });

  it("maps major markets to their currency", () => {
    expect(currencyForCountry("US").code).toBe("USD");
    expect(currencyForCountry("gb").code).toBe("GBP");
    expect(currencyForCountry("AE").code).toBe("AED");
    expect(currencyForCountry("SG").code).toBe("SGD");
  });

  it("prefers an operator-managed value over the fail-safe snapshot", () => {
    const usd = currencyForCountry("US", [{ code: "USD", locale: "en-US", ratePerInr: 0.02 }]);
    expect(usd.ratePerInr).toBe(0.02);
  });

  it("falls back to INR when the operator disables a configured currency", () => {
    expect(currencyForCountry("US", []).code).toBe("INR");
  });

  it("maps every eurozone country to EUR", () => {
    for (const country of ["DE", "FR", "IT", "ES", "NL", "IE", "PT", "FI"]) {
      expect(currencyForCountry(country).code).toBe("EUR");
    }
  });

  it("resolves every ISO country currency when its operator rate is active", () => {
    const rates = Object.values(countryToCurrency).map((code) => ({
      code,
      locale: "en",
      ratePerInr: 1,
    }));
    for (const [country, code] of Object.entries(countryToCurrency)) {
      expect(currencyForCountry(country, rates).code, country).toBe(code);
    }
  });
});

describe("formatDisplayMoney", () => {
  it("keeps exact INR formatting for the home market", () => {
    expect(formatDisplayMoney(89900, INR)).toBe("₹899");
  });

  it("converts to an approximate local price", () => {
    // 89900 paise = ₹899; at 0.0115 USD/INR that is ~$10.34.
    const usd = formatDisplayMoney(89900, currencyForCountry("US"));
    expect(usd).toContain("10.34");
    expect(usd).toContain("$");
  });

  it("respects zero-decimal currencies", () => {
    // ₹899 * 1.7 = ¥1,528 — JPY has no minor units.
    const jpy = formatDisplayMoney(89900, currencyForCountry("JP"));
    expect(jpy).toContain("1,528");
    expect(jpy).not.toContain(".");
  });
});

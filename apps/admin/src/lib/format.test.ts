import { describe, expect, it } from "vitest";

import { formatDate, formatMoney } from "./format";

describe("formatMoney", () => {
  it("formats whole rupees without paise", () => {
    expect(formatMoney(89900)).toBe("₹899");
  });

  it("keeps paise when present", () => {
    expect(formatMoney(89950)).toBe("₹899.50");
  });

  it("formats lakh-scale amounts with Indian grouping", () => {
    expect(formatMoney(12345600)).toBe("₹1,23,456");
  });

  it("rejects negative and non-integer amounts", () => {
    expect(() => formatMoney(-1)).toThrow(RangeError);
    expect(() => formatMoney(99.5)).toThrow(RangeError);
  });
});

describe("formatDate", () => {
  it("formats ISO timestamps", () => {
    expect(formatDate("2026-07-11T00:00:00Z")).toMatch(/11 Jul 2026/);
  });

  it("returns a dash for invalid input", () => {
    expect(formatDate("not-a-date")).toBe("—");
  });
});

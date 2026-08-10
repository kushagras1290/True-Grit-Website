import { describe, expect, it } from "vitest";

import { IMAGE_SPECIFICATIONS, imageDimensions } from "./image-specifications";

describe("image specifications", () => {
  it("keeps every identifier unique and every dimension integral", () => {
    expect(new Set(IMAGE_SPECIFICATIONS.map((entry) => entry.id)).size).toBe(
      IMAGE_SPECIFICATIONS.length,
    );

    for (const entry of IMAGE_SPECIFICATIONS) {
      expect(Number.isInteger(entry.width)).toBe(true);
      expect(Number.isInteger(entry.height)).toBe(true);
      expect(Number.isInteger(entry.safeArea.width)).toBe(true);
      expect(Number.isInteger(entry.safeArea.height)).toBe(true);
      expect(entry.safeArea.width).toBeLessThanOrEqual(entry.width);
      expect(entry.safeArea.height).toBeLessThanOrEqual(entry.height);
    }
  });

  it("keeps all website banner canvases aligned with the rendered frame", () => {
    const banners = IMAGE_SPECIFICATIONS.filter((entry) => entry.group === "Banners");

    expect(banners).toHaveLength(3);
    expect(banners.every((entry) => imageDimensions(entry) === "1672 × 464 px")).toBe(true);
  });

  it("keeps the product, brand-mark, and favicon canvases fixed", () => {
    expect(
      Object.fromEntries(IMAGE_SPECIFICATIONS.map((entry) => [entry.id, imageDimensions(entry)])),
    ).toMatchObject({
      "product-image": "1200 × 1200 px",
      "category-thumbnail": "1200 × 1200 px",
      "brand-mark": "256 × 256 px",
      favicon: "64 × 64 px",
    });
  });
});

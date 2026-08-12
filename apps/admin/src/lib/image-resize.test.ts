import { describe, expect, it } from "vitest";

import { resizeImageToSpec } from "./image-resize";

// jsdom has no real image decoder or canvas renderer, so this cannot verify
// pixel output -- what matters here, and what jsdom can verify, is the
// contract every upload call site depends on: a file that cannot be resized
// (undecodable content, no canvas support) must never block the upload, it
// must fall back to the original file untouched.
describe("resizeImageToSpec", () => {
  it("falls back to the original file when the browser cannot decode it", async () => {
    const original = new File(["not actually an image"], "photo.jpg", { type: "image/jpeg" });

    const result = await resizeImageToSpec(original, { width: 1200, height: 1200 });

    expect(result).toBe(original);
  });
});

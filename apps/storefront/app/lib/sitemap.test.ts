import { describe, expect, it } from "vitest";

import { loadSitemapXml, sitemapResponse, type CatalogueRuntime } from "./catalogue.server";

const API_URL = "https://api.test";

const XML =
  '<?xml version="1.0" encoding="UTF-8"?>\n' +
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
  "  <url><loc>https://shop.test/product/ragi</loc></url>\n" +
  "</urlset>\n";

/** A runtime whose service binding answers with a fixed response, so these
 * exercise the real branch the deployed storefront takes (API_WORKER) without
 * a network. */
function runtimeReturning(response: Response | (() => never)): CatalogueRuntime {
  return {
    apiUrl: API_URL,
    apiWorker: {
      fetch: (async () => {
        if (typeof response === "function") response();
        return response as Response;
      }) as unknown as typeof fetch,
    },
  };
}

describe("sitemap loading", () => {
  it("passes the API's XML through untouched", async () => {
    const runtime = runtimeReturning(new Response(XML, { status: 200 }));
    expect(await loadSitemapXml("products", runtime)).toBe(XML);
  });

  it("requests the kind that was asked for", async () => {
    const seen: string[] = [];
    const runtime: CatalogueRuntime = {
      apiUrl: API_URL,
      apiWorker: {
        fetch: (async (request: Request) => {
          seen.push(request.url);
          return new Response(XML, { status: 200 });
        }) as unknown as typeof fetch,
      },
    };
    await loadSitemapXml("discussions", runtime);
    expect(seen).toEqual([`${API_URL}/v1/public/sitemaps/discussions`]);
  });

  // The live bug: /sitemaps/products was 500ing on the API and the storefront
  // republished that as a 200 with an empty urlset — an authoritative "this
  // section has no pages", which is worse for indexing than no answer at all.
  it("reports a failed API call as null rather than an empty urlset", async () => {
    expect(
      await loadSitemapXml("products", runtimeReturning(new Response("", { status: 500 }))),
    ).toBeNull();
  });

  it("reports a thrown request as null", async () => {
    const runtime = runtimeReturning(() => {
      throw new Error("socket closed");
    });
    expect(await loadSitemapXml("recipes", runtime)).toBeNull();
  });

  it("serves an empty urlset in demo mode, where there is genuinely nothing to list", async () => {
    const xml = await loadSitemapXml("products", { apiUrl: "" });
    expect(xml).toContain("<urlset");
    expect(xml).not.toContain("<url>");
  });
});

describe("sitemap responses", () => {
  it("serves 200 XML when the API answers", async () => {
    const response = await sitemapResponse("products", runtimeReturning(new Response(XML)));
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("application/xml; charset=utf-8");
    expect(await response.text()).toBe(XML);
  });

  it("serves 503 when the API fails, so crawlers retry instead of dropping URLs", async () => {
    const response = await sitemapResponse(
      "products",
      runtimeReturning(new Response("", { status: 500 })),
    );
    expect(response.status).toBe(503);
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("never caches a failure", async () => {
    const response = await sitemapResponse(
      "blog",
      runtimeReturning(new Response("", { status: 502 })),
    );
    expect(response.headers.get("cache-control")).not.toContain("max-age");
  });

  it("caches a successful sitemap briefly", async () => {
    const response = await sitemapResponse("farms", runtimeReturning(new Response(XML)));
    expect(response.headers.get("cache-control")).toBe("public, max-age=300");
  });
});

import { categories, products } from "@truegrit/contracts/fixtures";

import { catalogueRuntime, loadSiteDocument } from "./catalogue.server";

type DocumentKey = "robots_txt" | "sitemap_xml" | "llms_txt";

export async function publicDocumentResponse(
  key: DocumentKey,
  request: Request,
  context: unknown,
): Promise<Response> {
  const runtime = catalogueRuntime(context);
  const remote = await loadSiteDocument(key, runtime);
  const fallback = fallbackDocument(key, request);
  return new Response(remote?.content ?? fallback.content, {
    headers: {
      "content-type": remote?.contentType ?? fallback.contentType,
      "cache-control": "public, max-age=300",
    },
  });
}

function origin(request: Request): string {
  return new URL(request.url).origin;
}

function absolute(request: Request, path: string): string {
  return `${origin(request)}${path}`;
}

function fallbackDocument(
  key: DocumentKey,
  request: Request,
): { content: string; contentType: string } {
  if (key === "robots_txt") {
    return {
      content: [
        "User-agent: *",
        "Allow: /",
        "Disallow: /checkout",
        "Disallow: /account",
        "Disallow: /payment/",
        "",
        `Sitemap: ${absolute(request, "/sitemap.xml")}`,
        "",
      ].join("\n"),
      contentType: "text/plain; charset=utf-8",
    };
  }

  if (key === "llms_txt") {
    return {
      content: [
        "# True Grit",
        "",
        "Traceable organic food from verified farms, with product, farm, recipe, and policy pages.",
        "",
        "## Core Pages",
        `- Home: ${absolute(request, "/")}`,
        `- Shop: ${absolute(request, "/shop")}`,
        `- Farmers: ${absolute(request, "/farms")}`,
        `- Recipes: ${absolute(request, "/recipes")}`,
        `- Blog: ${absolute(request, "/blog")}`,
        `- Community: ${absolute(request, "/community")}`,
        `- Standards: ${absolute(request, "/standards")}`,
        "",
        "## Product Categories",
        ...categories.map(
          (category) => `- ${category.name}: ${absolute(request, `/category/${category.slug}`)}`,
        ),
        "",
        "## Featured Product URLs",
        ...products.map(
          (product) => `- ${product.name}: ${absolute(request, `/product/${product.slug}`)}`,
        ),
        "",
      ].join("\n"),
      contentType: "text/plain; charset=utf-8",
    };
  }

  // sitemap_xml is an index in demo mode too, mirroring the real backend
  // shape (`services/site_documents.py::sitemap_index_xml`) — the per-type
  // files behind it (`/sitemaps/*.xml`) carry the actual product/category/
  // blog/recipe/farm/page URLs.
  const kinds = ["products", "categories", "pages", "blog", "recipes", "farms", "discussions"];
  const entries = kinds
    .map((kind) => `  <sitemap><loc>${escapeXml(absolute(request, `/sitemaps/${kind}.xml`))}</loc></sitemap>`)
    .join("\n");
  return {
    content:
      '<?xml version="1.0" encoding="UTF-8"?>\n' +
      '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
      `${entries}\n` +
      "</sitemapindex>\n",
    contentType: "application/xml; charset=utf-8",
  };
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

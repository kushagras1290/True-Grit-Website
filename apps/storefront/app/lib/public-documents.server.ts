import { articles, categories, products, recipes } from "@truegrit/contracts/fixtures";

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
        `- Journal: ${absolute(request, "/journal")}`,
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

  const paths = [
    "/",
    "/shop",
    "/seasonal",
    "/farms",
    "/recipes",
    "/journal",
    "/standards",
    "/about",
    "/delivery",
    "/returns",
    "/contact",
    "/privacy",
    "/terms",
    "/help",
    ...categories.map((category) => `/category/${category.slug}`),
    ...products.map((product) => `/product/${product.slug}`),
    ...recipes.map((recipe) => `/recipes/${recipe.slug}`),
    ...articles.map((article) => `/journal/${article.slug}`),
  ];
  const urls = [...new Set(paths)]
    .map((path) => `  <url><loc>${escapeXml(absolute(request, path))}</loc></url>`)
    .join("\n");
  return {
    content:
      '<?xml version="1.0" encoding="UTF-8"?>\n' +
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
      `${urls}\n` +
      "</urlset>\n",
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

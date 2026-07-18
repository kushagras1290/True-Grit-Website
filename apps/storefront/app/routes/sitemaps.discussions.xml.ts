import type { Route } from "./+types/sitemaps.discussions.xml";
import { catalogueRuntime, loadSitemapXml } from "../lib/catalogue.server";

export async function loader({ context }: Route.LoaderArgs) {
  const xml = await loadSitemapXml("discussions", catalogueRuntime(context));
  return new Response(xml, {
    headers: { "content-type": "application/xml; charset=utf-8", "cache-control": "public, max-age=300" },
  });
}

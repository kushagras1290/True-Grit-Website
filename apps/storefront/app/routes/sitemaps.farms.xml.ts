import type { Route } from "./+types/sitemaps.farms.xml";
import { catalogueRuntime, loadSitemapXml } from "../lib/catalogue.server";

export async function loader({ context }: Route.LoaderArgs) {
  const xml = await loadSitemapXml("farms", catalogueRuntime(context));
  return new Response(xml, {
    headers: { "content-type": "application/xml; charset=utf-8", "cache-control": "public, max-age=300" },
  });
}

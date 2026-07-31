import type { Route } from "./+types/sitemaps.products.xml";
import { catalogueRuntime, sitemapResponse } from "../lib/catalogue.server";

export async function loader({ context }: Route.LoaderArgs) {
  return sitemapResponse("products", catalogueRuntime(context));
}

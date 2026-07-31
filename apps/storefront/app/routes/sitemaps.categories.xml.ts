import type { Route } from "./+types/sitemaps.categories.xml";
import { catalogueRuntime, sitemapResponse } from "../lib/catalogue.server";

export async function loader({ context }: Route.LoaderArgs) {
  return sitemapResponse("categories", catalogueRuntime(context));
}

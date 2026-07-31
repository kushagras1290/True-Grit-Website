import type { Route } from "./+types/sitemaps.recipes.xml";
import { catalogueRuntime, sitemapResponse } from "../lib/catalogue.server";

export async function loader({ context }: Route.LoaderArgs) {
  return sitemapResponse("recipes", catalogueRuntime(context));
}

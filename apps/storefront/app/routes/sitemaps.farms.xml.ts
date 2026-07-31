import type { Route } from "./+types/sitemaps.farms.xml";
import { catalogueRuntime, sitemapResponse } from "../lib/catalogue.server";

export async function loader({ context }: Route.LoaderArgs) {
  return sitemapResponse("farms", catalogueRuntime(context));
}

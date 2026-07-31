import type { Route } from "./+types/sitemaps.pages.xml";
import { catalogueRuntime, sitemapResponse } from "../lib/catalogue.server";

export async function loader({ context }: Route.LoaderArgs) {
  return sitemapResponse("pages", catalogueRuntime(context));
}

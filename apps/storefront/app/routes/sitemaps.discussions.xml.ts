import type { Route } from "./+types/sitemaps.discussions.xml";
import { catalogueRuntime, sitemapResponse } from "../lib/catalogue.server";

export async function loader({ context }: Route.LoaderArgs) {
  return sitemapResponse("discussions", catalogueRuntime(context));
}

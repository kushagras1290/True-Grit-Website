import type { Route } from "./+types/sitemaps.blog.xml";
import { catalogueRuntime, sitemapResponse } from "../lib/catalogue.server";

export async function loader({ context }: Route.LoaderArgs) {
  return sitemapResponse("blog", catalogueRuntime(context));
}

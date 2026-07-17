import type { Route } from "./+types/sitemap.xml";
import { publicDocumentResponse } from "../lib/public-documents.server";

export async function loader({ request, context }: Route.LoaderArgs) {
  return publicDocumentResponse("sitemap_xml", request, context);
}

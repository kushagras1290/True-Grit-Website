import type { Route } from "./+types/robots.txt";
import { publicDocumentResponse } from "../lib/public-documents.server";

export async function loader({ request, context }: Route.LoaderArgs) {
  return publicDocumentResponse("robots_txt", request, context);
}

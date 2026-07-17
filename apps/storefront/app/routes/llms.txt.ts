import type { Route } from "./+types/llms.txt";
import { publicDocumentResponse } from "../lib/public-documents.server";

export async function loader({ request, context }: Route.LoaderArgs) {
  return publicDocumentResponse("llms_txt", request, context);
}

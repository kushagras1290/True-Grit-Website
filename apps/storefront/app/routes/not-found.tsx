import { data } from "react-router";

import type { Route } from "./+types/not-found";

export async function loader() {
  throw data("Not found", { status: 404 });
}

export default function NotFound(_props: Route.ComponentProps) {
  return null;
}

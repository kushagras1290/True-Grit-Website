import { getPublicApiUrl } from "./public-env";

export type RecommendationPlacement =
  "product" | "cart" | "homepage" | "category" | "shop" | "order";

export interface RecommendationTrackingContext {
  sourceProductId?: string | null;
  recommendedProductId: string;
  recommendationRunId?: string | null;
  placement: RecommendationPlacement;
}

const SESSION_KEY = "truegrit.recommendations.session.v1";

function visitorSessionId(): string {
  if (typeof window === "undefined") return "server-render";
  const existing = window.sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const created =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  window.sessionStorage.setItem(SESSION_KEY, created);
  return created;
}

/** Best-effort product analytics. It never blocks navigation or add-to-cart;
 * checkout attribution is the authoritative revenue record. */
export function trackRecommendation(
  context: RecommendationTrackingContext,
  eventType: "impression" | "click" | "add_to_cart",
): void {
  const apiUrl = getPublicApiUrl();
  if (!apiUrl || typeof window === "undefined") return;
  void fetch(`${apiUrl}/v1/public/recommendation-events`, {
    method: "POST",
    credentials: "include",
    keepalive: true,
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      visitorSessionId: visitorSessionId(),
      sourceProductId: context.sourceProductId || undefined,
      recommendedProductId: context.recommendedProductId,
      recommendationRunId: context.recommendationRunId || undefined,
      placement: context.placement,
      eventType,
    }),
  }).catch(() => undefined);
}

export function recommendationHref(slug: string, context: RecommendationTrackingContext): string {
  const params = new URLSearchParams({ recPlacement: context.placement });
  if (context.sourceProductId) params.set("recSource", context.sourceProductId);
  if (context.recommendationRunId) params.set("recRun", context.recommendationRunId);
  return `/product/${slug}?${params.toString()}`;
}

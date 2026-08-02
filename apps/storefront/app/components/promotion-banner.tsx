/**
 * Renders a `FeaturedPromotion` (or the checkout's own `FeaturedPromotionInfo`,
 * an identical shape) in one of two registers:
 *
 * - `full`: the homepage `promotion_banner` block, directly under the hero --
 *   full-bleed, brand-coloured, sized like the newsletter strip.
 * - `compact`: the checkout-page callout -- a bordered card in the order
 *   summary rail, not the entire banner (explicitly not full-width: it has to
 *   sit alongside delivery address fields without taking over the page).
 *
 * Both read the same `{headline, description, code}` shape so the homepage
 * and checkout can never drift into two hand-maintained versions of the same
 * offer -- see `loadFeaturedPromotion` in `catalogue.server.ts`.
 */

export interface PromotionBannerContent {
  headline: string;
  description: string | null;
  code: string | null;
}

export function PromotionBanner({
  promotion,
  variant,
}: {
  promotion: PromotionBannerContent;
  variant: "full" | "compact";
}) {
  if (variant === "compact") {
    return (
      <div className="rounded-md border border-brand/30 bg-brand/5 p-4">
        <p className="text-sm font-medium text-brand">{promotion.headline}</p>
        {promotion.description ? (
          <p className="mt-1 text-xs text-ink-muted">{promotion.description}</p>
        ) : null}
        {promotion.code ? (
          <p className="mt-2 text-xs text-ink-muted">
            Use code{" "}
            <span className="rounded-sm bg-brand px-1.5 py-0.5 font-mono font-semibold text-ink-inverse">
              {promotion.code}
            </span>{" "}
            at checkout.
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <section className="bg-brand text-ink-inverse">
      <div className="mx-auto flex max-w-[80rem] flex-col items-center gap-2 px-4 py-6 text-center sm:px-6 md:flex-row md:justify-center md:gap-4 md:py-5">
        <p className="font-display text-lg md:text-xl">{promotion.headline}</p>
        {promotion.description ? (
          <p className="text-sm text-white/85 md:border-l md:border-white/25 md:pl-4">
            {promotion.description}
          </p>
        ) : null}
        {promotion.code ? (
          <span className="inline-flex items-center rounded-sm bg-canvas px-3 py-1 text-sm font-semibold text-brand">
            {promotion.code}
          </span>
        ) : null}
      </div>
    </section>
  );
}

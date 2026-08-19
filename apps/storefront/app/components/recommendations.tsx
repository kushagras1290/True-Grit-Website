/**
 * A row of real, data-driven product recommendations -- bestsellers (ranked
 * by actual quantity sold) or "customers also bought" (real co-purchase
 * counts), never a curated or fabricated list. See
 * `catalogue.server.ts` `loadBestsellers` / `loadAlsoBought` and
 * `CatalogueRepository.list_bestsellers` / `list_also_bought` on the API.
 *
 * Reads as ordinary merchandising copy wherever it appears (a heading like
 * "Customers also bought", not a labelled "Recommendations" widget), and
 * renders nothing when there is no real data behind it -- an empty row would
 * be the one thing that reads as fake.
 */

import type { ProductSummary, RecommendedProduct } from "@truegrit/contracts";
import { useEffect, useRef } from "react";

import { ProductCard, Section } from "./catalogue";
import { Slider } from "./slider";
import { useLocalizeText } from "../lib/i18n/localized-text";
import {
  recommendationHref,
  trackRecommendation,
  type RecommendationPlacement,
} from "../lib/recommendation-tracking";

export function RecommendedProducts({
  heading,
  eyebrow = "Picked by shoppers",
  products,
  tone,
  placement = "homepage",
  sourceProductId,
}: {
  heading: string;
  eyebrow?: string;
  products: Array<ProductSummary | RecommendedProduct>;
  tone?: "canvas" | "surface" | "subtle" | "inverse";
  placement?: RecommendationPlacement;
  sourceProductId?: string | null;
}) {
  const localize = useLocalizeText();
  const impressionKeyRef = useRef("");
  const entries = products.map((entry) =>
    "product" in entry
      ? entry
      : {
          product: entry,
          recommendation: {
            runId: null,
            sourceProductId: sourceProductId ?? "",
            score: 0,
            confidence: 0,
            lift: 0,
            cosineSimilarity: 0,
            reason: "trending" as const,
          },
        },
  );
  const impressionKey = entries
    .map((entry) => `${entry.recommendation.runId ?? "live"}:${entry.product.id}`)
    .join(",");
  useEffect(() => {
    if (!impressionKey || impressionKeyRef.current === impressionKey) return;
    impressionKeyRef.current = impressionKey;
    for (const entry of entries) {
      trackRecommendation(
        {
          sourceProductId: entry.recommendation.sourceProductId || sourceProductId,
          recommendedProductId: entry.product.id,
          recommendationRunId: entry.recommendation.runId,
          placement,
        },
        "impression",
      );
    }
  }, [entries, impressionKey, placement, sourceProductId]);
  if (products.length === 0) return null;
  return (
    <Section eyebrow={localize(eyebrow)} heading={localize(heading)} tone={tone}>
      <Slider ariaLabel={localize(heading)}>
        {entries.map((entry) => {
          const context = {
            sourceProductId: entry.recommendation.sourceProductId || sourceProductId,
            recommendedProductId: entry.product.id,
            recommendationRunId: entry.recommendation.runId,
            placement,
          };
          return (
            <div
              key={entry.product.id}
              className="w-[calc(50%-0.5rem)] shrink-0 snap-start sm:w-[calc(33.3%-0.7rem)] lg:w-[calc(25%-0.75rem)]"
            >
              <ProductCard
                product={entry.product}
                href={recommendationHref(entry.product.slug, context)}
                onNavigate={() => trackRecommendation(context, "click")}
              />
            </div>
          );
        })}
      </Slider>
    </Section>
  );
}

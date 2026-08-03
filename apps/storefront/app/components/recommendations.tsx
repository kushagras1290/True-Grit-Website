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

import type { ProductSummary } from "@truegrit/contracts";

import { ProductCard, Section } from "./catalogue";
import { Slider } from "./slider";
import { useLocalizeText } from "../lib/i18n/localized-text";

export function RecommendedProducts({
  heading,
  eyebrow = "Picked by shoppers",
  products,
  tone,
}: {
  heading: string;
  eyebrow?: string;
  products: ProductSummary[];
  tone?: "canvas" | "surface" | "subtle" | "inverse";
}) {
  const localize = useLocalizeText();
  if (products.length === 0) return null;
  return (
    <Section eyebrow={localize(eyebrow)} heading={localize(heading)} tone={tone}>
      <Slider ariaLabel={localize(heading)}>
        {products.map((product) => (
          <div
            key={product.id}
            className="w-[calc(50%-0.5rem)] shrink-0 snap-start sm:w-[calc(33.3%-0.7rem)] lg:w-[calc(25%-0.75rem)]"
          >
            <ProductCard product={product} />
          </div>
        ))}
      </Slider>
    </Section>
  );
}

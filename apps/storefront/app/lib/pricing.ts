import type { ProductSummary, VariantSummary } from "@truegrit/contracts";

/** What a visitor actually pays for one item, and — only when a genuine
 *  discount produced it — the real price to show struck through next to it. */
export interface EffectivePrice {
  amountMinor: number;
  /** Set only when `amountMinor` is a genuine discount off the real price.
   *  Never set for a markup: this codebase never fabricates a "was" price to
   *  dress one up as a discount (see `services/price_adjustments.py`). */
  originalMinor: number | null;
}

function resolve(
  listMinor: number,
  saleMinor: number | null,
  adjustedMinor: number | null,
): EffectivePrice {
  // An active price-adjustment rule takes full precedence over the older,
  // per-variant "sale" field below it — the two are never combined, so a
  // product carrying both shows exactly one comparison, not two stacked ones.
  if (adjustedMinor !== null) {
    return adjustedMinor < listMinor
      ? { amountMinor: adjustedMinor, originalMinor: listMinor }
      : { amountMinor: adjustedMinor, originalMinor: null };
  }
  if (saleMinor !== null && saleMinor < listMinor) {
    return { amountMinor: saleMinor, originalMinor: listMinor };
  }
  return { amountMinor: listMinor, originalMinor: null };
}

export function productEffectivePrice(product: ProductSummary): EffectivePrice {
  return resolve(product.priceMinor, product.saleMinor, product.adjustedMinor);
}

export function variantEffectivePrice(variant: VariantSummary): EffectivePrice {
  return resolve(variant.listMinor, variant.saleMinor, variant.adjustedMinor);
}

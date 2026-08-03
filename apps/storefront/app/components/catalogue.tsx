/** Catalogue presentation: product cards, category tiles, produce art direction.
 *
 * No photography ships with the repo, so each product renders a quiet
 * botanical placeholder driven by its category theme — real media assets slot
 * into the same frame via Cloudflare Images at integration time. */

import type { CategorySummary, ProductSummary } from "@truegrit/contracts";
import { themeVars } from "@truegrit/ui";
import { useEffect, useState } from "react";
import { Link } from "react-router";

import { usePriceFormatter } from "../lib/currency";
import { mediaUrl } from "../lib/media";
import { productEffectivePrice } from "../lib/pricing";
import { getPublicApiUrl } from "../lib/public-env";
import { StarRating } from "./reviews";
import { LocalizedText, useLocalizeText } from "../lib/i18n/localized-text";

const PRODUCE_GLYPHS: Record<string, string> = {
  "organic-alphonso-mangoes": "M",
  "organic-baby-spinach": "S",
  "sprouted-ragi-flour": "R",
  "wood-pressed-groundnut-oil": "O",
  "himalayan-red-rajma": "R",
};

function useLiveProductImage(slug: string, imageUrl?: string | null): string | null | undefined {
  const [resolvedImageUrl, setResolvedImageUrl] = useState(imageUrl);

  useEffect(() => {
    setResolvedImageUrl(imageUrl);
    const apiUrl = getPublicApiUrl();
    if (!apiUrl) return;

    let active = true;
    fetch(`${apiUrl}/v1/public/products/${encodeURIComponent(slug)}`, {
      headers: { accept: "application/json" },
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((product: { imageUrl?: string | null } | null) => {
        if (active && product?.imageUrl && product.imageUrl !== imageUrl) {
          setResolvedImageUrl(product.imageUrl);
        }
      })
      .catch(() => undefined);

    return () => {
      active = false;
    };
  }, [imageUrl, slug]);

  return resolvedImageUrl;
}

export function ProduceFrame({
  slug,
  alt,
  imageUrl,
  className = "",
}: {
  slug: string;
  alt: string;
  imageUrl?: string | null;
  className?: string;
}) {
  const resolvedImageUrl = useLiveProductImage(slug, imageUrl);
  return (
    <div
      role="img"
      aria-label={alt}
      className={`relative flex items-center justify-center overflow-hidden bg-subtle ${className}`}
    >
      {resolvedImageUrl ? (
        <img
          src={mediaUrl(resolvedImageUrl)}
          alt=""
          className="h-full w-full object-contain p-2"
          loading="lazy"
        />
      ) : (
        <>
          <span
            aria-hidden
            className="font-display text-[5rem] leading-none text-brand/15 select-none"
          >
            {PRODUCE_GLYPHS[slug] ?? alt.charAt(0).toUpperCase()}
          </span>
          <span
            aria-hidden
            className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-brand/10 to-transparent"
          />
        </>
      )}
    </div>
  );
}

export function AvailabilityNote({
  availability,
}: {
  availability: ProductSummary["availability"];
}) {
  if (availability === "in_stock") return null;
  const label = availability === "low_stock" ? "Only a few left" : "Out of stock";
  const tone = availability === "low_stock" ? "text-accent" : "text-ink-muted";
  return <p className={`text-xs font-medium ${tone}`}>{label}</p>;
}

export function ProductCard({ product }: { product: ProductSummary }) {
  const price = usePriceFormatter();
  const effective = productEffectivePrice(product);
  return (
    <article className="group">
      <Link to={`/product/${product.slug}`} className="block">
        <ProduceFrame
          slug={product.slug}
          alt={product.imageAlt}
          imageUrl={product.imageUrl}
          className="aspect-square rounded-md transition-transform duration-200 group-hover:scale-[1.01]"
        />
        <div className="pt-3">
          <p className="text-xs text-ink-muted">
            {product.farmName} · {product.region.split(",")[0]}
          </p>
          <h3 className="mt-0.5 text-base font-medium text-ink group-hover:text-brand">
            {product.name}
          </h3>
          {product.ratingCount > 0 ? (
            <p className="mt-1 flex items-center gap-1.5 text-xs">
              <StarRating rating={Math.round(product.ratingAverage)} />
              <span className="text-ink-muted">({product.ratingCount})</span>
            </p>
          ) : null}
          <p className="mt-1 text-sm text-ink">
            {effective.originalMinor !== null ? (
              <>
                <span className="font-semibold">{price(effective.amountMinor)}</span>{" "}
                <s className="text-ink-muted">{price(effective.originalMinor)}</s>
              </>
            ) : (
              <span className="font-semibold">{price(effective.amountMinor)}</span>
            )}{" "}
            <span className="text-ink-muted">· {product.unitLabel}</span>
          </p>
          <AvailabilityNote availability={product.availability} />
        </div>
      </Link>
    </article>
  );
}

export function ProductGrid({ products }: { products: ProductSummary[] }) {
  if (products.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-line-strong px-6 py-14 text-center">
        <p className="font-display text-lg text-ink">
          <LocalizedText>Nothing here right now</LocalizedText>
        </p>
        <p className="mt-1 text-sm text-ink-muted">
          <LocalizedText>
            This harvest is between seasons. Browse the rest of the market meanwhile.
          </LocalizedText>
        </p>
        <Link
          to="/shop"
          className="mt-4 inline-block text-sm font-medium text-brand hover:underline"
        >
          <LocalizedText>Browse all products</LocalizedText>
        </Link>
      </div>
    );
  }
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-3 lg:grid-cols-4">
      {products.map((product) => (
        <li key={product.id}>
          <ProductCard product={product} />
        </li>
      ))}
    </ul>
  );
}

/**
 * Tile aspect per surface. Portrait tiles read as *content* and stack into a
 * wall when there are many, so only the tall `feature` variant keeps 4:5;
 * `rail` is landscape because a horizontal browse band is navigation, and its
 * height sets how much of the page the band costs.
 */
const CATEGORY_TILE_ASPECT = {
  feature: "aspect-[4/5]",
  rail: "aspect-[3/2]",
} as const;

export type CategoryTileVariant = keyof typeof CATEGORY_TILE_ASPECT;

/**
 * A category as an image tile.
 *
 * Roughly three quarters of the catalogue's categories carry no hero image, so
 * the no-image state is a deliberate typographic treatment — a large initial
 * over the theme colour, matching `ProduceFrame` — rather than a bare colour
 * block. A grid that mixes photographs with flat swatches reads as broken; one
 * that mixes photographs with a consistent lettered fallback reads as designed.
 */
export function CategoryTile({
  category,
  variant = "feature",
  productCount = category.productCount,
}: {
  category: CategorySummary;
  variant?: CategoryTileVariant;
  productCount?: number;
}) {
  const imageUrl = mediaUrl(category.imageUrl);
  return (
    <Link
      to={`/category/${category.slug}`}
      style={themeVars(category.themeKey)}
      className={`group relative flex ${CATEGORY_TILE_ASPECT[variant]} flex-col justify-end overflow-hidden rounded-md p-5`}
    >
      <span
        aria-hidden
        className="absolute inset-0 bg-[var(--theme-bg)] transition-transform duration-200 group-hover:scale-[1.02]"
      />
      {imageUrl ? (
        <>
          <img
            src={imageUrl}
            alt=""
            loading="lazy"
            className="absolute inset-0 h-full w-full object-contain"
          />
          <span aria-hidden className="absolute inset-0 bg-black/35" />
        </>
      ) : (
        <span
          aria-hidden
          className="absolute inset-0 flex items-center justify-center overflow-hidden"
        >
          <span className="font-display text-[6rem] leading-none text-[var(--theme-fg)] opacity-15 select-none">
            {category.name.charAt(0).toUpperCase()}
          </span>
        </span>
      )}
      <span className={"relative " + (imageUrl ? "text-white" : "text-[var(--theme-fg)]")}>
        {category.seasonLabel ? (
          <span className="mb-2 inline-block rounded-full bg-white/20 px-2.5 py-0.5 text-xs">
            {category.seasonLabel}
          </span>
        ) : null}
        <span className="block font-display text-xl leading-tight">{category.name}</span>
        <span className="mt-1 block text-sm opacity-80">
          {productCount} <LocalizedText>product</LocalizedText>
          {productCount === 1 ? "" : "s"}
        </span>
      </span>
    </Link>
  );
}

/**
 * One category as a pill link with its product count.
 *
 * Subcategories deliberately share their department's photograph, so rendering
 * a row of them as image tiles produces four identical pictures side by side.
 * As chips they read as what they are — navigation into a narrower slice — and
 * a department's sections fit on one line instead of a second tile grid.
 */
export function CategoryChip({
  label,
  count,
  href,
  active = false,
}: {
  label: string;
  count: number;
  href: string;
  active?: boolean;
}) {
  return (
    <Link
      to={href}
      aria-current={active ? "true" : undefined}
      className={
        "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm transition-colors " +
        (active
          ? "border-brand bg-brand text-ink-inverse"
          : "border-line-strong text-ink hover:bg-canvas hover:text-brand")
      }
    >
      {label}
      <span className={active ? "opacity-70" : "text-ink-muted"}>{count}</span>
    </Link>
  );
}

export function Section({
  eyebrow,
  heading,
  children,
  tone = "canvas",
}: {
  eyebrow?: string;
  heading?: string;
  children: React.ReactNode;
  tone?: "canvas" | "surface" | "subtle" | "inverse";
}) {
  const localize = useLocalizeText();
  const tones = {
    canvas: "",
    surface: "bg-surface",
    subtle: "bg-subtle/50",
    inverse: "bg-inverse text-ink-inverse",
  } as const;
  return (
    <section className={tones[tone]}>
      <div className="mx-auto max-w-[80rem] px-4 py-14 sm:px-6 md:py-20">
        {eyebrow ? (
          <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
            {localize(eyebrow)}
          </p>
        ) : null}
        {heading ? (
          <h2 className="mt-2 mb-8 max-w-2xl font-display text-2xl leading-tight md:text-3xl">
            {localize(heading)}
          </h2>
        ) : null}
        {children}
      </div>
    </section>
  );
}

export function Breadcrumbs({ items }: { items: Array<{ label: string; path: string }> }) {
  const localize = useLocalizeText();
  return (
    <nav aria-label={localize("Breadcrumb")} className="mx-auto max-w-[80rem] px-4 pt-6 sm:px-6">
      <ol className="flex flex-wrap items-center gap-1.5 text-sm text-ink-muted">
        {items.map((item, index) => (
          <li key={item.path} className="flex items-center gap-1.5">
            {index > 0 ? <span aria-hidden>/</span> : null}
            {index === items.length - 1 ? (
              <span aria-current="page" className="text-ink">
                {item.label}
              </span>
            ) : (
              <Link to={item.path} className="hover:text-brand hover:underline">
                {item.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

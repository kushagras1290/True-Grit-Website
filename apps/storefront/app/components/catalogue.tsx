/** Catalogue presentation: product cards, category tiles, produce art direction.
 *
 * No photography ships with the repo, so each product renders a quiet
 * botanical placeholder driven by its category theme — real media assets slot
 * into the same frame via Cloudflare Images at integration time. */

import type { CategorySummary, ProductSummary } from "@truegrit/contracts";
import { themeVars, type ThemeKey } from "@truegrit/ui";
import { Link } from "react-router";

import { usePriceFormatter } from "../lib/currency";

const PRODUCE_GLYPHS: Record<string, string> = {
  "organic-alphonso-mangoes": "M",
  "organic-baby-spinach": "S",
  "sprouted-ragi-flour": "R",
  "wood-pressed-groundnut-oil": "O",
  "himalayan-red-rajma": "R",
};

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
  return (
    <div
      role="img"
      aria-label={alt}
      className={`relative flex items-center justify-center overflow-hidden bg-subtle ${className}`}
    >
      {imageUrl ? (
        <img src={imageUrl} alt="" className="h-full w-full object-cover" loading="lazy" />
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
  const onSale = product.saleMinor !== null && product.saleMinor < product.priceMinor;
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
          <p className="mt-1 text-sm text-ink">
            {onSale ? (
              <>
                <span className="font-semibold">{price(product.saleMinor!)}</span>{" "}
                <s className="text-ink-muted">{price(product.priceMinor)}</s>
              </>
            ) : (
              <span className="font-semibold">{price(product.priceMinor)}</span>
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
        <p className="font-display text-lg text-ink">Nothing here right now</p>
        <p className="mt-1 text-sm text-ink-muted">
          This harvest is between seasons. Browse the rest of the market meanwhile.
        </p>
        <Link
          to="/shop"
          className="mt-4 inline-block text-sm font-medium text-brand hover:underline"
        >
          Browse all products
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

export function CategoryTile({ category }: { category: CategorySummary }) {
  return (
    <Link
      to={`/category/${category.slug}`}
      style={themeVars(category.themeKey as ThemeKey)}
      className="group relative flex aspect-[4/5] flex-col justify-end overflow-hidden rounded-md p-5"
    >
      <span
        aria-hidden
        className="absolute inset-0 bg-[var(--theme-bg)] transition-transform duration-200 group-hover:scale-[1.02]"
      />
      {category.imageUrl ? (
        <>
          <img
            src={category.imageUrl}
            alt=""
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
          />
          <span aria-hidden className="absolute inset-0 bg-black/25" />
        </>
      ) : null}
      <span className="relative text-[var(--theme-fg)]">
        {category.seasonLabel ? (
          <span className="mb-2 inline-block rounded-full bg-white/15 px-2.5 py-0.5 text-xs">
            {category.seasonLabel}
          </span>
        ) : null}
        <span className="block font-display text-xl leading-tight">{category.name}</span>
        <span className="mt-1 block text-sm opacity-80">{category.productCount} products</span>
      </span>
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
          <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">{eyebrow}</p>
        ) : null}
        {heading ? (
          <h2 className="mt-2 mb-8 max-w-2xl font-display text-2xl leading-tight md:text-3xl">
            {heading}
          </h2>
        ) : null}
        {children}
      </div>
    </section>
  );
}

export function Breadcrumbs({ items }: { items: Array<{ label: string; path: string }> }) {
  return (
    <nav aria-label="Breadcrumb" className="mx-auto max-w-[80rem] px-4 pt-6 sm:px-6">
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

/** CMS block renderer — exhaustive over known types; unknown blocks fail safely. */

import type {
  CategorySummary,
  FarmDetail,
  ProductSummary,
  PublicPageBlock,
} from "@truegrit/contracts";
import { Link } from "react-router";

import { CategoryTile, ProductGrid, Section } from "./catalogue";

export interface BlockData {
  productsBySlug: Map<string, ProductSummary>;
  categoriesBySlug: Map<string, CategorySummary>;
  farmsBySlug: Map<string, FarmDetail>;
}

function HeroBlockView({ block }: { block: Extract<PublicPageBlock, { type: "hero" }> }) {
  const slides = (block.props.slides ?? []).filter(
    (slide) => slide.enabled !== false && slide.imageUrl,
  );
  if (slides.length === 0 && block.props.imageUrl) {
    slides.push({
      imageUrl: block.props.imageUrl,
      imageAlt: block.props.imageAlt || block.props.heading,
      href: block.props.primaryAction.href,
      label: block.props.primaryAction.label,
      enabled: true,
    });
  }

  if (slides.length > 0) {
    return (
      <section className="bg-canvas">
        <div className="mx-auto max-w-[80rem] px-4 py-4 sm:px-6">
          <div className="relative overflow-hidden rounded-md bg-[#d8c8b4]">
            <div className="absolute inset-0 bg-gradient-to-r from-[#d8c8b4] via-[#d8c8b4]/90 to-[#d8c8b4]/50" />
            <div className="relative grid gap-5 px-4 py-5 md:min-h-[18rem] md:grid-cols-[22rem_1fr] md:items-center md:px-7">
              <form
                action="/search"
                method="get"
                className="rounded-md bg-surface p-5 shadow-overlay md:p-6"
              >
                <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
                  {block.props.eyebrow}
                </p>
                <h1 className="mt-2 font-display text-2xl leading-tight text-ink">
                  {block.props.heading}
                </h1>
                <p className="mt-2 text-sm leading-6 text-ink-muted">{block.props.text}</p>
                <div className="mt-4 divide-y divide-line rounded-sm border border-line-strong">
                  <label className="block">
                    <span className="sr-only">Food type</span>
                    <select
                      name="q"
                      defaultValue=""
                      className="min-h-11 w-full bg-surface px-3 text-sm text-ink outline-none"
                    >
                      <option value="">Select food type</option>
                      <option value="fruit">Fresh fruits</option>
                      <option value="vegetables">Organic vegetables</option>
                      <option value="grains">Grains and millets</option>
                      <option value="oil">Cold-pressed oils</option>
                    </select>
                  </label>
                  <label className="block">
                    <span className="sr-only">Harvest focus</span>
                    <select
                      name="focus"
                      defaultValue=""
                      className="min-h-11 w-full bg-surface px-3 text-sm text-ink outline-none"
                    >
                      <option value="">Select harvest focus</option>
                      <option value="fresh">Fresh this week</option>
                      <option value="pantry">Pantry staples</option>
                      <option value="farm">Verified farm produce</option>
                    </select>
                  </label>
                  <label className="block">
                    <span className="sr-only">Budget</span>
                    <select
                      name="budget"
                      defaultValue=""
                      className="min-h-11 w-full bg-surface px-3 text-sm text-ink outline-none"
                    >
                      <option value="">Select budget</option>
                      <option value="under-250">Under Rs 250</option>
                      <option value="250-750">Rs 250 to Rs 750</option>
                      <option value="750-plus">Rs 750 plus</option>
                    </select>
                  </label>
                </div>
                <button
                  type="submit"
                  className="mt-3 inline-flex min-h-11 w-full items-center justify-center rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90"
                >
                  Search
                </button>
                {block.props.secondaryAction ? (
                  <Link
                    to={block.props.secondaryAction.href}
                    className="mt-3 block text-right text-xs font-medium text-brand hover:underline"
                  >
                    {block.props.secondaryAction.label}
                  </Link>
                ) : null}
              </form>

              <div className="grid grid-cols-5 items-end gap-2 md:h-full md:gap-3">
                {slides.map((slide, index) => (
                  <Link
                    key={`${slide.imageUrl}-${slide.href}`}
                    to={slide.href}
                    className={
                      "group relative flex min-h-24 items-end justify-center overflow-hidden rounded-sm bg-white/25 " +
                      (index === 0 ? "col-span-2 md:min-h-56" : "md:min-h-40")
                    }
                    aria-label={slide.label}
                  >
                    <img
                      src={slide.imageUrl}
                      alt={slide.imageAlt || slide.label}
                      className="h-full w-full object-contain transition-transform duration-200 group-hover:scale-[1.02]"
                      fetchPriority={index === 0 ? "high" : "auto"}
                      loading={index === 0 ? "eager" : "lazy"}
                    />
                    <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-2 pt-8 pb-2 text-xs font-medium text-white">
                      {slide.label}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="bg-brand text-ink-inverse">
      <div className="mx-auto grid max-w-[80rem] gap-10 px-4 py-16 sm:px-6 md:grid-cols-[3fr_2fr] md:py-24">
        <div className="max-w-xl">
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-80">
            {block.props.eyebrow}
          </p>
          <h1 className="mt-4 font-display text-4xl leading-[1.08] md:text-5xl">
            {block.props.heading}
          </h1>
          <p className="mt-5 max-w-md text-base opacity-90 md:text-lg">{block.props.text}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              to={block.props.primaryAction.href}
              className="inline-flex min-h-11 items-center rounded-sm bg-canvas px-5 text-sm font-medium text-brand hover:opacity-90"
            >
              {block.props.primaryAction.label}
            </Link>
            {block.props.secondaryAction ? (
              <Link
                to={block.props.secondaryAction.href}
                className="inline-flex min-h-11 items-center rounded-sm border border-white/40 px-5 text-sm font-medium text-ink-inverse hover:bg-white/10"
              >
                {block.props.secondaryAction.label}
              </Link>
            ) : null}
          </div>
        </div>
        <div aria-hidden className="hidden items-center justify-center md:flex">
          <div className="relative h-64 w-64">
            <span className="absolute inset-0 rounded-full border border-white/25" />
            <span className="absolute inset-6 rounded-full border border-white/15" />
            <span className="absolute inset-12 rounded-full bg-white/10" />
            <span className="absolute inset-0 flex items-center justify-center font-display text-6xl text-white/30">
              TG
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

export function CmsBlock({ block, data }: { block: PublicPageBlock; data: BlockData }) {
  if (!block.enabled) return null;

  switch (block.type) {
    case "hero":
      return <HeroBlockView block={block} />;

    case "category_collection": {
      const categories = block.props.categorySlugs.flatMap(
        (slug) => data.categoriesBySlug.get(slug) ?? [],
      );
      if (categories.length === 0) return null;
      return (
        <Section eyebrow="The market" heading={block.props.heading}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {categories.map((category) => (
              <CategoryTile key={category.id} category={category} />
            ))}
          </div>
        </Section>
      );
    }

    case "product_collection": {
      const products = block.props.productSlugs
        .slice(0, block.props.limit)
        .flatMap((slug) => data.productsBySlug.get(slug) ?? []);
      if (products.length === 0) return null;
      return (
        <Section eyebrow="Picked this week" heading={block.props.heading} tone="surface">
          <ProductGrid products={products} />
        </Section>
      );
    }

    case "farmer_story": {
      const farm = data.farmsBySlug.get(block.props.farmSlug);
      return (
        <Section tone="subtle">
          <figure className="mx-auto max-w-3xl text-center">
            <blockquote className="font-display text-2xl leading-snug text-ink md:text-3xl">
              “{block.props.quote}”
            </blockquote>
            <figcaption className="mt-4 text-sm text-ink-muted">
              {block.props.attribution}
              {farm ? (
                <>
                  {" — "}
                  <Link to={`/farms/${farm.slug}`} className="text-brand hover:underline">
                    visit the farm
                  </Link>
                </>
              ) : null}
            </figcaption>
          </figure>
        </Section>
      );
    }

    case "faq":
      return (
        <Section eyebrow="Our standards" heading={block.props.heading}>
          <dl className="mx-auto grid max-w-4xl gap-6 md:grid-cols-2">
            {block.props.items.map((item) => (
              <div key={item.question} className="border-t border-line pt-4">
                <dt className="font-medium text-ink">{item.question}</dt>
                <dd className="mt-1.5 text-sm text-ink-muted">{item.answer}</dd>
              </div>
            ))}
          </dl>
        </Section>
      );

    case "rich_text":
      return (
        <Section>
          <div className="mx-auto max-w-2xl space-y-4 text-base text-ink">
            {block.props.paragraphs.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </div>
        </Section>
      );

    case "newsletter":
      return (
        <Section tone="inverse">
          <div className="mx-auto max-w-xl text-center">
            <h2 className="font-display text-3xl">{block.props.heading}</h2>
            <p className="mt-2 text-sm opacity-80">{block.props.consentText}</p>
            <form
              className="mt-6 flex flex-col gap-2 sm:flex-row"
              onSubmit={(event) => event.preventDefault()}
            >
              <label htmlFor="newsletter-email" className="sr-only">
                Email address
              </label>
              <input
                id="newsletter-email"
                type="email"
                required
                placeholder="you@example.com"
                className="min-h-11 flex-1 rounded-sm border border-white/30 bg-white/10 px-4 text-sm text-ink-inverse placeholder:text-white/50"
              />
              <button
                type="submit"
                className="min-h-11 rounded-sm bg-canvas px-5 text-sm font-medium text-brand hover:opacity-90"
              >
                Subscribe
              </button>
            </form>
          </div>
        </Section>
      );

    default: {
      // A future backend may ship block types this build does not know.
      // Render nothing rather than crash the page (ADR-005).
      const unknown = block as { type?: string };
      if (typeof console !== "undefined") {
        console.error("Unknown CMS block type skipped:", unknown.type);
      }
      return null;
    }
  }
}

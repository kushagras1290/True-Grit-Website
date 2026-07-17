/** CMS block renderer — exhaustive over known types; unknown blocks fail safely. */

import type {
  CategorySummary,
  FarmDetail,
  ProductSummary,
  PublicPageBlock,
} from "@truegrit/contracts";
import { useEffect, useState } from "react";
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
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    if (activeIndex >= slides.length) setActiveIndex(0);
  }, [activeIndex, slides.length]);

  useEffect(() => {
    if (slides.length <= 1) return undefined;
    const timer = window.setInterval(() => {
      setActiveIndex((index) => (index + 1) % slides.length);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [slides.length]);

  if (slides.length > 0) {
    const activeSlide = slides[Math.min(activeIndex, slides.length - 1)]!;
    return (
      <section className="bg-canvas">
        <div className="mx-auto max-w-[80rem] px-4 py-4 sm:px-6">
          <div className="relative overflow-hidden rounded-md bg-[#d8c8b4]">
            <div className="relative px-3 py-3 md:px-5 md:py-5">
              <div>
                <Link
                  to={activeSlide.href}
                  className="group relative block min-h-52 overflow-hidden rounded-md bg-white/25 md:min-h-72"
                  aria-label={activeSlide.label}
                >
                  <img
                    src={activeSlide.imageUrl}
                    alt={activeSlide.imageAlt || activeSlide.label}
                    className="absolute inset-0 h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.01]"
                    fetchPriority="high"
                    loading="eager"
                  />
                  <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/65 to-transparent px-4 pt-16 pb-3 text-sm font-medium text-white">
                    {activeSlide.label}
                  </span>
                </Link>

                <div className="mt-3 flex justify-end gap-1">
                  {slides.map((slide, index) => (
                    <button
                      key={`${slide.imageUrl}-${index}-dot`}
                      type="button"
                      onClick={() => setActiveIndex(index)}
                      className={
                        "h-1.5 rounded-full transition-all " +
                        (index === activeIndex ? "w-5 bg-brand" : "w-1.5 bg-white/70")
                      }
                      aria-label={`Show ${slide.label}`}
                    />
                  ))}
                </div>
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

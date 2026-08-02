/** CMS block renderer — exhaustive over known types; unknown blocks fail safely. */

import type {
  CategorySummary,
  FarmDetail,
  ProductSummary,
  PublicPageBlock,
} from "@truegrit/contracts";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router";

import { mediaUrl } from "../lib/media";
import { CategoryTile, ProductCard, Section } from "./catalogue";
import { BannerBrandLockup } from "./page-banner";
import { Slider } from "./slider";

export interface BlockData {
  productsBySlug: Map<string, ProductSummary>;
  categoriesBySlug: Map<string, CategorySummary>;
  farmsBySlug: Map<string, FarmDetail>;
}

// Matches the API's inline link syntax exactly (domain/blocks.py
// `_INLINE_LINK_PATTERN`): `[label](href)`, href already revalidated
// server-side (only `/`, `https://`, `http://`, `mailto:`, never `//`). This
// is the ONLY way a link can appear in rich text — raw HTML is rejected at
// save time (ADR-005), so there is nothing here for dangerouslySetInnerHTML
// to ever need.
const INLINE_LINK_PATTERN = /\[([^[\]\n]{1,120})\]\(([^\s()]{1,512})\)/g;

/** A same-site path the router can handle, as opposed to an absolute URL or a
 * `mailto:`. The API already rejects anything outside that allow-list; this
 * only decides which element renders it. */
function isInternalHref(href: string): boolean {
  return href.startsWith("/") && !href.startsWith("//");
}

function renderRichTextParagraph(paragraph: string) {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  INLINE_LINK_PATTERN.lastIndex = 0;
  while ((match = INLINE_LINK_PATTERN.exec(paragraph)) !== null) {
    const [full, label, href] = match;
    if (match.index > lastIndex) {
      nodes.push(paragraph.slice(lastIndex, match.index));
    }
    const isInternal = isInternalHref(href!);
    nodes.push(
      isInternal ? (
        <Link
          key={key++}
          to={href!}
          className="text-brand underline underline-offset-2 hover:no-underline"
        >
          {label}
        </Link>
      ) : (
        <a
          key={key++}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-brand underline underline-offset-2 hover:no-underline"
        >
          {label}
        </a>
      ),
    );
    lastIndex = match.index + full!.length;
  }
  if (lastIndex < paragraph.length) {
    nodes.push(paragraph.slice(lastIndex));
  }
  return nodes;
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
      <section className="bg-banner">
        <div className="relative w-full overflow-hidden">
          <Link
            to={activeSlide.href}
            // Fixed, not minimum: matches BANNER_FRAME in page-banner.tsx so
            // every uploaded slide (exported at exactly 1672×464px) is scaled
            // to this one designed size, never stretched further by content.
            className="group relative block h-[21rem] overflow-hidden bg-white/25 md:h-[29rem]"
            aria-label={activeSlide.label}
          >
            <img
              src={mediaUrl(activeSlide.imageUrl)}
              alt={activeSlide.imageAlt || activeSlide.label}
              className="absolute inset-0 h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.01]"
              fetchPriority="high"
              loading="eager"
            />
            <span
              aria-hidden
              className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/15 to-black/20"
            />
            <span className="absolute top-5 left-5">
              <BannerBrandLockup />
            </span>
            <span className="absolute inset-x-0 bottom-0 px-5 pt-20 pb-5 text-sm font-medium text-white">
              {activeSlide.label}
            </span>
          </Link>

          <div className="absolute right-5 bottom-5 flex gap-1">
            {slides.map((slide, index) => (
              <button
                key={`${slide.imageUrl}-${index}-dot`}
                type="button"
                onClick={() => setActiveIndex(index)}
                className={
                  "h-1.5 rounded-full transition-all " +
                  (index === activeIndex ? "w-5 bg-white" : "w-1.5 bg-white/70")
                }
                aria-label={`Show ${slide.label}`}
              />
            ))}
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
      // Resolved through the live categories map, so an unpublished
      // (disabled) category simply drops out of the row — the public API
      // stops returning it and flatMap skips the missing slug.
      const categories = block.props.categorySlugs.flatMap(
        (slug) => data.categoriesBySlug.get(slug) ?? [],
      );
      if (categories.length === 0) return null;
      return (
        <Section eyebrow="The market" heading={block.props.heading}>
          <Slider ariaLabel={block.props.heading}>
            {categories.map((category) => (
              <div
                key={category.id}
                className="w-[calc(50%-0.5rem)] shrink-0 snap-start sm:w-[calc(33.3%-0.7rem)] lg:w-[calc(25%-0.75rem)]"
              >
                <CategoryTile category={category} />
              </div>
            ))}
          </Slider>
        </Section>
      );
    }

    case "product_collection": {
      // Same live-data contract as categories: disabled products are absent
      // from the API response, so they never render here.
      const products = block.props.productSlugs
        .slice(0, block.props.limit)
        .flatMap((slug) => data.productsBySlug.get(slug) ?? []);
      if (products.length === 0) return null;
      return (
        <Section eyebrow="Picked this week" heading={block.props.heading} tone="surface">
          <Slider ariaLabel={block.props.heading}>
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
              <p key={index}>{renderRichTextParagraph(paragraph)}</p>
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

    case "page_links": {
      // A card is parked by unticking it, not by deleting the copy — the same
      // contract as a hero slide. An empty list therefore means "the owner
      // hid every card", which is a section with nothing left to say.
      const items = block.props.items.filter((item) => item.enabled);
      if (items.length === 0) return null;
      // The same hairline-list rhythm as the FAQ block above (border-t + pt-4
      // per row, gap-6, max-w-4xl), not a grid of card boxes: the homepage
      // reads as one editorial page, and a wall of bordered tiles was the one
      // section that broke that register.
      const linkClassName = "group block";
      return (
        <Section eyebrow="Explore the site" heading={block.props.heading}>
          {block.props.intro ? (
            <p className="mx-auto -mt-4 mb-8 max-w-2xl text-base text-ink-muted">
              {block.props.intro}
            </p>
          ) : null}
          <ul className="mx-auto grid max-w-4xl gap-6 md:grid-cols-2">
            {items.map((item, index) => {
              const body = (
                <>
                  <span className="flex items-baseline gap-1.5 font-medium text-ink group-hover:text-brand">
                    {item.label}
                    <span
                      aria-hidden
                      className="text-brand transition-transform group-hover:translate-x-0.5"
                    >
                      →
                    </span>
                  </span>
                  {item.description ? (
                    <span className="mt-1.5 block text-sm text-ink-muted">{item.description}</span>
                  ) : null}
                </>
              );
              return (
                <li key={`${item.href}-${index}`} className="border-t border-line pt-4">
                  {isInternalHref(item.href) ? (
                    <Link to={item.href} className={linkClassName}>
                      {body}
                    </Link>
                  ) : (
                    <a
                      href={item.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={linkClassName}
                    >
                      {body}
                    </a>
                  )}
                </li>
              );
            })}
          </ul>
        </Section>
      );
    }

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

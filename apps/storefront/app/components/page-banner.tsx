/**
 * Full-bleed page banner, dimensionally identical to the homepage hero.
 *
 * The homepage hero (`HeroBlockView` in blocks.tsx) is a full-width band of
 * `h-[21rem]` growing to `md:h-[29rem]`, with the image cropped to fill it.
 * Keeping those exact numbers in `BANNER_FRAME` is what makes the blog and
 * category banners read as the same element rather than "another image" —
 * change them here and every banner moves together.
 *
 * A *fixed* height, not a minimum: every image uploaded here is exported at
 * exactly `1672 × 464 px` (see the image dimensions guide), and `object-cover`
 * scales it to fill whatever box it is given. A `min-h` box grows the moment a
 * long heading, description or CTA needs more room than the minimum — and the
 * image, having no independent size, grows right along with it, upscaling and
 * cropping further than the shipped asset was ever meant to. Fixing the height
 * and letting `overflow-hidden` protect it keeps the image at its designed
 * scale regardless of how much copy an editor puts inside. The text overlay is
 * `absolute inset-0` for the same reason: it must never influence the frame's
 * height by sitting in normal flow.
 *
 * The band is rendered even when no image is configured, so the space a banner
 * occupies never collapses and a page does not visibly reflow the moment an
 * owner uploads one. The heading sits over the image, so the banner carries the
 * page title rather than duplicating it.
 */

import type { ReactNode } from "react";
import { Link } from "react-router";

import { mediaUrl } from "../lib/media";
import { useLocalizeText } from "../lib/i18n/localized-text";

/** Matches the homepage hero exactly — see the module comment. */
export const BANNER_FRAME = "relative h-[21rem] w-full overflow-hidden md:h-[29rem]";
export const DEFAULT_PAGE_BANNER_IMAGE = "/banners/content/default-market-banner.png";

export interface PageBannerProps {
  imageUrl?: string | null;
  imageAlt?: string | null;
  eyebrow?: string | null;
  heading: string;
  description?: string | null;
  /** Turns the whole banner into a link, matching the homepage hero's slides. */
  href?: string | null;
  /** Rendered under the description — a call to action, a count, a chip row. */
  children?: ReactNode;
  /** `eager` for the banner at the top of a page the visitor landed on. */
  loading?: "eager" | "lazy";
}

/** Exact brand lockup shared by every photographic banner. */
export function BannerBrandLockup() {
  return (
    <span className="inline-flex w-fit items-center gap-2.5 rounded-sm border border-white/25 bg-black/25 px-2.5 py-2 text-white shadow-sm backdrop-blur-sm">
      <img
        src="/brand/true-grit-mark.webp"
        alt=""
        aria-hidden
        className="h-8 w-8 rounded-[0.2rem] object-cover"
      />
      <span className="font-display text-sm tracking-[0.18em] uppercase">True Grit</span>
    </span>
  );
}

export function PageBanner({
  imageUrl,
  imageAlt,
  eyebrow,
  heading,
  description,
  href,
  children,
  loading = "eager",
}: PageBannerProps) {
  const localize = useLocalizeText();
  // A banner is never a blank gradient. CMS media remains authoritative, but
  // null/empty records get a real project-owned photograph while an editor is
  // still preparing route-specific art.
  const resolved = mediaUrl(imageUrl || DEFAULT_PAGE_BANNER_IMAGE);

  const content = (
    <>
      <img
        src={resolved}
        alt=""
        aria-hidden
        className="absolute inset-0 h-full w-full scale-105 object-cover opacity-45 blur-md"
      />
      <img
        src={resolved}
        // Decorative: the heading below carries the meaning, so an empty alt
        // avoids a screen reader announcing the same words twice. A caller
        // that supplies real alt text gets it used.
        alt={imageAlt ? localize(imageAlt) : ""}
        className="absolute inset-0 h-full w-full object-contain"
        fetchPriority={loading === "eager" ? "high" : "auto"}
        loading={loading}
      />
      {/* The scrim is what keeps the heading legible over an arbitrary photo,
          and it doubles as the banner's background when there is no image. */}
      <span
        aria-hidden
        className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/35 to-black/10"
      />
      {/* `absolute inset-0`, not a normal-flow sibling: this box must never be
          able to grow the frame past its fixed height (see BANNER_FRAME above).
          Long copy scrolls into the padding it has rather than stretching the
          image behind it. */}
      <div className="absolute inset-0 mx-auto flex max-w-[80rem] flex-col overflow-y-auto px-4 py-8 sm:px-6 md:py-10">
        <BannerBrandLockup />
        <div className="mt-auto pt-12">
          {eyebrow ? (
            <p className="text-xs font-semibold tracking-[0.14em] text-white/80 uppercase">
              {localize(eyebrow)}
            </p>
          ) : null}
          <h1 className="mt-2 max-w-3xl font-display text-3xl leading-tight text-white md:text-5xl">
            {localize(heading)}
          </h1>
          {description ? (
            <p className="mt-3 max-w-2xl text-base text-white/85">{localize(description)}</p>
          ) : null}
          {children ? <div className="mt-5">{children}</div> : null}
        </div>
      </div>
    </>
  );

  if (href) {
    return (
      <section className="bg-banner">
        <Link to={href} className={`group block ${BANNER_FRAME}`} aria-label={localize(heading)}>
          {content}
        </Link>
      </section>
    );
  }

  return (
    <section className="bg-banner">
      <div className={BANNER_FRAME}>{content}</div>
    </section>
  );
}

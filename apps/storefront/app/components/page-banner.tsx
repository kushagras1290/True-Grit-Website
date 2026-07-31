/**
 * Full-bleed page banner, dimensionally identical to the homepage hero.
 *
 * The homepage hero (`HeroBlockView` in blocks.tsx) is a full-width band of
 * `min-h-[21rem]` growing to `md:min-h-[29rem]`, with the image cropped to fill
 * it. Keeping those exact numbers in `BANNER_FRAME` is what makes the blog and
 * category banners read as the same element rather than "another image" —
 * change them here and every banner moves together.
 *
 * The band is rendered even when no image is configured, so the space a banner
 * occupies never collapses and a page does not visibly reflow the moment an
 * owner uploads one. The heading sits over the image, so the banner carries the
 * page title rather than duplicating it.
 */

import type { ReactNode } from "react";
import { Link } from "react-router";

import { mediaUrl } from "../lib/media";

/** Matches the homepage hero exactly — see the module comment. */
export const BANNER_FRAME = "relative min-h-[21rem] w-full overflow-hidden md:min-h-[29rem]";

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
  const resolved = imageUrl ? mediaUrl(imageUrl) : null;

  const content = (
    <>
      {resolved ? (
        <img
          src={resolved}
          // Decorative: the heading below carries the meaning, so an empty alt
          // avoids a screen reader announcing the same words twice. A caller
          // that supplies real alt text gets it used.
          alt={imageAlt || ""}
          className="absolute inset-0 h-full w-full object-cover"
          fetchPriority={loading === "eager" ? "high" : "auto"}
          loading={loading}
        />
      ) : null}
      {/* The scrim is what keeps the heading legible over an arbitrary photo,
          and it doubles as the banner's background when there is no image. */}
      <span
        aria-hidden
        className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/35 to-black/10"
      />
      <div className="relative mx-auto flex min-h-[21rem] max-w-[80rem] flex-col justify-end px-4 py-10 sm:px-6 md:min-h-[29rem] md:py-14">
        {eyebrow ? (
          <p className="text-xs font-semibold tracking-[0.14em] text-white/80 uppercase">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="mt-2 max-w-3xl font-display text-3xl leading-tight text-white md:text-5xl">
          {heading}
        </h1>
        {description ? (
          <p className="mt-3 max-w-2xl text-base text-white/85">{description}</p>
        ) : null}
        {children ? <div className="mt-5">{children}</div> : null}
      </div>
    </>
  );

  if (href) {
    return (
      <section className="bg-[#d8c8b4]">
        <Link to={href} className={`group block ${BANNER_FRAME}`} aria-label={heading}>
          {content}
        </Link>
      </section>
    );
  }

  return (
    <section className="bg-[#d8c8b4]">
      <div className={BANNER_FRAME}>{content}</div>
    </section>
  );
}

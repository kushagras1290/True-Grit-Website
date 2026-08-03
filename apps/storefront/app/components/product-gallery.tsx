/**
 * Amazon-style product image viewer: a large main image with a thumbnail
 * strip beneath it -- click a thumbnail, the main image swaps to it.
 *
 * The default (first) thumbnail is always the product's one required image,
 * rendered through `ProduceFrame` so it keeps that component's live-refresh
 * and category-glyph-placeholder behaviour unchanged. Once a customer picks
 * a gallery photo, this renders it directly -- `ProduceFrame`'s own
 * `useLiveProductImage` re-fetches the product's *main* image in the
 * background and would otherwise silently swap a chosen gallery photo back
 * to the main one the moment that fetch resolves.
 */

import type { ProductImage } from "@truegrit/contracts";
import { useState } from "react";

import { ProduceFrame } from "./catalogue";
import { mediaUrl } from "../lib/media";
import { useLocalizeText } from "../lib/i18n/localized-text";

export function ProductGallery({
  slug,
  mainImageUrl,
  mainImageAlt,
  galleryImages,
  className = "",
}: {
  slug: string;
  mainImageUrl?: string | null;
  mainImageAlt: string;
  galleryImages: ProductImage[];
  className?: string;
}) {
  const localize = useLocalizeText();
  const [selected, setSelected] = useState(0);
  const hasGallery = galleryImages.length > 0;

  return (
    <div>
      <div className={className}>
        {selected === 0 ? (
          <ProduceFrame
            slug={slug}
            alt={mainImageAlt}
            imageUrl={mainImageUrl}
            className="h-full w-full"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center overflow-hidden bg-subtle">
            <img
              src={mediaUrl(galleryImages[selected - 1]!.imageUrl)}
              alt={galleryImages[selected - 1]!.imageAlt ?? mainImageAlt}
              className="h-full w-full object-contain p-2"
              loading="lazy"
            />
          </div>
        )}
      </div>

      {hasGallery ? (
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          <button
            type="button"
            aria-label={localize("Show main product photo")}
            aria-current={selected === 0}
            onClick={() => setSelected(0)}
            className={`h-16 w-16 shrink-0 overflow-hidden rounded-sm border-2 ${
              selected === 0 ? "border-brand" : "border-transparent hover:border-line-strong"
            }`}
          >
            <ProduceFrame
              slug={slug}
              alt={mainImageAlt}
              imageUrl={mainImageUrl}
              className="h-full w-full"
            />
          </button>
          {galleryImages.map((image, index) => (
            <button
              key={image.id}
              type="button"
              aria-label={`Show photo ${index + 2}`}
              aria-current={selected === index + 1}
              onClick={() => setSelected(index + 1)}
              className={`h-16 w-16 shrink-0 overflow-hidden rounded-sm border-2 bg-subtle ${
                selected === index + 1
                  ? "border-brand"
                  : "border-transparent hover:border-line-strong"
              }`}
            >
              <img
                src={mediaUrl(image.imageUrl)}
                alt=""
                className="h-full w-full object-contain p-1"
                loading="lazy"
              />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

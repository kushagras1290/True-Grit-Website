/** Heart toggle for saving a product to the wishlist. Anonymous visitors are
 * sent to `/account`, which already explains how to sign in (via the header
 * menu) rather than duplicating that flow here. */

import { Heart } from "lucide-react";
import { useNavigate } from "react-router";

import { useLocalizeText } from "../lib/i18n/localized-text";
import { useCustomer } from "../lib/customer-auth";
import { useWishlist } from "../lib/wishlist";

export function WishlistButton({
  productId,
  className = "",
}: {
  productId: string;
  className?: string;
}) {
  const { status } = useCustomer();
  const { isSaved, toggle } = useWishlist();
  const navigate = useNavigate();
  const localize = useLocalizeText();
  const saved = isSaved(productId);
  const label = localize(saved ? "Remove from wishlist" : "Save to wishlist");

  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={saved}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        if (status !== "authenticated") {
          void navigate("/account");
          return;
        }
        void toggle(productId);
      }}
      className={`inline-flex h-9 w-9 items-center justify-center rounded-full bg-surface/90 text-ink shadow-sm transition hover:text-brand ${className}`}
    >
      <Heart
        size={18}
        fill={saved ? "currentColor" : "none"}
        className={saved ? "text-brand" : ""}
      />
    </button>
  );
}

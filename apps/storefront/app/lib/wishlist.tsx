/**
 * Wishlist: a signed-in customer saving a product for later. Unlike the
 * cart (client-side, localStorage-only — see `cart.tsx`), this syncs to the
 * API so a saved item follows the customer across devices; a wishlist with
 * no server backing wouldn't be worth having.
 *
 * `toggle` assumes the caller has already gated the action on
 * `useCustomer().status === "authenticated"` (the wishlist button does this,
 * redirecting an anonymous visitor to `/account` instead of calling toggle)
 * — as defence in depth, toggle itself still no-ops for anyone else, so
 * nothing can ever show as "saved" without a real signed-in customer behind
 * it.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  addToWishlist,
  commerceLive,
  listWishlistProductIds,
  removeFromWishlist,
} from "./commerce";
import { useCustomer } from "./customer-auth";

interface WishlistContextValue {
  isSaved: (productId: string) => boolean;
  toggle: (productId: string) => Promise<void>;
  loading: boolean;
}

const WishlistContext = createContext<WishlistContextValue | null>(null);

export function WishlistProvider({ children }: { children: ReactNode }) {
  const { customer, status } = useCustomer();
  const [productIds, setProductIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (status !== "authenticated" || !customer || !commerceLive) {
      setProductIds(new Set());
      return;
    }
    let cancelled = false;
    setLoading(true);
    listWishlistProductIds()
      .then((ids) => {
        if (!cancelled) setProductIds(new Set(ids));
      })
      .catch(() => {
        // A failed hydrate just leaves every heart icon unfilled; toggling
        // still works per item on its own request.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [status, customer]);

  const toggle = useCallback(
    async (productId: string) => {
      if (status !== "authenticated") return;
      const alreadySaved = productIds.has(productId);
      setProductIds((current) => {
        const next = new Set(current);
        if (alreadySaved) next.delete(productId);
        else next.add(productId);
        return next;
      });
      // Demo mode has no live API to persist to; the optimistic flip above
      // is the whole experience there, same posture the cart takes toward
      // checkout in demo mode.
      if (!commerceLive) return;
      try {
        if (alreadySaved) await removeFromWishlist(productId);
        else await addToWishlist(productId);
      } catch {
        setProductIds((current) => {
          const next = new Set(current);
          if (alreadySaved) next.add(productId);
          else next.delete(productId);
          return next;
        });
      }
    },
    [productIds, status],
  );

  const isSaved = useCallback((productId: string) => productIds.has(productId), [productIds]);

  const value = useMemo<WishlistContextValue>(
    () => ({ isSaved, toggle, loading }),
    [isSaved, toggle, loading],
  );

  return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>;
}

export function useWishlist(): WishlistContextValue {
  const context = useContext(WishlistContext);
  if (!context) throw new Error("useWishlist must be used inside WishlistProvider");
  return context;
}

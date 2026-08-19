/**
 * Release-1 cart: client-side, persisted to localStorage. Totals shown here are
 * estimates only — the API is authoritative from checkout onward (Release 2).
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

export interface CartLine {
  productSlug: string;
  productName: string;
  variantId: string;
  variantName: string;
  unitMinor: number;
  preorder?: boolean;
  recommendationSourceProductId?: string;
  recommendationRunId?: string;
  recommendationPlacement?: "product" | "cart" | "homepage" | "category" | "shop" | "order";
  quantity: number;
}

interface CartContextValue {
  lines: CartLine[];
  count: number;
  subtotalMinor: number;
  add: (line: Omit<CartLine, "quantity">, quantity?: number) => void;
  setQuantity: (variantId: string, quantity: number, preorder?: boolean) => void;
  remove: (variantId: string, preorder?: boolean) => void;
  clear: () => void;
}

const CartContext = createContext<CartContextValue | null>(null);
const STORAGE_KEY = "truegrit.cart.v1";
const MAX_QUANTITY = 12;

function readStorage(): CartLine[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as CartLine[]) : [];
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setLines(readStorage());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
  }, [lines, hydrated]);

  const add = useCallback((line: Omit<CartLine, "quantity">, quantity = 1) => {
    setLines((current) => {
      const existing = current.find(
        (entry) =>
          entry.variantId === line.variantId && Boolean(entry.preorder) === Boolean(line.preorder),
      );
      if (existing) {
        return current.map((entry) =>
          entry.variantId === line.variantId && Boolean(entry.preorder) === Boolean(line.preorder)
            ? { ...entry, quantity: Math.min(entry.quantity + quantity, MAX_QUANTITY) }
            : entry,
        );
      }
      return [...current, { ...line, quantity: Math.min(quantity, MAX_QUANTITY) }];
    });
  }, []);

  const setQuantity = useCallback((variantId: string, quantity: number, preorder = false) => {
    setLines((current) =>
      quantity <= 0
        ? current.filter(
            (entry) =>
              entry.variantId !== variantId || Boolean(entry.preorder) !== Boolean(preorder),
          )
        : current.map((entry) =>
            entry.variantId === variantId && Boolean(entry.preorder) === Boolean(preorder)
              ? { ...entry, quantity: Math.min(quantity, MAX_QUANTITY) }
              : entry,
          ),
    );
  }, []);

  const remove = useCallback((variantId: string, preorder = false) => {
    setLines((current) =>
      current.filter(
        (entry) => entry.variantId !== variantId || Boolean(entry.preorder) !== Boolean(preorder),
      ),
    );
  }, []);

  const clear = useCallback(() => setLines([]), []);

  const value = useMemo<CartContextValue>(() => {
    const count = lines.reduce((sum, entry) => sum + entry.quantity, 0);
    const subtotalMinor = lines.reduce((sum, entry) => sum + entry.unitMinor * entry.quantity, 0);
    return { lines, count, subtotalMinor, add, setQuantity, remove, clear };
  }, [lines, add, setQuantity, remove, clear]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used inside CartProvider");
  return context;
}

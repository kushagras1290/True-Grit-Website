/** Site chrome: announcement bar, header, footer. Editorial, not boxed. */

import type { PublicBootstrap } from "@truegrit/contracts";
import { Search, ShoppingBasket } from "lucide-react";
import { useState } from "react";
import { Link, NavLink } from "react-router";

import { useCart } from "../lib/cart";

export function Header({ bootstrap }: { bootstrap: PublicBootstrap }) {
  const { count } = useCart();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <>
      {bootstrap.announcement ? (
        <div className="bg-brand px-4 py-2 text-center text-sm text-ink-inverse">
          {bootstrap.announcement.path ? (
            <Link to={bootstrap.announcement.path} className="hover:underline">
              {bootstrap.announcement.message}
            </Link>
          ) : (
            bootstrap.announcement.message
          )}
        </div>
      ) : null}

      <header className="sticky top-0 z-40 border-b border-line bg-canvas/95 backdrop-blur">
        <div className="mx-auto flex max-w-[80rem] items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="flex min-h-11 min-w-11 items-center justify-center md:hidden"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              onClick={() => setMenuOpen((open) => !open)}
            >
              <span className="sr-only">{menuOpen ? "Close menu" : "Open menu"}</span>
              <span aria-hidden className="space-y-1">
                <span className="block h-0.5 w-5 bg-ink" />
                <span className="block h-0.5 w-5 bg-ink" />
                <span className="block h-0.5 w-3.5 bg-ink" />
              </span>
            </button>
            <Link to="/" className="font-display text-xl font-semibold tracking-tight text-brand">
              TRUE GRIT
            </Link>
          </div>

          <nav aria-label="Primary" className="hidden md:block">
            <ul className="flex items-center gap-6">
              {bootstrap.navigation.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    className={({ isActive }) =>
                      `text-sm ${isActive ? "font-medium text-brand" : "text-ink hover:text-brand"}`
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          <div className="flex items-center gap-1">
            <Link
              to="/search"
              className="flex min-h-11 min-w-11 items-center justify-center text-ink hover:text-brand"
              aria-label="Search"
            >
              <Search size={19} />
            </Link>
            <Link
              to="/cart"
              className="relative flex min-h-11 min-w-11 items-center justify-center text-ink hover:text-brand"
              aria-label={`Cart, ${count} item${count === 1 ? "" : "s"}`}
            >
              <ShoppingBasket size={20} />
              {count > 0 ? (
                <span
                  aria-hidden
                  className="absolute top-1 right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-ink-inverse"
                >
                  {count}
                </span>
              ) : null}
            </Link>
          </div>
        </div>

        {menuOpen ? (
          <nav id="mobile-nav" aria-label="Mobile" className="border-t border-line bg-canvas md:hidden">
            <ul className="px-4 py-3">
              {bootstrap.navigation.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    onClick={() => setMenuOpen(false)}
                    className="block min-h-11 py-2.5 text-base text-ink"
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        ) : null}
      </header>
    </>
  );
}

export function Footer({ bootstrap }: { bootstrap: PublicBootstrap }) {
  return (
    <footer className="mt-20 bg-inverse text-ink-inverse">
      <div className="mx-auto grid max-w-[80rem] gap-10 px-4 py-14 sm:px-6 md:grid-cols-[2fr_1fr_1fr]">
        <div>
          <p className="font-display text-2xl">TRUE GRIT</p>
          <p className="mt-3 max-w-sm text-sm opacity-80">
            Traceable organic food from verified farms, responsible brands and seasonal harvests —
            delivered with complete transparency.
          </p>
        </div>
        <nav aria-label="Footer market">
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-70">Market</p>
          <ul className="mt-3 space-y-2 text-sm">
            {bootstrap.navigation.map((item) => (
              <li key={item.path}>
                <Link to={item.path} className="opacity-90 hover:underline">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <nav aria-label="Footer support">
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-70">Support</p>
          <ul className="mt-3 space-y-2 text-sm">
            {bootstrap.footerNavigation.map((item) => (
              <li key={item.path}>
                <Link to={item.path} className="opacity-90 hover:underline">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
      <div className="border-t border-white/10 px-4 py-4 text-center text-xs opacity-60">
        © 2026 True Grit. Certified organic, honestly traded.
      </div>
    </footer>
  );
}

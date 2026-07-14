/** Site chrome: announcement bar, header, footer. Editorial, not boxed. */

import type { PublicBootstrap } from "@truegrit/contracts";
import { Search, ShoppingBasket, UserRound, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, NavLink } from "react-router";

import { useCart } from "../lib/cart";
import {
  AuthError,
  GoogleSignInButton,
  requestPasswordReset,
  useCustomer,
} from "../lib/customer-auth";

type AuthMode = "signin" | "register";

function ForgotPassword() {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);

  if (done) {
    return (
      <p className="text-xs text-ink-muted">
        If that email has an account, a reset link is on its way.
      </p>
    );
  }
  if (!open) {
    return (
      <button
        type="button"
        className="text-xs text-brand underline-offset-4 hover:underline"
        onClick={() => setOpen(true)}
      >
        Forgot password?
      </button>
    );
  }
  return (
    <form
      className="flex items-center gap-2"
      onSubmit={async (event) => {
        event.preventDefault();
        const email = String(new FormData(event.currentTarget).get("email") ?? "");
        setPending(true);
        try {
          await requestPasswordReset(email);
        } finally {
          setPending(false);
          setDone(true);
        }
      }}
    >
      <input
        name="email"
        type="email"
        required
        placeholder="you@example.com"
        className="min-h-9 flex-1 rounded-sm border border-line bg-canvas px-2 text-sm text-ink"
      />
      <button
        type="submit"
        disabled={pending}
        className="min-h-9 rounded-sm border border-line px-3 text-xs font-medium text-ink hover:bg-canvas disabled:opacity-60"
      >
        {pending ? "…" : "Send"}
      </button>
    </form>
  );
}

const FIELD_CLASS =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

function AccountSummary({
  email,
  name,
  onNavigate,
  onSignOut,
  pending,
}: {
  email: string;
  name: string;
  onNavigate: () => void;
  onSignOut: () => void;
  pending: boolean;
}) {
  return (
    <div className="space-y-3 px-4 py-4">
      <div>
        <p className="text-sm font-medium text-ink">{name}</p>
        <p className="text-xs text-ink-muted">{email}</p>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <Link
          to="/account"
          className="rounded-sm border border-line px-3 py-2 text-center hover:bg-canvas"
          onClick={onNavigate}
        >
          Your account
        </Link>
        <Link
          to="/cart"
          className="rounded-sm border border-line px-3 py-2 text-center hover:bg-canvas"
          onClick={onNavigate}
        >
          Cart
        </Link>
      </div>
      <button
        type="button"
        className="min-h-11 w-full rounded-sm border border-line px-3 text-sm text-ink hover:bg-canvas disabled:opacity-60"
        onClick={onSignOut}
        disabled={pending}
      >
        {pending ? "Signing out…" : "Sign out"}
      </button>
    </div>
  );
}

function CustomerPortal() {
  const { customer, status, login, register, loginWithGoogle, logout } = useCustomer();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<AuthMode>("signin");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const reportError = useCallback((message: string) => setError(message), []);

  const handleGoogle = useCallback(
    async (credential: string) => {
      setError(null);
      setPending(true);
      try {
        await loginWithGoogle(credential);
        setOpen(false);
      } catch (caught) {
        setError(caught instanceof AuthError ? caught.message : "Google sign-in failed.");
      } finally {
        setPending(false);
      }
    },
    [loginWithGoogle],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    setError(null);
    setPending(true);
    try {
      if (mode === "register") {
        await register({ name: String(form.get("name") ?? ""), email, password });
      } else {
        await login(email, password);
      }
      setOpen(false);
    } catch (caught) {
      setError(
        caught instanceof AuthError ? caught.message : "Something went wrong. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }

  function switchMode(next: AuthMode) {
    setMode(next);
    setError(null);
  }

  const signedIn = status === "authenticated" && customer !== null;

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        className="flex min-h-11 min-w-11 items-center justify-center text-ink hover:text-brand"
        aria-label={signedIn ? "Open account" : "Sign in"}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <UserRound size={20} />
      </button>
      {open ? (
        <div
          role="dialog"
          aria-label="Customer account"
          className="absolute top-full right-0 z-50 mt-2 w-[min(23rem,calc(100vw-2rem))] rounded-md border border-line bg-surface shadow-overlay"
        >
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <div>
              <p className="font-medium text-ink">{signedIn ? "Account" : "Welcome"}</p>
              <p className="text-xs text-ink-muted">
                {signedIn ? customer.email : "Sign in to track orders and rewards"}
              </p>
            </div>
            <button
              type="button"
              className="flex h-8 w-8 items-center justify-center text-ink-muted hover:text-ink"
              aria-label="Close account panel"
              onClick={() => setOpen(false)}
            >
              <X size={17} />
            </button>
          </div>

          {signedIn ? (
            <AccountSummary
              name={customer.displayName}
              email={customer.email}
              pending={pending}
              onNavigate={() => setOpen(false)}
              onSignOut={async () => {
                setPending(true);
                await logout();
                setPending(false);
              }}
            />
          ) : (
            <div className="space-y-4 px-4 py-4">
              <GoogleSignInButton onCredential={handleGoogle} onError={reportError} />

              <div className="flex items-center gap-3 text-xs text-ink-muted">
                <span className="h-px flex-1 bg-line" />
                or
                <span className="h-px flex-1 bg-line" />
              </div>

              <div className="grid grid-cols-2 gap-1 rounded-sm bg-canvas p-1 text-sm">
                {(["signin", "register"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={
                      "min-h-9 rounded-sm px-3 font-medium " +
                      (mode === value ? "bg-surface text-ink shadow-sm" : "text-ink-muted")
                    }
                    aria-pressed={mode === value}
                    onClick={() => switchMode(value)}
                  >
                    {value === "signin" ? "Sign in" : "Create account"}
                  </button>
                ))}
              </div>

              <form className="space-y-3" onSubmit={handleSubmit}>
                {mode === "register" ? (
                  <label className="block space-y-1">
                    <span className="text-xs font-medium text-ink-muted">Name</span>
                    <input
                      name="name"
                      type="text"
                      autoComplete="name"
                      required
                      className={FIELD_CLASS}
                      placeholder="Priya Sharma"
                    />
                  </label>
                ) : null}
                <label className="block space-y-1">
                  <span className="text-xs font-medium text-ink-muted">Email</span>
                  <input
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    className={FIELD_CLASS}
                    placeholder="you@example.com"
                  />
                </label>
                <label className="block space-y-1">
                  <span className="text-xs font-medium text-ink-muted">Password</span>
                  <input
                    name="password"
                    type="password"
                    autoComplete={mode === "register" ? "new-password" : "current-password"}
                    required
                    minLength={mode === "register" ? 10 : undefined}
                    className={FIELD_CLASS}
                    placeholder={mode === "register" ? "At least 10 characters" : "Your password"}
                  />
                </label>

                {error ? (
                  <p role="alert" className="text-sm text-danger">
                    {error}
                  </p>
                ) : null}

                <button
                  type="submit"
                  className="min-h-11 w-full rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-95 disabled:opacity-60"
                  disabled={pending}
                >
                  {pending ? "Please wait…" : mode === "register" ? "Create account" : "Sign in"}
                </button>
              </form>

              {mode === "signin" ? (
                <div className="pt-1">
                  <ForgotPassword />
                </div>
              ) : null}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

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
            <CustomerPortal />
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
          <nav
            id="mobile-nav"
            aria-label="Mobile"
            className="border-t border-line bg-canvas md:hidden"
          >
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

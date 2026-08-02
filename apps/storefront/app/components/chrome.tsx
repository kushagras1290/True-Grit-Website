/** Site chrome: announcement bar, header, footer. Editorial, not boxed. */

import type { PublicBootstrap } from "@truegrit/contracts";
import { Search, ShoppingBasket, UserRound, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Form, Link, NavLink } from "react-router";

import { useCart } from "../lib/cart";
import {
  AuthError,
  FacebookSignInButton,
  GoogleSignInButton,
  requestPasswordReset,
  useCustomer,
  type PhoneVerification,
} from "../lib/customer-auth";
import { useLocaleContext } from "../lib/i18n/context";
import { useSiteSettings, type SiteSettings } from "../lib/site-settings";
import { HeaderLanguageSwitcher, LanguageSwitcher } from "./language-switcher";
import { AddPhonePrompt, PhoneAuthPanel, PhoneVerifier } from "./phone-auth";

type AuthMode = "phone" | "signin" | "register";

const AUTH_MODE_LABELS: Record<AuthMode, string> = {
  phone: "Mobile",
  signin: "Email",
  register: "Sign up",
};

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

/** Name only the methods currently on offer, so the panel never advertises a
 *  route the owner has switched off. */
function signInSubtitle(auth: SiteSettings["auth"]): string {
  const methods = [
    auth.phoneOtp ? "your mobile" : null,
    auth.password ? "email" : null,
    auth.google ? "Google" : null,
    auth.facebook ? "Facebook" : null,
  ].filter((value): value is string => value !== null);
  if (methods.length === 0) return "Sign-in is temporarily unavailable";
  if (methods.length === 1) return `Sign in with ${methods[0]}`;
  return `Sign in with ${methods.slice(0, -1).join(", ")} or ${methods.at(-1)}`;
}

function AccountSummary({
  email,
  phone,
  name,
  onNavigate,
  onSignOut,
  pending,
}: {
  email: string | null;
  phone: string | null;
  name: string;
  onNavigate: () => void;
  onSignOut: () => void;
  pending: boolean;
}) {
  const { t } = useLocaleContext();
  return (
    <div className="space-y-3 px-4 py-4">
      <div>
        <p className="text-sm font-medium text-ink">{name}</p>
        {/* A phone-only account has no address, so lead with whichever
            identifier this customer actually has. */}
        <p className="text-xs text-ink-muted">{email ?? phone ?? t("auth.noContact")}</p>
        {email && phone ? <p className="text-xs text-ink-muted">{phone}</p> : null}
      </div>

      <AddPhonePrompt />

      <div className="grid grid-cols-2 gap-2 text-sm">
        <Link
          to="/account"
          className="rounded-sm border border-line px-3 py-2 text-center hover:bg-canvas"
          onClick={onNavigate}
        >
          {t("auth.yourAccount")}
        </Link>
        <Link
          to="/cart"
          className="rounded-sm border border-line px-3 py-2 text-center hover:bg-canvas"
          onClick={onNavigate}
        >
          {t("common.cart")}
        </Link>
      </div>
      <button
        type="button"
        className="min-h-11 w-full rounded-sm border border-line px-3 text-sm text-ink hover:bg-canvas disabled:opacity-60"
        onClick={onSignOut}
        disabled={pending}
      >
        {pending ? t("auth.signingOut") : t("auth.signOut")}
      </button>
    </div>
  );
}

function CustomerPortal() {
  const { customer, status, login, register, loginWithGoogle, loginWithFacebook, logout } =
    useCustomer();
  // Which sign-in methods the owner has switched on, already ANDed with what
  // the API is configured for — see lib/site-settings.
  const { auth } = useSiteSettings();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  // Proof of a mobile, held between the verify step and the account being
  // created. Registration will not submit without it.
  const [registerPhone, setRegisterPhone] = useState<PhoneVerification | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Only the tabs that lead somewhere. Mobile first where it is available: it is
  // the shortest path for most Indian customers and needs no password.
  const availableModes = useMemo<AuthMode[]>(() => {
    const modes: AuthMode[] = [];
    if (auth.phoneOtp) modes.push("phone");
    if (auth.password) modes.push("signin");
    if (auth.password && auth.registration) modes.push("register");
    return modes;
  }, [auth.phoneOtp, auth.password, auth.registration]);

  const [mode, setMode] = useState<AuthMode>(() => availableModes[0] ?? "phone");

  // A switch can be flipped while the panel is open. Fall back rather than
  // leaving the customer staring at a form the API would now reject.
  useEffect(() => {
    if (availableModes.length > 0 && !availableModes.includes(mode)) {
      setMode(availableModes[0]!);
      setRegisterPhone(null);
    }
  }, [availableModes, mode]);

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

  const handleFacebook = useCallback(
    async (accessToken: string) => {
      setError(null);
      setPending(true);
      try {
        await loginWithFacebook(accessToken);
        setOpen(false);
      } catch (caught) {
        setError(caught instanceof AuthError ? caught.message : "Facebook sign-in failed.");
      } finally {
        setPending(false);
      }
    },
    [loginWithFacebook],
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
        // Only insist on the proof while passcodes are switched on: with them
        // off the API drops the requirement too, so demanding it here would
        // block a sign-up the server would happily accept.
        if (auth.phoneOtp && registerPhone === null) {
          setError("Verify your mobile number first.");
          return;
        }
        await register({
          name: String(form.get("name") ?? ""),
          email,
          password,
          phoneVerificationToken: registerPhone?.verificationToken,
        });
      } else {
        await login(email, password);
      }
      setOpen(false);
    } catch (caught) {
      setError(
        caught instanceof AuthError ? caught.message : "Something went wrong. Please try again.",
      );
      // Send them back to the number step only when the proof itself is gone.
      // For an ordinary rejection — a taken email, a weak password — the token is
      // still good, and re-verifying would cost them another text to fix a typo.
      if (caught instanceof AuthError && caught.code === "phone_verification_required") {
        setRegisterPhone(null);
      }
    } finally {
      setPending(false);
    }
  }

  function switchMode(next: AuthMode) {
    setMode(next);
    setError(null);
    setRegisterPhone(null);
  }

  const signedIn = status === "authenticated" && customer !== null;
  const showFederated = auth.google || auth.facebook;
  // The email/password form is the last step of registration, not the first:
  // while a new customer still owes us a verified number, the phone step stands
  // in its place. With passcodes switched off there is no number to verify, so
  // the form is the whole of registration.
  const showCredentialsForm =
    (mode === "signin" || (mode === "register" && (registerPhone !== null || !auth.phoneOtp))) &&
    availableModes.includes(mode);
  const noSignInAvailable = availableModes.length === 0 && !showFederated;

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
                {signedIn
                  ? (customer.email ?? customer.phone ?? "Signed in")
                  : signInSubtitle(auth)}
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
              phone={customer.phone}
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
              {noSignInAvailable ? (
                <p className="rounded-sm border border-dashed border-line px-3 py-4 text-center text-sm text-ink-muted">
                  Signing in is temporarily unavailable. Please check back shortly or{" "}
                  <Link to="/contact" className="text-brand hover:underline">
                    contact us
                  </Link>
                  .
                </p>
              ) : null}

              {showFederated ? (
                <div className="space-y-2">
                  {auth.google ? (
                    <GoogleSignInButton onCredential={handleGoogle} onError={reportError} />
                  ) : null}
                  {auth.facebook ? (
                    <FacebookSignInButton onAccessToken={handleFacebook} onError={reportError} />
                  ) : null}
                </div>
              ) : null}

              {/* The divider only earns its place when there is something on
                  both sides of it. */}
              {showFederated && availableModes.length > 0 ? (
                <div className="flex items-center gap-3 text-xs text-ink-muted">
                  <span className="h-px flex-1 bg-line" />
                  or
                  <span className="h-px flex-1 bg-line" />
                </div>
              ) : null}

              {/* A single remaining method needs no tab strip to choose between. */}
              {availableModes.length > 1 ? (
                <div
                  className="grid gap-1 rounded-sm bg-canvas p-1 text-sm"
                  style={{
                    gridTemplateColumns: `repeat(${availableModes.length}, minmax(0, 1fr))`,
                  }}
                >
                  {availableModes.map((value) => (
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
                      {AUTH_MODE_LABELS[value]}
                    </button>
                  ))}
                </div>
              ) : null}

              {mode === "phone" && auth.phoneOtp ? (
                <PhoneAuthPanel onDone={() => setOpen(false)} />
              ) : null}

              {mode === "register" && auth.phoneOtp && registerPhone === null ? (
                <PhoneVerifier
                  intent="register"
                  heading="First, verify your mobile"
                  hint="Every account needs a verified number for delivery updates."
                  onVerified={(verification) => setRegisterPhone(verification)}
                />
              ) : null}

              {showCredentialsForm ? (
                <form className="space-y-3" onSubmit={handleSubmit}>
                  {mode === "register" && registerPhone !== null ? (
                    <p className="rounded-sm border border-line bg-canvas px-3 py-2 text-xs text-ink-muted">
                      Mobile verified ✓{" "}
                      <button
                        type="button"
                        className="text-brand underline-offset-4 hover:underline"
                        onClick={() => setRegisterPhone(null)}
                      >
                        Change
                      </button>
                    </p>
                  ) : null}
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
              ) : null}

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

/** Global product search: an inline box on wider screens; small screens keep
 * the icon that leads to the full search page. Both land on /search. */
function GlobalSearch() {
  const { t } = useLocaleContext();
  return (
    <Form method="get" action="/search" role="search" className="hidden lg:block">
      <label htmlFor="global-search" className="sr-only">
        {t("common.searchProducts")}
      </label>
      <div className="relative">
        <Search
          size={15}
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-ink-muted"
        />
        <input
          id="global-search"
          name="q"
          type="search"
          placeholder={t("common.searchPlaceholder")}
          autoComplete="off"
          className="min-h-9 w-44 rounded-full border border-line bg-surface pr-3 pl-8 text-sm text-ink transition-[width] duration-200 placeholder:text-ink-muted focus:w-64 focus:border-brand focus:outline-none"
        />
      </div>
    </Form>
  );
}

export function Header({ bootstrap }: { bootstrap: PublicBootstrap }) {
  const { count } = useCart();
  const { t } = useLocaleContext();
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

      <header className="sticky top-0 z-40 border-b border-line bg-canvas/95 backdrop-blur print:hidden">
        <div className="flex w-full items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="flex min-h-11 min-w-11 items-center justify-center md:hidden"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              onClick={() => setMenuOpen((open) => !open)}
            >
              <span className="sr-only">
                {menuOpen ? t("common.closeMenu") : t("common.openMenu")}
              </span>
              <span aria-hidden className="space-y-1">
                <span className="block h-0.5 w-5 bg-ink" />
                <span className="block h-0.5 w-5 bg-ink" />
                <span className="block h-0.5 w-3.5 bg-ink" />
              </span>
            </button>
            <Link
              to="/"
              aria-label="True Grit home"
              className="inline-flex items-center gap-2 font-display text-xl font-semibold tracking-tight text-brand"
            >
              <img
                src="/brand/true-grit-mark.webp"
                alt=""
                width={36}
                height={36}
                className="h-9 w-9 rounded-full object-cover"
              />
              <span>TRUE GRIT</span>
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
            {/* Left of the search box on purpose — a returning visitor scans
                right-to-left from search to cart, so the language control
                needs to be the first thing in that path, not buried after it. */}
            <HeaderLanguageSwitcher className="hidden sm:inline-flex" />
            <GlobalSearch />
            <CustomerPortal />
            <Link
              to="/search"
              className="flex min-h-11 min-w-11 items-center justify-center text-ink hover:text-brand lg:hidden"
              aria-label={t("common.search")}
            >
              <Search size={19} />
            </Link>
            <Link
              to="/cart"
              className="relative flex min-h-11 min-w-11 items-center justify-center text-ink hover:text-brand"
              aria-label={t("common.cartWithCount", { count })}
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
            {/* The switcher is in the mobile menu as well as the footer:
                a visitor who cannot read the page should not have to scroll
                past the whole of it to find the way out. */}
            <div className="border-t border-line px-4 py-3">
              <LanguageSwitcher />
            </div>
          </nav>
        ) : null}
      </header>
    </>
  );
}

export function Footer({ bootstrap }: { bootstrap: PublicBootstrap }) {
  const { t } = useLocaleContext();
  return (
    <footer className="mt-20 bg-inverse text-ink-inverse print:hidden">
      <div className="mx-auto grid max-w-[80rem] gap-10 px-4 py-14 sm:px-6 md:grid-cols-[2fr_1fr_1fr]">
        <div>
          <p className="font-display text-2xl">TRUE GRIT</p>
          <p className="mt-3 max-w-sm text-sm opacity-80">{t("footer.tagline")}</p>
          {/* The permanent home of the language control. The header carries one
              too on small screens, but this is the one that is always present
              and always in the same place. */}
          <div className="mt-6">
            <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-70">
              {t("language.label")}
            </p>
            <LanguageSwitcher tone="dark" className="mt-2" />
          </div>
        </div>
        <nav aria-label={t("footer.market")}>
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-70">
            {t("footer.market")}
          </p>
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
        <nav aria-label={t("footer.support")}>
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-70">
            {t("footer.support")}
          </p>
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
        {t("footer.rights")}
      </div>
    </footer>
  );
}

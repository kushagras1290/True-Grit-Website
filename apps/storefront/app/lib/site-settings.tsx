/**
 * Owner-controlled storefront switches: which sign-in methods to offer, whether
 * to take payments, and the blog banner image.
 *
 * Resolved server-side in the root loader and handed down through context, so
 * the header renders the right buttons on first paint rather than flashing a
 * sign-in method the API would refuse. The API returns switches already ANDed
 * with its own configuration (see `services/feature_settings.py`), so a `true`
 * here always means the feature will actually work.
 *
 * Every flag defaults to the permissive value. If the API is unreachable — or
 * the storefront is running in demo-data mode with no API at all — the
 * storefront behaves exactly as it did before these switches existed, rather
 * than presenting a site nobody can sign into.
 */

import type { StorefrontEffects, StorefrontTheme } from "@truegrit/contracts";
import { createContext, useContext, type ReactNode } from "react";

import { DEFAULT_EFFECTS, DEFAULT_THEME, normalizeEffects, normalizeTheme } from "./theme";

export interface SiteSettings {
  auth: {
    google: boolean;
    facebook: boolean;
    phoneOtp: boolean;
    password: boolean;
    registration: boolean;
  };
  payments: {
    enabled: boolean;
    disabledNotice: string;
  };
  promotions: {
    enabled: boolean;
  };
  recommendations: {
    enabled: boolean;
  };
  subscriptions: {
    enabled: boolean;
  };
  dietCertFilters: {
    enabled: boolean;
  };
  giftCards: {
    enabled: boolean;
  };
  loyalty: { enabled: boolean };
  pickup: { enabled: boolean };
  preorders: { enabled: boolean };
  deliveryZones: { enabled: boolean };
  b2b: { enabled: boolean };
  i18n: { englishOnly: boolean };
  banners: {
    blogImageUrl: string;
    blogImageAlt: string;
    farmsImageUrl: string;
    farmsImageAlt: string;
  };
  /** Owner-chosen colours: the site-wide set plus any per-path overrides.
   *  Carried on this response rather than fetched separately so the first byte
   *  of HTML is already the right colour. */
  theme: StorefrontTheme;
  effects: StorefrontEffects;
  /** Hex colour for the help widget, or "" to inherit the brand colour.
   *  Validated server-side to a hex triplet before it is stored, because it
   *  ends up in an inline style attribute. */
  supportBotColor: string;
  /** Whether the floating "Ask us" launcher should render at all. False means
   *  the button itself must not appear, not just that sending a message would
   *  fail -- see `components/support-bot-widget.tsx`. */
  supportBotStorefrontEnabled: boolean;
}

export const DEFAULT_PAYMENTS_DISABLED_NOTICE =
  "We are not taking orders at the moment. Leave your details and we will get in touch as soon as ordering reopens.";

export const DEFAULT_SITE_SETTINGS: SiteSettings = {
  auth: { google: true, facebook: true, phoneOtp: true, password: true, registration: true },
  payments: { enabled: true, disabledNotice: DEFAULT_PAYMENTS_DISABLED_NOTICE },
  // Off by default (matches migration 0060) -- a marketing feature switched on
  // deliberately once a promotion is configured, not a permissive fallback.
  promotions: { enabled: false },
  // On by default -- recommendations need no setup, they are computed live
  // from real order data, so shipping them on is the permissive value here.
  recommendations: { enabled: true },
  // Off by default (matches migration 0064) -- not needed at launch, an
  // owner switches it on deliberately, the same reasoning as `promotions`.
  subscriptions: { enabled: false },
  // On by default, same reasoning as `recommendations` -- reads tags/
  // certifications already assigned in the product editor, no setup needed.
  dietCertFilters: { enabled: true },
  // Off by default (matches migration 0082) -- real stored value an owner
  // issues deliberately, same reasoning as `promotions`.
  giftCards: { enabled: false },
  loyalty: { enabled: false },
  pickup: { enabled: false },
  preorders: { enabled: false },
  deliveryZones: { enabled: false },
  b2b: { enabled: false },
  i18n: { englishOnly: false },
  banners: { blogImageUrl: "", blogImageAlt: "", farmsImageUrl: "", farmsImageAlt: "" },
  theme: DEFAULT_THEME,
  effects: DEFAULT_EFFECTS,
  supportBotColor: "",
  // Matches the backend default (services/support_bot_settings.py: both
  // widgets default to enabled until an owner turns one off).
  supportBotStorefrontEnabled: true,
};

/** Coerce an untrusted API payload into a complete `SiteSettings`.
 *
 * Missing or wrongly-typed fields fall back to the default rather than to
 * `false`: a partial response from an older API build must not switch sign-in
 * off for everyone. */
export function normalizeSiteSettings(input: unknown): SiteSettings {
  const source = (input ?? {}) as Partial<{
    auth: Partial<SiteSettings["auth"]>;
    payments: Partial<SiteSettings["payments"]>;
    promotions: Partial<SiteSettings["promotions"]>;
    recommendations: Partial<SiteSettings["recommendations"]>;
    subscriptions: Partial<SiteSettings["subscriptions"]>;
    dietCertFilters: Partial<SiteSettings["dietCertFilters"]>;
    giftCards: Partial<SiteSettings["giftCards"]>;
    loyalty: Partial<SiteSettings["loyalty"]>;
    pickup: Partial<SiteSettings["pickup"]>;
    preorders: Partial<SiteSettings["preorders"]>;
    deliveryZones: Partial<SiteSettings["deliveryZones"]>;
    b2b: Partial<SiteSettings["b2b"]>;
    i18n: Partial<SiteSettings["i18n"]>;
    banners: Partial<SiteSettings["banners"]>;
    theme: unknown;
    effects: unknown;
    supportBotColor: unknown;
    supportBotStorefrontEnabled: unknown;
  }>;
  const auth = source.auth ?? {};
  const payments = source.payments ?? {};
  const promotions = source.promotions ?? {};
  const recommendations = source.recommendations ?? {};
  const subscriptions = source.subscriptions ?? {};
  const dietCertFilters = source.dietCertFilters ?? {};
  const giftCards = source.giftCards ?? {};
  const loyalty = source.loyalty ?? {};
  const pickup = source.pickup ?? {};
  const preorders = source.preorders ?? {};
  const deliveryZones = source.deliveryZones ?? {};
  const b2b = source.b2b ?? {};
  const i18n = source.i18n ?? {};
  const banners = source.banners ?? {};

  const bool = (value: unknown, fallback: boolean): boolean =>
    typeof value === "boolean" ? value : fallback;
  const text = (value: unknown, fallback: string): string =>
    typeof value === "string" && value.trim() ? value : fallback;

  return {
    auth: {
      google: bool(auth.google, DEFAULT_SITE_SETTINGS.auth.google),
      facebook: bool(auth.facebook, DEFAULT_SITE_SETTINGS.auth.facebook),
      phoneOtp: bool(auth.phoneOtp, DEFAULT_SITE_SETTINGS.auth.phoneOtp),
      password: bool(auth.password, DEFAULT_SITE_SETTINGS.auth.password),
      registration: bool(auth.registration, DEFAULT_SITE_SETTINGS.auth.registration),
    },
    payments: {
      enabled: bool(payments.enabled, DEFAULT_SITE_SETTINGS.payments.enabled),
      disabledNotice: text(payments.disabledNotice, DEFAULT_PAYMENTS_DISABLED_NOTICE),
    },
    promotions: {
      enabled: bool(promotions.enabled, DEFAULT_SITE_SETTINGS.promotions.enabled),
    },
    recommendations: {
      enabled: bool(recommendations.enabled, DEFAULT_SITE_SETTINGS.recommendations.enabled),
    },
    subscriptions: {
      enabled: bool(subscriptions.enabled, DEFAULT_SITE_SETTINGS.subscriptions.enabled),
    },
    dietCertFilters: {
      enabled: bool(dietCertFilters.enabled, DEFAULT_SITE_SETTINGS.dietCertFilters.enabled),
    },
    giftCards: {
      enabled: bool(giftCards.enabled, DEFAULT_SITE_SETTINGS.giftCards.enabled),
    },
    loyalty: { enabled: bool(loyalty.enabled, DEFAULT_SITE_SETTINGS.loyalty.enabled) },
    pickup: { enabled: bool(pickup.enabled, DEFAULT_SITE_SETTINGS.pickup.enabled) },
    preorders: { enabled: bool(preorders.enabled, DEFAULT_SITE_SETTINGS.preorders.enabled) },
    deliveryZones: {
      enabled: bool(deliveryZones.enabled, DEFAULT_SITE_SETTINGS.deliveryZones.enabled),
    },
    b2b: { enabled: bool(b2b.enabled, DEFAULT_SITE_SETTINGS.b2b.enabled) },
    i18n: { englishOnly: bool(i18n.englishOnly, DEFAULT_SITE_SETTINGS.i18n.englishOnly) },
    banners: {
      blogImageUrl: text(banners.blogImageUrl, ""),
      blogImageAlt: text(banners.blogImageAlt, ""),
      farmsImageUrl: text(banners.farmsImageUrl, ""),
      farmsImageAlt: text(banners.farmsImageAlt, ""),
    },
    theme: normalizeTheme(source.theme),
    effects: normalizeEffects(source.effects),
    // Re-checked here rather than trusted: this value is applied as an inline
    // style, and normalize() exists precisely to not trust the payload.
    supportBotColor: /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(String(source.supportBotColor))
      ? String(source.supportBotColor)
      : "",
    supportBotStorefrontEnabled: bool(
      source.supportBotStorefrontEnabled,
      DEFAULT_SITE_SETTINGS.supportBotStorefrontEnabled,
    ),
  };
}

const SiteSettingsContext = createContext<SiteSettings>(DEFAULT_SITE_SETTINGS);

export function SiteSettingsProvider({
  settings,
  children,
}: {
  settings: SiteSettings;
  children: ReactNode;
}) {
  return <SiteSettingsContext.Provider value={settings}>{children}</SiteSettingsContext.Provider>;
}

export function useSiteSettings(): SiteSettings {
  return useContext(SiteSettingsContext);
}

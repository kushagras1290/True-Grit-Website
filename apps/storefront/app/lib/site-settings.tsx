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
  banners: { blogImageUrl: "", blogImageAlt: "", farmsImageUrl: "", farmsImageAlt: "" },
  theme: DEFAULT_THEME,
  effects: DEFAULT_EFFECTS,
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
    banners: Partial<SiteSettings["banners"]>;
    theme: unknown;
    effects: unknown;
  }>;
  const auth = source.auth ?? {};
  const payments = source.payments ?? {};
  const promotions = source.promotions ?? {};
  const recommendations = source.recommendations ?? {};
  const subscriptions = source.subscriptions ?? {};
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
    banners: {
      blogImageUrl: text(banners.blogImageUrl, ""),
      blogImageAlt: text(banners.blogImageAlt, ""),
      farmsImageUrl: text(banners.farmsImageUrl, ""),
      farmsImageAlt: text(banners.farmsImageAlt, ""),
    },
    theme: normalizeTheme(source.theme),
    effects: normalizeEffects(source.effects),
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

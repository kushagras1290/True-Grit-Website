/**
 * Owner-controlled colour theme.
 *
 * The storefront's palette lives in CSS custom properties (`@truegrit/ui`
 * tokens). A theme is nothing more than a sparse set of overrides for those
 * properties: one site-wide set, plus per-path sets for pages that want their
 * own look.
 *
 * Three rules keep it from ever breaking a page:
 *
 * * **Sparse wins.** A missing or blank token means "keep the shipped value",
 *   so a partial payload from an older API — or a theme where the owner only
 *   changed the accent — degrades to the stock palette, never to a page of
 *   undefined colours.
 * * **Values are validated, not trusted.** Only `#rgb`/`#rrggbb`/`#rrggbbaa`
 *   and a short list of CSS colour functions get through. The theme is
 *   interpolated into a `<style>` element, so anything else would be a CSS
 *   injection point.
 * * **Resolution happens in the browser, from one payload.** The whole theme
 *   ships on the first response and the active path picks its overrides out of
 *   it, so a client-side navigation re-themes on the spot with no second
 *   request and no flash of the previous page's colours.
 */

import {
  AMBIENT_EFFECT_KEYS,
  CURSOR_TRAIL_KEYS,
  THEME_TOKEN_KEYS,
  type AmbientEffectKey,
  type CursorTrailKey,
  type StorefrontEffects,
  type StorefrontTheme,
  type ThemeTokens,
} from "@truegrit/contracts";
import { createContext, useContext, type ReactNode } from "react";

export const DEFAULT_THEME: StorefrontTheme = { global: {}, pages: {} };

/** Nothing on by default. A storefront that started snowing because a field
 *  failed to parse would be worse than one that never snowed. */
export const DEFAULT_EFFECTS: StorefrontEffects = {
  ambient: { effect: "none", color: "#ffffff", intensity: 3 },
  cursor: { trail: "none", color: "#24483a", hideNativeCursor: false },
};

/** CSS custom property each token writes to. */
const TOKEN_PROPERTY: Record<(typeof THEME_TOKEN_KEYS)[number], string> = {
  bgCanvas: "--color-bg-canvas",
  bgSurface: "--color-bg-surface",
  bgSubtle: "--color-bg-subtle",
  bgInverse: "--color-bg-inverse",
  bannerBackdrop: "--color-banner-backdrop",
  textPrimary: "--color-text-primary",
  textSecondary: "--color-text-secondary",
  textInverse: "--color-text-inverse",
  brandPrimary: "--color-brand-primary",
  brandAccent: "--color-brand-accent",
  brandGold: "--color-brand-gold",
  borderSubtle: "--color-border-subtle",
  borderStrong: "--color-border-strong",
  danger: "--color-danger",
  success: "--color-success",
  warning: "--color-warning",
};

const HEX_PATTERN = /^#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
// Deliberately narrow: enough for the alpha-bearing borders the stock theme
// uses, with no room for `url(...)`, a semicolon, or a closing brace.
const FUNCTIONAL_PATTERN = /^(?:rgb|rgba|hsl|hsla|color-mix)\([a-z0-9\s%,./#-]{1,180}\)$/i;

/** True when a value is safe to interpolate into a stylesheet as a colour. */
export function isValidThemeColor(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > 200) return false;
  return HEX_PATTERN.test(trimmed) || FUNCTIONAL_PATTERN.test(trimmed);
}

/** Keep only the known token keys carrying a valid colour. */
export function normalizeThemeTokens(input: unknown): ThemeTokens {
  if (!input || typeof input !== "object") return {};
  const source = input as Record<string, unknown>;
  const tokens: ThemeTokens = {};
  for (const key of THEME_TOKEN_KEYS) {
    const value = source[key];
    if (typeof value === "string" && isValidThemeColor(value)) {
      tokens[key] = value.trim();
    }
  }
  return tokens;
}

/** A storefront path an override may be attached to. */
function isThemePath(path: string): boolean {
  return path.startsWith("/") && !path.startsWith("//") && path.length <= 200;
}

export function normalizeTheme(input: unknown): StorefrontTheme {
  if (!input || typeof input !== "object") return DEFAULT_THEME;
  const source = input as { global?: unknown; pages?: unknown };
  const pages: Record<string, ThemeTokens> = {};
  if (source.pages && typeof source.pages === "object") {
    for (const [path, value] of Object.entries(source.pages as Record<string, unknown>)) {
      if (!isThemePath(path)) continue;
      const tokens = normalizeThemeTokens(value);
      if (Object.keys(tokens).length > 0) pages[path] = tokens;
    }
  }
  return { global: normalizeThemeTokens(source.global), pages };
}

/**
 * The tokens in force for one path: the site-wide set with that page's
 * overrides layered on top.
 *
 * Matching is exact, then longest-prefix on a path segment boundary — so an
 * override on `/blog` also dresses `/blog/how-to-read-a-label`, while `/blogs`
 * (a different page) is untouched. A page can therefore be themed without
 * enumerating every article under it.
 */
export function resolveThemeTokens(theme: StorefrontTheme, pathname: string): ThemeTokens {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") || "/" : pathname;
  let match = theme.pages[path];
  if (!match) {
    let bestLength = 0;
    for (const [candidate, tokens] of Object.entries(theme.pages)) {
      if (candidate === "/" || candidate.length <= bestLength) continue;
      if (path === candidate || path.startsWith(`${candidate}/`)) {
        match = tokens;
        bestLength = candidate.length;
      }
    }
  }
  return { ...theme.global, ...(match ?? {}) };
}

/** The `:root { … }` rule for a token set, or "" when nothing is overridden. */
export function themeStyleSheet(tokens: ThemeTokens): string {
  const declarations = THEME_TOKEN_KEYS.flatMap((key) => {
    const value = tokens[key];
    if (!value || !isValidThemeColor(value)) return [];
    return [`${TOKEN_PROPERTY[key]}:${value.trim()}`];
  });
  return declarations.length > 0 ? `:root{${declarations.join(";")}}` : "";
}

/**
 * Coerce an untrusted effects payload into a complete `StorefrontEffects`.
 *
 * Every unreadable field falls back to "off" rather than to a default effect:
 * an owner who never chose snow must not get snow because a column was empty.
 */
export function normalizeEffects(input: unknown): StorefrontEffects {
  if (!input || typeof input !== "object") return DEFAULT_EFFECTS;
  const source = input as { ambient?: unknown; cursor?: unknown };
  const ambient = (source.ambient ?? {}) as Record<string, unknown>;
  const cursor = (source.cursor ?? {}) as Record<string, unknown>;

  const effect = AMBIENT_EFFECT_KEYS.includes(ambient.effect as AmbientEffectKey)
    ? (ambient.effect as AmbientEffectKey)
    : DEFAULT_EFFECTS.ambient.effect;
  const trail = CURSOR_TRAIL_KEYS.includes(cursor.trail as CursorTrailKey)
    ? (cursor.trail as CursorTrailKey)
    : DEFAULT_EFFECTS.cursor.trail;
  const intensity =
    typeof ambient.intensity === "number" && Number.isFinite(ambient.intensity)
      ? Math.min(5, Math.max(1, Math.round(ambient.intensity)))
      : DEFAULT_EFFECTS.ambient.intensity;

  const color = (value: unknown, fallback: string): string =>
    typeof value === "string" && isValidThemeColor(value) ? value.trim() : fallback;

  return {
    ambient: {
      effect,
      color: color(ambient.color, DEFAULT_EFFECTS.ambient.color),
      intensity,
    },
    cursor: {
      trail,
      color: color(cursor.color, DEFAULT_EFFECTS.cursor.color),
      hideNativeCursor:
        typeof cursor.hideNativeCursor === "boolean"
          ? cursor.hideNativeCursor
          : DEFAULT_EFFECTS.cursor.hideNativeCursor,
    },
  };
}

const ThemeContext = createContext<StorefrontTheme>(DEFAULT_THEME);

export function ThemeProvider({
  theme,
  children,
}: {
  theme: StorefrontTheme;
  children: ReactNode;
}) {
  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export function useTheme(): StorefrontTheme {
  return useContext(ThemeContext);
}

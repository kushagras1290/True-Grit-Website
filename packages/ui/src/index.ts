/** Shared UI helpers for True Grit frontends. */

/** Join conditional class names, dropping falsy values. */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export type ThemeKey = "forest" | "sage" | "terracotta" | "charcoal" | "gold";

/** Applied when a category carries no theme, or one this build does not know. */
export const DEFAULT_THEME_KEY: ThemeKey = "forest";

const THEME_VARS: Record<ThemeKey, Record<string, string>> = {
  forest: {
    "--theme-bg": "var(--color-brand-primary)",
    "--theme-fg": "var(--color-text-inverse)",
  },
  sage: {
    "--theme-bg": "var(--color-bg-subtle)",
    "--theme-fg": "var(--color-text-primary)",
  },
  terracotta: {
    "--theme-bg": "var(--color-brand-accent)",
    "--theme-fg": "var(--color-text-inverse)",
  },
  charcoal: {
    "--theme-bg": "var(--color-bg-inverse)",
    "--theme-fg": "var(--color-text-inverse)",
  },
  gold: {
    "--theme-bg": "var(--color-brand-gold)",
    "--theme-fg": "var(--color-text-inverse)",
  },
};

/**
 * Map a category theme key to its background/foreground CSS custom property pair.
 *
 * Accepts an arbitrary string because the value comes from an editor-managed
 * database column, not from this build's type union: an unrecognised key falls
 * back to the default theme instead of returning nothing. Returning `undefined`
 * would leave `--theme-bg` unset and render the surface completely unstyled.
 */
export function themeVars(theme: string | null | undefined): Record<string, string> {
  if (theme && theme in THEME_VARS) return THEME_VARS[theme as ThemeKey];
  return THEME_VARS[DEFAULT_THEME_KEY];
}

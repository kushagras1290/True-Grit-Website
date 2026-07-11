/** Shared UI helpers for True Grit frontends. */

/** Join conditional class names, dropping falsy values. */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export type ThemeKey = "forest" | "sage" | "terracotta" | "charcoal";

/** Map a category theme key to its background/foreground CSS custom property pair. */
export function themeVars(theme: ThemeKey): Record<string, string> {
  switch (theme) {
    case "forest":
      return { "--theme-bg": "var(--color-brand-primary)", "--theme-fg": "var(--color-text-inverse)" };
    case "sage":
      return { "--theme-bg": "var(--color-bg-subtle)", "--theme-fg": "var(--color-text-primary)" };
    case "terracotta":
      return { "--theme-bg": "var(--color-brand-accent)", "--theme-fg": "var(--color-text-inverse)" };
    case "charcoal":
      return { "--theme-bg": "var(--color-bg-inverse)", "--theme-fg": "var(--color-text-inverse)" };
  }
}

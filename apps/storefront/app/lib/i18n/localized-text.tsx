/**
 * Source-text localization for storefront-owned copy.
 *
 * The catalogue is keyed by English source text rather than by symbolic keys,
 * so a component translates by handing over the words it would otherwise
 * render. Anything with no catalogue entry — CMS bodies, catalogue names,
 * customer-authored text — falls through unchanged, which is what makes it safe
 * to apply these helpers indiscriminately.
 */

import { useCallback, type ReactNode } from "react";

import { useLocaleContext } from "./context";
import { EN_MESSAGES, translate, type MessageKey, type ResolvedMessages } from "./messages";

const SOURCE_TO_KEY = new Map<string, MessageKey>(
  Object.entries(EN_MESSAGES).map(([key, source]) => [source, key as MessageKey]),
);

export type FormatValues = Readonly<Record<string, string | number>>;

export function translateSource(messages: ResolvedMessages, source: string): string {
  const key = SOURCE_TO_KEY.get(source);
  return key ? translate(messages, key) : source;
}

/**
 * Substitute `{placeholder}` values into an already-translated template.
 *
 * Unsupplied placeholders are left verbatim, matching `translate()`: a visible
 * `{count}` is diagnosable, whereas silently emptying it hides the bug.
 */
function interpolate(template: string, values: FormatValues): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match,
  );
}

export function formatSource(
  messages: ResolvedMessages,
  source: string,
  values: FormatValues,
): string {
  return interpolate(translateSource(messages, source), values);
}

/** Translate storefront-owned copy by its English source text.
 *
 * This is intended for literal UI copy. CMS and catalogue values are already
 * localized by the API and simply fall through unchanged when no source entry
 * exists. Keeping this as a React component lets simple JSX text participate
 * in i18n without turning every short label into a bespoke component hook.
 */
export function LocalizedText({ children }: { children: ReactNode }) {
  const { messages } = useLocaleContext();
  if (typeof children !== "string") return children;
  return translateSource(messages, children);
}

/** Localize string-valued props such as headings, placeholders and aria labels. */
export function useLocalizeText(): (source: string) => string {
  const { messages } = useLocaleContext();
  return useCallback((source: string) => translateSource(messages, source), [messages]);
}

/**
 * Localize copy that interpolates a runtime value.
 *
 * Template literals cannot be translated after the fact — `Reviews for Mangoes`
 * is not a catalogue entry and never will be. The source string keeps the
 * placeholder (`"Reviews for {product}"`), which *is* a catalogue entry, and
 * the value is substituted after translation. The catalogue generator shields
 * `{name}` spans from the machine translator for exactly this reason, so
 * placeholders survive into every language.
 *
 * ```tsx
 * const format = useLocalizeFormat();
 * <h2>{format("Reviews for {product}", { product: product.name })}</h2>
 * ```
 */
export function useLocalizeFormat(): (source: string, values: FormatValues) => string {
  const { messages } = useLocaleContext();
  return useCallback(
    (source: string, values: FormatValues) => formatSource(messages, source, values),
    [messages],
  );
}

/**
 * Pick a singular or plural source string, then translate it.
 *
 * The storefront used to render `{count} <LocalizedText>product</LocalizedText>
 * {count === 1 ? "" : "s"}` — an English "s" glued onto a translated noun,
 * which produces "5 उत्पाद s" in Hindi and its equivalent in every other
 * language. Translating two complete phrases instead means each language gets
 * whole, grammatical words.
 *
 * The *selection* between the two follows English rules (one vs. not-one),
 * because English is the source language and both forms must exist in the
 * source catalogue to be translated at all. Languages with richer plural
 * categories therefore get the "other" form for every count above one, which is
 * correct far more often than a bolted-on "s" ever was, but is not full CLDR
 * pluralisation — that would need per-locale plural forms the machine
 * translation pipeline cannot reliably produce.
 *
 * ```tsx
 * const plural = useLocalizePlural();
 * <p>{plural("{count} product", "{count} products", total, { count: total })}</p>
 * ```
 */
export function useLocalizePlural(): (
  one: string,
  other: string,
  count: number,
  values?: FormatValues,
) => string {
  const { messages } = useLocaleContext();
  return useCallback(
    (one: string, other: string, count: number, values?: FormatValues) =>
      formatSource(messages, count === 1 ? one : other, values ?? { count }),
    [messages],
  );
}

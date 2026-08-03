import { useCallback, type ReactNode } from "react";

import { useLocaleContext } from "./context";
import { EN_MESSAGES, translate, type MessageKey, type ResolvedMessages } from "./messages";

const SOURCE_TO_KEY = new Map<string, MessageKey>(
  Object.entries(EN_MESSAGES).map(([key, source]) => [source, key as MessageKey]),
);

export function translateSource(messages: ResolvedMessages, source: string): string {
  const key = SOURCE_TO_KEY.get(source);
  return key ? translate(messages, key) : source;
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

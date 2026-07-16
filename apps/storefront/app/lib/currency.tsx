/**
 * Display-currency conversion by visitor country.
 *
 * Catalogue prices are stored and charged in INR minor units (paise). For
 * international visitors we *display* an approximate local-currency price so
 * the number is meaningful at a glance.
 *
 * The rates below are rough, hand-maintained snapshots (INR -> unit of target
 * currency) intended for display only — a live currency-conversion service
 * will replace this table. Checkout always states the INR amount actually
 * charged.
 */

import { formatMoney } from "@truegrit/contracts";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

export interface DisplayCurrency {
  /** ISO 4217 code, e.g. "USD". */
  code: string;
  /** BCP 47 locale used to format the amount, e.g. "en-US". */
  locale: string;
  /** Approximate value of 1 INR in this currency. 1 for INR itself. */
  ratePerInr: number;
}

export const INR: DisplayCurrency = { code: "INR", locale: "en-IN", ratePerInr: 1 };

// Approximate mid-2026 rates. Display only — replace with a live converter.
// Locales stay English-based so numbers match the (English) storefront copy;
// Intl still applies each currency's own symbol and decimal conventions.
const CURRENCIES: Record<string, DisplayCurrency> = {
  USD: { code: "USD", locale: "en-US", ratePerInr: 0.0115 },
  EUR: { code: "EUR", locale: "en-IE", ratePerInr: 0.0105 },
  GBP: { code: "GBP", locale: "en-GB", ratePerInr: 0.009 },
  AED: { code: "AED", locale: "en-AE", ratePerInr: 0.042 },
  SAR: { code: "SAR", locale: "en-SA", ratePerInr: 0.043 },
  QAR: { code: "QAR", locale: "en-QA", ratePerInr: 0.042 },
  KWD: { code: "KWD", locale: "en-KW", ratePerInr: 0.0035 },
  BHD: { code: "BHD", locale: "en-BH", ratePerInr: 0.0043 },
  OMR: { code: "OMR", locale: "en-OM", ratePerInr: 0.0044 },
  SGD: { code: "SGD", locale: "en-SG", ratePerInr: 0.015 },
  MYR: { code: "MYR", locale: "en-MY", ratePerInr: 0.049 },
  THB: { code: "THB", locale: "en-TH", ratePerInr: 0.37 },
  JPY: { code: "JPY", locale: "en-JP", ratePerInr: 1.7 },
  KRW: { code: "KRW", locale: "en-KR", ratePerInr: 15.5 },
  CNY: { code: "CNY", locale: "en-CN", ratePerInr: 0.081 },
  HKD: { code: "HKD", locale: "en-HK", ratePerInr: 0.09 },
  AUD: { code: "AUD", locale: "en-AU", ratePerInr: 0.017 },
  NZD: { code: "NZD", locale: "en-NZ", ratePerInr: 0.0185 },
  CAD: { code: "CAD", locale: "en-CA", ratePerInr: 0.0155 },
  CHF: { code: "CHF", locale: "en-CH", ratePerInr: 0.0092 },
  SEK: { code: "SEK", locale: "en-SE", ratePerInr: 0.11 },
  NOK: { code: "NOK", locale: "en-NO", ratePerInr: 0.115 },
  DKK: { code: "DKK", locale: "en-DK", ratePerInr: 0.078 },
  ZAR: { code: "ZAR", locale: "en-ZA", ratePerInr: 0.2 },
  LKR: { code: "LKR", locale: "en-LK", ratePerInr: 3.4 },
  BDT: { code: "BDT", locale: "en-BD", ratePerInr: 1.35 },
  NPR: { code: "NPR", locale: "en-NP", ratePerInr: 1.6 },
  IDR: { code: "IDR", locale: "en-ID", ratePerInr: 180 },
  PHP: { code: "PHP", locale: "en-PH", ratePerInr: 0.65 },
  VND: { code: "VND", locale: "en-VN", ratePerInr: 290 },
  BRL: { code: "BRL", locale: "en-BR", ratePerInr: 0.062 },
  MXN: { code: "MXN", locale: "en-MX", ratePerInr: 0.21 },
  TRY: { code: "TRY", locale: "en-TR", ratePerInr: 0.45 },
  ILS: { code: "ILS", locale: "en-IL", ratePerInr: 0.038 },
  EGP: { code: "EGP", locale: "en-EG", ratePerInr: 0.55 },
  KES: { code: "KES", locale: "en-KE", ratePerInr: 1.45 },
  NGN: { code: "NGN", locale: "en-NG", ratePerInr: 17.5 },
};

const EUROZONE = [
  "AT",
  "BE",
  "HR",
  "CY",
  "EE",
  "FI",
  "FR",
  "DE",
  "GR",
  "IE",
  "IT",
  "LV",
  "LT",
  "LU",
  "MT",
  "NL",
  "PT",
  "SK",
  "SI",
  "ES",
];

const COUNTRY_TO_CURRENCY: Record<string, string> = {
  IN: "INR",
  US: "USD",
  GB: "GBP",
  AE: "AED",
  SA: "SAR",
  QA: "QAR",
  KW: "KWD",
  BH: "BHD",
  OM: "OMR",
  SG: "SGD",
  MY: "MYR",
  TH: "THB",
  JP: "JPY",
  KR: "KRW",
  CN: "CNY",
  HK: "HKD",
  AU: "AUD",
  NZ: "NZD",
  CA: "CAD",
  CH: "CHF",
  SE: "SEK",
  NO: "NOK",
  DK: "DKK",
  ZA: "ZAR",
  LK: "LKR",
  BD: "BDT",
  NP: "NPR",
  ID: "IDR",
  PH: "PHP",
  VN: "VND",
  BR: "BRL",
  MX: "MXN",
  TR: "TRY",
  IL: "ILS",
  EG: "EGP",
  KE: "KES",
  NG: "NGN",
  ...Object.fromEntries(EUROZONE.map((country) => [country, "EUR"])),
};

/** The display currency for a visitor country; INR for India and any country
 * we do not have a rough rate for. */
export function currencyForCountry(country: string): DisplayCurrency {
  const code = COUNTRY_TO_CURRENCY[country.toUpperCase()];
  if (!code || code === "INR") return INR;
  return CURRENCIES[code] ?? INR;
}

/** Format INR minor units in the given display currency. INR keeps the exact
 * catalogue formatting; other currencies show an approximate converted price
 * with the currency's own decimal conventions (Intl handles JPY vs USD). */
export function formatDisplayMoney(amountMinorInr: number, currency: DisplayCurrency): string {
  if (currency.code === "INR") return formatMoney(amountMinorInr);
  const value = (amountMinorInr / 100) * currency.ratePerInr;
  return new Intl.NumberFormat(currency.locale, {
    style: "currency",
    currency: currency.code,
  }).format(value);
}

const CurrencyContext = createContext<DisplayCurrency>(INR);

export function CurrencyProvider({ country, children }: { country: string; children: ReactNode }) {
  const currency = useMemo(() => currencyForCountry(country), [country]);
  return <CurrencyContext.Provider value={currency}>{children}</CurrencyContext.Provider>;
}

export function useDisplayCurrency(): DisplayCurrency {
  return useContext(CurrencyContext);
}

/** A formatter for INR minor units in the visitor's display currency. */
export function usePriceFormatter(): (amountMinorInr: number) => string {
  const currency = useDisplayCurrency();
  return useCallback(
    (amountMinorInr: number) => formatDisplayMoney(amountMinorInr, currency),
    [currency],
  );
}

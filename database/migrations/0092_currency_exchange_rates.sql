-- 0092_currency_exchange_rates: operator-managed display conversion values.
--
-- Catalogue and checkout amounts remain canonical INR minor units.  These
-- rates only control the visitor-facing approximate local-currency display,
-- so changing a rate can never rewrite a product, cart, order, refund or
-- payout.  Rates are integer micros (1 INR * 1,000,000) to avoid storing
-- money-critical configuration as a binary float.
PRAGMA foreign_keys = ON;

CREATE TABLE currency_exchange_rates (
  currency_code TEXT PRIMARY KEY CHECK (
    length(currency_code) = 3 AND currency_code = upper(currency_code)
  ),
  locale TEXT NOT NULL,
  rate_micros INTEGER NOT NULL CHECK (rate_micros > 0),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
);

INSERT INTO currency_exchange_rates
  (currency_code, locale, rate_micros, active, updated_at, updated_by)
VALUES
  ('INR', 'en-IN', 1000000, 1, '2026-08-08T00:00:00Z', NULL),
  ('USD', 'en-US',   11500, 1, '2026-08-08T00:00:00Z', NULL),
  ('EUR', 'en-IE',   10500, 1, '2026-08-08T00:00:00Z', NULL),
  ('GBP', 'en-GB',    9000, 1, '2026-08-08T00:00:00Z', NULL),
  ('AED', 'en-AE',   42000, 1, '2026-08-08T00:00:00Z', NULL),
  ('SAR', 'en-SA',   43000, 1, '2026-08-08T00:00:00Z', NULL),
  ('QAR', 'en-QA',   42000, 1, '2026-08-08T00:00:00Z', NULL),
  ('KWD', 'en-KW',    3500, 1, '2026-08-08T00:00:00Z', NULL),
  ('BHD', 'en-BH',    4300, 1, '2026-08-08T00:00:00Z', NULL),
  ('OMR', 'en-OM',    4400, 1, '2026-08-08T00:00:00Z', NULL),
  ('SGD', 'en-SG',   15000, 1, '2026-08-08T00:00:00Z', NULL),
  ('MYR', 'en-MY',   49000, 1, '2026-08-08T00:00:00Z', NULL),
  ('THB', 'en-TH',  370000, 1, '2026-08-08T00:00:00Z', NULL),
  ('JPY', 'en-JP', 1700000, 1, '2026-08-08T00:00:00Z', NULL),
  ('KRW', 'en-KR',15500000, 1, '2026-08-08T00:00:00Z', NULL),
  ('CNY', 'en-CN',   81000, 1, '2026-08-08T00:00:00Z', NULL),
  ('HKD', 'en-HK',   90000, 1, '2026-08-08T00:00:00Z', NULL),
  ('AUD', 'en-AU',   17000, 1, '2026-08-08T00:00:00Z', NULL),
  ('NZD', 'en-NZ',   18500, 1, '2026-08-08T00:00:00Z', NULL),
  ('CAD', 'en-CA',   15500, 1, '2026-08-08T00:00:00Z', NULL),
  ('CHF', 'en-CH',    9200, 1, '2026-08-08T00:00:00Z', NULL),
  ('SEK', 'en-SE',  110000, 1, '2026-08-08T00:00:00Z', NULL),
  ('NOK', 'en-NO',  115000, 1, '2026-08-08T00:00:00Z', NULL),
  ('DKK', 'en-DK',   78000, 1, '2026-08-08T00:00:00Z', NULL),
  ('ZAR', 'en-ZA',  200000, 1, '2026-08-08T00:00:00Z', NULL),
  ('LKR', 'en-LK', 3400000, 1, '2026-08-08T00:00:00Z', NULL),
  ('BDT', 'en-BD', 1350000, 1, '2026-08-08T00:00:00Z', NULL),
  ('NPR', 'en-NP', 1600000, 1, '2026-08-08T00:00:00Z', NULL),
  ('IDR', 'en-ID',180000000,1, '2026-08-08T00:00:00Z', NULL),
  ('PHP', 'en-PH',  650000, 1, '2026-08-08T00:00:00Z', NULL),
  ('VND', 'en-VN',290000000,1, '2026-08-08T00:00:00Z', NULL),
  ('BRL', 'en-BR',   62000, 1, '2026-08-08T00:00:00Z', NULL),
  ('MXN', 'en-MX',  210000, 1, '2026-08-08T00:00:00Z', NULL),
  ('TRY', 'en-TR',  450000, 1, '2026-08-08T00:00:00Z', NULL),
  ('ILS', 'en-IL',   38000, 1, '2026-08-08T00:00:00Z', NULL),
  ('EGP', 'en-EG',  550000, 1, '2026-08-08T00:00:00Z', NULL),
  ('KES', 'en-KE', 1450000, 1, '2026-08-08T00:00:00Z', NULL),
  ('NGN', 'en-NG',17500000, 1, '2026-08-08T00:00:00Z', NULL);

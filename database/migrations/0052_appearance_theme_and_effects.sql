-- 0052_appearance_theme_and_effects: owner-editable colours and ambient
-- effects, per site, per page, and per visitor country.
--
-- WHY A TABLE AND NOT `app_settings`
-- The colour theme is not one value, it is one value *per scope*: the
-- site-wide palette, an override for `/shop`, an override for visitors in
-- Germany. That is a row per scope, and squeezing it into the flat key/value
-- store would mean synthesising keys like `theme./blog.brandPrimary` and
-- parsing scopes back out of them. Effects ride on the same row because they
-- are the same decision -- "what does this page look like" -- reached from
-- the same admin page.
--
-- SCOPE, AND THE THREE KINDS OF ROW
-- * 'global'        -- the site-wide baseline. Always exists.
-- * '/path'         -- a single page and everything beneath it, regardless of
--                      who is visiting. Wins over a country override for the
--                      same colour: an editorial page's intentional design is
--                      not something a geo experiment should silently undo.
-- * 'country:XX'     -- an ISO-3166 alpha-2 code, uppercase. Overrides the
--                      global palette (or the global effects) for visitors
--                      Cloudflare's edge resolves to that country -- the same
--                      signal `resolveCountry()` already uses for currency and
--                      catalogue release. "Diwali colours for visitors in
--                      India" or "no snow effect outside winter markets" are
--                      what this exists for.
-- The three prefixes can never collide (paths start with '/', country codes
-- are exactly two letters, 'global' is neither), so the CHECK enforces the
-- shape rather than trusting every future writer to remember it.
--
-- RESOLUTION (see `services/appearance.load_public_appearance`)
-- Colours: global, then the visitor's country override, then the page
-- override for the current path -- each layer replaces only the keys it sets.
-- Effects: the visitor's country override if one exists, else the global
-- default. Effects are not merged key-by-key like colours are: a "snowfall"
-- effect and a "no effect" default do not have a sensible in-between, so a
-- country override replaces the whole ambient+cursor configuration rather
-- than patching pieces of it.
--
-- SPARSE JSON, ON PURPOSE
-- `tokens_json` holds only the colours somebody actually changed for that
-- scope, and `effects_json` on a 'country:XX' row is empty unless that
-- country has its own override. A missing key means "keep the shipped value
-- (or the global effects)", so a half-written theme degrades to the stock
-- palette instead of a page of undefined colours, and adding a new token to
-- the design system does not require rewriting every stored row. The
-- storefront re-validates every value against a colour allow-list before it
-- reaches a stylesheet (`lib/theme.isValidThemeColor`) -- these strings are
-- interpolated into CSS, so the database is not treated as trusted input.
--
-- EFFECTS DEFAULT TO OFF
-- No row, or an unreadable one, resolves to no ambient effect and no cursor
-- trail. A storefront that started snowing because a column failed to parse
-- would be a worse failure than one that never snowed.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, and the insert is idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS theme_settings (
  scope       TEXT PRIMARY KEY
              CHECK (
                scope = 'global'
                OR scope LIKE '/%'
                -- `upper(scope) = scope` would demand the *whole* string be
                -- uppercase, which "country:IN" (lowercase prefix, uppercase
                -- code) never is -- substr() checks only the two-letter code
                -- after the fixed-case "country:" literal.
                OR (
                  scope LIKE 'country:__'
                  AND substr(scope, 9, 2) = upper(substr(scope, 9, 2))
                )
              ),
  tokens_json TEXT NOT NULL DEFAULT '{}',
  effects_json TEXT NOT NULL DEFAULT '{}',
  updated_at  TEXT NOT NULL,
  updated_by  TEXT REFERENCES users(id) ON DELETE SET NULL
);

-- The global row always exists so the admin console has something to load and
-- the API never has to distinguish "no theme" from "theme not yet created".
-- Empty objects mean the shipped palette and no effects.
INSERT OR IGNORE INTO theme_settings (scope, tokens_json, effects_json, updated_at) VALUES
  ('global', '{}', '{}', '2026-08-01T00:00:00Z');

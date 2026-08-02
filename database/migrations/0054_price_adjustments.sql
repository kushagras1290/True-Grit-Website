-- 0054_price_adjustments: a signed percentage markup/discount, scopable by
-- country, by a single product, by a whole category, or combined with
-- country -- most-specific-wins.
--
-- `percent` is signed: positive raises the real price a customer pays (a
-- genuine markup, e.g. for cost or positioning), negative genuinely reduces
-- it (a real discount off the real list price). This is deliberately NOT a
-- "was/now" fake-anchor mechanic -- there is exactly one real price, this
-- table adjusts it, and the storefront only ever shows a struck-through
-- "original" price alongside a genuine (negative) discount, never to dress up
-- a markup as if something had been discounted from it. See
-- `services/price_adjustments.py` for resolution and rendering rules.
--
-- `scope` mirrors the `'global'` / ISO-3166 alpha-2 sentinel already used by
-- `announcements.country` and `homepage_country_overrides.country`.
--
-- `product_id` and `category_id` are mutually exclusive "what does this rule
-- target" selectors (enforced by the CHECK below): a real product id narrows
-- the rule to just that product; a real category id narrows it to every
-- product in that category; both NULL means "every product" for that scope.
-- Resolution priority (most to least specific), see `resolve_adjustments`:
-- scope+product > global+product > scope+category > global+category >
-- scope-only > global-only. A product cannot also be individually targeted
-- *and* covered by a category rule in the same tier -- product always wins.
--
-- All three dimensions (scope, product, category) are optional, so
-- uniqueness can't be a plain composite primary key the way
-- `homepage_country_overrides(country, block_id)` is -- two rows with
-- `product_id = NULL, category_id = NULL` for the same scope would not
-- collide on a raw UNIQUE(scope, product_id, category_id), since SQL treats
-- every NULL as distinct. `COALESCE(..., '')` closes that gap; no real
-- product or category id can ever be an empty string (`new_id()` always
-- prefixes and never emits '').
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT.
PRAGMA foreign_keys = ON;

CREATE TABLE price_adjustments (
  id          TEXT PRIMARY KEY,
  scope       TEXT NOT NULL DEFAULT 'global'
              CHECK (
                scope = 'global'
                OR (length(scope) = 2 AND substr(scope, 1, 2) = upper(substr(scope, 1, 2)))
              ),
  product_id  TEXT REFERENCES products(id) ON DELETE CASCADE,
  category_id TEXT REFERENCES categories(id) ON DELETE CASCADE,
  -- -90..500: never lets a discount push a positive list price to zero or
  -- below, and caps a markup at 6x -- a sane ceiling on what this admin
  -- surface alone can do to a price without a second, deliberate change.
  percent     INTEGER NOT NULL CHECK (percent BETWEEN -90 AND 500),
  active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at  TEXT NOT NULL,
  created_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
  updated_at  TEXT NOT NULL,
  updated_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
  CHECK (product_id IS NULL OR category_id IS NULL)
);

CREATE UNIQUE INDEX idx_price_adjustments_scope_target
  ON price_adjustments(scope, COALESCE(product_id, ''), COALESCE(category_id, ''));

-- Supports "delete every rule for this product/category" when either is
-- removed (belt-and-braces alongside the ON DELETE CASCADE above) and the
-- admin console's per-product / per-category rule lookup.
CREATE INDEX idx_price_adjustments_product ON price_adjustments(product_id);
CREATE INDEX idx_price_adjustments_category ON price_adjustments(category_id);

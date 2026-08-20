-- 0115_price_tiers: country pricing-bracket management on top of the
-- existing `price_adjustments` engine.
--
-- A bracket is a convenience manager for a batch of global-scope,
-- no-product, no-category `price_adjustments` rows -- the existing
-- "scope-only" resolution tier (least specific), so a manual per-product or
-- per-category rule added later on the Sale & Discounts page still overrides
-- a bracket for that one case. Checkout and the storefront read
-- `price_adjustments` exactly as before; this migration adds no new pricing
-- logic anywhere, only a tagging column so bracket-driven rows are
-- identifiable and safely cleanable.
PRAGMA foreign_keys = ON;

CREATE TABLE price_tier_brackets (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  -- Same bound as price_adjustments.percent -- never lets a bracket push a
  -- positive list price to zero or below, and caps a markup at 6x.
  percent INTEGER NOT NULL CHECK (percent BETWEEN -90 AND 500),
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT REFERENCES users(id) ON DELETE SET NULL
);

-- One bracket per country: reassigning a country is an UPDATE of this row,
-- not a second row, so "which bracket is X in" is never ambiguous.
CREATE TABLE price_tier_countries (
  country_code TEXT PRIMARY KEY CHECK (
    length(country_code) = 2 AND country_code = upper(country_code)
  ),
  bracket_id TEXT NOT NULL REFERENCES price_tier_brackets(id) ON DELETE CASCADE,
  assigned_at TEXT NOT NULL,
  assigned_by TEXT REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_price_tier_countries_bracket ON price_tier_countries(bracket_id);

-- Tags a price_adjustments row as bracket-managed. ON DELETE CASCADE (not
-- SET NULL): a bracket-driven global country markup has no meaning without
-- its bracket, so deleting the bracket removes the rule instead of leaving
-- an orphaned, untagged, still-active global rule behind silently.
ALTER TABLE price_adjustments ADD COLUMN bracket_id TEXT
  REFERENCES price_tier_brackets(id) ON DELETE CASCADE;

CREATE INDEX idx_price_adjustments_bracket ON price_adjustments(bracket_id);

-- Three starter brackets at the requested percentages. Deliberately no
-- country assignments: which real countries count as "tier 1/2/3" is a
-- business call for the admin to make in the UI, not something to guess at
-- and bake into a migration.
INSERT INTO price_tier_brackets (id, label, percent, sort_order, created_at, updated_at) VALUES
  ('ptier_1', 'Tier 1', 100, 0, '2026-08-20T00:00:00Z', '2026-08-20T00:00:00Z'),
  ('ptier_2', 'Tier 2', 75, 1, '2026-08-20T00:00:00Z', '2026-08-20T00:00:00Z'),
  ('ptier_3', 'Tier 3', 50, 2, '2026-08-20T00:00:00Z', '2026-08-20T00:00:00Z');

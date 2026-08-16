-- 0104_recipe_cuisine: give each recipe its own cuisine instead of assuming one.
--
-- `recipeCuisine` is one of the fields Google's Recipes report asks for, and
-- the storefront was filling it from a hard-coded "Indian" constant. That was
-- accurate only for as long as all 48 recipes were Indian preparations. The
-- moment a recipe targets a non-Indian search market, a site-wide constant
-- starts publishing a false claim in structured data, which is exactly the kind
-- of thing that earns a manual action.
--
-- Existing rows are backfilled to 'Indian' because that is what every published
-- recipe currently is -- verified against all 48 slugs in the live sitemap on
-- 2026-08-16, from aloo-fry-in-mustard-oil through whole-wheat-pasta. New
-- recipes must state their own.
--
-- Nullable rather than NOT NULL DEFAULT: an unset cuisine should omit the
-- structured-data field, not silently assert a wrong one. The storefront treats
-- NULL as "say nothing".
PRAGMA foreign_keys = ON;

ALTER TABLE recipes ADD COLUMN cuisine TEXT;

UPDATE recipes SET cuisine = 'Indian' WHERE cuisine IS NULL;

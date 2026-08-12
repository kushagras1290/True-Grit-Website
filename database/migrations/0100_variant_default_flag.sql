-- 0100_variant_default_flag: explicit default variant per product.
--
-- Every reader of a product's variant list (the product editor's General
-- tab SKU/price fields, the products list SKU column, the storefront
-- product page's initial selection) has always just taken `variants[0]`
-- from a list ordered `ORDER BY sort_order, name` -- and since no code path
-- ever set `sort_order` above its default of 0, that was really "whichever
-- variant sorts first alphabetically by name", with no way for an operator
-- to see or change which one that was. This makes the choice explicit and
-- operator-controlled instead of an accident of naming.
PRAGMA foreign_keys = ON;

ALTER TABLE product_variants ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0
  CHECK (is_default IN (0, 1));

-- Backfill: mark whichever variant every reader already treated as "the"
-- variant (lowest sort_order, then name, then id as a final deterministic
-- tiebreak) as the explicit default, so this migration changes no
-- product's displayed price/SKU on its own -- only future edits can.
UPDATE product_variants
SET is_default = 1
WHERE id = (
  SELECT v2.id
  FROM product_variants v2
  WHERE v2.product_id = product_variants.product_id
  ORDER BY v2.sort_order, v2.name, v2.id
  LIMIT 1
);

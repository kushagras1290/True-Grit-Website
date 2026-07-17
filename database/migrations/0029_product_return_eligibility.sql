-- 0029_product_return_eligibility: owner-controlled per-product return
-- eligibility. Defaults to eligible (1) — most organic pantry/dry goods can
-- be returned; the owner unchecks it for genuinely non-returnable items
-- (e.g. certain fresh perishables) from the product editor.
PRAGMA foreign_keys = ON;

ALTER TABLE products ADD COLUMN return_eligible INTEGER NOT NULL DEFAULT 1
  CHECK (return_eligible IN (0, 1));

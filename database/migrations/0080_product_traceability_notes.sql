-- 0080_product_traceability_notes: real, admin-editable data behind the
-- product-detail "traceability" fields that have existed in the contract
-- and been rendered on the storefront product page since day one, but were
-- always hardcoded to "" in the backend (repositories/catalogue.py) because
-- no products column ever backed them.
--
-- Free text, not a structured date: `harvest_note` matches how the contract
-- already types it (a plain string, not a date type), and free text is a
-- strict superset -- an admin who just wants a date can type one, but this
-- also covers "harvested the week of 3 March 2026" or "picked to order",
-- which a rigid date column could not express for a small-farm marketplace.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, plain
-- ALTER TABLE ADD COLUMN (idempotent in spirit -- D1/SQLite has no
-- IF NOT EXISTS for columns, matching every other ALTER TABLE ADD COLUMN
-- migration in this codebase).
ALTER TABLE products ADD COLUMN harvest_note TEXT;
ALTER TABLE products ADD COLUMN growing_method TEXT;
ALTER TABLE products ADD COLUMN storage_guidance TEXT;

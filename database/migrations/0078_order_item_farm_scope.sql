-- 0078_order_item_farm_scope: denormalizes the owning farm onto order_items
-- so orders can finally be scoped to the farm-owner sub-admin they belong
-- to -- `list_orders`/`get_order_detail`/`search_orders`/
-- `update_order_status`/`issue_refund` have never filtered by
-- `principal.farm_id`, even though `database/seeds/development.sql`
-- documents that `orders.view` on the farm_owner role is meant to mean
-- "orders for my farm," not every order in the marketplace.
--
-- WHY A DENORMALIZED COLUMN, NOT A LIVE JOIN TO products.farm_id
-- order_items already snapshots product_name/variant_name/sku at order time
-- rather than joining products live, specifically so a later catalogue edit
-- can never rewrite what an existing order's history says. products.farm_id
-- is nullable and ON DELETE SET NULL, so a live join would let a product
-- being reassigned to another farm (or deleted) silently change which farm
-- an already-placed order is attributed to. Snapshotting at insert time
-- avoids that the same way the other columns on this table already do.
--
-- BACKFILL CAVEAT
-- Existing rows had no farm_id captured at order time, so the backfill below
-- is best-effort: it reads products.farm_id as it stands today, which may
-- not match what was true when the order was placed if a product changed
-- farms or was deleted since. This is unavoidable -- the information was
-- never recorded -- and only affects historical orders; every order placed
-- after this migration gets a permanent, accurate snapshot.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every
-- statement idempotent to rerun.
PRAGMA foreign_keys = ON;

ALTER TABLE order_items ADD COLUMN farm_id TEXT REFERENCES farms(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_order_items_farm ON order_items(farm_id);

UPDATE order_items
SET farm_id = (SELECT p.farm_id FROM products p WHERE p.id = order_items.product_id)
WHERE product_id IS NOT NULL
  AND farm_id IS NULL;

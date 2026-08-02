-- 0060_coupons_and_promotions: activate the dormant promotions/coupons schema
-- from 0005_commerce.sql, add the marketing copy columns checkout needs, wire
-- RBAC, and give the homepage its "what's on offer" banner.
--
-- WHY THIS EXTENDS 0005 RATHER THAN CREATING NEW TABLES
-- `promotions`, `promotion_rules`, `promotion_actions`, `coupons` and
-- `coupon_redemptions` shipped in 0005_commerce.sql on day one and have been
-- completely dormant since -- no repository, service, route or UI has ever
-- touched them (confirmed by repo-wide search). The schema is already
-- correctly normalised for this feature: `promotions` is the campaign,
-- `coupons` are named codes against it (a promotion with none is an
-- automatic, no-code discount; one with codes only applies when a customer
-- enters one), `promotion_actions` is the discount math, and
-- `coupon_redemptions` is the usage ledger. This migration activates it
-- exactly the way 0057 activated `reviews`, rather than redesigning it.
--
-- WHY headline/description ARE NEW COLUMNS HERE
-- The homepage banner and the checkout box show the same promotion copy, but
-- checkout is a hardcoded route, not a CMS page -- it cannot pull text from a
-- page-block's `props` the way the homepage banner can. Marketing copy
-- therefore has to live on the promotion itself, the one place both surfaces
-- can read it from.
--
-- WHY THE SWITCH IS OFF BY DEFAULT
-- Unlike `commerce.payments.enabled` (core functionality, defaults on),
-- promotions are an optional marketing feature nobody has configured yet on
-- a fresh install. Shipping it on with zero promotions configured would be
-- harmless (nothing to show), but shipping it off matches the operator's own
-- framing: a tickbox they deliberately switch on once they have an offer
-- ready, not a feature that's silently already live.
--
-- WHY THE HOMEPAGE BLOCK SHIPS ENABLED ANYWAY
-- `promotion_banner` resolves live on every render, the same as
-- `reviews_showcase` and `product_collection` in rule mode: with the
-- sitewide switch off, or no active promotion, the public endpoint returns
-- nothing and the block renders nothing (see `services.promotions` and
-- `components/blocks.tsx`). The sitewide switch is therefore the one real
-- control -- flipping it is what makes the banner appear, matching "once
-- enabled it will show" -- rather than needing the block *and* the switch
-- both remembered.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every insert
-- and update idempotent.
PRAGMA foreign_keys = ON;

ALTER TABLE promotions ADD COLUMN headline TEXT;
ALTER TABLE promotions ADD COLUMN description TEXT;

-- The "is there a currently-active promotion" and "resolve the best one"
-- reads both filter on status first.
CREATE INDEX IF NOT EXISTS idx_promotions_status_priority
  ON promotions(status, priority DESC);

CREATE INDEX IF NOT EXISTS idx_promotion_rules_promotion
  ON promotion_rules(promotion_id);

CREATE INDEX IF NOT EXISTS idx_promotion_actions_promotion
  ON promotion_actions(promotion_id);

CREATE INDEX IF NOT EXISTS idx_coupons_promotion
  ON coupons(promotion_id);

-- Usage-limit checks at checkout are COUNT(*) queries scoped by coupon
-- (total) and by coupon + customer (per-customer).
CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_coupon
  ON coupon_redemptions(coupon_id);

CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_coupon_customer
  ON coupon_redemptions(coupon_id, customer_user_id);

INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('commerce.promotions.enabled', '0', '2026-08-02T00:00:00Z');

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_promotions_view', 'promotions.view', 'View coupons and promotions'),
  ('prm_promotions_manage', 'promotions.manage', 'Create, edit, archive and issue coupons and promotions');

-- Owner, Admin and Manager -- a discount campaign is a commercial call with
-- real revenue impact, the same tier that governs revenue payouts and price
-- adjustments, and never a role scoped to one operational area.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('promotions.view', 'promotions.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('promotions.view', 'promotions.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('promotions.view', 'promotions.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

-- Homepage: the banner slot, directly under the hero (index 1, not appended).
-- NOTE: `json_insert(content_json, '$.blocks[1]', ...)` looks right but is a
-- silent no-op whenever index 1 is already occupied -- SQLite's json_insert
-- only writes to an array index that is genuinely absent (or `$.blocks[#]`,
-- the end). Splicing into the middle of an existing array instead requires
-- rebuilding it: peel off block 0, inject the new block as position 1, then
-- the rest shifted up, aggregated back into an array with json_group_array
-- over an ORDER BY subquery.
-- Idempotent via the same NOT EXISTS-on-type guard 0049/0057 use.
UPDATE page_versions
SET content_json = json_set(
  content_json,
  '$.blocks',
  (
    SELECT json_group_array(json(item))
    FROM (
      SELECT block.value AS item, block.key * 2 AS ord
      FROM json_each(page_versions.content_json, '$.blocks') AS block
      WHERE block.key = 0
      UNION ALL
      SELECT '{"id":"blk_promotion_banner","type":"promotion_banner","version":1,"enabled":true,"props":{"source":"rule"}}' AS item, 1 AS ord
      UNION ALL
      SELECT block.value AS item, block.key * 2 + 2 AS ord
      FROM json_each(page_versions.content_json, '$.blocks') AS block
      WHERE block.key >= 1
      ORDER BY ord
    )
  )
)
WHERE page_id = 'pag_home'
  AND NOT EXISTS (
    SELECT 1
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'promotion_banner'
  );

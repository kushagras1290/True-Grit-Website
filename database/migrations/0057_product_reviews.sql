-- 0057_product_reviews: verified-purchase product ratings and reviews, plus a
-- self-populating "what customers are saying" homepage section.
--
-- WHY THIS EXTENDS 0005 RATHER THAN CREATING A NEW TABLE
-- `reviews` shipped in 0005_commerce.sql on day one and has been dormant ever
-- since -- no repository, service, route or UI has ever touched it. Its shape
-- is already right for this feature (`status` pending/approved/rejected/removed,
-- a `UNIQUE(product_id, customer_user_id, order_id)` guard against duplicate
-- reviews of the same purchase), so this migration brings it in line with the
-- moderation columns every later content table carries (`updated_at`,
-- `moderation_reason`) rather than starting over.
--
-- WHY STATUS STARTS 'pending', NOT 'visible'
-- Discussions and content_comments moderate content that is already live --
-- moderation reacts to something a customer already saw. A review is different:
-- a 1-star rant should never reach a product page even for the seconds between
-- posting and a moderator seeing it, so a review is invisible until staff with
-- `reviews.moderate` approve it. This is the same pending-first posture as
-- `content_submissions` and `farm_partnership_requests`.
--
-- WHY A REVIEW REQUIRES AN ORDER
-- `order_id` was already nullable in 0005, but this feature requires it on
-- every write: `services.reviews.create_review` checks the calling customer
-- owns a completed order containing the product before it will insert a row.
-- "Anyone can review anything" invites exactly the kind of unverified noise a
-- traceable-food marketplace is trying not to be. The column stays nullable at
-- the schema level only because SQLite/D1 cannot add a NOT NULL column without
-- a full table rebuild; the constraint is enforced in the service instead.
--
-- WHY THE HOMEPAGE SECTION SHIPS ENABLED WITH ZERO REVIEWS
-- `reviews_showcase` in "rule" mode resolves live, the same as
-- `product_collection`/`category_collection` in rule mode: it always shows the
-- current top-rated approved reviews, never a stale snapshot. With no approved
-- reviews yet, it resolves to an empty set and the storefront renders nothing
-- for that section (the same graceful-empty behaviour category/product rows
-- already have) rather than shipping disabled and waiting for an operator to
-- remember to turn it on once reviews exist.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every insert and
-- update idempotent.
PRAGMA foreign_keys = ON;

ALTER TABLE reviews ADD COLUMN moderation_reason TEXT;
ALTER TABLE reviews ADD COLUMN updated_at TEXT NOT NULL DEFAULT '2026-08-02T00:00:00Z';

-- The admin moderation queue reads newest-first across every product; 0005
-- only indexed the per-product public read.
CREATE INDEX IF NOT EXISTS idx_reviews_status_created
  ON reviews(status, created_at DESC);

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_reviews_view', 'reviews.view', 'View product reviews and ratings'),
  ('prm_reviews_moderate', 'reviews.moderate', 'Approve, reject or remove product reviews');

-- Owner, Admin and Manager: reviews are commerce-adjacent (tied to orders and
-- products), so Order Manager / Product Manager territory, not the
-- content-moderation roles (Blogger, Chef) that police discussions/comments.
--
-- Guarded with EXISTS because, like every role these migrations touch besides
-- rol_manager (0013_users_roles_contact.sql), a role only exists once the dev
-- seed runs -- a deployed database with no matching role must not error here.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('reviews.view', 'reviews.moderate')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('reviews.view', 'reviews.moderate')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('reviews.view', 'reviews.moderate')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

-- Homepage: "What customers are saying", appended below the FAQ/standards
-- block and above the page-snippet directory -- social proof reads naturally
-- after the product picks and before the site-wide link list. Idempotent via
-- the same NOT EXISTS-on-type guard 0049 uses for page_links.
UPDATE page_versions
SET content_json = json_insert(
  content_json,
  '$.blocks[#]',
  json('{
    "id": "blk_reviews_showcase",
    "type": "reviews_showcase",
    "version": 1,
    "enabled": true,
    "props": {
      "heading": "What customers are saying",
      "subheading": "Real ratings from verified purchases.",
      "source": "rule",
      "reviewIds": [],
      "limit": 8,
      "minRating": 4
    }
  }')
)
WHERE page_id = 'pag_home'
  AND NOT EXISTS (
    SELECT 1
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'reviews_showcase'
  );

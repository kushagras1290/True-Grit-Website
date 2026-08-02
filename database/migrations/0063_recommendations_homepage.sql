-- 0063_recommendations_homepage: seed the `recommendations` block (real
-- bestsellers, computed live from `order_items` -- see
-- CatalogueRepository.list_bestsellers / list_also_bought,
-- domain/blocks.py RecommendationsBlock) onto the homepage by default.
--
-- WHY IT SHIPS ON THE HOMEPAGE ALREADY, RATHER THAN AS AN OPT-IN BLOCK
-- Recommendations need no configuration -- there is nothing for an operator
-- to curate or forget to set up, unlike a promotion or a manual product row.
-- Shipping it live out of the box is what makes the storefront read as
-- "recommending its own products" from day one; leaving it as an ADDABLE-only
-- block an operator has to discover and add would defeat that. It is still a
-- normal, addable/removable CMS block afterwards (see
-- ADDABLE_HOMEPAGE_SECTION_TYPES in api/admin.py) -- this migration only
-- decides the shipped default.
--
-- Appended at the end of the block list (a merchandising close, just before
-- the newsletter signup), the same NOT EXISTS-on-type idempotent guard
-- 0049/0057/0060 all use.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables.
PRAGMA foreign_keys = ON;

UPDATE page_versions
SET content_json = json_insert(
  content_json,
  '$.blocks[#]',
  json('{
    "id": "blk_recommendations",
    "type": "recommendations",
    "version": 1,
    "enabled": true,
    "props": {
      "heading": "Customer favourites",
      "subheading": "Picked by shoppers",
      "limit": 8
    }
  }')
)
WHERE page_id = 'pag_home'
  AND NOT EXISTS (
    SELECT 1
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'recommendations'
  );

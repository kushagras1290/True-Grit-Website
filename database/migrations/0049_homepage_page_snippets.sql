-- 0049_homepage_page_snippets: give the homepage a directory of the rest of
-- the site -- one short, human-written snippet per page -- so a first-time
-- customer can see what exists without opening the header menu.
--
-- WHY A BLOCK AND NOT A HARDCODED FOOTER
-- The snippets are marketing copy: they get reworded, reordered, switched off
-- for a campaign, and extended when a new page ships. Anything that changes on
-- that cadence belongs in `page_versions.content_json` where Homepage Settings
-- can edit it, not in a storefront component behind a deploy. `page_links` is
-- a registered block type (domain/blocks.py, @truegrit/contracts), so every
-- href goes through the same allow-list as every other block link and unknown
-- block types are still rejected on save (ADR-005).
--
-- PLACEMENT
-- Appended, which puts it below the standards FAQ and above the footer -- the
-- conventional spot for a site directory, and the one that does not push the
-- market itself further down the page. Homepage Settings can reorder it.
--
-- IDEMPOTENT
-- The NOT EXISTS guard means a re-run, or a database that already grew this
-- section by hand, is left alone rather than given a duplicate.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables.
PRAGMA foreign_keys = ON;

UPDATE page_versions
SET content_json = json_insert(
  content_json,
  '$.blocks[#]',
  json('{
    "id": "blk_page_links",
    "type": "page_links",
    "version": 1,
    "enabled": true,
    "props": {
      "heading": "Everything else on True Grit",
      "intro": "A one-line tour of the rest of the site, so you can find what you need without hunting through the menu.",
      "items": [
        {"label": "Shop the market", "description": "Every organic product we carry, filtered by food type, farm or price.", "href": "/shop", "enabled": true},
        {"label": "What is in season", "description": "The harvests running right now, so fruit and vegetables arrive at their best.", "href": "/seasonal", "enabled": true},
        {"label": "Our farms", "description": "The certified growers behind each lot, with their paperwork and methods.", "href": "/farms", "enabled": true},
        {"label": "Recipes", "description": "Straightforward cooking for the ingredients already in your basket.", "href": "/recipes", "enabled": true},
        {"label": "Journal", "description": "Practical guides to buying, storing and reading labels on organic food.", "href": "/blog", "enabled": true},
        {"label": "Community", "description": "Ask a question or compare notes with other customers and growers.", "href": "/community", "enabled": true},
        {"label": "Our standards", "description": "What certified, traceable and fairly traded actually mean here.", "href": "/standards", "enabled": true},
        {"label": "About True Grit", "description": "Why the market exists and how it is put together.", "href": "/about", "enabled": true},
        {"label": "Delivery", "description": "Dispatch days, packing, and what it costs to get an order to you.", "href": "/delivery", "enabled": true},
        {"label": "Returns and refunds", "description": "What to do when food arrives damaged, late or below standard.", "href": "/returns", "enabled": true},
        {"label": "Help", "description": "Answers to the questions our support team is asked most often.", "href": "/help", "enabled": true},
        {"label": "Contact us", "description": "Reach a person about an order, a farm, or anything else.", "href": "/contact", "enabled": true}
      ]
    }
  }')
)
WHERE page_id = 'pag_home'
  AND NOT EXISTS (
    SELECT 1
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'page_links'
  );

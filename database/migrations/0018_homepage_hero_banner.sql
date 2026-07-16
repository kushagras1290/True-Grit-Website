-- 0018_homepage_hero_banner: configure the storefront homepage hero image.
--
-- Keep this D1-safe: no BEGIN TRANSACTION or SAVEPOINT. The published home
-- page is seeded with the hero block first; site-control editing preserves that
-- shape.
UPDATE page_versions
SET content_json = json_set(
  content_json,
  '$.blocks[0].props.imageUrl', '/homepage-hero.png',
  '$.blocks[0].props.imageAlt', 'Organic mangoes held in a sunlit orchard'
)
WHERE id IN (
  SELECT p.published_version_id
  FROM pages p
  WHERE p.slug = 'home'
    AND p.archived_at IS NULL
    AND p.published_version_id IS NOT NULL
);

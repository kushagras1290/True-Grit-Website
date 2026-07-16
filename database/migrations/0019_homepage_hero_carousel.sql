-- 0019_homepage_hero_carousel: default clickable homepage hero slides.
--
-- No explicit transaction statements: Cloudflare D1 migrations reject BEGIN /
-- SAVEPOINT on this project.
UPDATE page_versions
SET content_json = json_set(
  content_json,
  '$.blocks[0].props.slides',
  json('[
    {
      "imageUrl": "/homepage-hero.png",
      "imageAlt": "Organic mangoes held in a sunlit orchard",
      "href": "/shop",
      "label": "Explore the market",
      "enabled": true
    },
    {
      "imageUrl": "/homepage-hero-tomatoes.png",
      "imageAlt": "Organic tomatoes harvested in a mountain field",
      "href": "/category/organic-vegetables",
      "label": "Shop vegetables",
      "enabled": true
    },
    {
      "imageUrl": "/homepage-hero-roots.png",
      "imageAlt": "Fresh carrots and beets pulled from organic soil",
      "href": "/category/organic-vegetables",
      "label": "Shop root vegetables",
      "enabled": true
    },
    {
      "imageUrl": "/homepage-hero-greens.png",
      "imageAlt": "Fresh leafy greens and herbs held in a farm field",
      "href": "/category/organic-vegetables",
      "label": "Shop fresh greens",
      "enabled": true
    },
    {
      "imageUrl": "/homepage-hero-citrus.png",
      "imageAlt": "Seasonal citrus and pears in an organic orchard",
      "href": "/seasonal",
      "label": "See seasonal fruit",
      "enabled": true
    }
  ]')
)
WHERE id IN (
  SELECT p.published_version_id
  FROM pages p
  WHERE p.slug = 'home'
    AND p.archived_at IS NULL
    AND p.published_version_id IS NOT NULL
);

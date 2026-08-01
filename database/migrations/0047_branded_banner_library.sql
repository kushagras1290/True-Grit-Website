-- 0047_branded_banner_library: configure the repository-backed branded banner
-- family for homepage campaigns, catalogue pages and editorial content.

PRAGMA foreign_keys = ON;

-- The database remains the source of truth for the homepage carousel. Images
-- are immutable versioned assets in the app, while labels and destinations can
-- still be changed from Site Control.
UPDATE page_versions
SET content_json = json_set(
  content_json,
  '$.blocks[' || (
    SELECT block.key
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'hero'
    LIMIT 1
  ) || '].props.imageUrl',
  '/banners/home/01-weekly-produce-reset.webp',
  '$.blocks[' || (
    SELECT block.key
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'hero'
    LIMIT 1
  ) || '].props.imageAlt',
  'A weekly organic produce order being sorted for storage and cooking',
  '$.blocks[' || (
    SELECT block.key
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'hero'
    LIMIT 1
  ) || '].props.slides',
  json('[
    {"imageUrl":"/banners/home/01-weekly-produce-reset.webp","imageAlt":"A weekly organic produce order being sorted for storage and cooking","href":"/blog/20-minute-produce-storage-reset","label":"Make fresh produce last longer","enabled":true},
    {"imageUrl":"/banners/home/02-traceable-organic-food.webp","imageAlt":"A farm packing table with produce lots, tags and weighing tools","href":"/blog/how-to-read-organic-food-label-india","label":"Learn the five-point organic label check","enabled":true},
    {"imageUrl":"/banners/home/03-leafy-greens-storage.webp","imageAlt":"Spinach and coriander drying before refrigerator storage","href":"/category/vegetables","label":"Store leafy greens without trapping moisture","enabled":true},
    {"imageUrl":"/banners/home/04-millets-for-the-meal.webp","imageAlt":"Four distinct millet grains, flours and an everyday cooked millet dish","href":"/category/staple-grains","label":"Choose the right millet for the meal","enabled":true},
    {"imageUrl":"/banners/home/05-pulses-pantry-to-pot.webp","imageAlt":"Dry, soaking and cooked pulses arranged from pantry to pot","href":"/category/pulses-legumes","label":"Plan pulses from pantry to pot","enabled":true},
    {"imageUrl":"/banners/home/06-protect-cooking-oils.webp","imageAlt":"Wood-pressed oils stored in dark glass away from heat and sunlight","href":"/category/oils-cooking-fats","label":"Protect the flavour of cooking oils","enabled":true},
    {"imageUrl":"/banners/home/07-plan-fruit-by-ripeness.webp","imageAlt":"Seasonal fruit separated by ripeness and order of use","href":"/category/fruits","label":"Plan seasonal fruit by ripeness","enabled":true},
    {"imageUrl":"/banners/home/08-harvest-sort-pack.webp","imageAlt":"Fresh vegetables being shaded, sorted and packed at the farm","href":"/farms","label":"See what careful handling looks like","enabled":true},
    {"imageUrl":"/banners/home/09-build-a-better-breakfast.webp","imageAlt":"Ragi, oats, fruit, yoghurt and nuts arranged for a practical breakfast","href":"/category/breakfast-spreads","label":"Build a breakfast you will repeat","enabled":true},
    {"imageUrl":"/banners/home/10-whole-spices-small-batches.webp","imageAlt":"Whole spices, freshly ground spices and dry pantry jars","href":"/category/spices-seasonings","label":"Buy aromatic spices in useful quantities","enabled":true},
    {"imageUrl":"/banners/home/11-cold-chain-dairy.webp","imageAlt":"Clean small-batch dairy cooling and handling equipment","href":"/category/dairy-farm-fresh","label":"Follow freshness through the cold chain","enabled":true},
    {"imageUrl":"/banners/home/12-balcony-food-garden.webp","imageAlt":"An attainable balcony herb garden with compost and seedlings","href":"/category/organic-gardening","label":"Grow something useful in a small space","enabled":true}
  ]')
)
WHERE page_id = 'pag_home'
  AND EXISTS (
    SELECT 1
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'hero'
  );

-- Every category page gets the banner for its top-level department. This keeps
-- subcategory imagery relevant without requiring 120 near-duplicate assets.
UPDATE categories
SET hero_image_url = '/banners/categories/' || COALESCE(
      CASE WHEN parent_id IS NULL THEN slug END,
      (SELECT parent.slug FROM categories AS parent WHERE parent.id = categories.parent_id)
    ) || '.webp',
    hero_image_alt = COALESCE(
      NULLIF(TRIM(hero_image_alt), ''),
      name || ' from the True Grit organic market'
    ),
    updated_at = '2026-08-01T09:00:00Z'
WHERE COALESCE(
    CASE WHEN parent_id IS NULL THEN slug END,
    (SELECT parent.slug FROM categories AS parent WHERE parent.id = categories.parent_id)
  ) IN (
    'baby-kids','bakery-breads','breakfast-spreads','dairy-farm-fresh','eco-living',
    'fermented-foods','flours-baking','flowers-puja','frozen-chilled','fruits',
    'gift-hampers','global-pantry','herbs-aromatics','natural-home-care',
    'natural-personal-care','natural-sweeteners','nuts-seeds-dried-fruit',
    'oils-cooking-fats','organic-gardening','pantry-condiments','pet-care',
    'plant-based-foods','pulses-legumes','ready-to-cook','snacks-treats',
    'spices-seasonings','staple-grains','tea-coffee-beverages','vegetables',
    'wellness-supplements'
  );

UPDATE app_settings
SET value = CASE key
      WHEN 'banner.blog.image_url' THEN '/banners/content/blog-editorial-guides.webp'
      WHEN 'banner.blog.image_alt' THEN 'Produce, batch records and a notebook for practical True Grit food guides'
    END,
    updated_at = '2026-08-01T09:00:00Z'
WHERE key IN ('banner.blog.image_url', 'banner.blog.image_alt');

UPDATE articles
SET hero_image_url = '/banners/content/blog-editorial-guides.webp',
    hero_image_alt = COALESCE(
      NULLIF(TRIM(hero_image_alt), ''),
      'True Grit practical organic food guide'
    )
WHERE hero_image_url IS NULL
   OR TRIM(hero_image_url) = ''
   OR hero_image_url = '/content/default-blog.webp';

UPDATE recipes
SET hero_image_url = '/banners/content/recipes-cook-with-purpose.webp',
    hero_image_alt = COALESCE(
      NULLIF(TRIM(hero_image_alt), ''),
      'Seasonal ingredients prepared in a True Grit kitchen'
    )
WHERE hero_image_url IS NULL
   OR TRIM(hero_image_url) = ''
   OR hero_image_url = '/content/default-recipe.webp';

UPDATE discussions
SET image_url = '/banners/content/community-useful-conversations.webp',
    image_alt = COALESCE(
      NULLIF(TRIM(image_alt), ''),
      'True Grit community members sharing practical food knowledge'
    )
WHERE image_url IS NULL
   OR TRIM(image_url) = ''
   OR image_url = '/content/default-discussion.webp';

DROP TRIGGER IF EXISTS articles_default_image_after_insert;
CREATE TRIGGER articles_default_image_after_insert
AFTER INSERT ON articles
WHEN NULLIF(TRIM(NEW.hero_image_url), '') IS NULL
BEGIN
  UPDATE articles
  SET hero_image_url = '/banners/content/blog-editorial-guides.webp',
      hero_image_alt = COALESCE(
        NULLIF(TRIM(NEW.hero_image_alt), ''),
        'True Grit practical organic food guide'
      )
  WHERE id = NEW.id;
END;

DROP TRIGGER IF EXISTS recipes_default_image_after_insert;
CREATE TRIGGER recipes_default_image_after_insert
AFTER INSERT ON recipes
WHEN NULLIF(TRIM(NEW.hero_image_url), '') IS NULL
BEGIN
  UPDATE recipes
  SET hero_image_url = '/banners/content/recipes-cook-with-purpose.webp',
      hero_image_alt = COALESCE(
        NULLIF(TRIM(NEW.hero_image_alt), ''),
        'Seasonal ingredients prepared in a True Grit kitchen'
      )
  WHERE id = NEW.id;
END;

DROP TRIGGER IF EXISTS discussions_default_image_after_insert;
CREATE TRIGGER discussions_default_image_after_insert
AFTER INSERT ON discussions
WHEN NULLIF(TRIM(NEW.image_url), '') IS NULL
   OR NEW.image_url = '/content/default-discussion.webp'
BEGIN
  UPDATE discussions
  SET image_url = '/banners/content/community-useful-conversations.webp',
      image_alt = COALESCE(
        NULLIF(TRIM(NEW.image_alt), ''),
        'True Grit community members sharing practical food knowledge'
      )
  WHERE id = NEW.id;
END;

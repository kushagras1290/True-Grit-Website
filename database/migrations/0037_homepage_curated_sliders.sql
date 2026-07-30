-- 0037_homepage_curated_sliders: expand both homepage market collections to
-- twelve owner-curated slots. The storefront shows four cards at a time on
-- desktop and Site Control can replace or reorder every saved slug.

UPDATE page_versions
SET content_json = json_set(
  content_json,
  '$.blocks[' || (
    SELECT block.key
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'category_collection'
    LIMIT 1
  ) || '].props.categorySlugs',
  json('[
    "fruits",
    "vegetables",
    "staple-grains",
    "pulses-legumes",
    "flours-baking",
    "oils-cooking-fats",
    "spices-seasonings",
    "natural-sweeteners",
    "nuts-seeds-dried-fruit",
    "breakfast-spreads",
    "pantry-condiments",
    "snacks-treats"
  ]')
)
WHERE page_id = 'pag_home'
  AND EXISTS (
    SELECT 1
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'category_collection'
  );

UPDATE page_versions
SET content_json = json_set(
  content_json,
  '$.blocks[' || (
    SELECT block.key
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'product_collection'
    LIMIT 1
  ) || '].props.productSlugs',
  json('[
    "organic-kesar-mango",
    "organic-mature-spinach",
    "organic-brown-basmati-rice",
    "organic-moong-dal",
    "organic-whole-wheat-atta",
    "organic-cold-pressed-mustard-oil",
    "organic-turmeric-powder",
    "organic-wild-forest-honey",
    "organic-kashmiri-almonds",
    "organic-rolled-oats",
    "organic-roasted-makhana",
    "organic-assam-black-tea"
  ]'),
  '$.blocks[' || (
    SELECT block.key
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'product_collection'
    LIMIT 1
  ) || '].props.limit',
  12
)
WHERE page_id = 'pag_home'
  AND EXISTS (
    SELECT 1
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'product_collection'
  );

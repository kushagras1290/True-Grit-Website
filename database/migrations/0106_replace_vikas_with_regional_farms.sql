-- Replace the single public Vikas Farms profile with two farms from each of
-- Bagi, Sajerah, Najirpur and Khutmili. Product ownership is redistributed so
-- every published product continues to have a traceable farm.
PRAGMA foreign_keys = ON;

INSERT INTO farms (
  id, name, slug, farmer_name, region, country_code, story_json,
  methods_json, seasonal_calendar_json, status, seo_title, seo_description,
  created_at, created_by, updated_at, updated_by, hero_image_url,
  hero_image_alt, commission_bps
) VALUES
  (
    'farm_bagi_1', 'Bagi Farm I', 'bagi-farm-i', NULL, 'Bagi, India', 'IN',
    '{"summary":"A Bagi farm growing traditional wheat with careful soil and crop management.","body":"Bagi Farm I grows traditional wheat for True Grit''s flour, daliya, semolina, pasta and vermicelli range, with field-level traceability from harvest to small-batch processing.","methods":["Traditional wheat cultivation","Soil-led crop management","Batch traceability from field to pack"]}',
    '["Traditional wheat cultivation","Soil-led crop management","Batch traceability from field to pack"]',
    '[]', 'published', 'Bagi Farm I — True Grit',
    'Meet Bagi Farm I, a partner farm growing traditional wheat for the True Grit catalogue.',
    '2026-08-17T12:00:00Z', 'usr_catalogue_system', '2026-08-17T12:00:00Z', 'usr_catalogue_system',
    '/banners/farms/bagi-farm-i.webp', 'Farmer inspecting mature wheat at Bagi Farm I', 1500
  ),
  (
    'farm_bagi_2', 'Bagi Farm II', 'bagi-farm-ii', NULL, 'Bagi, India', 'IN',
    '{"summary":"A second Bagi farm tending rain-fed field crops on carefully managed soil.","body":"Bagi Farm II supplies Banshi wheat grown and handled in small batches, keeping each lot connected to its field and harvest.","methods":["Rain-aware field cultivation","Small-batch grain handling","Lot-level crop records"]}',
    '["Rain-aware field cultivation","Small-batch grain handling","Lot-level crop records"]',
    '[]', 'published', 'Bagi Farm II — True Grit',
    'Meet Bagi Farm II, a partner farm supplying Banshi wheat for the True Grit catalogue.',
    '2026-08-17T12:00:00Z', 'usr_catalogue_system', '2026-08-17T12:00:00Z', 'usr_catalogue_system',
    '/banners/farms/bagi-farm-ii.webp', 'Farmers crossing green rain-fed fields at Bagi Farm II', 1500
  ),
  (
    'farm_sajerah_1', 'Sajerah Farm I', 'sajerah-farm-i', NULL, 'Sajerah, India', 'IN',
    '{"summary":"A Sajerah oilseed farm growing mustard across open, fertile fields.","body":"Sajerah Farm I grows mustard seed for True Grit''s small-batch oils, with careful harvest handling and clear origin records.","methods":["Seasonal mustard cultivation","Careful seed drying and sorting","Field-to-press traceability"]}',
    '["Seasonal mustard cultivation","Careful seed drying and sorting","Field-to-press traceability"]',
    '[]', 'published', 'Sajerah Farm I — True Grit',
    'Meet Sajerah Farm I, a partner farm growing mustard seed for small-batch oils.',
    '2026-08-17T12:00:00Z', 'usr_catalogue_system', '2026-08-17T12:00:00Z', 'usr_catalogue_system',
    '/banners/farms/sajerah-farm-i.webp', 'Farmer walking through mustard fields at Sajerah Farm I', 1500
  ),
  (
    'farm_sajerah_2', 'Sajerah Farm II', 'sajerah-farm-ii', NULL, 'Sajerah, India', 'IN',
    '{"summary":"A second Sajerah farm combining traditional crops with attentive water management.","body":"Sajerah Farm II grows Paigambari wheat for a range of everyday staples, using simple irrigation and small-batch post-harvest handling.","methods":["Traditional Paigambari wheat","Measured field irrigation","Small-batch milling and processing"]}',
    '["Traditional Paigambari wheat","Measured field irrigation","Small-batch milling and processing"]',
    '[]', 'published', 'Sajerah Farm II — True Grit',
    'Meet Sajerah Farm II, a partner farm growing Paigambari wheat for the True Grit catalogue.',
    '2026-08-17T12:00:00Z', 'usr_catalogue_system', '2026-08-17T12:00:00Z', 'usr_catalogue_system',
    '/banners/farms/sajerah-farm-ii.webp', 'Farmer tending irrigated crops at Sajerah Farm II', 1500
  ),
  (
    'farm_najirpur_1', 'Najirpur Farm I', 'najirpur-farm-i', NULL, 'Najirpur, India', 'IN',
    '{"summary":"A Najirpur farm harvesting and sorting sesame for seed and oil.","body":"Najirpur Farm I grows sesame for True Grit''s seed and oil range, bundling, drying and sorting each harvest before small-batch processing.","methods":["Hand-harvested sesame","Natural drying and seed sorting","Field-to-press batch records"]}',
    '["Hand-harvested sesame","Natural drying and seed sorting","Field-to-press batch records"]',
    '[]', 'published', 'Najirpur Farm I — True Grit',
    'Meet Najirpur Farm I, a partner farm growing sesame for seed and oil.',
    '2026-08-17T12:00:00Z', 'usr_catalogue_system', '2026-08-17T12:00:00Z', 'usr_catalogue_system',
    '/banners/farms/najirpur-farm-i.webp', 'Farmers gathering sesame stalks at Najirpur Farm I', 1500
  ),
  (
    'farm_najirpur_2', 'Najirpur Farm II', 'najirpur-farm-ii', NULL, 'Najirpur, India', 'IN',
    '{"summary":"A second Najirpur farm growing lentils and field peas in well-kept plots.","body":"Najirpur Farm II supplies red lentils and white field peas, monitoring soil and moisture through the season and keeping harvested lots separate.","methods":["Pulse crop rotation","Soil and moisture checks","Separated harvest lots"]}',
    '["Pulse crop rotation","Soil and moisture checks","Separated harvest lots"]',
    '[]', 'published', 'Najirpur Farm II — True Grit',
    'Meet Najirpur Farm II, a partner farm growing lentils and field peas.',
    '2026-08-17T12:00:00Z', 'usr_catalogue_system', '2026-08-17T12:00:00Z', 'usr_catalogue_system',
    '/banners/farms/najirpur-farm-ii.webp', 'Farmer checking a pulse crop at Najirpur Farm II', 1500
  ),
  (
    'farm_khutmili_1', 'Khutmili Farm I', 'khutmili-farm-i', NULL, 'Khutmili, India', 'IN',
    '{"summary":"A Khutmili farm growing flax for seeds and cold-pressed oil.","body":"Khutmili Farm I grows flax for True Grit''s seed and oil range, with patient crop care and clean separation between harvested lots.","methods":["Seasonal flax cultivation","Careful seed cleaning","Field-to-press traceability"]}',
    '["Seasonal flax cultivation","Careful seed cleaning","Field-to-press traceability"]',
    '[]', 'published', 'Khutmili Farm I — True Grit',
    'Meet Khutmili Farm I, a partner farm growing flax for seed and oil.',
    '2026-08-17T12:00:00Z', 'usr_catalogue_system', '2026-08-17T12:00:00Z', 'usr_catalogue_system',
    '/banners/farms/khutmili-farm-i.webp', 'Farmer walking through blue flax at Khutmili Farm I', 1500
  ),
  (
    'farm_khutmili_2', 'Khutmili Farm II', 'khutmili-farm-ii', NULL, 'Khutmili, India', 'IN',
    '{"summary":"A second Khutmili farm growing and hand-sorting black gram.","body":"Khutmili Farm II grows black gram for True Grit''s whole dal, broken dal, sattu and besan range, sorting pods and grain in small batches.","methods":["Black gram crop care","Hand sorting after harvest","Small-batch pulse processing"]}',
    '["Black gram crop care","Hand sorting after harvest","Small-batch pulse processing"]',
    '[]', 'published', 'Khutmili Farm II — True Grit',
    'Meet Khutmili Farm II, a partner farm growing black gram for the True Grit catalogue.',
    '2026-08-17T12:00:00Z', 'usr_catalogue_system', '2026-08-17T12:00:00Z', 'usr_catalogue_system',
    '/banners/farms/khutmili-farm-ii.webp', 'Farmers sorting black gram at Khutmili Farm II', 1500
  );

UPDATE products SET farm_id = 'farm_bagi_1' WHERE id IN (
  'prd_catalogue_01', 'prd_catalogue_18', 'prd_catalogue_21', 'prd_catalogue_24', 'prd_catalogue_27'
);
UPDATE products SET farm_id = 'farm_bagi_2' WHERE id IN (
  'prd_catalogue_02', 'prd_catalogue_19', 'prd_catalogue_22', 'prd_catalogue_25', 'prd_catalogue_28'
);
UPDATE products SET farm_id = 'farm_sajerah_1' WHERE id IN ('prd_catalogue_04', 'prd_catalogue_05');
UPDATE products SET farm_id = 'farm_sajerah_2' WHERE id IN (
  'prd_catalogue_03', 'prd_catalogue_20', 'prd_catalogue_23', 'prd_catalogue_26', 'prd_catalogue_29'
);
UPDATE products SET farm_id = 'farm_najirpur_1' WHERE id IN (
  'prd_catalogue_09', 'prd_catalogue_10', 'prd_catalogue_11'
);
UPDATE products SET farm_id = 'farm_najirpur_2' WHERE id IN (
  'prd_catalogue_16', 'prd_catalogue_17', 'prd_catalogue_30'
);
UPDATE products SET farm_id = 'farm_khutmili_1' WHERE id IN (
  'prd_catalogue_06', 'prd_catalogue_07', 'prd_catalogue_08'
);
UPDATE products SET farm_id = 'farm_khutmili_2' WHERE id IN (
  'prd_catalogue_12', 'prd_catalogue_13', 'prd_catalogue_14', 'prd_catalogue_15'
);

-- Keep catalogue copy and search results aligned with the newly assigned farm.
UPDATE products
SET short_description = replace(
      short_description,
      'Vikas Farms',
      (SELECT f.name FROM farms f WHERE f.id = products.farm_id)
    ),
    seo_description = replace(
      seo_description,
      'Vikas Farms',
      (SELECT f.name FROM farms f WHERE f.id = products.farm_id)
    ),
    updated_at = '2026-08-17T12:00:00Z',
    updated_by = 'usr_catalogue_system'
WHERE id LIKE 'prd_catalogue_%';

UPDATE product_versions
SET content_json = replace(
  content_json,
  'Vikas Farms',
  (
    SELECT f.name
    FROM products p
    JOIN farms f ON f.id = p.farm_id
    WHERE p.id = product_versions.product_id
  )
)
WHERE product_id LIKE 'prd_catalogue_%';

UPDATE search_products
SET farm_name = (
      SELECT f.name
      FROM products p
      JOIN farms f ON f.id = p.farm_id
      WHERE p.id = search_products.product_id
    ),
    short_description = replace(
      short_description,
      'Vikas Farms',
      (
        SELECT f.name
        FROM products p
        JOIN farms f ON f.id = p.farm_id
        WHERE p.id = search_products.product_id
      )
    )
WHERE product_id LIKE 'prd_catalogue_%';

-- Publish a fresh homepage version so both the hero slide and farmer story no
-- longer link to the retired Vikas profile.
INSERT INTO page_versions (
  id, page_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  'pgv_home_regional_farms_20260817', p.id,
  COALESCE((SELECT MAX(version_number) + 1 FROM page_versions WHERE page_id = p.id), 1),
  json_set(
    pv.content_json,
    '$.blocks[0].props.imageUrl', '/banners/home/catalogue/00-our-farms.webp',
    '$.blocks[0].props.imageAlt', 'Partner farmers walking between varied crop fields',
    '$.blocks[0].props.slides', json('[{"imageUrl":"/banners/home/catalogue/00-our-farms.webp","imageAlt":"Partner farmers walking between varied crop fields","href":"/farms","label":"Meet our farms","enabled":true},{"imageUrl":"/banners/home/catalogue/01-complete-organic-range.webp","imageAlt":"True Grit traditional grains, pulses, seeds and cold-pressed oils","href":"/shop","label":"Explore the complete organic range","enabled":true},{"imageUrl":"/banners/home/catalogue/03-traditional-small-batch.webp","imageAlt":"Traditional small-batch flour and grain processing","href":"/blog/from-farm-to-flour-how-true-grit-products-are-made","label":"See how your food is made","enabled":true},{"imageUrl":"/banners/home/catalogue/04-cook-with-true-grit.webp","imageAlt":"A traditional Indian meal prepared with True Grit pantry staples","href":"/recipes","label":"Cook with True Grit","enabled":true}]'),
    '$.blocks[4].props.farmSlug', 'bagi-farm-i',
    '$.blocks[4].props.quote', 'Traditional food begins with careful farming and clear field-to-pack records.',
    '$.blocks[4].props.attribution', 'Bagi Farm I'
  ),
  'Replace Vikas Farms with eight regional farm partners', 'published',
  '2026-08-17T12:00:00Z', 'usr_catalogue_system',
  '2026-08-17T12:00:00Z', 'usr_catalogue_system', '2026-08-17T12:00:00Z'
FROM pages p
JOIN page_versions pv ON pv.id = p.published_version_id
WHERE p.slug = 'home';

UPDATE pages
SET published_version_id = 'pgv_home_regional_farms_20260817',
    updated_at = '2026-08-17T12:00:00Z',
    updated_by = 'usr_catalogue_system'
WHERE slug = 'home';

-- Retain the old row only for historical order/revenue foreign keys. Archived
-- farms are excluded from the public listing, detail route and sitemap.
UPDATE farms
SET status = 'archived',
    updated_at = '2026-08-17T12:00:00Z',
    updated_by = 'usr_catalogue_system'
WHERE id = 'farm_vikas';

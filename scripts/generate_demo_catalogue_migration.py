"""Promote the existing fixture catalogue into a forward production migration.

The large catalogue was originally authored in development.sql.  This small
generator keeps that established product/category copy intact while making the
SQL safe for D1 migrations and repeatable development seeding.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "database" / "seeds" / "development.sql"
MIGRATION_PATH = ROOT / "database" / "migrations" / "0059_restore_demo_catalogue.sql"
START_MARKER = "-- Comprehensive organic-market catalogue expansion"
END_MARKER = "DROP TABLE extra_catalogue_sections;"
CLEANUP_PATTERN = re.compile(
    r"-- Keep migrated fixture search rows singular during development seeding\.\n"
    r"DELETE FROM search_products\n"
    r"WHERE product_id LIKE 'prd_market_%' OR product_id LIKE 'prd_extra_%';\n*"
)

ENTITY_TABLES = (
    "categories",
    "category_versions",
    "products",
    "product_versions",
    "product_categories",
    "product_variants",
    "variant_prices",
    "inventory_levels",
    "product_certifications",
    "product_tags",
)


def locate_block(sql: str) -> tuple[int, int, str]:
    start = sql.index(START_MARKER)
    end = sql.index(END_MARKER, start) + len(END_MARKER)
    return start, end, sql[start:end]


def make_repeatable(block: str) -> str:
    entity_pattern = "|".join(ENTITY_TABLES)
    block = re.sub(
        rf"(?m)^INSERT INTO ({entity_pattern})(?=\s|\()",
        r"INSERT OR IGNORE INTO \1",
        block,
    )
    return block.replace("/media/catalogue/generated/", "/banners/categories/")


def make_migration_block(block: str) -> str:
    block = make_repeatable(block)
    block = re.sub(
        r"(?m)^CREATE TEMP TABLE ([a-z_]+)",
        r"DROP TABLE IF EXISTS \1;\nCREATE TABLE \1",
        block,
    )
    for fixture_actor in ("usr_pm", "usr_admin", "usr_editor"):
        block = block.replace(f"'{fixture_actor}'", "'usr_catalogue_system'")
    farm_case = """CASE
    WHEN department_order BETWEEN 1 AND 3 THEN
      CASE (product_number % 3) WHEN 0 THEN 'farm_devika' WHEN 1 THEN 'farm_anandvan' ELSE 'farm_himgiri' END
    WHEN department_order BETWEEN 4 AND 10 THEN
      CASE (product_number % 2) WHEN 0 THEN 'farm_anandvan' ELSE 'farm_himgiri' END
    ELSE NULL
  END,"""
    block = block.replace(farm_case, "NULL,")
    block = re.sub(
        r"(?ms)^INSERT OR IGNORE INTO product_certifications \(.*?;\n",
        "",
        block,
    )
    return block


HEADER = """-- 0059_restore_demo_catalogue: restore the preferred catalogue presentation.
-- The 800 image-backed products first authored for fixture mode are promoted
-- to normal migrated customer data. Another 695 useful products are retained
-- from 0056 and restyled to match, producing exactly 1,500 public products.
-- Surplus rows remain archived for order-history integrity.
PRAGMA foreign_keys = ON;

-- Promote the five hand-authored launch products and their four original
-- departments as migrated data too; production must not depend on dev seeds.
INSERT OR IGNORE INTO farms (
  id, name, slug, farmer_name, region, country_code, established_year,
  story_json, methods_json, status, seo_title, seo_description,
  created_at, created_by, updated_at, updated_by
) VALUES
  ('farm_devika','Devika Organics','devika-organics','Devika Kulkarni','Ratnagiri, Maharashtra','IN',1998,'{"summary":"Three generations of Alphonso orchards farmed without synthetic inputs since 1998."}','["Tree ripening","Compost-fed orchards","Hand grading"]','published','Devika Organics | Ratnagiri orchards','Certified organic Alphonso orchards in Ratnagiri.','2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('farm_anandvan','Anandvan Collective','anandvan-collective','Ravi Patil','Wardha, Maharashtra','IN',2011,'{"summary":"A 40-family collective growing millets, pulses and oilseeds on regenerated soil."}','["Rain-fed cultivation","Collective stone milling","Low-temperature pressing"]','published','Anandvan Collective | Regenerative farming','A Wardha collective growing millets, pulses and oilseeds.','2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('farm_himgiri','Himgiri Terraces','himgiri-terraces','Tara Negi','Uttarkashi, Uttarakhand','IN',2015,'{"summary":"High-altitude terraced farms growing rajma, amaranth and Himalayan spices."}','["Terrace farming","Glacial irrigation","Hand sorting"]','published','Himgiri Terraces | Himalayan farms','High-altitude organic terraces in Uttarkashi.','2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system');

INSERT OR IGNORE INTO categories (
  id, internal_name, name, slug, parent_id, path, level, sort_order, status,
  visibility, short_description, hero_eyebrow, hero_title, hero_description,
  theme_key, product_assignment_mode, hero_image_url, hero_image_alt,
  created_at, created_by, updated_at, updated_by
) VALUES
  ('cat_fresh_fruits','Fresh Fruits','Fresh Fruits','fresh-fruits',NULL,'/fresh-fruits',0,1,'published','public','Seasonal organic fruit picked at peak ripeness.','In season now','Fruit, at its honest best','Traceable fruit from verified orchards.','terracotta','manual','/banners/categories/fruits.webp','Seasonal organic fruit','2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('cat_vegetables','Organic Vegetables','Organic Vegetables','organic-vegetables',NULL,'/organic-vegetables',0,2,'published','public','Everyday vegetables from tested, rested soil.','From living soil','Vegetables with a story','Fresh vegetables from verified growers.','sage','manual','/banners/categories/vegetables.webp','Fresh organic vegetables','2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('cat_grains','Grains and Millets','Grains & Millets','grains-and-millets',NULL,'/grains-and-millets',0,3,'published','public','Heritage grains and millets milled in small batches.','Slow staples','The grains your grandmother knew','Single-origin grains and pulses for daily cooking.','forest','manual','/banners/categories/staple-grains.webp','Organic grains and millets','2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('cat_oils','Cold-Pressed Oils','Cold-Pressed Oils','cold-pressed-oils',NULL,'/cold-pressed-oils',0,4,'published','public','Wood-pressed and cold-pressed single-origin oils.','Pressed, not processed','Oil the slow way','Small-batch cooking oils with clear source and press dates.','charcoal','manual','/banners/categories/oils-cooking-fats.webp','Cold-pressed cooking oils','2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('cat_stone_fruit','Stone Fruit','Stone Fruit','stone-fruit','cat_fresh_fruits','/fresh-fruits/stone-fruit',1,1,'published','public','Mangoes, peaches and plums at the peak of their short season.','Fresh Fruits','Stone Fruit','Tree-ripened fruit selected around its natural season.','terracotta','manual','/banners/categories/fruits.webp','Seasonal stone fruit','2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('cat_leafy_greens','Leafy Greens','Leafy Greens','leafy-greens','cat_vegetables','/organic-vegetables/leafy-greens',1,1,'published','public','Spinach, amaranth and mustard greens cut to order.','Organic Vegetables','Leafy Greens','Tender greens harvested and cooled for dependable freshness.','sage','manual','/banners/categories/vegetables.webp','Fresh organic leafy greens','2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system');

INSERT OR IGNORE INTO products (
  id, internal_name, name, slug, product_type, farm_id, status,
  short_description, seo_title, seo_description, image_url, image_alt,
  accepts_orders, created_at, created_by, updated_at, updated_by
) VALUES
  ('prd_alphonso','Alphonso Mangoes 2026','Organic Alphonso Mangoes','organic-alphonso-mangoes','fresh_fruit','farm_devika','published','Ratnagiri Alphonso, tree-ripened and carbide-free, from Devika Organics.','Organic Alphonso Mangoes | Ratnagiri','Tree-ripened organic Alphonso mangoes from Ratnagiri.','/banners/categories/fruits.webp','Organic Alphonso mangoes',1,'2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('prd_spinach','Baby Spinach','Organic Baby Spinach','organic-baby-spinach','vegetable','farm_anandvan','published','Tender baby spinach, harvested at dawn and chilled within the hour.','Organic Baby Spinach | Harvested at dawn','Fresh baby spinach from the Anandvan Collective.','/banners/categories/vegetables.webp','Fresh organic baby spinach',1,'2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('prd_ragi','Sprouted Ragi Flour','Sprouted Ragi Flour','sprouted-ragi-flour','grain','farm_anandvan','published','Stone-milled finger millet, sprouted for easier digestion and deeper flavour.','Sprouted Ragi Flour | Stone-milled','Sprouted finger millet flour from the Anandvan Collective.','/banners/categories/staple-grains.webp','Organic sprouted ragi flour',1,'2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('prd_groundnut_oil','Wood-Pressed Groundnut Oil','Wood-Pressed Groundnut Oil','wood-pressed-groundnut-oil','oil','farm_anandvan','published','Single-origin groundnuts, wood-pressed at low RPM within a week of shelling.','Wood-Pressed Groundnut Oil | Single origin','Wood-pressed groundnut oil from the Anandvan Collective.','/banners/categories/oils-cooking-fats.webp','Wood-pressed groundnut cooking oil',1,'2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('prd_rajma','Himalayan Rajma','Himalayan Red Rajma','himalayan-red-rajma','grain','farm_himgiri','published','Small red kidney beans from high-altitude terraces, known for quick cooking.','Himalayan Red Rajma | Uttarkashi','Red rajma grown at altitude by Himgiri Terraces.','/banners/categories/pulses-legumes.webp','Organic Himalayan red rajma',1,'2026-07-01T00:00:00Z','usr_catalogue_system','2026-08-02T15:00:00Z','usr_catalogue_system');

INSERT OR IGNORE INTO product_categories
  (product_id, category_id, is_primary, sort_order, assigned_at, assigned_by)
VALUES
  ('prd_alphonso','cat_fresh_fruits',1,1,'2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prd_spinach','cat_vegetables',1,1,'2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prd_ragi','cat_grains',1,1,'2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prd_rajma','cat_grains',1,2,'2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prd_groundnut_oil','cat_oils',1,1,'2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prd_alphonso','cat_stone_fruit',0,1,'2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prd_spinach','cat_leafy_greens',0,1,'2026-07-01T00:00:00Z','usr_catalogue_system');

INSERT OR IGNORE INTO product_variants
  (id, product_id, sku, name, weight_value, weight_unit, status, sort_order, created_at, updated_at)
VALUES
  ('var_alphonso_1kg','prd_alphonso','TRG-MNG-1KG','1 kg box (3-4 mangoes)',1,'kg','active',1,'2026-07-01T00:00:00Z','2026-08-02T15:00:00Z'),
  ('var_alphonso_2kg','prd_alphonso','TRG-MNG-2KG','2 kg box (7-8 mangoes)',2,'kg','active',2,'2026-07-01T00:00:00Z','2026-08-02T15:00:00Z'),
  ('var_spinach_250g','prd_spinach','TRG-SPN-250','250 g bunch',250,'g','active',1,'2026-07-01T00:00:00Z','2026-08-02T15:00:00Z'),
  ('var_ragi_500g','prd_ragi','TRG-RGI-500','500 g pack',500,'g','active',1,'2026-07-01T00:00:00Z','2026-08-02T15:00:00Z'),
  ('var_ragi_1kg','prd_ragi','TRG-RGI-1KG','1 kg pack',1,'kg','active',2,'2026-07-01T00:00:00Z','2026-08-02T15:00:00Z'),
  ('var_oil_500ml','prd_groundnut_oil','TRG-GNO-500','500 ml glass bottle',500,'ml','active',1,'2026-07-01T00:00:00Z','2026-08-02T15:00:00Z'),
  ('var_oil_1l','prd_groundnut_oil','TRG-GNO-1L','1 L glass bottle',1,'l','active',2,'2026-07-01T00:00:00Z','2026-08-02T15:00:00Z'),
  ('var_rajma_500g','prd_rajma','TRG-RJM-500','500 g pack',500,'g','active',1,'2026-07-01T00:00:00Z','2026-08-02T15:00:00Z');

INSERT OR IGNORE INTO variant_prices
  (id, variant_id, market_code, currency_code, list_amount_minor, sale_amount_minor, tax_inclusive, status, created_at, created_by)
VALUES
  ('prc_alphonso_1kg','var_alphonso_1kg','IN','INR',89900,NULL,1,'active','2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prc_alphonso_2kg','var_alphonso_2kg','IN','INR',169900,149900,1,'active','2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prc_spinach_250g','var_spinach_250g','IN','INR',6900,NULL,1,'active','2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prc_ragi_500g','var_ragi_500g','IN','INR',14500,NULL,1,'active','2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prc_ragi_1kg','var_ragi_1kg','IN','INR',26900,NULL,1,'active','2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prc_oil_500ml','var_oil_500ml','IN','INR',42500,NULL,1,'active','2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prc_oil_1l','var_oil_1l','IN','INR',79900,74900,1,'active','2026-07-01T00:00:00Z','usr_catalogue_system'),
  ('prc_rajma_500g','var_rajma_500g','IN','INR',19900,NULL,1,'active','2026-07-01T00:00:00Z','usr_catalogue_system');

INSERT OR IGNORE INTO inventory_levels
  (variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at)
VALUES
  ('var_alphonso_1kg','loc_mumbai',120,4,20,1,'2026-08-02T15:00:00Z'),
  ('var_alphonso_2kg','loc_mumbai',60,2,10,1,'2026-08-02T15:00:00Z'),
  ('var_spinach_250g','loc_mumbai',200,0,40,1,'2026-08-02T15:00:00Z'),
  ('var_ragi_500g','loc_mumbai',340,0,50,1,'2026-08-02T15:00:00Z'),
  ('var_ragi_1kg','loc_mumbai',180,0,30,1,'2026-08-02T15:00:00Z'),
  ('var_oil_500ml','loc_mumbai',90,1,15,1,'2026-08-02T15:00:00Z'),
  ('var_oil_1l','loc_mumbai',45,0,10,1,'2026-08-02T15:00:00Z'),
  ('var_rajma_500g','loc_mumbai',80,0,25,1,'2026-08-02T15:00:00Z');

DELETE FROM search_products
WHERE product_id IN ('prd_alphonso','prd_spinach','prd_ragi','prd_groundnut_oil','prd_rajma');
INSERT INTO search_products
  (product_id,name,slug,brand_name,farm_name,category_names,keywords,short_description)
SELECT p.id,p.name,p.slug,'',COALESCE(f.name,''),COALESCE(c.name,''),
       lower(p.name || ' organic traceable'),p.short_description
FROM products p
LEFT JOIN farms f ON f.id=p.farm_id
LEFT JOIN product_categories pc ON pc.product_id=p.id AND pc.is_primary=1
LEFT JOIN categories c ON c.id=pc.category_id
WHERE p.id IN ('prd_alphonso','prd_spinach','prd_ragi','prd_groundnut_oil','prd_rajma');

UPDATE variant_prices
SET status = 'inactive'
WHERE variant_id IN (
  SELECT id FROM product_variants
  WHERE product_id LIKE 'prd_mass_%'
    AND CAST(substr(product_id, 10) AS INTEGER) > 311
);

UPDATE product_variants
SET status = 'inactive', updated_at = '2026-08-02T15:00:00Z'
WHERE product_id LIKE 'prd_mass_%'
  AND CAST(substr(product_id, 10) AS INTEGER) > 311;

UPDATE products
SET status = 'archived', indexing_policy = 'noindex',
    archived_at = COALESCE(archived_at, '2026-08-02T15:00:00Z'),
    updated_at = '2026-08-02T15:00:00Z', updated_by = 'usr_catalogue_system'
WHERE id LIKE 'prd_mass_%' AND CAST(substr(id, 10) AS INTEGER) > 311;

-- Keep the useful 0056 departments, but make their cards use the preferred
-- image-backed catalogue treatment. Empty surplus subcategories are hidden.
UPDATE categories
SET status = 'archived', visibility = 'hidden', indexing_policy = 'noindex',
    archived_at = COALESCE(archived_at, '2026-08-02T15:00:00Z'),
    updated_at = '2026-08-02T15:00:00Z', updated_by = 'usr_catalogue_system'
WHERE id LIKE 'cat_mass_%'
  AND NOT EXISTS (
    SELECT 1
    FROM product_categories pc
    JOIN products p ON p.id = pc.product_id AND p.status = 'published'
    WHERE pc.category_id = categories.id
  );

UPDATE categories
SET hero_image_url = '/banners/categories/' ||
      CASE
        WHEN slug IN ('farm-fresh-proteins','free-range-eggs','fresh-mushrooms','fresh-sprouts','fresh-tofu-tempeh','egg-value-packs','mushroom-grow-kits','protein-meal-prep','sprouting-seeds') THEN 'dairy-farm-fresh'
        WHEN slug IN ('pasta-noodles-couscous','wholegrain-pasta','gluten-free-pasta','asian-noodles','couscous-specialty-grains','filled-pasta','pasta-sauces','kids-pasta-shapes','lasagne-oven-pasta') THEN 'global-pantry'
        WHEN slug IN ('soups-stocks-preserved','ready-soups','stocks-broths','canned-beans-pulses','canned-tomatoes-vegetables','dry-soup-mixes','prepared-meal-bowls','pickled-vegetables','fruit-preserves') THEN 'pantry-condiments'
        WHEN slug IN ('juices-water-functional','cold-pressed-juices','natural-hydration','sparkling-water-soda','wellness-shots','iced-tea','plant-protein-shakes','traditional-sharbat','drink-concentrates') THEN 'tea-coffee-beverages'
        WHEN slug IN ('chocolate-confectionery','dark-chocolate','milk-vegan-chocolate','chocolate-treats','natural-confectionery','cacao-baking-chocolate','nut-chocolate-bars','festival-chocolate-boxes','kids-chocolate-treats') THEN 'snacks-treats'
        WHEN slug = 'regional-indian-pantry' OR parent_id = 'cat_complete_regional-indian-pantry' THEN 'pantry-condiments'
        WHEN slug = 'free-from-special-diet' OR parent_id = 'cat_complete_free-from-special-diet' THEN 'flours-baking'
        WHEN slug = 'baby-care-parenting' OR parent_id = 'cat_complete_baby-care-parenting' THEN 'baby-kids'
        WHEN slug = 'family-wellness-care' OR parent_id = 'cat_complete_family-wellness-care' THEN 'wellness-supplements'
        WHEN slug = 'kitchen-dining-storage' OR parent_id = 'cat_complete_kitchen-dining-storage' THEN 'eco-living'
        WHEN slug = 'bulk-refill-value' OR parent_id = 'cat_complete_bulk-refill-value' THEN 'staple-grains'
        ELSE 'ready-to-cook'
      END || '.webp',
    hero_image_alt = name || ' product selection',
    hero_eyebrow = 'The complete market',
    updated_at = '2026-08-02T15:00:00Z', updated_by = 'usr_catalogue_system'
WHERE (id LIKE 'cat_complete_%' OR id LIKE 'cat_mass_%')
  AND status = 'published';

UPDATE products
SET image_url = (
      SELECT c.hero_image_url
      FROM product_categories pc
      JOIN categories c ON c.id = pc.category_id
      WHERE pc.product_id = products.id AND c.status = 'published'
      ORDER BY pc.is_primary DESC, pc.sort_order
      LIMIT 1
    ),
    image_alt = name || ' from the True Grit market',
    short_description = name || ' with clear sourcing, pack size, current price and dependable availability.',
    updated_at = '2026-08-02T15:00:00Z', updated_by = 'usr_catalogue_system'
WHERE id LIKE 'prd_complete_%'
   OR (id LIKE 'prd_mass_%' AND CAST(substr(id, 10) AS INTEGER) <= 311);

DELETE FROM search_products
WHERE product_id LIKE 'prd_mass_%' AND CAST(substr(product_id, 10) AS INTEGER) > 311;

-- Rebuild only these FTS rows so this migration and development seeding remain
-- deterministic even if a local database has seen the fixture catalogue before.
DELETE FROM search_products
WHERE product_id LIKE 'prd_market_%' OR product_id LIKE 'prd_extra_%';

"""


VARIANTS = r"""

-- Every promoted product keeps its familiar lead pack and gains a smaller
-- trial/everyday option plus a family/value option. Both additions carry live
-- INR prices and stock, so the options are genuinely purchasable.
INSERT OR IGNORE INTO product_variants (
  id, product_id, sku, name, option_values_json, weight_value, weight_unit,
  package_description, status, sort_order, created_at, updated_at
)
SELECT
  lead.id || '_small', lead.product_id, lead.sku || '-S',
  CASE
    WHEN lead.weight_unit IN ('g','ml') THEN printf('%g %s small pack', MAX(lead.weight_value / 2.0, 1), lead.weight_unit)
    WHEN lead.weight_unit IN ('kg','l') THEN printf('%g %s small pack', MAX(lead.weight_value / 2.0, 0.25), lead.weight_unit)
    ELSE 'Single / small pack'
  END,
  json_object('pack', 'small'),
  CASE WHEN lead.weight_unit = 'unit' THEN 1 ELSE MAX(lead.weight_value / 2.0, 0.25) END,
  lead.weight_unit, 'Smaller pack for first orders and lighter household use',
  'active', 2, '2026-08-02T15:00:00Z', '2026-08-02T15:00:00Z'
FROM product_variants lead
WHERE lead.id GLOB 'var_market_[0-9][0-9][0-9][0-9]'
   OR lead.id GLOB 'var_extra_[0-9][0-9][0-9][0-9]'
   OR lead.id GLOB 'var_complete_[0-9][0-9][0-9][0-9]'
   OR (lead.id GLOB 'var_mass_[0-9][0-9][0-9][0-9]' AND CAST(substr(lead.id, 10) AS INTEGER) <= 311)
UNION ALL
SELECT
  lead.id || '_family', lead.product_id, lead.sku || '-F',
  CASE
    WHEN lead.weight_unit IN ('g','ml','kg','l') THEN printf('%g %s family pack', lead.weight_value * 2, lead.weight_unit)
    ELSE 'Family / value pack'
  END,
  json_object('pack', 'family'),
  CASE WHEN lead.weight_unit = 'unit' THEN 2 ELSE lead.weight_value * 2 END,
  lead.weight_unit, 'Larger value pack for repeat orders and family use',
  'active', 3, '2026-08-02T15:00:00Z', '2026-08-02T15:00:00Z'
FROM product_variants lead
WHERE lead.id GLOB 'var_market_[0-9][0-9][0-9][0-9]'
   OR lead.id GLOB 'var_extra_[0-9][0-9][0-9][0-9]'
   OR lead.id GLOB 'var_complete_[0-9][0-9][0-9][0-9]'
   OR (lead.id GLOB 'var_mass_[0-9][0-9][0-9][0-9]' AND CAST(substr(lead.id, 10) AS INTEGER) <= 311);

INSERT OR IGNORE INTO variant_prices (
  id, variant_id, market_code, currency_code, list_amount_minor,
  sale_amount_minor, tax_inclusive, status, created_at, created_by
)
SELECT
  price.id || '_small', price.variant_id || '_small', price.market_code,
  price.currency_code, MAX(CAST(price.list_amount_minor * 0.58 AS INTEGER), 3900),
  NULL, price.tax_inclusive, 'active', '2026-08-02T15:00:00Z', 'usr_catalogue_system'
FROM variant_prices price
WHERE price.variant_id GLOB 'var_market_[0-9][0-9][0-9][0-9]'
   OR price.variant_id GLOB 'var_extra_[0-9][0-9][0-9][0-9]'
   OR price.variant_id GLOB 'var_complete_[0-9][0-9][0-9][0-9]'
   OR (price.variant_id GLOB 'var_mass_[0-9][0-9][0-9][0-9]' AND CAST(substr(price.variant_id, 10) AS INTEGER) <= 311)
UNION ALL
SELECT
  price.id || '_family', price.variant_id || '_family', price.market_code,
  price.currency_code, CAST(price.list_amount_minor * 1.82 AS INTEGER),
  CAST(price.list_amount_minor * 1.68 AS INTEGER), price.tax_inclusive,
  'active', '2026-08-02T15:00:00Z', 'usr_catalogue_system'
FROM variant_prices price
WHERE price.variant_id GLOB 'var_market_[0-9][0-9][0-9][0-9]'
   OR price.variant_id GLOB 'var_extra_[0-9][0-9][0-9][0-9]'
   OR price.variant_id GLOB 'var_complete_[0-9][0-9][0-9][0-9]'
   OR (price.variant_id GLOB 'var_mass_[0-9][0-9][0-9][0-9]' AND CAST(substr(price.variant_id, 10) AS INTEGER) <= 311);

INSERT OR IGNORE INTO inventory_levels (
  variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at
)
SELECT lead.variant_id || '_small', lead.location_id,
       MAX(CAST(lead.on_hand * 1.35 AS INTEGER), 36), 0,
       MAX(lead.reorder_threshold, 12), 1, '2026-08-02T15:00:00Z'
FROM inventory_levels lead
WHERE lead.variant_id GLOB 'var_market_[0-9][0-9][0-9][0-9]'
   OR lead.variant_id GLOB 'var_extra_[0-9][0-9][0-9][0-9]'
   OR lead.variant_id GLOB 'var_complete_[0-9][0-9][0-9][0-9]'
   OR (lead.variant_id GLOB 'var_mass_[0-9][0-9][0-9][0-9]' AND CAST(substr(lead.variant_id, 10) AS INTEGER) <= 311)
UNION ALL
SELECT lead.variant_id || '_family', lead.location_id,
       MAX(CAST(lead.on_hand * 0.65 AS INTEGER), 18), 0,
       MAX(CAST(lead.reorder_threshold * 0.8 AS INTEGER), 8), 1,
       '2026-08-02T15:00:00Z'
FROM inventory_levels lead
WHERE lead.variant_id GLOB 'var_market_[0-9][0-9][0-9][0-9]'
   OR lead.variant_id GLOB 'var_extra_[0-9][0-9][0-9][0-9]'
   OR lead.variant_id GLOB 'var_complete_[0-9][0-9][0-9][0-9]'
   OR (lead.variant_id GLOB 'var_mass_[0-9][0-9][0-9][0-9]' AND CAST(substr(lead.variant_id, 10) AS INTEGER) <= 311);

-- Complete the five hand-authored launch products to three variants each.
INSERT OR IGNORE INTO product_variants
  (id, product_id, sku, name, option_values_json, weight_value, weight_unit,
   package_description, status, sort_order, created_at, updated_at)
VALUES
  ('var_alphonso_5kg','prd_alphonso','TRG-MNG-5KG','5 kg family crate','{"pack":"family"}',5,'kg','Ventilated family crate','active',3,'2026-08-02T15:00:00Z','2026-08-02T15:00:00Z'),
  ('var_spinach_500g','prd_spinach','TRG-SPN-500','500 g family bunch','{"pack":"family"}',500,'g','Two breathable bunches','active',2,'2026-08-02T15:00:00Z','2026-08-02T15:00:00Z'),
  ('var_spinach_1kg','prd_spinach','TRG-SPN-1KG','1 kg kitchen box','{"pack":"value"}',1,'kg','Chilled kitchen-size box','active',3,'2026-08-02T15:00:00Z','2026-08-02T15:00:00Z'),
  ('var_ragi_2kg','prd_ragi','TRG-RGI-2KG','2 kg family pack','{"pack":"family"}',2,'kg','Resealable family flour pack','active',3,'2026-08-02T15:00:00Z','2026-08-02T15:00:00Z'),
  ('var_oil_2l','prd_groundnut_oil','TRG-GNO-2L','2 L family tin','{"pack":"family"}',2,'l','Light-protective reusable tin','active',3,'2026-08-02T15:00:00Z','2026-08-02T15:00:00Z'),
  ('var_rajma_1kg','prd_rajma','TRG-RJM-1KG','1 kg family pack','{"pack":"family"}',1,'kg','Resealable family pulse pack','active',2,'2026-08-02T15:00:00Z','2026-08-02T15:00:00Z'),
  ('var_rajma_2kg','prd_rajma','TRG-RJM-2KG','2 kg value pack','{"pack":"value"}',2,'kg','Low-waste value pulse pack','active',3,'2026-08-02T15:00:00Z','2026-08-02T15:00:00Z');

INSERT OR IGNORE INTO variant_prices
  (id, variant_id, market_code, currency_code, list_amount_minor,
   sale_amount_minor, tax_inclusive, status, created_at, created_by)
VALUES
  ('prc_alphonso_5kg','var_alphonso_5kg','IN','INR',399900,369900,1,'active','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('prc_spinach_500g','var_spinach_500g','IN','INR',12900,11900,1,'active','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('prc_spinach_1kg','var_spinach_1kg','IN','INR',23900,21900,1,'active','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('prc_ragi_2kg','var_ragi_2kg','IN','INR',49900,45900,1,'active','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('prc_oil_2l','var_oil_2l','IN','INR',149900,139900,1,'active','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('prc_rajma_1kg','var_rajma_1kg','IN','INR',36900,34900,1,'active','2026-08-02T15:00:00Z','usr_catalogue_system'),
  ('prc_rajma_2kg','var_rajma_2kg','IN','INR',69900,64900,1,'active','2026-08-02T15:00:00Z','usr_catalogue_system');

INSERT OR IGNORE INTO inventory_levels
  (variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at)
VALUES
  ('var_alphonso_5kg','loc_mumbai',24,0,8,1,'2026-08-02T15:00:00Z'),
  ('var_spinach_500g','loc_mumbai',90,0,20,1,'2026-08-02T15:00:00Z'),
  ('var_spinach_1kg','loc_mumbai',42,0,12,1,'2026-08-02T15:00:00Z'),
  ('var_ragi_2kg','loc_mumbai',85,0,18,1,'2026-08-02T15:00:00Z'),
  ('var_oil_2l','loc_mumbai',28,0,8,1,'2026-08-02T15:00:00Z'),
  ('var_rajma_1kg','loc_mumbai',65,0,15,1,'2026-08-02T15:00:00Z'),
  ('var_rajma_2kg','loc_mumbai',34,0,10,1,'2026-08-02T15:00:00Z');
"""


def main() -> None:
    seed = SEED_PATH.read_text(encoding="utf-8")
    start, end, fixture_block = locate_block(seed)
    fixture_block = CLEANUP_PATTERN.sub("", fixture_block)

    repeatable_fixture = make_repeatable(fixture_block)
    cleanup = (
        "-- Keep migrated fixture search rows singular during development seeding.\n"
        "DELETE FROM search_products\n"
        "WHERE product_id LIKE 'prd_market_%' OR product_id LIKE 'prd_extra_%';\n\n"
    )
    first_line_end = repeatable_fixture.index("\n") + 1
    repeatable_fixture = (
        repeatable_fixture[:first_line_end]
        + cleanup
        + repeatable_fixture[first_line_end:]
    )
    SEED_PATH.write_text(
        seed[:start] + repeatable_fixture + seed[end:], encoding="utf-8", newline="\n"
    )

    migration = HEADER + make_migration_block(fixture_block) + VARIANTS
    MIGRATION_PATH.write_text(migration, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

-- 0059_restore_demo_catalogue: restore the preferred catalogue presentation.
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

-- Comprehensive organic-market catalogue expansion
-- Twenty departments and
-- eighty focused subcategories cover food, pantry, wellbeing, home and garden.
-- Each subcategory carries eight real catalogue products with variants, prices,
-- stock, search data and editable published versions.
DROP TABLE IF EXISTS market_catalogue_sections;
CREATE TABLE market_catalogue_sections (
  n INTEGER PRIMARY KEY,
  department_order INTEGER NOT NULL,
  department_name TEXT NOT NULL,
  department_slug TEXT NOT NULL,
  section_order INTEGER NOT NULL,
  section_name TEXT NOT NULL,
  section_slug TEXT NOT NULL,
  products_json TEXT NOT NULL
);

INSERT INTO market_catalogue_sections VALUES
  (1,1,'Fresh Fruits','fruits',1,'Tropical Fruits','tropical-fruits','["Kesar Mango","Dasheri Mango","Papaya","Pineapple","Dragon Fruit","Passion Fruit","Custard Apple","Sapota"]'),
  (2,1,'Fresh Fruits','fruits',2,'Citrus Fruits','citrus-fruits','["Nagpur Orange","Sweet Lime","Kinnow","Grapefruit","Eureka Lemon","Kagzi Lime","Pomelo","Galgal"]'),
  (3,1,'Fresh Fruits','fruits',3,'Berries and Small Fruits','berries-small-fruits','["Strawberry","Cape Gooseberry","Mulberry","Jamun","Karonda","Phalsa","Raspberry","Blueberry"]'),
  (4,1,'Fresh Fruits','fruits',4,'Melons and Orchard Fruits','melons-orchard-fruits','["Watermelon","Muskmelon","Kashmiri Apple","Green Pear","White Guava","Pomegranate","Fresh Fig","Indian Jujube"]'),
  (5,2,'Fresh Vegetables','vegetables',1,'Leafy Vegetables','leafy-vegetables','["Mature Spinach","Red Amaranth","Green Amaranth","Mustard Greens","Fenugreek Leaves","Bathua Greens","Malabar Spinach","Sorrel Leaves"]'),
  (6,2,'Fresh Vegetables','vegetables',2,'Roots and Tubers','roots-tubers','["Red Carrot","Beetroot","White Radish","Purple Sweet Potato","Baby Potato","Elephant Yam","Taro Root","Fresh Turmeric Root"]'),
  (7,2,'Fresh Vegetables','vegetables',3,'Gourds and Squashes','gourds-squashes','["Bottle Gourd","Ridge Gourd","Bitter Gourd","Snake Gourd","Ivy Gourd","Ash Gourd","Yellow Pumpkin","Zucchini"]'),
  (8,2,'Fresh Vegetables','vegetables',4,'Cruciferous and Stem Vegetables','cruciferous-stem-vegetables','["Cauliflower","Green Cabbage","Red Cabbage","Broccoli","Kohlrabi","Brussels Sprouts","Celery","Leek"]'),
  (9,3,'Fresh Herbs and Aromatics','herbs-aromatics',1,'Culinary Herbs','culinary-herbs','["Coriander Bunch","Mint Bunch","Fresh Dill","Fresh Basil","Fresh Oregano","Fresh Thyme","Fresh Rosemary","Fresh Parsley"]'),
  (10,3,'Fresh Herbs and Aromatics','herbs-aromatics',2,'Microgreens','microgreens','["Radish Microgreens","Mustard Microgreens","Sunflower Shoots","Pea Shoots","Broccoli Microgreens","Beet Microgreens","Amaranth Microgreens","Coriander Microgreens"]'),
  (11,3,'Fresh Herbs and Aromatics','herbs-aromatics',3,'Edible Flowers','edible-flowers','["Marigold Petals","Rose Petals","Nasturtium Flowers","Butterfly Pea Flowers","Hibiscus Flowers","Banana Blossoms","Moringa Flowers","Pumpkin Blossoms"]'),
  (12,3,'Fresh Herbs and Aromatics','herbs-aromatics',4,'Fresh Aromatics','fresh-aromatics','["Fresh Ginger","Fresh Garlic","Green Chilli","Birds Eye Chilli","Lemongrass","Fresh Curry Leaves","Spring Onion","Fresh Galangal"]'),
  (13,4,'Rice, Grains and Millets','staple-grains',1,'Rice Varieties','rice-varieties','["Brown Basmati Rice","Red Rice","Black Rice","Gobindobhog Rice","Sona Masoori Rice","Kolam Rice","Navara Rice","Hand Pounded Rice"]'),
  (14,4,'Rice, Grains and Millets','staple-grains',2,'Wheat and Barley','wheat-barley','["Khapli Wheat","Sharbati Wheat","Lokwan Wheat","Emmer Wheat Berries","Pearl Barley","Hulless Barley","Wheat Dalia","Barley Dalia"]'),
  (15,4,'Rice, Grains and Millets','staple-grains',3,'Millets','millets','["Whole Ragi","Whole Jowar","Whole Bajra","Foxtail Millet","Little Millet","Kodo Millet","Barnyard Millet","Proso Millet"]'),
  (16,4,'Rice, Grains and Millets','staple-grains',4,'Ancient and Alternative Grains','ancient-alternative-grains','["Amaranth Grain","Buckwheat Groats","Quinoa","Job Tears","Sama Rice","Sorghum Grits","Corn Grits","Rolled Barley"]'),
  (17,5,'Pulses and Legumes','pulses-legumes',1,'Lentils and Dals','lentils-dals','["Toor Dal","Moong Dal","Masoor Dal","Chana Dal","Urad Dal","Moong Chilka Dal","Masoor Chilka Dal","Urad Chilka Dal"]'),
  (18,5,'Pulses and Legumes','pulses-legumes',2,'Beans','beans','["Kashmiri Rajma","Chitra Rajma","Black Eyed Beans","Moth Beans","Adzuki Beans","White Beans","Lima Beans","Hyacinth Beans"]'),
  (19,5,'Pulses and Legumes','pulses-legumes',3,'Chickpeas','chickpeas','["Kabuli Chickpeas","Desi Black Chickpeas","Green Chickpeas","Brown Chickpeas","Roasted Chickpeas","Split Chickpeas","Sprouted Chickpeas","Chickpea Grits"]'),
  (20,5,'Pulses and Legumes','pulses-legumes',4,'Peas and Specialty Pulses','peas-specialty-pulses','["Yellow Peas","Green Peas Dried","Horse Gram","Whole Green Moong","Whole Black Urad","Whole Masoor","Cowpeas","Pigeon Peas Whole"]'),
  (21,6,'Flours and Baking','flours-baking',1,'Wheat Flours','wheat-flours','["Whole Wheat Atta","Khapli Wheat Atta","Sharbati Atta","Multigrain Atta","Whole Wheat Bread Flour","Durum Wheat Flour","Wheat Bran","Fine Semolina"]'),
  (22,6,'Flours and Baking','flours-baking',2,'Millet Flours','millet-flours','["Ragi Flour","Jowar Flour","Bajra Flour","Foxtail Millet Flour","Kodo Millet Flour","Barnyard Millet Flour","Little Millet Flour","Proso Millet Flour"]'),
  (23,6,'Flours and Baking','flours-baking',3,'Gluten Free Flours','gluten-free-flours','["Brown Rice Flour","Chickpea Flour","Buckwheat Flour","Amaranth Flour","Corn Flour","Tapioca Flour","Coconut Flour","Green Banana Flour"]'),
  (24,6,'Flours and Baking','flours-baking',4,'Specialty Baking Ingredients','specialty-baking','["Almond Meal","Flaxseed Meal","Cocoa Powder","Cacao Nibs","Baking Soda","Natural Vanilla Powder","Arrowroot Starch","Dry Active Yeast"]'),
  (25,7,'Oils and Cooking Fats','oils-cooking-fats',1,'Cold Pressed Speciality Oils','cold-pressed-speciality-oils','["Cold Pressed Mustard Oil","Cold Pressed Sesame Oil","Cold Pressed Coconut Oil","Cold Pressed Sunflower Oil","Cold Pressed Safflower Oil","Cold Pressed Flaxseed Oil","Cold Pressed Niger Seed Oil","Cold Pressed Rice Bran Oil"]'),
  (26,7,'Oils and Cooking Fats','oils-cooking-fats',2,'Traditional Cooking Fats','traditional-cooking-fats','["A2 Cow Ghee","Buffalo Ghee","Cultured Cow Ghee","Bilona Ghee","Coconut Ghee Blend","Grass Fed Butter","White Butter","Cooking Coconut Cream"]'),
  (27,7,'Oils and Cooking Fats','oils-cooking-fats',3,'Seed Oils','seed-oils','["Pumpkin Seed Oil","Hemp Seed Oil","Watermelon Seed Oil","Black Seed Oil","Perilla Seed Oil","Poppy Seed Oil","Chia Seed Oil","Grape Seed Oil"]'),
  (28,7,'Oils and Cooking Fats','oils-cooking-fats',4,'Nut Oils','nut-oils','["Almond Oil Culinary","Walnut Oil","Cashew Oil","Hazelnut Oil","Pistachio Oil","Macadamia Oil","Peanut Oil Roasted","Apricot Kernel Oil"]'),
  (29,8,'Spices and Seasonings','spices-seasonings',1,'Whole Spices','whole-spices','["Cumin Seeds","Coriander Seeds","Black Peppercorns","Green Cardamom","Black Cardamom","Cloves","Cinnamon Sticks","Fennel Seeds"]'),
  (30,8,'Spices and Seasonings','spices-seasonings',2,'Ground Spices','ground-spices','["Turmeric Powder","Coriander Powder","Cumin Powder","Black Pepper Powder","Dry Ginger Powder","Garlic Powder","Onion Powder","Fennel Powder"]'),
  (31,8,'Spices and Seasonings','spices-seasonings',3,'Spice Blends','spice-blends','["Garam Masala","Sambar Masala","Rasam Powder","Chaat Masala","Pav Bhaji Masala","Kitchen King Masala","Biryani Masala","Panch Phoron"]'),
  (32,8,'Spices and Seasonings','spices-seasonings',4,'Chillies and Peppers','chillies-peppers','["Kashmiri Chilli Powder","Guntur Chilli Powder","Byadgi Chilli","Bhut Jolokia Flakes","Dried Red Chillies","Green Peppercorns","Long Pepper","Cubeb Pepper"]'),
  (33,9,'Natural Sweeteners','natural-sweeteners',1,'Jaggery','jaggery','["Cane Jaggery Block","Jaggery Powder","Palm Jaggery","Coconut Jaggery","Date Palm Jaggery","Liquid Jaggery","Spiced Jaggery Bites","Jaggery Cubes"]'),
  (34,9,'Natural Sweeteners','natural-sweeteners',2,'Honey','honey','["Wild Forest Honey","Mustard Blossom Honey","Litchi Honey","Jamun Honey","Himalayan Multifloral Honey","Ajwain Honey","Eucalyptus Honey","Raw Comb Honey"]'),
  (35,9,'Natural Sweeteners','natural-sweeteners',3,'Syrups and Nectar','syrups-nectar','["Date Syrup","Coconut Nectar","Maple Syrup","Agave Nectar","Carob Syrup","Molasses","Rice Malt Syrup","Palm Nectar"]'),
  (36,9,'Natural Sweeteners','natural-sweeteners',4,'Natural Sugars','natural-sugars','["Raw Cane Sugar","Muscovado Sugar","Coconut Sugar","Date Sugar","Palm Sugar","Demerara Sugar","Rock Sugar","Stevia Leaf Powder"]'),
  (37,10,'Nuts, Seeds and Dried Fruit','nuts-seeds-dried-fruit',1,'Nuts','nuts','["Kashmiri Almonds","Walnuts","Cashews","Pistachios","Hazelnuts","Brazil Nuts","Pecans","Macadamia Nuts"]'),
  (38,10,'Nuts, Seeds and Dried Fruit','nuts-seeds-dried-fruit',2,'Seeds','seeds','["Pumpkin Seeds","Sunflower Seeds","Flax Seeds","Chia Seeds","White Sesame Seeds","Black Sesame Seeds","Hemp Hearts","Watermelon Seeds"]'),
  (39,10,'Nuts, Seeds and Dried Fruit','nuts-seeds-dried-fruit',3,'Dried Fruits','dried-fruits','["Medjool Dates","Black Raisins","Golden Raisins","Dried Apricots","Dried Figs","Dried Cranberries","Dried Mulberries","Dried Prunes"]'),
  (40,10,'Nuts, Seeds and Dried Fruit','nuts-seeds-dried-fruit',4,'Trail Mixes','trail-mixes','["Classic Nut Trail Mix","Seed and Berry Mix","Spiced Indian Trail Mix","Cacao Energy Mix","Himalayan Fruit Mix","Roasted Seed Mix","Kids Fruit and Nut Mix","Unsalted Trek Mix"]'),
  (41,11,'Breakfast and Spreads','breakfast-spreads',1,'Cereals and Porridge','cereals-porridge','["Rolled Oats","Steel Cut Oats","Millet Porridge Mix","Ragi Porridge Mix","Barley Porridge","Red Rice Flakes","Quinoa Flakes","Multigrain Dalia"]'),
  (42,11,'Breakfast and Spreads','breakfast-spreads',2,'Granola and Muesli','granola-muesli','["Almond Honey Granola","Cacao Millet Granola","Fruit and Seed Muesli","No Sugar Muesli","Coconut Granola","Ragi Crunch Granola","Quinoa Nut Granola","Spiced Apple Muesli"]'),
  (43,11,'Breakfast and Spreads','breakfast-spreads',3,'Nut and Seed Spreads','nut-seed-spreads','["Smooth Peanut Butter","Crunchy Peanut Butter","Almond Butter","Cashew Butter","Tahini","Sunflower Seed Butter","Hazelnut Cacao Spread","Mixed Nut Butter"]'),
  (44,11,'Breakfast and Spreads','breakfast-spreads',4,'Traditional Breakfast Mixes','traditional-breakfast-mixes','["Idli Batter Mix","Dosa Batter Mix","Ragi Dosa Mix","Adai Mix","Poha Breakfast Mix","Upma Mix","Millet Pongal Mix","Moong Cheela Mix"]'),
  (45,12,'Pantry and Condiments','pantry-condiments',1,'Sauces and Chutneys','sauces-chutneys','["Tomato Chilli Sauce","Green Chilli Sauce","Tamarind Date Chutney","Mint Coriander Chutney","Garlic Chutney","Peanut Chutney","Mango Chutney","Coconut Chutney Powder"]'),
  (46,12,'Pantry and Condiments','pantry-condiments',2,'Pickles','pickles','["Raw Mango Pickle","Lemon Pickle","Mixed Vegetable Pickle","Green Chilli Pickle","Garlic Pickle","Gongura Pickle","Bamboo Shoot Pickle","Amla Pickle"]'),
  (47,12,'Pantry and Condiments','pantry-condiments',3,'Salt and Seasoning','salt-seasoning','["Pink Rock Salt","Sea Salt","Black Salt","Smoked Salt","Herb Salt","Garlic Salt","Celery Salt","Mineral Salt Flakes"]'),
  (48,12,'Pantry and Condiments','pantry-condiments',4,'Vinegars and Ferments','vinegars-ferments','["Apple Cider Vinegar","Coconut Vinegar","Sugarcane Vinegar","Rice Vinegar","Kombucha Vinegar","Ginger Vinegar","Raw Mango Vinegar","Balsamic Style Vinegar"]'),
  (49,13,'Snacks and Treats','snacks-treats',1,'Savoury Snacks','savoury-snacks','["Roasted Makhana","Masala Peanuts","Roasted Chana","Millet Chivda","Jowar Puffs","Bajra Namkeen","Banana Chips","Sweet Potato Chips"]'),
  (50,13,'Snacks and Treats','snacks-treats',2,'Sweet Snacks','sweet-snacks','["Sesame Jaggery Chikki","Peanut Chikki","Ragi Laddoo","Date Nut Bites","Coconut Jaggery Bites","Dry Fruit Laddoo","Amaranth Chikki","Til Rewari"]'),
  (51,13,'Snacks and Treats','snacks-treats',3,'Crackers and Crisps','crackers-crisps','["Ragi Crackers","Seed Crackers","Whole Wheat Mathri","Millet Khakhra","Chickpea Crisps","Rice Papad","Lentil Crackers","Flaxseed Lavash"]'),
  (52,13,'Snacks and Treats','snacks-treats',4,'Energy Bars','energy-bars','["Date Almond Bar","Peanut Cacao Bar","Ragi Energy Bar","Seed Protein Bar","Coconut Cashew Bar","Fig Walnut Bar","Apricot Millet Bar","Coffee Cacao Bar"]'),
  (53,14,'Tea, Coffee and Beverages','tea-coffee-beverages',1,'Tea','tea','["Assam Black Tea","Darjeeling First Flush","Nilgiri Black Tea","Kangra Green Tea","White Tea","Oolong Tea","Masala Chai Blend","Kashmiri Kahwa"]'),
  (54,14,'Tea, Coffee and Beverages','tea-coffee-beverages',2,'Coffee','coffee','["Arabica Coffee Beans","Robusta Coffee Beans","Monsoon Malabar Coffee","Filter Coffee Blend","Single Estate Coffee","Cold Brew Coffee","Decaf Arabica Coffee","Coffee Drip Bags"]'),
  (55,14,'Tea, Coffee and Beverages','tea-coffee-beverages',3,'Herbal Infusions','herbal-infusions','["Tulsi Infusion","Lemongrass Infusion","Hibiscus Infusion","Moringa Infusion","Ginger Turmeric Infusion","Chamomile Infusion","Butterfly Pea Infusion","Peppermint Infusion"]'),
  (56,14,'Tea, Coffee and Beverages','tea-coffee-beverages',4,'Drink Mixes','drink-mixes','["Raw Cacao Drink Mix","Turmeric Latte Mix","Ragi Malt","Sattu Drink Mix","Aam Panna Mix","Jaljeera Mix","Beetroot Latte Mix","Spiced Almond Drink Mix"]'),
  (57,15,'Dairy and Farm Fresh','dairy-farm-fresh',1,'Milk and Cream','milk-cream','["A2 Cow Milk","Buffalo Milk","Cow Milk","Goat Milk","Fresh Cream","Cultured Buttermilk","Spiced Buttermilk","Fresh Malai"]'),
  (58,15,'Dairy and Farm Fresh','dairy-farm-fresh',2,'Yoghurt and Cultured Dairy','yoghurt-cultured-dairy','["Natural Cow Yoghurt","Buffalo Yoghurt","Greek Style Yoghurt","Mango Yoghurt","Probiotic Yoghurt","Hung Curd","Fresh Lassi","Mango Lassi"]'),
  (59,15,'Dairy and Farm Fresh','dairy-farm-fresh',3,'Cheese and Paneer','cheese-paneer','["Fresh Cow Paneer","Buffalo Paneer","Malai Paneer","Smoked Paneer","Cheddar Cheese","Gouda Cheese","Feta Style Cheese","Mozzarella Cheese"]'),
  (60,15,'Dairy and Farm Fresh','dairy-farm-fresh',4,'Ghee and Butter','ghee-butter','["Cow Milk Ghee","Buffalo Milk Ghee","Cultured Ghee","A2 Bilona Ghee","Salted Butter","Unsalted Butter","Cultured Butter","Herb Butter"]'),
  (61,16,'Plant Based Foods','plant-based-foods',1,'Plant Milks','plant-milks','["Almond Milk","Oat Milk","Coconut Milk Beverage","Cashew Milk","Millet Milk","Rice Milk","Soy Milk","Peanut Milk"]'),
  (62,16,'Plant Based Foods','plant-based-foods',2,'Tofu and Fermented Protein','tofu-fermented-protein','["Firm Tofu","Silken Tofu","Smoked Tofu","Herb Tofu","Soy Tempeh","Chickpea Tempeh","Black Bean Tempeh","Fermented Tofu"]'),
  (63,16,'Plant Based Foods','plant-based-foods',3,'Vegan Spreads and Cheese','vegan-spreads-cheese','["Cashew Cheese Spread","Almond Feta","Coconut Yoghurt","Vegan Herb Butter","Sunflower Seed Pate","Smoked Cashew Cheese","Vegan Mayonnaise","Coconut Cream Cheese"]'),
  (64,16,'Plant Based Foods','plant-based-foods',4,'Plant Protein','plant-protein','["Pea Protein Powder","Hemp Protein Powder","Brown Rice Protein","Pumpkin Seed Protein","Sattu Protein Mix","Sprouted Moong Protein","Soy Protein Chunks","Jackfruit Protein Mix"]'),
  (65,17,'Bakery and Breads','bakery-breads',1,'Artisan Breads','artisan-breads','["Whole Wheat Sourdough","Multigrain Sourdough","Ragi Sourdough","Seeded Rye Bread","Khapli Wheat Bread","Millet Sandwich Bread","Olive Herb Bread","Walnut Raisin Bread"]'),
  (66,17,'Bakery and Breads','bakery-breads',2,'Flatbreads and Wraps','flatbreads-wraps','["Whole Wheat Roti Pack","Jowar Bhakri","Bajra Roti","Ragi Roti","Multigrain Wraps","Spinach Wraps","Beetroot Wraps","Khapli Thepla"]'),
  (67,17,'Bakery and Breads','bakery-breads',3,'Cookies and Biscuits','cookies-biscuits','["Ragi Cookies","Jowar Cookies","Whole Wheat Jaggery Biscuits","Almond Cookies","Coconut Cookies","Seeded Crackle Biscuits","Oat Raisin Cookies","Ginger Millet Cookies"]'),
  (68,17,'Bakery and Breads','bakery-breads',4,'Cakes and Tea Bakes','cakes-tea-bakes','["Banana Walnut Loaf","Carrot Jaggery Cake","Ragi Chocolate Cake","Lemon Millet Cake","Date Almond Loaf","Orange Semolina Cake","Coconut Tea Cake","Apple Cinnamon Loaf"]'),
  (69,18,'Natural Personal Care','natural-personal-care',1,'Skin Care','skin-care','["Rose Face Cleanser","Neem Face Wash","Aloe Face Gel","Turmeric Face Mask","Kumkumadi Face Oil","Shea Body Butter","Rose Water Toner","Herbal Lip Balm"]'),
  (70,18,'Natural Personal Care','natural-personal-care',2,'Hair Care','hair-care','["Amla Hair Oil","Bhringraj Hair Oil","Herbal Shampoo","Neem Shampoo","Hibiscus Conditioner","Shikakai Powder","Reetha Powder","Herbal Hair Mask"]'),
  (71,18,'Natural Personal Care','natural-personal-care',3,'Bath and Body','bath-body','["Neem Bath Soap","Sandalwood Soap","Charcoal Soap","Rose Soap","Handmade Body Wash","Herbal Hand Wash","Natural Deodorant","Foot Care Balm"]'),
  (72,18,'Natural Personal Care','natural-personal-care',4,'Oral Care','oral-care','["Herbal Toothpaste","Neem Tooth Powder","Bamboo Toothbrush","Copper Tongue Cleaner","Clove Mouth Rinse","Herbal Gum Oil","Miswak Sticks","Natural Dental Floss"]'),
  (73,19,'Natural Home Care','natural-home-care',1,'Laundry Care','laundry-care','["Soapnut Laundry Liquid","Natural Laundry Powder","Delicate Wash","Laundry Bar","Fabric Rinse","Stain Remover","Wool Wash","Laundry Soap Berries"]'),
  (74,19,'Natural Home Care','natural-home-care',2,'Dish Care','dish-care','["Natural Dishwash Liquid","Dishwash Bar","Dishwasher Powder","Copper Cleaner","Coconut Scrub Pad","Bottle Cleaning Powder","Lemon Dish Gel","Enzyme Dish Cleaner"]'),
  (75,19,'Natural Home Care','natural-home-care',3,'Surface Care','surface-care','["Natural Floor Cleaner","Kitchen Cleaner","Bathroom Cleaner","Glass Cleaner","Wood Surface Oil","Stone Cleaner","Multipurpose Cleaner","Enzyme Drain Cleaner"]'),
  (76,19,'Natural Home Care','natural-home-care',4,'Home Fragrance and Pest Care','home-fragrance-pest-care','["Citronella Incense","Natural Mosquito Spray","Neem Pest Spray","Cedar Wardrobe Blocks","Herbal Room Spray","Beeswax Candle","Camphor Tablets","Lemongrass Diffuser Oil"]'),
  (77,20,'Organic Gardening','organic-gardening',1,'Vegetable and Herb Seeds','vegetable-herb-seeds','["Tomato Seeds","Okra Seeds","Spinach Seeds","Coriander Seeds for Planting","Chilli Seeds","Bottle Gourd Seeds","Carrot Seeds","Basil Seeds for Planting"]'),
  (78,20,'Organic Gardening','organic-gardening',2,'Soil and Compost','soil-compost','["Vermicompost","Farmyard Compost","Leaf Compost","Coco Peat Block","Potting Soil Mix","Neem Cake Powder","Mustard Cake Fertiliser","Biochar Soil Blend"]'),
  (79,20,'Organic Gardening','organic-gardening',3,'Plant Nutrition and Protection','plant-nutrition-protection','["Seaweed Plant Tonic","Panchagavya Concentrate","Jeevamrit Concentrate","Neem Oil Garden Spray","Trichoderma Bio Fungicide","Sticky Pest Traps","Diatomaceous Earth","Micronutrient Plant Mix"]'),
  (80,20,'Organic Gardening','organic-gardening',4,'Garden Tools and Supplies','garden-tools-supplies','["Hand Trowel","Hand Cultivator","Pruning Shears","Coconut Coir Pots","Bamboo Plant Labels","Natural Jute Twine","Seedling Tray","Watering Can"]');

INSERT OR IGNORE INTO categories (
  id, internal_name, name, slug, parent_id, path, level, sort_order, status,
  visibility, short_description, hero_eyebrow, hero_title, hero_description,
  theme_key, product_assignment_mode, product_rule_json, published_version_id,
  seo_title, seo_description, created_at, created_by, updated_at, updated_by
)
SELECT
  'cat_market_' || department_slug,
  department_name || ' department',
  department_name,
  department_slug,
  NULL,
  '/' || department_slug,
  0,
  department_order + 10,
  'published',
  'public',
  'Explore our complete ' || lower(department_name) || ' range, selected for traceability, quality and practical everyday use.',
  'The complete market',
  department_name,
  'A broad collection of ' || lower(department_name) || ', organised so the full range stays easy to browse.',
  CASE (department_order % 5)
    WHEN 0 THEN 'terracotta' WHEN 1 THEN 'sage' WHEN 2 THEN 'forest'
    WHEN 3 THEN 'charcoal' ELSE 'gold'
  END,
  'manual',
  NULL,
  'ctv_market_' || department_slug || '_1',
  department_name || ' | True Grit Organic Market',
  'Shop traceable ' || lower(department_name) || ' from the True Grit organic market.',
  '2025-06-01T08:00:00Z',
  'usr_catalogue_system',
  '2026-07-30T08:00:00Z',
  'usr_catalogue_system'
FROM market_catalogue_sections
GROUP BY department_order, department_name, department_slug;

INSERT OR IGNORE INTO categories (
  id, internal_name, name, slug, parent_id, path, level, sort_order, status,
  visibility, short_description, hero_eyebrow, hero_title, hero_description,
  theme_key, product_assignment_mode, product_rule_json, published_version_id,
  seo_title, seo_description, created_at, created_by, updated_at, updated_by
)
SELECT
  'cat_market_' || section_slug,
  section_name || ' section',
  section_name,
  section_slug,
  'cat_market_' || department_slug,
  '/' || department_slug || '/' || section_slug,
  1,
  section_order,
  'published',
  'public',
  'A considered selection of ' || lower(section_name) || ' for a well-stocked organic home.',
  department_name,
  section_name,
  'Browse the full ' || lower(section_name) || ' range with clear pricing, stock and product information.',
  CASE (n % 5)
    WHEN 0 THEN 'terracotta' WHEN 1 THEN 'sage' WHEN 2 THEN 'forest'
    WHEN 3 THEN 'charcoal' ELSE 'gold'
  END,
  'manual',
  NULL,
  'ctv_market_' || section_slug || '_1',
  section_name || ' | True Grit Organic Market',
  'Shop ' || lower(section_name) || ' online with traceable sourcing and transparent product details.',
  '2025-06-01T08:00:00Z',
  'usr_catalogue_system',
  '2026-07-30T08:00:00Z',
  'usr_catalogue_system'
FROM market_catalogue_sections;

INSERT OR IGNORE INTO category_versions (
  id, category_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  'ctv_market_' || department_slug || '_1',
  'cat_market_' || department_slug,
  1,
  json_object('blocks', json_array()),
  'Initial comprehensive department',
  'published',
  '2025-06-01T08:00:00Z',
  'usr_catalogue_system',
  '2026-07-30T07:30:00Z',
  'usr_catalogue_system',
  '2026-07-30T08:00:00Z'
FROM market_catalogue_sections
GROUP BY department_slug
UNION ALL
SELECT
  'ctv_market_' || section_slug || '_1',
  'cat_market_' || section_slug,
  1,
  json_object('blocks', json_array()),
  'Initial comprehensive category',
  'published',
  '2025-06-01T08:00:00Z',
  'usr_catalogue_system',
  '2026-07-30T07:30:00Z',
  'usr_catalogue_system',
  '2026-07-30T08:00:00Z'
FROM market_catalogue_sections;

DROP TABLE IF EXISTS market_catalogue_products;
CREATE TABLE market_catalogue_products AS
SELECT
  ((sections.n - 1) * 8) + CAST(products.key AS INTEGER) + 1 AS product_number,
  sections.department_order,
  sections.department_name,
  sections.department_slug,
  sections.section_name,
  sections.section_slug,
  CAST(products.key AS INTEGER) + 1 AS product_order,
  CAST(products.value AS TEXT) AS product_name,
  'organic-' ||
    lower(replace(replace(replace(CAST(products.value AS TEXT), ' ', '-'), '&', 'and'), '/', '-'))
    AS product_slug
FROM market_catalogue_sections sections, json_each(sections.products_json) products;

INSERT OR IGNORE INTO products (
  id, internal_name, name, slug, product_type, farm_id, status,
  short_description, published_version_id, seo_title, seo_description,
  created_at, created_by, updated_at, updated_by
)
SELECT
  printf('prd_market_%04d', product_number),
  product_name || ' catalogue product',
  'Organic ' || product_name,
  product_slug,
  replace(section_slug, '-', '_'),
  NULL,
  'published',
  product_name || ' selected for dependable quality, clear provenance and everyday use.',
  printf('pvr_market_%04d_1', product_number),
  'Organic ' || product_name || ' | Buy Online',
  'Shop organic ' || lower(product_name) || ' with transparent sourcing, current stock and secure delivery.',
  datetime('2025-07-01T08:00:00Z', printf('+%d days', (product_number * 17) % 365)),
  'usr_catalogue_system',
  datetime('2025-07-01T08:00:00Z', printf('+%d days', (product_number * 17) % 365)),
  'usr_catalogue_system'
FROM market_catalogue_products;

INSERT OR IGNORE INTO product_versions (
  id, product_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  printf('pvr_market_%04d_1', product_number),
  printf('prd_market_%04d', product_number),
  1,
  json_object(
    'blocks', json_array(
      json_object(
        'id', printf('blk_market_product_%04d_overview', product_number),
        'type', 'rich_text',
        'version', 1,
        'enabled', json('true'),
        'props', json_object('paragraphs', json_array(
          'Our organic ' || lower(product_name) || ' is selected for clean flavour, dependable quality and practical everyday use.',
          'Store in a cool, dry place or refrigerate when fresh. Check the pack label for the current lot, origin and best-before guidance.'
        ))
      )
    )
  ),
  'Initial comprehensive catalogue listing',
  'published',
  datetime('2025-07-01T08:00:00Z', printf('+%d days', (product_number * 17) % 365)),
  'usr_catalogue_system',
  datetime('2025-07-01T08:30:00Z', printf('+%d days', (product_number * 17) % 365)),
  'usr_catalogue_system',
  datetime('2025-07-01T09:00:00Z', printf('+%d days', (product_number * 17) % 365))
FROM market_catalogue_products;

INSERT OR IGNORE INTO product_categories (
  product_id, category_id, is_primary, sort_order, assigned_at, assigned_by
)
SELECT
  printf('prd_market_%04d', product_number),
  'cat_market_' || section_slug,
  1,
  product_order,
  '2026-07-30T08:00:00Z',
  'usr_catalogue_system'
FROM market_catalogue_products
UNION ALL
SELECT
  printf('prd_market_%04d', product_number),
  'cat_market_' || department_slug,
  0,
  product_number,
  '2026-07-30T08:00:00Z',
  'usr_catalogue_system'
FROM market_catalogue_products;

INSERT OR IGNORE INTO product_variants (
  id, product_id, sku, name, option_values_json, weight_value, weight_unit,
  package_description, status, sort_order, created_at, updated_at
)
SELECT
  printf('var_market_%04d', product_number),
  printf('prd_market_%04d', product_number),
  printf('TGX-%04d', product_number),
  CASE
    WHEN department_order IN (1,2,3) THEN 'Fresh pack'
    WHEN department_order IN (7,14,15,16,18,19) THEN '500 ml pack'
    WHEN department_order = 20 THEN '1 unit'
    ELSE '500 g pack'
  END,
  json_object('pack', 'standard'),
  CASE
    WHEN department_order IN (1,2,3) THEN 500
    WHEN department_order IN (7,14,15,16,18,19) THEN 500
    WHEN department_order = 20 THEN 1
    ELSE 500
  END,
  CASE
    WHEN department_order IN (7,14,15,16,18,19) THEN 'ml'
    WHEN department_order = 20 THEN 'unit'
    ELSE 'g'
  END,
  CASE
    WHEN department_order IN (1,2,3) THEN 'Fresh produce pack'
    WHEN department_order = 20 THEN 'Single retail unit'
    ELSE 'Resealable retail pack'
  END,
  'active',
  1,
  '2026-07-30T08:00:00Z',
  '2026-07-30T08:00:00Z'
FROM market_catalogue_products;

INSERT OR IGNORE INTO variant_prices (
  id, variant_id, market_code, currency_code, list_amount_minor,
  sale_amount_minor, tax_inclusive, status, created_at, created_by
)
SELECT
  printf('prc_market_%04d', product_number),
  printf('var_market_%04d', product_number),
  'IN',
  'INR',
  6900 + ((product_number * 137) % 90000),
  CASE
    WHEN product_number % 7 = 0
      THEN CAST((6900 + ((product_number * 137) % 90000)) * 0.9 AS INTEGER)
    ELSE NULL
  END,
  1,
  'active',
  '2026-07-30T08:00:00Z',
  'usr_catalogue_system'
FROM market_catalogue_products;

INSERT OR IGNORE INTO inventory_levels (
  variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at
)
SELECT
  printf('var_market_%04d', product_number),
  'loc_mumbai',
  25 + ((product_number * 29) % 176),
  product_number % 5,
  12 + (product_number % 19),
  1,
  '2026-07-30T08:00:00Z'
FROM market_catalogue_products;


INSERT OR IGNORE INTO product_tags (product_id, tag_id)
SELECT printf('prd_market_%04d', product_number), 'tag_plant_based'
FROM market_catalogue_products
WHERE department_order NOT IN (15)
UNION ALL
SELECT printf('prd_market_%04d', product_number), 'tag_traditional'
FROM market_catalogue_products
WHERE department_order IN (4,5,6,7,8,9,12,13,14);

INSERT INTO search_products (
  product_id, name, slug, brand_name, farm_name, category_names, keywords,
  short_description
)
SELECT
  printf('prd_market_%04d', product_number),
  'Organic ' || product_name,
  product_slug,
  '',
  CASE
    WHEN department_order BETWEEN 1 AND 3 THEN 'Partner organic farms'
    WHEN department_order BETWEEN 4 AND 10 THEN 'Verified producer network'
    ELSE ''
  END,
  department_name || ', ' || section_name,
  lower(product_name || ' ' || department_name || ' ' || section_name || ' organic natural'),
  product_name || ' selected for dependable quality, clear provenance and everyday use.'
FROM market_catalogue_products;

DROP TABLE market_catalogue_products;
DROP TABLE market_catalogue_sections;

-- Department photography is deliberately shared by each department and its
-- four focused subcategories. Product cards inherit their primary category
-- image until an owner uploads a product-specific photograph in the admin.
UPDATE categories
SET
  hero_image_url = '/banners/categories/' || (
    SELECT COALESCE(parent.slug, categories.slug)
    FROM categories AS current
    LEFT JOIN categories AS parent ON parent.id = current.parent_id
    WHERE current.id = categories.id
  ) || '.webp',
  hero_image_alt = name || ' organic market selection'
WHERE id LIKE 'cat_market_%';

UPDATE page_versions
SET content_json = json_set(
  content_json,
  '$.blocks[1].props.categorySlugs',
  json('[
    "fruits", "vegetables", "staple-grains", "pulses-legumes",
    "flours-baking", "oils-cooking-fats", "spices-seasonings",
    "natural-sweeteners", "nuts-seeds-dried-fruit", "breakfast-spreads",
    "pantry-condiments", "snacks-treats"
  ]'),
  '$.blocks[2].props.productSlugs',
  json('[
    "organic-kesar-mango", "organic-mature-spinach",
    "organic-brown-basmati-rice", "organic-moong-dal",
    "organic-whole-wheat-atta", "organic-cold-pressed-mustard-oil",
    "organic-turmeric-powder", "organic-wild-forest-honey",
    "organic-kashmiri-almonds", "organic-rolled-oats",
    "organic-roasted-makhana", "organic-assam-black-tea"
  ]'),
  '$.blocks[2].props.limit',
  12
)
WHERE page_id = 'pag_home';

-- Additional complete-market departments. These records are normal catalogue
-- entities: each has a published version, categories, variant, INR price,
-- inventory, search data and a direct product image editable from admin.
DROP TABLE IF EXISTS extra_catalogue_sections;
CREATE TABLE extra_catalogue_sections (
  n INTEGER PRIMARY KEY,
  department_order INTEGER NOT NULL,
  department_name TEXT NOT NULL,
  department_slug TEXT NOT NULL,
  section_order INTEGER NOT NULL,
  section_name TEXT NOT NULL,
  section_slug TEXT NOT NULL,
  products_json TEXT NOT NULL
);

INSERT INTO extra_catalogue_sections VALUES
  (1,1,'Frozen and Chilled Foods','frozen-chilled',1,'Frozen Fruits and Vegetables','frozen-fruit-vegetables','["Frozen Green Peas","Frozen Sweet Corn","Frozen Mixed Vegetables","Frozen Mango Cubes","Frozen Strawberry","Frozen Blueberry","Frozen Spinach","Frozen Edamame"]'),
  (2,1,'Frozen and Chilled Foods','frozen-chilled',2,'Frozen Meals and Snacks','frozen-meals-snacks','["Vegetable Momos","Millet Vegetable Patties","Spinach Corn Samosas","Quinoa Khichdi Bowl","Brown Rice Biryani Bowl","Vegetable Curry Bowl","Ragi Idli Pack","Sweet Potato Tikkis"]'),
  (3,2,'Organic Baby and Kids','baby-kids',1,'Baby Food and Porridge','baby-food-porridge','["Rice Moong Baby Cereal","Ragi Banana Porridge","Oats Apple Porridge","Millet Vegetable Porridge","Sprouted Wheat Cereal","Mango Fruit Puree","Apple Pear Puree","Sweet Potato Puree"]'),
  (4,2,'Organic Baby and Kids','baby-kids',2,'Kids Snacks and Drinks','kids-snacks-drinks','["Banana Millet Puffs","Carrot Oat Biscuits","Ragi Cocoa Cookies","Fruit and Nut Mini Bar","Apple Cinnamon Bites","Mango Yoghurt Melts","Kids Sattu Drink","Strawberry Millet Drink"]'),
  (5,3,'Natural Pet Care','pet-care',1,'Dog Food and Treats','dog-food-treats','["Pumpkin Oat Dog Biscuits","Sweet Potato Dog Chews","Chicken Turmeric Dog Treats","Millet Vegetable Dog Meal","Brown Rice Dog Meal","Coconut Dental Chews","Peanut Butter Dog Bites","Moringa Dog Supplement"]'),
  (6,3,'Natural Pet Care','pet-care',2,'Cat Food and Grooming','cat-food-grooming','["Fish Cat Treats","Chicken Cat Bites","Pumpkin Cat Meal","Cat Grass Growing Kit","Neem Pet Shampoo","Oatmeal Pet Wash","Natural Paw Balm","Bamboo Pet Grooming Brush"]'),
  (7,4,'Wellness and Supplements','wellness-supplements',1,'Superfoods and Greens','superfoods-greens','["Moringa Leaf Powder","Spirulina Powder","Wheatgrass Powder","Barley Grass Powder","Amla Powder","Beetroot Powder","Baobab Powder","Acai Berry Powder"]'),
  (8,4,'Wellness and Supplements','wellness-supplements',2,'Herbal Supplements','herbal-supplements','["Ashwagandha Capsules","Triphala Tablets","Giloy Capsules","Brahmi Capsules","Shatavari Capsules","Turmeric Curcumin Capsules","Tulsi Capsules","Neem Leaf Capsules"]'),
  (9,5,'Eco Living Essentials','eco-living',1,'Reusable Kitchen','reusable-kitchen','["Beeswax Food Wrap Set","Organic Cotton Produce Bags","Bamboo Cutlery Set","Coconut Bottle Brush","Natural Dish Scrub Set","Reusable Tea Strainer","Bamboo Drinking Straws","Cotton Kitchen Towels"]'),
  (10,5,'Eco Living Essentials','eco-living',2,'Sustainable Storage','sustainable-storage','["Steel Lunch Box","Glass Pantry Jar Set","Cotton Bread Bag","Reusable Snack Pouches","Bamboo Spice Box","Steel Water Bottle","Natural Fibre Basket","Silicone Freezer Bag"]'),
  (11,6,'Ready to Cook Meals','ready-to-cook',1,'Indian Meal Mixes','indian-meal-mixes','["Vegetable Khichdi Mix","Millet Biryani Mix","Dal Tadka Meal Mix","Sambar Rice Mix","Palak Curry Base","Makhani Curry Base","Coconut Curry Base","Rajma Masala Meal Kit"]'),
  (12,6,'Ready to Cook Meals','ready-to-cook',2,'Instant Breakfast Staples','instant-breakfast-staples','["Instant Idli Mix","Instant Dosa Mix","Millet Upma Mix","Vegetable Poha Mix","Ragi Pancake Mix","Instant Moong Cheela Mix","Oats Uttapam Mix","Quinoa Pongal Mix"]'),
  (13,7,'Global Organic Pantry','global-pantry',1,'Mediterranean Pantry','mediterranean-pantry','["Extra Virgin Olive Oil","Green Olives","Kalamata Olives","Sun Dried Tomatoes","Organic Hummus","Tahini Dressing","Whole Wheat Couscous","Za''atar Seasoning"]'),
  (14,7,'Global Organic Pantry','global-pantry',2,'East Asian Pantry','east-asian-pantry','["Brown Rice Noodles","Buckwheat Soba Noodles","Organic Tamari","White Miso Paste","Red Miso Paste","Toasted Sesame Oil","Nori Seaweed Sheets","Rice Paper Wrappers"]'),
  (15,8,'Fermented and Cultured Foods','fermented-foods',1,'Kombucha and Cultured Drinks','kombucha-cultured-drinks','["Ginger Kombucha","Hibiscus Kombucha","Lemongrass Kombucha","Mango Kombucha","Beet Kvass","Water Kefir","Coconut Kefir","Kanji Drink"]'),
  (16,8,'Fermented and Cultured Foods','fermented-foods',2,'Ferments and Starters','ferments-starters','["Classic Sauerkraut","Beet Sauerkraut","Vegetable Kimchi","Fermented Carrots","Fermented Cucumber","Sourdough Starter","Kombucha SCOBY","Water Kefir Grains"]'),
  (17,9,'Flowers and Puja Essentials','flowers-puja',1,'Fresh Flowers and Petals','fresh-flowers-petals','["Marigold Garland","Jasmine Garland","Fresh Lotus Flowers","Fresh Rose Bunch","Loose Marigold Petals","Loose Rose Petals","Chrysanthemum Bunch","Tuberose Bunch"]'),
  (18,9,'Flowers and Puja Essentials','flowers-puja',2,'Natural Puja Supplies','natural-puja-supplies','["Natural Incense Sticks","Herbal Dhoop Cones","Cotton Puja Wicks","Cow Ghee Diyas","Natural Camphor","Sandalwood Powder","Kumkum Powder","Brass Puja Diya"]'),
  (19,10,'Organic Gift Hampers','gift-hampers',1,'Wellness Gift Hampers','wellness-gift-hampers','["Tea and Honey Hamper","Natural Self Care Hamper","Superfood Starter Hamper","Coffee Lovers Hamper","Healthy Snacking Hamper","Herbal Wellness Hamper","New Parent Care Hamper","Sustainable Home Hamper"]'),
  (20,10,'Organic Gift Hampers','gift-hampers',2,'Festival Gift Hampers','festival-gift-hampers','["Diwali Organic Hamper","Holi Natural Colours Hamper","Raksha Bandhan Hamper","Eid Dry Fruit Hamper","Christmas Pantry Hamper","Harvest Festival Hamper","Wedding Favour Hamper","Corporate Organic Hamper"]');

INSERT OR IGNORE INTO categories (
  id, internal_name, name, slug, parent_id, path, level, sort_order, status,
  visibility, short_description, hero_eyebrow, hero_title, hero_description,
  theme_key, product_assignment_mode, published_version_id, seo_title,
  seo_description, hero_image_url, hero_image_alt, created_at, created_by,
  updated_at, updated_by
)
SELECT
  'cat_extra_' || department_slug, department_name || ' department',
  department_name, department_slug, NULL, '/' || department_slug, 0,
  40 + department_order, 'published', 'public',
  'Explore our complete ' || lower(department_name) || ' range.',
  'More of the market', department_name,
  'A practical collection of ' || lower(department_name) || ' selected for quality and everyday use.',
  CASE (department_order % 4) WHEN 0 THEN 'forest' WHEN 1 THEN 'sage' WHEN 2 THEN 'terracotta' ELSE 'charcoal' END,
  'manual', 'ctv_extra_' || department_slug || '_1',
  department_name || ' | True Grit Organic Market',
  'Shop ' || lower(department_name) || ' with transparent product information.',
  '/banners/categories/' || department_slug || '.webp',
  department_name || ' collection',
  '2026-01-15T08:00:00Z', 'usr_catalogue_system', '2026-07-30T10:00:00Z', 'usr_catalogue_system'
FROM extra_catalogue_sections
GROUP BY department_order, department_name, department_slug;

INSERT OR IGNORE INTO categories (
  id, internal_name, name, slug, parent_id, path, level, sort_order, status,
  visibility, short_description, hero_eyebrow, hero_title, hero_description,
  theme_key, product_assignment_mode, published_version_id, seo_title,
  seo_description, hero_image_url, hero_image_alt, created_at, created_by,
  updated_at, updated_by
)
SELECT
  'cat_extra_' || section_slug, section_name || ' section', section_name,
  section_slug, 'cat_extra_' || department_slug,
  '/' || department_slug || '/' || section_slug, 1, section_order,
  'published', 'public',
  'A focused selection of ' || lower(section_name) || ' with current stock and clear product details.',
  department_name, section_name,
  'Browse ' || lower(section_name) || ' selected for a complete organic marketplace.',
  CASE (n % 4) WHEN 0 THEN 'forest' WHEN 1 THEN 'sage' WHEN 2 THEN 'terracotta' ELSE 'charcoal' END,
  'manual', 'ctv_extra_' || section_slug || '_1',
  section_name || ' | True Grit Organic Market',
  'Shop ' || lower(section_name) || ' online from True Grit.',
  '/banners/categories/' || department_slug || '.webp',
  section_name || ' collection',
  '2026-01-15T08:00:00Z', 'usr_catalogue_system', '2026-07-30T10:00:00Z', 'usr_catalogue_system'
FROM extra_catalogue_sections;

INSERT OR IGNORE INTO category_versions (
  id, category_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  'ctv_extra_' || department_slug || '_1', 'cat_extra_' || department_slug,
  1, json_object('blocks', json_array()), 'Initial expanded department',
  'published', '2026-01-15T08:00:00Z', 'usr_catalogue_system',
  '2026-07-30T09:30:00Z', 'usr_catalogue_system', '2026-07-30T10:00:00Z'
FROM extra_catalogue_sections GROUP BY department_slug
UNION ALL
SELECT
  'ctv_extra_' || section_slug || '_1', 'cat_extra_' || section_slug,
  1, json_object('blocks', json_array()), 'Initial expanded category',
  'published', '2026-01-15T08:00:00Z', 'usr_catalogue_system',
  '2026-07-30T09:30:00Z', 'usr_catalogue_system', '2026-07-30T10:00:00Z'
FROM extra_catalogue_sections;

DROP TABLE IF EXISTS extra_catalogue_products;
CREATE TABLE extra_catalogue_products AS
SELECT
  ((sections.n - 1) * 8) + CAST(items.key AS INTEGER) + 1 AS product_number,
  sections.department_order, sections.department_name, sections.department_slug,
  sections.section_name, sections.section_slug,
  CAST(items.key AS INTEGER) + 1 AS product_order,
  CAST(items.value AS TEXT) AS product_name,
  'organic-' || lower(replace(replace(replace(CAST(items.value AS TEXT), ' ', '-'), '&', 'and'), '/', '-')) AS product_slug
FROM extra_catalogue_sections AS sections, json_each(sections.products_json) AS items;

INSERT OR IGNORE INTO products (
  id, internal_name, name, slug, product_type, status, short_description,
  published_version_id, seo_title, seo_description, image_url, image_alt,
  created_at, created_by, updated_at, updated_by
)
SELECT
  printf('prd_extra_%04d', product_number), product_name || ' catalogue product',
  'Organic ' || product_name, product_slug, replace(section_slug, '-', '_'),
  'published',
  product_name || ' selected for dependable quality and practical everyday use.',
  printf('pvr_extra_%04d_1', product_number),
  'Organic ' || product_name || ' | Buy Online',
  'Shop organic ' || lower(product_name) || ' with current stock and clear product details.',
  '/banners/categories/' || department_slug || '.webp',
  'Organic ' || product_name,
  datetime('2026-01-15T08:00:00Z', printf('+%d days', (product_number * 13) % 190)),
  'usr_catalogue_system',
  datetime('2026-01-15T08:00:00Z', printf('+%d days', (product_number * 13) % 190)),
  'usr_catalogue_system'
FROM extra_catalogue_products;

INSERT OR IGNORE INTO product_versions (
  id, product_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  printf('pvr_extra_%04d_1', product_number),
  printf('prd_extra_%04d', product_number), 1,
  json_object('blocks', json_array(json_object(
    'id', printf('blk_extra_%04d_overview', product_number),
    'type', 'rich_text', 'version', 1, 'enabled', json('true'),
    'props', json_object('paragraphs', json_array(
      'Our organic ' || lower(product_name) || ' is selected for dependable quality and straightforward everyday use.',
      'Review the current pack for ingredient, storage, origin and best-before information.'
    ))
  ))),
  'Initial expanded catalogue listing', 'published',
  '2026-07-30T09:00:00Z', 'usr_catalogue_system', '2026-07-30T09:30:00Z',
  'usr_catalogue_system', '2026-07-30T10:00:00Z'
FROM extra_catalogue_products;

INSERT OR IGNORE INTO product_categories (
  product_id, category_id, is_primary, sort_order, assigned_at, assigned_by
)
SELECT printf('prd_extra_%04d', product_number), 'cat_extra_' || section_slug,
       1, product_order, '2026-07-30T10:00:00Z', 'usr_catalogue_system'
FROM extra_catalogue_products
UNION ALL
SELECT printf('prd_extra_%04d', product_number), 'cat_extra_' || department_slug,
       0, product_number, '2026-07-30T10:00:00Z', 'usr_catalogue_system'
FROM extra_catalogue_products;

INSERT OR IGNORE INTO product_variants (
  id, product_id, sku, name, option_values_json, weight_value, weight_unit,
  package_description, status, sort_order, created_at, updated_at
)
SELECT
  printf('var_extra_%04d', product_number),
  printf('prd_extra_%04d', product_number),
  printf('TGE-%04d', product_number),
  CASE WHEN department_order IN (5,9,10) THEN '1 unit' ELSE 'Standard pack' END,
  json_object('pack', 'standard'),
  CASE WHEN department_order IN (5,9,10) THEN 1 ELSE 500 END,
  CASE WHEN department_order IN (5,9,10) THEN 'unit' ELSE 'g' END,
  CASE WHEN department_order IN (5,9,10) THEN 'Single retail unit' ELSE 'Resealable retail pack' END,
  'active', 1, '2026-07-30T10:00:00Z', '2026-07-30T10:00:00Z'
FROM extra_catalogue_products;

INSERT OR IGNORE INTO variant_prices (
  id, variant_id, market_code, currency_code, list_amount_minor,
  sale_amount_minor, tax_inclusive, status, created_at, created_by
)
SELECT
  printf('prc_extra_%04d', product_number),
  printf('var_extra_%04d', product_number), 'IN', 'INR',
  9900 + ((product_number * 251) % 140000),
  CASE WHEN product_number % 9 = 0
    THEN CAST((9900 + ((product_number * 251) % 140000)) * 0.9 AS INTEGER)
    ELSE NULL END,
  1, 'active', '2026-07-30T10:00:00Z', 'usr_catalogue_system'
FROM extra_catalogue_products;

INSERT OR IGNORE INTO inventory_levels (
  variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at
)
SELECT printf('var_extra_%04d', product_number), 'loc_mumbai',
       30 + ((product_number * 31) % 170), product_number % 4,
       10 + (product_number % 15), 1, '2026-07-30T10:00:00Z'
FROM extra_catalogue_products;

INSERT INTO search_products (
  product_id, name, slug, brand_name, farm_name, category_names, keywords,
  short_description
)
SELECT
  printf('prd_extra_%04d', product_number), 'Organic ' || product_name,
  product_slug, '', '', department_name || ', ' || section_name,
  lower(product_name || ' ' || department_name || ' ' || section_name || ' organic natural'),
  product_name || ' selected for dependable quality and everyday use.'
FROM extra_catalogue_products;

-- Make every pre-existing published product carry an explicit database image,
-- rather than depending on a presentation-time fallback.
UPDATE products
SET
  image_url = (
    SELECT c.hero_image_url
    FROM product_categories AS pc
    JOIN categories AS c ON c.id = pc.category_id
    WHERE pc.product_id = products.id
      AND NULLIF(TRIM(c.hero_image_url), '') IS NOT NULL
    ORDER BY pc.is_primary DESC, pc.sort_order, c.id
    LIMIT 1
  ),
  image_alt = COALESCE(NULLIF(TRIM(image_alt), ''), name)
WHERE status = 'published'
  AND archived_at IS NULL
  AND NULLIF(TRIM(image_url), '') IS NULL
  AND EXISTS (
    SELECT 1
    FROM product_categories AS pc
    JOIN categories AS c ON c.id = pc.category_id
    WHERE pc.product_id = products.id
      AND NULLIF(TRIM(c.hero_image_url), '') IS NOT NULL
  );

-- Keep the original launch catalogue aligned with the matching department
-- photography instead of the generic homepage hero placeholders.
UPDATE categories
SET hero_image_url = CASE id
      WHEN 'cat_fresh_fruits' THEN '/banners/categories/fruits.webp'
      WHEN 'cat_vegetables' THEN '/banners/categories/vegetables.webp'
      WHEN 'cat_grains' THEN '/banners/categories/staple-grains.webp'
      WHEN 'cat_oils' THEN '/banners/categories/oils-cooking-fats.webp'
    END,
    hero_image_alt = CASE id
      WHEN 'cat_fresh_fruits' THEN 'Fresh organic fruit market selection'
      WHEN 'cat_vegetables' THEN 'Fresh organic vegetable market selection'
      WHEN 'cat_grains' THEN 'Organic grains and millets market selection'
      WHEN 'cat_oils' THEN 'Cold-pressed organic cooking oils'
    END,
    updated_at = '2026-07-30T12:00:00Z'
WHERE id IN ('cat_fresh_fruits', 'cat_vegetables', 'cat_grains', 'cat_oils');

UPDATE products
SET image_url = CASE id
      WHEN 'prd_alphonso' THEN '/banners/categories/fruits.webp'
      WHEN 'prd_spinach' THEN '/banners/categories/vegetables.webp'
      WHEN 'prd_ragi' THEN '/banners/categories/staple-grains.webp'
      WHEN 'prd_groundnut_oil' THEN '/banners/categories/oils-cooking-fats.webp'
      WHEN 'prd_rajma' THEN '/banners/categories/pulses-legumes.webp'
    END,
    image_alt = CASE id
      WHEN 'prd_alphonso' THEN 'Organic Alphonso mangoes'
      WHEN 'prd_spinach' THEN 'Fresh organic baby spinach'
      WHEN 'prd_ragi' THEN 'Organic sprouted ragi flour'
      WHEN 'prd_groundnut_oil' THEN 'Wood-pressed groundnut cooking oil'
      WHEN 'prd_rajma' THEN 'Organic Himalayan red rajma'
    END,
    updated_at = '2026-07-30T12:00:00Z'
WHERE id IN ('prd_alphonso', 'prd_spinach', 'prd_ragi', 'prd_groundnut_oil', 'prd_rajma');

UPDATE articles
SET hero_image_url = '/content/default-blog.webp',
    hero_image_alt = 'True Grit organic living journal'
WHERE NULLIF(TRIM(hero_image_url), '') IS NULL;

UPDATE recipes
SET hero_image_url = '/content/default-recipe.webp',
    hero_image_alt = 'Wholesome organic home-cooked meal'
WHERE NULLIF(TRIM(hero_image_url), '') IS NULL;

UPDATE discussions
SET image_url = '/content/default-discussion.webp',
    image_alt = 'True Grit community table'
WHERE NULLIF(TRIM(image_url), '') IS NULL;

DROP TABLE extra_catalogue_products;
DROP TABLE extra_catalogue_sections;

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

-- 0056_complete_customer_catalogue: customer-visible full-market catalogue.
-- These are real published catalogue rows served by the public API. The
-- development fixture is generated from this same migrated database.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO users (
  id, email, display_name, user_type, status, email_verified_at, created_at, updated_at
) VALUES (
  'usr_catalogue_system', 'catalogue-system@truegrit.internal',
  'Catalogue System', 'staff', 'active', '2026-08-02T05:00:00Z',
  '2026-08-02T05:00:00Z', '2026-08-02T05:00:00Z'
);

INSERT OR IGNORE INTO inventory_locations (
  id, code, name, location_type, timezone, active, created_at, updated_at
) VALUES (
  'loc_mumbai', 'MUM-01', 'Mumbai Fulfilment Centre', 'warehouse',
  'Asia/Kolkata', 1, '2026-08-02T05:00:00Z', '2026-08-02T05:00:00Z'
);

INSERT OR IGNORE INTO tags (id, key, label, tag_group, created_at) VALUES
  ('tag_high_protein', 'high-protein', 'High Protein', 'intention', '2026-08-02T05:00:00Z'),
  ('tag_plant_based', 'plant-based', 'Plant Based', 'diet', '2026-08-02T05:00:00Z'),
  ('tag_gluten_free', 'gluten-free', 'Gluten Free', 'diet', '2026-08-02T05:00:00Z'),
  ('tag_traditional', 'traditional-indian', 'Traditional Indian', 'intention', '2026-08-02T05:00:00Z');
-- Complete-market catalogue expansion. The original catalogue covers the
-- organic grocery core; these departments fill the practical gaps customers
-- expect from a full weekly market. Each row becomes one published category
-- and eight fully buyable products with a variant, price, stock and search row.
CREATE TEMP TABLE catalogue_completion_sections (
  n INTEGER PRIMARY KEY,
  department_order INTEGER NOT NULL,
  department_name TEXT NOT NULL,
  department_slug TEXT NOT NULL,
  banner_slug TEXT NOT NULL,
  section_order INTEGER NOT NULL,
  section_name TEXT NOT NULL,
  section_slug TEXT NOT NULL,
  variant_name TEXT NOT NULL,
  weight_value INTEGER NOT NULL,
  weight_unit TEXT NOT NULL,
  package_description TEXT NOT NULL,
  base_price_minor INTEGER NOT NULL,
  products_json TEXT NOT NULL
);

INSERT OR IGNORE INTO catalogue_completion_sections VALUES
  (1,1,'Farm Fresh Proteins','farm-fresh-proteins','dairy-farm-fresh',1,'Free Range Eggs','free-range-eggs','6-count carton',6,'unit','Recyclable six-egg carton',16900,'["Free Range Brown Eggs","Pasture Raised White Eggs","Country Hen Eggs","Omega 3 Enriched Eggs","Duck Eggs","Quail Eggs","Fertile Country Eggs","Heritage Breed Eggs"]'),
  (2,1,'Farm Fresh Proteins','farm-fresh-proteins','dairy-farm-fresh',2,'Fresh Mushrooms','fresh-mushrooms','200 g punnet',200,'g','Breathable produce punnet',12900,'["Button Mushrooms","Oyster Mushrooms","Shiitake Mushrooms","Milky Mushrooms","Portobello Mushrooms","Enoki Mushrooms","Lion''s Mane Mushrooms","Gourmet Mushroom Mix"]'),
  (3,1,'Farm Fresh Proteins','farm-fresh-proteins','plant-based-foods',3,'Fresh Sprouts','fresh-sprouts','200 g tray',200,'g','Fresh chilled tray',8900,'["Moong Bean Sprouts","Chickpea Sprouts","Moth Bean Sprouts","Alfalfa Sprouts","Broccoli Sprouts","Mixed Lentil Sprouts","Wheat Berry Sprouts","Five Bean Sprout Mix"]'),
  (4,1,'Farm Fresh Proteins','farm-fresh-proteins','plant-based-foods',4,'Fresh Tofu and Tempeh','fresh-tofu-tempeh','250 g pack',250,'g','Chilled sealed pack',15900,'["Firm Soy Tofu","Silken Tofu","Smoked Tofu","Herb Marinated Tofu","Soybean Tempeh","Chickpea Tempeh","Black Bean Tempeh","Ready Tofu Bhurji"]'),

  (5,2,'Pasta, Noodles and Couscous','pasta-noodles-couscous','global-pantry',1,'Wholegrain Pasta','wholegrain-pasta','500 g pack',500,'g','Recyclable dry-goods pack',18900,'["Whole Wheat Penne","Whole Wheat Fusilli","Durum Wheat Spaghetti","Spinach Whole Wheat Pasta","Beetroot Whole Wheat Pasta","Multigrain Macaroni","Semolina Shell Pasta","Herb Tagliatelle"]'),
  (6,2,'Pasta, Noodles and Couscous','pasta-noodles-couscous','global-pantry',2,'Gluten Free Pasta','gluten-free-pasta','400 g pack',400,'g','Resealable dry-goods pack',22900,'["Brown Rice Penne","Chickpea Fusilli","Red Lentil Spaghetti","Green Pea Pasta","Quinoa Macaroni","Buckwheat Pasta","Corn Rice Penne","Millet Spiral Pasta"]'),
  (7,2,'Pasta, Noodles and Couscous','pasta-noodles-couscous','global-pantry',3,'Asian Noodles','asian-noodles','300 g pack',300,'g','Dry noodle pack',17900,'["Whole Wheat Hakka Noodles","Brown Rice Vermicelli","Millet Noodles","Soba Noodles","Udon Noodles","Pad Thai Rice Noodles","Ramen Noodles","Glass Noodles"]'),
  (8,2,'Pasta, Noodles and Couscous','pasta-noodles-couscous','global-pantry',4,'Couscous and Specialty Grains','couscous-specialty-grains','500 g pack',500,'g','Resealable pantry pack',21900,'["Whole Wheat Couscous","Pearl Couscous","Maize Polenta","Bulgur Wheat","Freekeh Grain","Teff Grain","Fonio Grain","Farro Grain"]'),

  (9,3,'Soups, Stocks and Preserved Foods','soups-stocks-preserved','pantry-condiments',1,'Ready Soups','ready-soups','400 ml pouch',400,'ml','Shelf-stable soup pouch',14900,'["Tomato Basil Soup","Pumpkin Ginger Soup","Mixed Vegetable Soup","Mushroom Millet Soup","Spinach Pea Soup","Carrot Lentil Soup","Sweet Corn Soup","Roasted Red Pepper Soup"]'),
  (10,3,'Soups, Stocks and Preserved Foods','soups-stocks-preserved','pantry-condiments',2,'Stocks and Broths','stocks-broths','500 ml carton',500,'ml','Recyclable stock carton',16900,'["Vegetable Stock","Mushroom Stock","Tomato Cooking Broth","Ginger Turmeric Broth","Moringa Vegetable Broth","Roasted Garlic Stock","Coconut Curry Broth","Himalayan Herb Broth"]'),
  (11,3,'Soups, Stocks and Preserved Foods','soups-stocks-preserved','pantry-condiments',3,'Canned Beans and Pulses','canned-beans-pulses','400 g can',400,'g','BPA-free lined can',13900,'["Cooked Chickpeas","Cooked Kidney Beans","Cooked Black Beans","Cooked Cannellini Beans","Cooked Green Lentils","Cooked Black Chickpeas","Cooked Mixed Beans","Cooked Pigeon Peas"]'),
  (12,3,'Soups, Stocks and Preserved Foods','soups-stocks-preserved','pantry-condiments',4,'Canned Tomatoes and Vegetables','canned-tomatoes-vegetables','400 g can',400,'g','BPA-free lined can',12900,'["Whole Peeled Tomatoes","Chopped Tomatoes","Tomato Passata","Tomato Puree","Sweet Corn Kernels","Green Peas","Artichoke Hearts","Roasted Red Peppers"]'),

  (13,4,'Juices, Water and Functional Drinks','juices-water-functional','tea-coffee-beverages',1,'Cold Pressed Juices','cold-pressed-juices','250 ml bottle',250,'ml','Chilled recyclable bottle',11900,'["Orange Carrot Juice","Beetroot Apple Juice","Green Vegetable Juice","Pomegranate Juice","Pineapple Mint Juice","Watermelon Basil Juice","Amla Ginger Juice","Mixed Berry Juice"]'),
  (14,4,'Juices, Water and Functional Drinks','juices-water-functional','tea-coffee-beverages',2,'Coconut Water and Natural Hydration','natural-hydration','500 ml bottle',500,'ml','Recyclable hydration bottle',9900,'["Tender Coconut Water","Lemon Coconut Water","Watermelon Electrolyte Drink","Kokum Hydration Drink","Aloe Vera Drink","Cucumber Mint Water","Sabja Seed Cooler","Raw Mango Electrolyte Drink"]'),
  (15,4,'Juices, Water and Functional Drinks','juices-water-functional','tea-coffee-beverages',3,'Sparkling Water and Soda','sparkling-water-soda','330 ml bottle',330,'ml','Returnable glass bottle',8900,'["Plain Sparkling Water","Lemon Sparkling Water","Ginger Lime Soda","Kokum Soda","Rose Lemon Soda","Orange Peel Soda","Cucumber Tonic Water","Hibiscus Sparkling Water"]'),
  (16,4,'Juices, Water and Functional Drinks','juices-water-functional','wellness-supplements',4,'Wellness Shots','wellness-shots','60 ml bottle',60,'ml','Single-serve chilled bottle',7900,'["Ginger Turmeric Shot","Amla Immunity Shot","Wheatgrass Shot","Beetroot Energy Shot","Tulsi Ginger Shot","Aloe Amla Shot","Moringa Lemon Shot","Jamun Vinegar Shot"]'),

  (17,5,'Chocolate and Confectionery','chocolate-confectionery','snacks-treats',1,'Dark Chocolate','dark-chocolate','80 g bar',80,'g','Compostable chocolate wrapper',19900,'["70 Percent Dark Chocolate","85 Percent Dark Chocolate","Sea Salt Dark Chocolate","Almond Dark Chocolate","Orange Peel Dark Chocolate","Coffee Dark Chocolate","Coconut Dark Chocolate","Jaggery Sweetened Dark Chocolate"]'),
  (18,5,'Chocolate and Confectionery','chocolate-confectionery','snacks-treats',2,'Milk and Vegan Chocolate','milk-vegan-chocolate','80 g bar',80,'g','Compostable chocolate wrapper',18900,'["Classic Milk Chocolate","Hazelnut Milk Chocolate","Caramel Milk Chocolate","Coconut Milk Chocolate","Oat Milk Chocolate","Cashew Milk Chocolate","Rice Milk Chocolate","Vegan White Chocolate"]'),
  (19,5,'Chocolate and Confectionery','chocolate-confectionery','snacks-treats',3,'Truffles and Chocolate Treats','chocolate-treats','150 g box',150,'g','Gift-ready paper box',29900,'["Cacao Date Truffles","Coconut Cacao Truffles","Peanut Butter Cups","Almond Praline Bites","Hazelnut Cacao Bites","Chocolate Coated Raisins","Chocolate Coated Almonds","Chocolate Orange Thins"]'),
  (20,5,'Chocolate and Confectionery','chocolate-confectionery','snacks-treats',4,'Natural Candy and Confectionery','natural-confectionery','150 g pouch',150,'g','Resealable paper pouch',14900,'["Amla Candy","Ginger Candy","Tamarind Bites","Mango Fruit Leather","Guava Fruit Leather","Coconut Toffee","Sesame Brittle","Jaggery Fennel Candy"]'),

  (21,6,'Regional Indian Pantry','regional-indian-pantry','pantry-condiments',1,'South Indian Pantry','south-indian-pantry','500 g pack',500,'g','Regional pantry pack',17900,'["Kerala Matta Rice","Ponni Boiled Rice","Idli Rice","Karnataka Bisi Bele Bath Mix","Andhra Gongura Paste","Tamil Nadu Sambar Powder","Kerala Coconut Chutney Mix","Malabar Tamarind"]'),
  (22,6,'Regional Indian Pantry','regional-indian-pantry','spices-seasonings',2,'Himalayan and North East Pantry','himalayan-northeast-pantry','250 g pack',250,'g','Regional pantry pack',21900,'["Bhatt Black Soybean","Jakhiya Seeds","Jambu Himalayan Herb","Bamboo Shoot Preserve","Axone Fermented Soybean","Black Rice Poha","Perilla Seed Chutney","Himalayan Nettle Tea"]'),
  (23,6,'Regional Indian Pantry','regional-indian-pantry','pantry-condiments',3,'Western and Coastal Pantry','western-coastal-pantry','300 g pack',300,'g','Regional pantry pack',18900,'["Goan Recheado Masala","Konkani Sol Kadhi Mix","Maharashtrian Goda Masala","Gujarati Undhiyu Masala","Rajasthani Ker Sangri","Kashmiri Ver Masala","Sindhi Curry Masala","Malvani Curry Paste"]'),
  (24,6,'Regional Indian Pantry','regional-indian-pantry','pantry-condiments',4,'Eastern and Northern Pantry','eastern-northern-pantry','300 g pack',300,'g','Regional pantry pack',17900,'["Bengali Panch Phoron","Bihari Sattu Mix","Punjabi Wadiyan","Banarasi Chaat Masala","Awadhi Biryani Masala","Assamese Khar Mix","Odia Dalma Masala","Kashmiri Nadru Chips"]'),

  (25,7,'Free From and Special Diet','free-from-special-diet','flours-baking',1,'Certified Gluten Free','certified-gluten-free','500 g pack',500,'g','Allergen-controlled pack',23900,'["Gluten Free Bread Flour","Gluten Free Chapati Flour","Gluten Free Pancake Mix","Gluten Free Pizza Base Mix","Gluten Free Breadcrumbs","Gluten Free Baking Oats","Gluten Free Cookies","Gluten Free Seed Bread"]'),
  (26,7,'Free From and Special Diet','free-from-special-diet','natural-sweeteners',2,'No Added Sugar','no-added-sugar','250 g pack',250,'g','Resealable specialty pack',19900,'["No Added Sugar Granola","No Added Sugar Muesli","Date Sweetened Cookies","Jaggery Free Nut Bar","Unsweetened Fruit Spread","No Added Sugar Peanut Butter","Stevia Dark Chocolate","Monk Fruit Drink Mix"]'),
  (27,7,'Free From and Special Diet','free-from-special-diet','plant-based-foods',3,'High Protein Foods','high-protein-foods','500 g pack',500,'g','High-protein pantry pack',24900,'["Roasted Soy Nuts","Lupin Bean Flour","Pea Protein Granola","Chickpea Protein Pasta","Hemp Protein Powder","Pumpkin Seed Protein","Sattu Protein Mix","Mixed Dal Protein Khichdi"]'),
  (28,7,'Free From and Special Diet','free-from-special-diet','plant-based-foods',4,'Allergen Conscious Foods','allergen-conscious-foods','300 g pack',300,'g','Clearly labelled allergen-conscious pack',22900,'["Nut Free Seed Butter","Dairy Free Cacao Spread","Soy Free Protein Mix","Sesame Free Hummus Mix","Grain Free Crackers","Egg Free Baking Mix","Coconut Free Granola","Top Allergen Free Snack Box"]'),

  (29,8,'Baby Care and Parenting','baby-care-parenting','baby-kids',1,'Diapers and Wipes','diapers-wipes','standard pack',1,'unit','Family-size retail pack',39900,'["Bamboo Newborn Diapers","Bamboo Infant Diapers","Bamboo Toddler Diapers","Organic Cotton Nappies","Reusable Cloth Diaper","Unscented Baby Wipes","Reusable Cotton Wipes","Compostable Nappy Liners"]'),
  (30,8,'Baby Care and Parenting','baby-care-parenting','natural-personal-care',2,'Baby Bath and Skin','baby-bath-skin','200 ml bottle',200,'ml','Gentle-care retail bottle',24900,'["Gentle Baby Wash","Baby Shampoo","Baby Massage Oil","Baby Body Lotion","Baby Diaper Balm","Baby Face Cream","Baby Dusting Powder","Baby Sunscreen Lotion"]'),
  (31,8,'Baby Care and Parenting','baby-care-parenting','eco-living',3,'Feeding and Nursery','feeding-nursery','1 unit',1,'unit','Single nursery essential',34900,'["Steel Baby Feeding Bowl","Bamboo Baby Spoon","Silicone Free Sippy Cup","Glass Baby Bottle","Organic Cotton Bib","Muslin Swaddle Cloth","Natural Rubber Teether","Cotton Nursing Pillow"]'),
  (32,8,'Baby Care and Parenting','baby-care-parenting','wellness-supplements',4,'Maternity and Postpartum','maternity-postpartum','standard pack',1,'unit','Maternity care pack',29900,'["Pregnancy Herbal Tea","Postpartum Recovery Tea","Lactation Support Mix","Ragi Almond Panjiri","Nursing Balm","Stretch Mark Body Oil","Maternity Bath Salt","New Mother Nutrition Box"]'),

  (33,9,'Family Wellness and Care','family-wellness-care','wellness-supplements',1,'Menstrual Care','menstrual-care','standard pack',1,'unit','Personal care retail pack',24900,'["Organic Cotton Day Pads","Organic Cotton Night Pads","Organic Cotton Panty Liners","Reusable Cloth Pad Set","Menstrual Cup","Period Underwear","Herbal Period Comfort Tea","Menstrual Heat Patch"]'),
  (34,9,'Family Wellness and Care','family-wellness-care','natural-personal-care',2,'Natural First Aid','natural-first-aid','standard pack',1,'unit','Home first-aid essential',17900,'["Herbal Antiseptic Balm","Natural Insect Bite Balm","Calendula Skin Salve","Arnica Massage Balm","Neem Skin Spray","Herbal Vapour Rub","Aloe Burn Gel","Natural First Aid Kit"]'),
  (35,9,'Family Wellness and Care','family-wellness-care','wellness-supplements',3,'Sleep and Stress Support','sleep-stress-support','standard pack',1,'unit','Wellness retail pack',22900,'["Chamomile Sleep Tea","Ashwagandha Stress Tea","Lavender Pillow Mist","Magnesium Bath Flakes","Herbal Sleep Balm","Brahmi Calm Tonic","Tulsi Stress Support Drops","Sleep Ritual Gift Set"]'),
  (36,9,'Family Wellness and Care','family-wellness-care','natural-personal-care',4,'Everyday Family Hygiene','family-hygiene','standard pack',1,'unit','Family hygiene retail pack',15900,'["Herbal Hand Wash","Alcohol Free Hand Sanitiser","Natural Deodorant Stick","Herbal Foot Spray","Neem Hygiene Soap","Travel Hygiene Kit","Family Toothpaste Pack","Copper Tongue Cleaner Set"]'),

  (37,10,'Kitchen, Dining and Food Storage','kitchen-dining-storage','eco-living',1,'Natural Cookware','natural-cookware','1 unit',1,'unit','Single cookware item',79900,'["Cast Iron Tawa","Cast Iron Kadai","Iron Appam Pan","Clay Cooking Pot","Soapstone Cooking Pot","Steel Saucepan","Carbon Steel Frying Pan","Brass Tadka Pan"]'),
  (38,10,'Kitchen, Dining and Food Storage','kitchen-dining-storage','eco-living',2,'Serveware and Tableware','serveware-tableware','1 unit',1,'unit','Single tableware item',44900,'["Steel Thali Set","Brass Dinner Plate","Copper Water Tumbler","Ceramic Serving Bowl","Wooden Salad Bowl","Bamboo Snack Tray","Terracotta Water Jug","Coconut Shell Bowl Set"]'),
  (39,10,'Kitchen, Dining and Food Storage','kitchen-dining-storage','eco-living',3,'Food Storage','food-storage','1 unit',1,'unit','Single reusable storage item',39900,'["Steel Masala Dabba","Glass Storage Jar Set","Steel Tiffin Box","Ceramic Pickle Jar","Cotton Roti Wrap","Steel Produce Container","Glass Oil Dispenser","Bread Storage Tin"]'),
  (40,10,'Kitchen, Dining and Food Storage','kitchen-dining-storage','eco-living',4,'Food Preparation Tools','food-preparation-tools','1 unit',1,'unit','Single kitchen tool',29900,'["Wooden Chopping Board","Stone Mortar and Pestle","Coconut Grater","Steel Flour Sieve","Wooden Rolling Pin","Brass Lemon Squeezer","Bamboo Steamer Basket","Manual Grain Mill"]'),

  (41,11,'Bulk, Refill and Value Packs','bulk-refill-value','staple-grains',1,'Bulk Grains and Flours','bulk-grains-flours','5 kg value pack',5,'kg','Low-waste bulk pack',64900,'["Brown Rice Value Pack","Basmati Rice Value Pack","Whole Wheat Grain Value Pack","Whole Wheat Atta Value Pack","Ragi Flour Value Pack","Jowar Flour Value Pack","Rolled Oats Value Pack","Mixed Millet Value Pack"]'),
  (42,11,'Bulk, Refill and Value Packs','bulk-refill-value','pulses-legumes',2,'Bulk Pulses, Nuts and Seeds','bulk-pulses-nuts-seeds','2 kg value pack',2,'kg','Low-waste bulk pack',54900,'["Toor Dal Value Pack","Moong Dal Value Pack","Masoor Dal Value Pack","Chickpea Value Pack","Peanut Value Pack","Almond Family Pack","Mixed Seed Value Pack","Rajma Value Pack"]'),
  (43,11,'Bulk, Refill and Value Packs','bulk-refill-value','pantry-condiments',3,'Pantry Refills','pantry-refills','1 kg refill',1,'kg','Low-waste refill pouch',29900,'["Turmeric Powder Refill","Coriander Powder Refill","Cumin Seed Refill","Pink Salt Refill","Jaggery Powder Refill","Raw Sugar Refill","Tea Leaf Refill","Filter Coffee Refill"]'),
  (44,11,'Bulk, Refill and Value Packs','bulk-refill-value','natural-home-care',4,'Home Care Refills','home-care-refills','1 L refill',1,'l','Low-waste liquid refill pouch',34900,'["Dish Wash Liquid Refill","Laundry Liquid Refill","Floor Cleaner Refill","Hand Wash Refill","Toilet Cleaner Refill","Glass Cleaner Refill","Multipurpose Cleaner Refill","Fabric Conditioner Refill"]'),

  (45,12,'Meal Boxes and Subscriptions','meal-boxes-subscriptions','gift-hampers',1,'Fresh Produce Boxes','fresh-produce-boxes','1 curated box',1,'unit','Curated seasonal produce box',99900,'["Weekly Vegetable Box","Weekly Fruit Box","Fruit and Vegetable Family Box","Leafy Greens Box","Seasonal Orchard Box","Salad Vegetable Box","Juicing Produce Box","Farmers Choice Harvest Box"]'),
  (46,12,'Meal Boxes and Subscriptions','meal-boxes-subscriptions','ready-to-cook',2,'Cooking Meal Kits','cooking-meal-kits','1 meal kit',1,'unit','Pre-portioned family meal kit',69900,'["Khichdi Dinner Kit","Dal Rice Meal Kit","Millet Biryani Kit","Rajma Chawal Kit","Sambar Rice Kit","Palak Tofu Kit","Thai Curry Meal Kit","Mediterranean Bowl Kit"]'),
  (47,12,'Meal Boxes and Subscriptions','meal-boxes-subscriptions','breakfast-spreads',3,'Breakfast and Snack Boxes','breakfast-snack-boxes','1 curated box',1,'unit','Curated breakfast or snack box',74900,'["Healthy Breakfast Box","Kids Breakfast Box","Office Snack Box","High Protein Snack Box","Tea Time Box","Millet Discovery Box","No Added Sugar Snack Box","Travel Snack Box"]'),
  (48,12,'Meal Boxes and Subscriptions','meal-boxes-subscriptions','gift-hampers',4,'Household Subscription Boxes','household-subscription-boxes','1 monthly box',1,'unit','Monthly household essentials box',129900,'["Monthly Pantry Essentials Box","Monthly Cleaning Refill Box","Baby Essentials Box","Personal Care Essentials Box","Student Kitchen Starter Box","New Home Pantry Box","Senior Wellness Box","Festival Preparation Box"]');

INSERT OR IGNORE INTO categories (
  id, internal_name, name, slug, parent_id, path, level, sort_order, status,
  visibility, short_description, hero_eyebrow, hero_title, hero_description,
  theme_key, product_assignment_mode, published_version_id, seo_title,
  seo_description, hero_image_url, hero_image_alt, created_at, created_by,
  updated_at, updated_by
)
SELECT
  'cat_complete_' || department_slug,
  department_name || ' department', department_name, department_slug, NULL,
  '/' || department_slug, 0, 100 + department_order, 'published', 'public',
  'A complete selection of ' || lower(department_name) || ' for everyday households.',
  'Complete your weekly shop', department_name,
  'Browse dependable ' || lower(department_name) || ' with clear packs, prices and availability.',
  CASE (department_order % 5) WHEN 0 THEN 'gold' WHEN 1 THEN 'sage' WHEN 2 THEN 'terracotta' WHEN 3 THEN 'charcoal' ELSE 'forest' END,
  'manual', 'ctv_complete_' || department_slug || '_1',
  department_name || ' | True Grit Organic Market',
  'Shop ' || lower(department_name) || ' online from True Grit.',
  '/banners/categories/' || department_slug || '.webp',
  department_name || ' market selection',
  '2026-08-02T06:00:00Z', 'usr_catalogue_system', '2026-08-02T06:00:00Z', 'usr_catalogue_system'
FROM catalogue_completion_sections
GROUP BY department_order, department_name, department_slug;

INSERT OR IGNORE INTO categories (
  id, internal_name, name, slug, parent_id, path, level, sort_order, status,
  visibility, short_description, hero_eyebrow, hero_title, hero_description,
  theme_key, product_assignment_mode, published_version_id, seo_title,
  seo_description, hero_image_url, hero_image_alt, created_at, created_by,
  updated_at, updated_by
)
SELECT
  'cat_complete_' || section_slug, section_name || ' section', section_name,
  section_slug, 'cat_complete_' || department_slug,
  '/' || department_slug || '/' || section_slug, 1, section_order,
  'published', 'public',
  'Shop a practical selection of ' || lower(section_name) || '.',
  department_name, section_name,
  'Compare current ' || lower(section_name) || ' with transparent pack and stock information.',
  CASE (n % 5) WHEN 0 THEN 'gold' WHEN 1 THEN 'sage' WHEN 2 THEN 'terracotta' WHEN 3 THEN 'charcoal' ELSE 'forest' END,
  'manual', 'ctv_complete_' || section_slug || '_1',
  section_name || ' | True Grit Organic Market',
  'Shop ' || lower(section_name) || ' online from True Grit.',
  '/banners/categories/' || department_slug || '.webp',
  section_name || ' market selection',
  '2026-08-02T06:00:00Z', 'usr_catalogue_system', '2026-08-02T06:00:00Z', 'usr_catalogue_system'
FROM catalogue_completion_sections;

INSERT OR IGNORE INTO category_versions (
  id, category_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  'ctv_complete_' || department_slug || '_1',
  'cat_complete_' || department_slug, 1,
  json_object('blocks', json_array()), 'Complete-market department added',
  'published', '2026-08-02T05:30:00Z', 'usr_catalogue_system',
  '2026-08-02T05:45:00Z', 'usr_catalogue_system', '2026-08-02T06:00:00Z'
FROM catalogue_completion_sections GROUP BY department_slug
UNION ALL
SELECT
  'ctv_complete_' || section_slug || '_1',
  'cat_complete_' || section_slug, 1,
  json_object('blocks', json_array()), 'Complete-market category added',
  'published', '2026-08-02T05:30:00Z', 'usr_catalogue_system',
  '2026-08-02T05:45:00Z', 'usr_catalogue_system', '2026-08-02T06:00:00Z'
FROM catalogue_completion_sections;

CREATE TEMP TABLE catalogue_completion_products AS
SELECT
  ((sections.n - 1) * 8) + CAST(items.key AS INTEGER) + 1 AS product_number,
  sections.department_order, sections.department_name, sections.department_slug,
  sections.banner_slug, sections.section_name, sections.section_slug,
  sections.variant_name, sections.weight_value, sections.weight_unit,
  sections.package_description, sections.base_price_minor,
  CAST(items.key AS INTEGER) + 1 AS product_order,
  CAST(items.value AS TEXT) AS product_name,
  lower(replace(replace(replace(replace(CAST(items.value AS TEXT), ' ', '-'), '&', 'and'), '/', '-'), '''', ''))
    || '-' || sections.department_slug AS product_slug
FROM catalogue_completion_sections AS sections,
     json_each(sections.products_json) AS items;

INSERT OR IGNORE INTO products (
  id, internal_name, name, slug, product_type, status, short_description,
  published_version_id, seo_title, seo_description, image_url, image_alt,
  created_at, created_by, updated_at, updated_by
)
SELECT
  printf('prd_complete_%04d', product_number),
  product_name || ' complete-market product', product_name, product_slug,
  replace(section_slug, '-', '_'), 'published',
  product_name || ' selected for dependable quality, clear labelling and everyday use.',
  printf('pvr_complete_%04d_1', product_number),
  product_name || ' | Buy Online',
  'Shop ' || lower(product_name) || ' with current stock, pack and delivery information.',
  '/banners/categories/' || department_slug || '.webp', product_name,
  datetime('2026-02-01T08:00:00Z', printf('+%d days', (product_number * 17) % 180)),
  'usr_catalogue_system', '2026-08-02T06:00:00Z', 'usr_catalogue_system'
FROM catalogue_completion_products;

INSERT OR IGNORE INTO product_versions (
  id, product_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  printf('pvr_complete_%04d_1', product_number),
  printf('prd_complete_%04d', product_number), 1,
  json_object('blocks', json_array(json_object(
    'id', printf('blk_complete_%04d_overview', product_number),
    'type', 'rich_text', 'version', 1, 'enabled', json('true'),
    'props', json_object('paragraphs', json_array(
      product_name || ' is part of our complete weekly-market range, selected for practical everyday use.',
      'Check the current pack for ingredients, allergens, care, storage and best-before information.'
    ))
  ))),
  'Initial complete-market listing', 'published',
  '2026-08-02T05:30:00Z', 'usr_catalogue_system', '2026-08-02T05:45:00Z',
  'usr_catalogue_system', '2026-08-02T06:00:00Z'
FROM catalogue_completion_products;

INSERT OR IGNORE INTO product_categories (
  product_id, category_id, is_primary, sort_order, assigned_at, assigned_by
)
SELECT printf('prd_complete_%04d', product_number),
       'cat_complete_' || section_slug, 1, product_order,
       '2026-08-02T06:00:00Z', 'usr_catalogue_system'
FROM catalogue_completion_products
UNION ALL
SELECT printf('prd_complete_%04d', product_number),
       'cat_complete_' || department_slug, 0, product_number,
       '2026-08-02T06:00:00Z', 'usr_catalogue_system'
FROM catalogue_completion_products;

INSERT OR IGNORE INTO product_variants (
  id, product_id, sku, name, option_values_json, weight_value, weight_unit,
  package_description, status, sort_order, created_at, updated_at
)
SELECT
  printf('var_complete_%04d', product_number),
  printf('prd_complete_%04d', product_number),
  printf('TGC-%04d', product_number), variant_name,
  json_object('pack', variant_name), weight_value, weight_unit,
  package_description, 'active', 1,
  '2026-08-02T06:00:00Z', '2026-08-02T06:00:00Z'
FROM catalogue_completion_products;

INSERT OR IGNORE INTO variant_prices (
  id, variant_id, market_code, currency_code, list_amount_minor,
  sale_amount_minor, tax_inclusive, status, created_at, created_by
)
SELECT
  printf('prc_complete_%04d', product_number),
  printf('var_complete_%04d', product_number), 'IN', 'INR',
  base_price_minor + ((product_order - 1) * 1300),
  CASE WHEN product_number % 11 = 0
    THEN CAST((base_price_minor + ((product_order - 1) * 1300)) * 0.9 AS INTEGER)
    ELSE NULL END,
  1, 'active', '2026-08-02T06:00:00Z', 'usr_catalogue_system'
FROM catalogue_completion_products;

INSERT OR IGNORE INTO inventory_levels (
  variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at
)
SELECT
  printf('var_complete_%04d', product_number), 'loc_mumbai',
  36 + ((product_number * 29) % 165), product_number % 5,
  12 + (product_number % 18), 1, '2026-08-02T06:00:00Z'
FROM catalogue_completion_products;

INSERT OR IGNORE INTO product_tags (product_id, tag_id)
SELECT printf('prd_complete_%04d', product_number), 'tag_high_protein'
FROM catalogue_completion_products
WHERE department_order IN (1,7)
UNION ALL
SELECT printf('prd_complete_%04d', product_number), 'tag_plant_based'
FROM catalogue_completion_products
WHERE section_slug IN ('fresh-mushrooms','fresh-sprouts','fresh-tofu-tempeh','high-protein-foods')
UNION ALL
SELECT printf('prd_complete_%04d', product_number), 'tag_gluten_free'
FROM catalogue_completion_products
WHERE section_slug IN ('gluten-free-pasta','certified-gluten-free','allergen-conscious-foods')
UNION ALL
SELECT printf('prd_complete_%04d', product_number), 'tag_traditional'
FROM catalogue_completion_products
WHERE department_order = 6;

INSERT OR IGNORE INTO search_products (
  product_id, name, slug, brand_name, farm_name, category_names, keywords,
  short_description
)
SELECT
  printf('prd_complete_%04d', product_number), product_name, product_slug, '',
  'True Grit Partner Network', department_name || ', ' || section_name,
  lower(product_name || ' ' || department_name || ' ' || section_name || ' natural organic market'),
  product_name || ' selected for dependable quality, clear labelling and everyday use.'
FROM catalogue_completion_products;

DROP TABLE catalogue_completion_products;
DROP TABLE catalogue_completion_sections;

-- High-volume extension: four additional shopping aisles beneath every new
-- department. Four styles crossed with four subjects produce sixteen distinct
-- products per category without sacrificing readable, useful product names.
CREATE TEMP TABLE mass_catalogue_sections (
  n INTEGER PRIMARY KEY,
  department_slug TEXT NOT NULL,
  section_order INTEGER NOT NULL,
  section_name TEXT NOT NULL,
  section_slug TEXT NOT NULL,
  variant_name TEXT NOT NULL,
  weight_value INTEGER NOT NULL,
  weight_unit TEXT NOT NULL,
  package_description TEXT NOT NULL,
  base_price_minor INTEGER NOT NULL,
  styles_json TEXT NOT NULL,
  subjects_json TEXT NOT NULL
);

INSERT INTO mass_catalogue_sections VALUES
  (1,'farm-fresh-proteins',5,'Egg Value Packs','egg-value-packs','Selected carton',12,'unit','Recyclable egg carton',24900,'["6 Pack","12 Pack","Family Pack","Chef Pack"]','["Brown Hen Eggs","White Hen Eggs","Country Hen Eggs","Quail Eggs"]'),
  (2,'farm-fresh-proteins',6,'Mushroom Grow Kits','mushroom-grow-kits','1 grow kit',1,'unit','Ready-to-grow home kit',39900,'["Starter","Family","Refill","Professional"]','["Button Mushroom Grow Kit","Oyster Mushroom Grow Kit","Shiitake Mushroom Grow Kit","Milky Mushroom Grow Kit"]'),
  (3,'farm-fresh-proteins',7,'Protein Meal Prep','protein-meal-prep','300 g pack',300,'g','Chilled meal-prep pack',22900,'["Classic","Pepper","Tandoori","Garden Herb"]','["Tofu Cubes","Tempeh Strips","Tofu Steaks","Tempeh Crumble"]'),
  (4,'farm-fresh-proteins',8,'Sprouting Seeds','sprouting-seeds','250 g pouch',250,'g','Resealable seed pouch',14900,'["Small Pack","Family Pack","Bulk Pack","Refill Pack"]','["Moong Sprouting Seeds","Alfalfa Sprouting Seeds","Broccoli Sprouting Seeds","Mixed Bean Sprouting Seeds"]'),

  (5,'pasta-noodles-couscous',5,'Filled Pasta','filled-pasta','300 g pack',300,'g','Chilled pasta pack',27900,'["Fresh","Whole Wheat","Spinach Dough","Gluten Free"]','["Spinach Ravioli","Pumpkin Ravioli","Mushroom Ravioli","Herb Cannelloni"]'),
  (6,'pasta-noodles-couscous',6,'Pasta Sauces','pasta-sauces','300 g jar',300,'g','Reusable glass jar',21900,'["Classic","No Added Sugar","Low Salt","Family Size"]','["Tomato Basil Pasta Sauce","Roasted Pepper Pasta Sauce","Mushroom Pasta Sauce","Vegetable Ragu"]'),
  (7,'pasta-noodles-couscous',7,'Kids Pasta Shapes','kids-pasta-shapes','300 g pack',300,'g','Recyclable pasta pack',17900,'["Whole Wheat","Beetroot","Spinach","Millet"]','["Star Pasta","Animal Pasta","Alphabet Pasta","Mini Shell Pasta"]'),
  (8,'pasta-noodles-couscous',8,'Lasagne and Oven Pasta','lasagne-oven-pasta','400 g pack',400,'g','Recyclable pasta pack',23900,'["Durum Wheat","Whole Wheat","Gluten Free","Spinach"]','["Lasagne Sheets","Cannelloni Tubes","Jumbo Pasta Shells","Oven Pasta Squares"]'),

  (9,'soups-stocks-preserved',5,'Dry Soup Mixes','dry-soup-mixes','100 g pouch',100,'g','Resealable soup pouch',12900,'["Single Serve","Family","Travel","Value"]','["Tomato Soup Mix","Vegetable Soup Mix","Mushroom Soup Mix","Lentil Soup Mix"]'),
  (10,'soups-stocks-preserved',6,'Prepared Meal Bowls','prepared-meal-bowls','400 g bowl',400,'g','Shelf-stable meal bowl',22900,'["Classic","Family","Protein Rich","Low Salt"]','["Rajma Rice Bowl","Millet Khichdi Bowl","Chickpea Curry Bowl","Vegetable Stew Bowl"]'),
  (11,'soups-stocks-preserved',7,'Pickled Vegetables','pickled-vegetables','300 g jar',300,'g','Reusable glass jar',16900,'["Classic","Spicy","Garlic","No Added Sugar"]','["Carrot Pickle","Cucumber Pickle","Beetroot Pickle","Mixed Vegetable Pickle"]'),
  (12,'soups-stocks-preserved',8,'Fruit Preserves','fruit-preserves','250 g jar',250,'g','Reusable glass jar',18900,'["Classic","No Added Sugar","Chia","Family Size"]','["Mango Preserve","Strawberry Preserve","Fig Preserve","Mixed Berry Preserve"]'),

  (13,'juices-water-functional',5,'Iced Tea','iced-tea','330 ml bottle',330,'ml','Returnable glass bottle',9900,'["Classic","No Added Sugar","Sparkling","Concentrated"]','["Lemon Iced Tea","Peach Iced Tea","Hibiscus Iced Tea","Tulsi Iced Tea"]'),
  (14,'juices-water-functional',6,'Plant Protein Shakes','plant-protein-shakes','250 ml bottle',250,'ml','Chilled recyclable bottle',15900,'["Pea Protein","Hemp Protein","Seed Protein","Mixed Plant Protein"]','["Cacao Shake","Vanilla Shake","Coffee Shake","Berry Shake"]'),
  (15,'juices-water-functional',7,'Traditional Sharbat','traditional-sharbat','500 ml bottle',500,'ml','Reusable glass bottle',18900,'["Classic","Jaggery","No Added Sugar","Concentrated"]','["Rose Sharbat","Khus Sharbat","Kokum Sharbat","Bael Sharbat"]'),
  (16,'juices-water-functional',8,'Drink Concentrates','drink-concentrates','500 ml bottle',500,'ml','Reusable concentrate bottle',17900,'["Classic","Family","Travel","Low Sugar"]','["Aam Panna Concentrate","Jaljeera Concentrate","Nimbu Pani Concentrate","Ginger Lemon Concentrate"]'),

  (17,'chocolate-confectionery',5,'Cacao and Baking Chocolate','cacao-baking-chocolate','200 g pouch',200,'g','Resealable baking pouch',24900,'["Raw","Single Origin","Dark","Organic"]','["Cacao Powder","Cacao Nibs","Cacao Butter","Chocolate Chips"]'),
  (18,'chocolate-confectionery',6,'Nut Chocolate Bars','nut-chocolate-bars','80 g bar',80,'g','Compostable chocolate wrapper',22900,'["Dark Chocolate","Milk Chocolate","Vegan Chocolate","Jaggery Chocolate"]','["Almond Bar","Hazelnut Bar","Cashew Bar","Peanut Bar"]'),
  (19,'chocolate-confectionery',7,'Festival Chocolate Boxes','festival-chocolate-boxes','1 gift box',1,'unit','Gift-ready paper box',49900,'["Mini","Classic","Premium","Corporate"]','["Diwali Chocolate Box","Holi Chocolate Box","Eid Chocolate Box","Christmas Chocolate Box"]'),
  (20,'chocolate-confectionery',8,'Kids Chocolate Treats','kids-chocolate-treats','150 g pack',150,'g','Resealable treat pouch',17900,'["No Added Sugar","Millet","Fruit Sweetened","Mini"]','["Cacao Cookies","Chocolate Bites","Cacao Wafer","Chocolate Granola Cluster"]'),

  (21,'regional-indian-pantry',5,'Regional Pickles','regional-pickles','300 g jar',300,'g','Reusable glass jar',18900,'["Andhra","Punjabi","Gujarati","Kerala"]','["Mango Pickle","Lemon Pickle","Garlic Pickle","Mixed Vegetable Pickle"]'),
  (22,'regional-indian-pantry',6,'Papad and Fryums','papad-fryums','250 g pack',250,'g','Moisture-resistant pantry pack',14900,'["Handmade","Sun Dried","Spiced","Mini"]','["Rice Papad","Urad Papad","Moong Papad","Millet Fryums"]'),
  (23,'regional-indian-pantry',7,'Regional Sweets','regional-sweets','250 g box',250,'g','Gift-ready paper box',27900,'["Jaggery","Millet","Dry Fruit","Traditional"]','["Laddoo","Halwa","Peda","Barfi"]'),
  (24,'regional-indian-pantry',8,'Fresh Batters','fresh-batters','500 g pouch',500,'g','Chilled batter pouch',12900,'["Fresh","Multigrain","Ragi","Family"]','["Idli Batter","Dosa Batter","Adai Batter","Appam Batter"]'),

  (25,'free-from-special-diet',5,'Keto and Low Carb','keto-low-carb','300 g pack',300,'g','Resealable specialty pack',29900,'["Keto","Low Carb","High Fibre","Seed Rich"]','["Almond Bread Mix","Coconut Roti Mix","Seed Cracker Mix","Cauliflower Rice Mix"]'),
  (26,'free-from-special-diet',6,'Vegan Alternatives','vegan-alternatives','250 g pack',250,'g','Chilled vegan pack',26900,'["Cashew","Almond","Coconut","Herbed"]','["Vegan Cheese","Vegan Yoghurt","Vegan Cream","Vegan Dessert"]'),
  (27,'free-from-special-diet',7,'Low Sodium Foods','low-sodium-foods','300 g pack',300,'g','Clearly labelled specialty pack',21900,'["No Salt Added","Low Sodium","Herb Seasoned","Mineral Balanced"]','["Soup Mix","Seed Crackers","Dal Mix","Vegetable Stock"]'),
  (28,'free-from-special-diet',8,'Gut Friendly Foods','gut-friendly-foods','300 g pack',300,'g','Resealable wellness pack',23900,'["Probiotic","Prebiotic","Fermented","High Fibre"]','["Oat Mix","Granola","Seed Blend","Breakfast Porridge"]'),

  (29,'baby-care-parenting',5,'Baby Laundry Care','baby-laundry-care','500 ml pack',500,'ml','Gentle-care refill pack',24900,'["Unscented","Gentle","Plant Based","Concentrated"]','["Baby Laundry Liquid","Baby Fabric Rinse","Baby Stain Remover","Baby Bottle Cleanser"]'),
  (30,'baby-care-parenting',6,'Toddler Feeding','toddler-feeding','1 unit',1,'unit','Single feeding essential',29900,'["Bamboo","Steel","Silicone Free","Travel"]','["Toddler Plate","Snack Cup","Training Spoon","Sippy Tumbler"]'),
  (31,'baby-care-parenting',7,'Natural Toys and Learning','natural-toys-learning','1 unit',1,'unit','Single natural play item',34900,'["Neem Wood","Natural Rubber","Organic Cotton","Handmade"]','["Building Blocks","Baby Rattle","Stacking Toy","Sensory Ball"]'),
  (32,'baby-care-parenting',8,'Nursery Textiles','nursery-textiles','1 unit',1,'unit','Single nursery textile',49900,'["Organic Cotton","Muslin","Undyed","Quilted"]','["Crib Sheet","Baby Blanket","Cot Sheet","Changing Mat"]'),

  (33,'family-wellness-care',5,'Mens Grooming','mens-grooming','standard pack',1,'unit','Personal care retail pack',21900,'["Neem","Charcoal","Sandalwood","Herbal"]','["Face Wash","Shaving Cream","After Shave Balm","Hair Styling Cream"]'),
  (34,'family-wellness-care',6,'Senior Nutrition','senior-nutrition','500 g pack',500,'g','Easy-open nutrition pack',27900,'["High Fibre","Low Sugar","Protein Rich","Easy Digest"]','["Breakfast Porridge","Nutrition Drink Mix","Millet Meal Mix","Nut and Seed Powder"]'),
  (35,'family-wellness-care',7,'Fitness Recovery','fitness-recovery','standard pack',1,'unit','Recovery care retail pack',29900,'["Magnesium","Herbal","Eucalyptus","Deep Recovery"]','["Bath Salts","Massage Oil","Muscle Balm","Foot Soak"]'),
  (36,'family-wellness-care',8,'Travel Wellness','travel-wellness','1 travel pack',1,'unit','Compact reusable travel pack',19900,'["Pocket","Family","Refillable","Travel"]','["Hygiene Kit","First Aid Kit","Sleep Kit","Digestive Care Kit"]'),

  (37,'kitchen-dining-storage',5,'Kitchen Knives','kitchen-knives','1 knife',1,'unit','Single boxed kitchen knife',89900,'["Carbon Steel","Stainless Steel","Bamboo Handle","Professional"]','["Chef Knife","Paring Knife","Bread Knife","Vegetable Cleaver"]'),
  (38,'kitchen-dining-storage',6,'Natural Bakeware','natural-bakeware','1 unit',1,'unit','Single bakeware item',59900,'["Steel","Cast Iron","Ceramic","Non Toxic"]','["Cake Tin","Loaf Pan","Pie Dish","Muffin Tray"]'),
  (39,'kitchen-dining-storage',7,'Small Kitchen Appliances','small-kitchen-appliances','1 appliance',1,'unit','Single boxed appliance',149900,'["Manual","Compact","Steel","Low Energy"]','["Spice Grinder","Citrus Juicer","Hand Blender","Yoghurt Maker"]'),
  (40,'kitchen-dining-storage',8,'Kitchen Cleaning Tools','kitchen-cleaning-tools','1 unit',1,'unit','Single cleaning accessory',19900,'["Coconut Fibre","Bamboo","Natural","Heavy Duty"]','["Dish Brush","Bottle Brush","Pot Scrubber","Counter Cloth Set"]'),

  (41,'bulk-refill-value',5,'Bulk Breakfast','bulk-breakfast','value pack',2,'kg','Low-waste breakfast value pack',59900,'["2 kg","5 kg","Family","Refill"]','["Rolled Oats Pack","Millet Muesli Pack","Ragi Porridge Pack","Poha Pack"]'),
  (42,'bulk-refill-value',6,'Bulk Cooking Oils','bulk-cooking-oils','value can',2,'l','Low-waste cooking oil can',89900,'["2 L","5 L","Refill","Family"]','["Groundnut Oil Can","Mustard Oil Can","Sesame Oil Can","Coconut Oil Can"]'),
  (43,'bulk-refill-value',7,'Bulk Snacks','bulk-snacks','value pack',1,'kg','Low-waste snack value pack',69900,'["500 g","1 kg","Office","Party"]','["Roasted Makhana Pack","Roasted Chana Pack","Millet Chivda Pack","Trail Mix Pack"]'),
  (44,'bulk-refill-value',8,'Bulk Pet Essentials','bulk-pet-essentials','value pack',2,'kg','Pet-care value pack',79900,'["1 kg","2 kg","Monthly","Value"]','["Dog Biscuit Pack","Cat Treat Pack","Pet Meal Mix","Natural Pet Litter"]'),

  (45,'meal-boxes-subscriptions',5,'Regional Meal Boxes','regional-meal-boxes','1 meal box',1,'unit','Curated regional meal box',99900,'["3 Meal","5 Meal","Family","Discovery"]','["South Indian Box","North Indian Box","Coastal Indian Box","Himalayan Box"]'),
  (46,'meal-boxes-subscriptions',6,'Festival Celebration Boxes','festival-celebration-boxes','1 celebration box',1,'unit','Gift-ready celebration box',129900,'["Mini","Classic","Premium","Corporate"]','["Diwali Celebration Box","Holi Celebration Box","Eid Celebration Box","Christmas Celebration Box"]'),
  (47,'meal-boxes-subscriptions',7,'Wellness Subscriptions','wellness-subscriptions','1 subscription box',1,'unit','Curated monthly wellness box',109900,'["Monthly","Quarterly","Starter","Premium"]','["Herbal Tea Box","Superfood Box","Natural Self Care Box","Healthy Snack Box"]'),
  (48,'meal-boxes-subscriptions',8,'Office Pantry Boxes','office-pantry-boxes','1 pantry box',1,'unit','Curated workplace pantry box',149900,'["Small Team","Medium Team","Large Team","Monthly"]','["Coffee Pantry Box","Tea Pantry Box","Snack Pantry Box","Breakfast Pantry Box"]');

INSERT OR IGNORE INTO categories (
  id, internal_name, name, slug, parent_id, path, level, sort_order, status,
  visibility, short_description, hero_eyebrow, hero_title, hero_description,
  theme_key, product_assignment_mode, published_version_id, seo_title,
  seo_description, hero_image_url, hero_image_alt, created_at, created_by,
  updated_at, updated_by
)
SELECT
  'cat_mass_' || section_slug, section_name || ' high-volume section',
  section_name, section_slug, 'cat_complete_' || department_slug,
  '/' || department_slug || '/' || section_slug, 1, section_order,
  'published', 'public',
  'Explore sixteen practical choices across ' || lower(section_name) || '.',
  (SELECT name FROM categories WHERE id = 'cat_complete_' || department_slug),
  section_name,
  'Compare pack sizes, styles and current availability across ' || lower(section_name) || '.',
  CASE (n % 5) WHEN 0 THEN 'gold' WHEN 1 THEN 'sage' WHEN 2 THEN 'terracotta' WHEN 3 THEN 'charcoal' ELSE 'forest' END,
  'manual', 'ctv_mass_' || section_slug || '_1',
  section_name || ' | True Grit Organic Market',
  'Shop ' || lower(section_name) || ' online from True Grit.',
  '/banners/categories/' || department_slug || '.webp',
  section_name || ' product selection',
  '2026-08-02T07:00:00Z', 'usr_catalogue_system', '2026-08-02T07:00:00Z', 'usr_catalogue_system'
FROM mass_catalogue_sections;

INSERT OR IGNORE INTO category_versions (
  id, category_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  'ctv_mass_' || section_slug || '_1', 'cat_mass_' || section_slug, 1,
  json_object('blocks', json_array()), 'High-volume category added',
  'published', '2026-08-02T06:30:00Z', 'usr_catalogue_system',
  '2026-08-02T06:45:00Z', 'usr_catalogue_system', '2026-08-02T07:00:00Z'
FROM mass_catalogue_sections;

CREATE TEMP TABLE mass_catalogue_products AS
SELECT
  ((sections.n - 1) * 16) + (CAST(styles.key AS INTEGER) * 4)
    + CAST(subjects.key AS INTEGER) + 1 AS product_number,
  sections.department_slug, sections.section_name, sections.section_slug,
  sections.variant_name, sections.weight_value, sections.weight_unit,
  sections.package_description, sections.base_price_minor,
  (CAST(styles.key AS INTEGER) * 4) + CAST(subjects.key AS INTEGER) + 1 AS product_order,
  CAST(styles.value AS TEXT) || ' ' || CAST(subjects.value AS TEXT) AS product_name,
  lower(replace(replace(replace(replace(
    CAST(styles.value AS TEXT) || '-' || CAST(subjects.value AS TEXT),
    ' ', '-'), '&', 'and'), '/', '-'), '''', '')) || '-' || sections.section_slug AS product_slug
FROM mass_catalogue_sections AS sections,
     json_each(sections.styles_json) AS styles,
     json_each(sections.subjects_json) AS subjects;

INSERT OR IGNORE INTO products (
  id, internal_name, name, slug, product_type, status, short_description,
  published_version_id, seo_title, seo_description, image_url, image_alt,
  created_at, created_by, updated_at, updated_by
)
SELECT
  printf('prd_mass_%04d', product_number), product_name || ' market product',
  product_name, product_slug, replace(section_slug, '-', '_'), 'published',
  product_name || ' with a clearly labelled pack, current price and dependable availability.',
  printf('pvr_mass_%04d_1', product_number), product_name || ' | Buy Online',
  'Shop ' || lower(product_name) || ' online with current stock and delivery information.',
  '/banners/categories/' || department_slug || '.webp', product_name,
  datetime('2026-03-01T08:00:00Z', printf('+%d days', (product_number * 11) % 150)),
  'usr_catalogue_system', '2026-08-02T07:00:00Z', 'usr_catalogue_system'
FROM mass_catalogue_products;

INSERT OR IGNORE INTO product_versions (
  id, product_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  printf('pvr_mass_%04d_1', product_number),
  printf('prd_mass_%04d', product_number), 1,
  json_object('blocks', json_array(json_object(
    'id', printf('blk_mass_%04d_overview', product_number),
    'type', 'rich_text', 'version', 1, 'enabled', json('true'),
    'props', json_object('paragraphs', json_array(
      product_name || ' extends the True Grit market with more useful choice for a complete weekly shop.',
      'Review the current pack for ingredients, allergens, care, storage and best-before information.'
    ))
  ))), 'Initial high-volume listing', 'published',
  '2026-08-02T06:30:00Z', 'usr_catalogue_system', '2026-08-02T06:45:00Z',
  'usr_catalogue_system', '2026-08-02T07:00:00Z'
FROM mass_catalogue_products;

INSERT OR IGNORE INTO product_categories (
  product_id, category_id, is_primary, sort_order, assigned_at, assigned_by
)
SELECT printf('prd_mass_%04d', product_number), 'cat_mass_' || section_slug,
       1, product_order, '2026-08-02T07:00:00Z', 'usr_catalogue_system'
FROM mass_catalogue_products
UNION ALL
SELECT printf('prd_mass_%04d', product_number), 'cat_complete_' || department_slug,
       0, product_number, '2026-08-02T07:00:00Z', 'usr_catalogue_system'
FROM mass_catalogue_products;

INSERT OR IGNORE INTO product_variants (
  id, product_id, sku, name, option_values_json, weight_value, weight_unit,
  package_description, status, sort_order, created_at, updated_at
)
SELECT printf('var_mass_%04d', product_number),
       printf('prd_mass_%04d', product_number), printf('TGM-%04d', product_number),
       variant_name, json_object('pack', variant_name), weight_value, weight_unit,
       package_description, 'active', 1,
       '2026-08-02T07:00:00Z', '2026-08-02T07:00:00Z'
FROM mass_catalogue_products;

INSERT OR IGNORE INTO variant_prices (
  id, variant_id, market_code, currency_code, list_amount_minor,
  sale_amount_minor, tax_inclusive, status, created_at, created_by
)
SELECT printf('prc_mass_%04d', product_number),
       printf('var_mass_%04d', product_number), 'IN', 'INR',
       base_price_minor + ((product_order - 1) * 900),
       CASE WHEN product_number % 13 = 0
         THEN CAST((base_price_minor + ((product_order - 1) * 900)) * 0.9 AS INTEGER)
         ELSE NULL END,
       1, 'active', '2026-08-02T07:00:00Z', 'usr_catalogue_system'
FROM mass_catalogue_products;

INSERT OR IGNORE INTO inventory_levels (
  variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at
)
SELECT printf('var_mass_%04d', product_number), 'loc_mumbai',
       28 + ((product_number * 37) % 190), product_number % 6,
       10 + (product_number % 20), 1, '2026-08-02T07:00:00Z'
FROM mass_catalogue_products;

INSERT OR IGNORE INTO search_products (
  product_id, name, slug, brand_name, farm_name, category_names, keywords,
  short_description
)
SELECT printf('prd_mass_%04d', product_number), product_name, product_slug, '',
       'True Grit Partner Network', section_name,
       lower(product_name || ' ' || section_name || ' natural organic market'),
       product_name || ' with a clearly labelled pack, current price and dependable availability.'
FROM mass_catalogue_products;

DROP TABLE mass_catalogue_products;
DROP TABLE mass_catalogue_sections;

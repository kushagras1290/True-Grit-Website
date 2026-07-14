-- Development seed data for True Grit. Synthetic data only — never production customers.
PRAGMA foreign_keys = ON;

-- Staff users
INSERT INTO users (id, email, display_name, user_type, status, email_verified_at, created_at, updated_at) VALUES
  ('usr_admin', 'admin@truegrit.test', 'Asha Rao', 'staff', 'active', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('usr_editor', 'editor@truegrit.test', 'Kabir Mehta', 'staff', 'active', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('usr_pm', 'catalogue@truegrit.test', 'Meera Iyer', 'staff', 'active', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('usr_ops', 'ops@truegrit.test', 'Dev Sharma', 'staff', 'active', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');

-- Roles
INSERT OR IGNORE INTO roles (id, key, name, description, is_system, created_at) VALUES
  ('rol_super_admin', 'super_admin', 'Super Administrator', 'All permissions', 1, '2026-07-01T00:00:00Z'),
  ('rol_admin', 'admin', 'Administrator', 'Broad operational management', 1, '2026-07-01T00:00:00Z'),
  ('rol_content_editor', 'content_editor', 'Content Editor', 'Draft and edit content', 1, '2026-07-01T00:00:00Z'),
  ('rol_publisher', 'publisher', 'Publisher', 'Publish approved content', 1, '2026-07-01T00:00:00Z'),
  ('rol_product_manager', 'product_manager', 'Product Manager', 'Products, variants, prices', 1, '2026-07-01T00:00:00Z'),
  ('rol_inventory_manager', 'inventory_manager', 'Inventory Manager', 'Inventory view and adjustments', 1, '2026-07-01T00:00:00Z'),
  ('rol_order_manager', 'order_manager', 'Order Manager', 'Orders and fulfilment', 1, '2026-07-01T00:00:00Z'),
  ('rol_manager', 'manager', 'Manager', 'Catalogue, content, inventory, orders and media', 1, '2026-07-01T00:00:00Z'),
  ('rol_inventory', 'inventory', 'Inventory', 'Inventory and order monitoring', 1, '2026-07-01T00:00:00Z');

-- Permissions
INSERT INTO permissions (id, key, description) VALUES
  ('prm_products_view', 'products.view', 'View products'),
  ('prm_products_create', 'products.create', 'Create products'),
  ('prm_products_edit', 'products.edit', 'Edit products'),
  ('prm_products_approve', 'products.approve', 'Approve products'),
  ('prm_products_publish', 'products.publish', 'Publish products'),
  ('prm_products_archive', 'products.archive', 'Archive products'),
  ('prm_categories_view', 'categories.view', 'View categories'),
  ('prm_categories_create', 'categories.create', 'Create categories'),
  ('prm_categories_edit', 'categories.edit', 'Edit categories'),
  ('prm_categories_approve', 'categories.approve', 'Approve categories'),
  ('prm_categories_publish', 'categories.publish', 'Publish categories'),
  ('prm_pages_view', 'pages.view', 'View pages'),
  ('prm_pages_create', 'pages.create', 'Create pages'),
  ('prm_pages_edit', 'pages.edit', 'Edit pages'),
  ('prm_pages_approve', 'pages.approve', 'Approve pages'),
  ('prm_pages_publish', 'pages.publish', 'Publish pages'),
  ('prm_media_view', 'media.view', 'View media'),
  ('prm_media_upload', 'media.upload', 'Upload media'),
  ('prm_media_edit', 'media.edit', 'Edit media'),
  ('prm_media_archive', 'media.archive', 'Archive media'),
  ('prm_orders_view', 'orders.view', 'View orders'),
  ('prm_orders_cancel', 'orders.cancel', 'Cancel orders'),
  ('prm_orders_refund', 'orders.refund', 'Refund orders'),
  ('prm_inventory_view', 'inventory.view', 'View inventory'),
  ('prm_inventory_adjust', 'inventory.adjust', 'Adjust inventory'),
  ('prm_customers_view', 'customers.view', 'View customers'),
  ('prm_customers_export', 'customers.export', 'Export customers'),
  ('prm_users_view', 'users.view', 'View users'),
  ('prm_users_invite', 'users.invite', 'Invite users'),
  ('prm_users_manage_roles', 'users.manage_roles', 'Manage user roles'),
  ('prm_audit_view', 'audit.view', 'View audit log'),
  ('prm_settings_view', 'settings.view', 'View settings'),
  ('prm_settings_edit', 'settings.edit', 'Edit settings');

-- Super admin gets everything
INSERT INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions;

INSERT INTO role_permissions (role_id, permission_id) VALUES
  ('rol_content_editor', 'prm_pages_view'),
  ('rol_content_editor', 'prm_pages_create'),
  ('rol_content_editor', 'prm_pages_edit'),
  ('rol_content_editor', 'prm_categories_view'),
  ('rol_content_editor', 'prm_categories_edit'),
  ('rol_content_editor', 'prm_media_view'),
  ('rol_content_editor', 'prm_media_upload'),
  ('rol_publisher', 'prm_pages_view'),
  ('rol_publisher', 'prm_pages_approve'),
  ('rol_publisher', 'prm_pages_publish'),
  ('rol_publisher', 'prm_categories_view'),
  ('rol_publisher', 'prm_categories_approve'),
  ('rol_publisher', 'prm_categories_publish'),
  ('rol_product_manager', 'prm_products_view'),
  ('rol_product_manager', 'prm_products_create'),
  ('rol_product_manager', 'prm_products_edit'),
  ('rol_product_manager', 'prm_categories_view'),
  ('rol_product_manager', 'prm_media_view'),
  ('rol_product_manager', 'prm_media_upload'),
  ('rol_inventory_manager', 'prm_inventory_view'),
  ('rol_inventory_manager', 'prm_inventory_adjust'),
  ('rol_inventory_manager', 'prm_products_view'),
  ('rol_order_manager', 'prm_orders_view'),
  ('rol_order_manager', 'prm_orders_cancel'),
  ('rol_order_manager', 'prm_customers_view'),
  ('rol_manager', 'prm_products_view'),
  ('rol_manager', 'prm_products_create'),
  ('rol_manager', 'prm_products_edit'),
  ('rol_manager', 'prm_products_publish'),
  ('rol_manager', 'prm_products_archive'),
  ('rol_manager', 'prm_categories_view'),
  ('rol_manager', 'prm_categories_create'),
  ('rol_manager', 'prm_categories_edit'),
  ('rol_manager', 'prm_categories_publish'),
  ('rol_manager', 'prm_pages_view'),
  ('rol_manager', 'prm_pages_create'),
  ('rol_manager', 'prm_pages_edit'),
  ('rol_manager', 'prm_pages_publish'),
  ('rol_manager', 'prm_media_view'),
  ('rol_manager', 'prm_media_upload'),
  ('rol_manager', 'prm_media_edit'),
  ('rol_manager', 'prm_orders_view'),
  ('rol_manager', 'prm_orders_cancel'),
  ('rol_manager', 'prm_inventory_view'),
  ('rol_manager', 'prm_inventory_adjust'),
  ('rol_manager', 'prm_customers_view'),
  ('rol_manager', 'prm_audit_view'),
  ('rol_inventory', 'prm_inventory_view'),
  ('rol_inventory', 'prm_inventory_adjust'),
  ('rol_inventory', 'prm_products_view'),
  ('rol_inventory', 'prm_orders_view');

INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by) VALUES
  ('usr_admin', 'rol_super_admin', '2026-07-01T00:00:00Z', 'usr_admin'),
  ('usr_editor', 'rol_content_editor', '2026-07-01T00:00:00Z', 'usr_admin'),
  ('usr_pm', 'rol_product_manager', '2026-07-01T00:00:00Z', 'usr_admin'),
  ('usr_ops', 'rol_inventory_manager', '2026-07-01T00:00:00Z', 'usr_admin'),
  ('usr_ops', 'rol_order_manager', '2026-07-01T00:00:00Z', 'usr_admin');

-- Farm-owner sub-admin: a staff user scoped to a single farm (see 0009).
INSERT INTO roles (id, key, name, description, is_system, created_at) VALUES
  ('rol_farm_owner', 'farm_owner', 'Farm Owner', 'Manage own farm products and stock', 1, '2026-07-01T00:00:00Z');

INSERT INTO role_permissions (role_id, permission_id) VALUES
  ('rol_farm_owner', 'prm_products_view'),
  ('rol_farm_owner', 'prm_products_create'),
  ('rol_farm_owner', 'prm_products_edit'),
  ('rol_farm_owner', 'prm_products_publish'),
  ('rol_farm_owner', 'prm_products_archive'),
  ('rol_farm_owner', 'prm_media_view'),
  ('rol_farm_owner', 'prm_media_upload'),
  ('rol_farm_owner', 'prm_inventory_view'),
  ('rol_farm_owner', 'prm_inventory_adjust');

INSERT INTO users (id, email, display_name, user_type, status, email_verified_at, created_at, updated_at) VALUES
  ('usr_farmowner', 'owner@devika.test', 'Devika Kulkarni', 'staff', 'active', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');

INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by) VALUES
  ('usr_farmowner', 'rol_farm_owner', '2026-07-01T00:00:00Z', 'usr_admin');

-- Password: devikafarm1 (synthetic — change for any shared environment).
INSERT INTO user_credentials (user_id, password_hash, created_at, updated_at) VALUES
  ('usr_farmowner', 'pbkdf2_sha256$50000$YMMj0RYC+Hn+V+vIjfMyJQ==$APwBvRJgA1ShNDkySplvH/8MdEAwEjjAkebakQfDlhc=', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');

-- Media placeholders (object keys reference R2 layout)
INSERT INTO media_assets (id, object_key, original_filename, mime_type, size_bytes, width_px, height_px, alt_text, visibility, processing_status, created_at, created_by, updated_at, updated_by) VALUES
  ('med_hero_home', 'originals/med_hero_home/harvest-table.jpg', 'harvest-table.jpg', 'image/jpeg', 482000, 2400, 1500, 'A wooden harvest table with seasonal organic produce', 'public', 'ready', '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z', 'usr_editor'),
  ('med_farm_devika', 'originals/med_farm_devika/devika-fields.jpg', 'devika-fields.jpg', 'image/jpeg', 391000, 2000, 1250, 'Morning light over the terraced fields of Devika Organics', 'public', 'ready', '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z', 'usr_editor'),
  ('med_prod_mango', 'originals/med_prod_mango/alphonso-crate.jpg', 'alphonso-crate.jpg', 'image/jpeg', 287000, 1600, 1600, 'A crate of ripe Alphonso mangoes', 'public', 'ready', '2026-07-01T00:00:00Z', 'usr_pm', '2026-07-01T00:00:00Z', 'usr_pm');

-- Certifications
INSERT INTO certifications (id, name, issuing_body, slug, created_at, updated_at) VALUES
  ('cert_india_organic', 'India Organic (NPOP)', 'APEDA', 'india-organic', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('cert_jaivik_bharat', 'Jaivik Bharat', 'FSSAI', 'jaivik-bharat', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('cert_pgs_india', 'PGS-India Green', 'Ministry of Agriculture', 'pgs-india', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');

-- Farms
INSERT INTO farms (id, name, slug, farmer_name, region, country_code, established_year, story_json, hero_media_id, status, seo_title, seo_description, created_at, created_by, updated_at, updated_by) VALUES
  ('farm_devika', 'Devika Organics', 'devika-organics', 'Devika Kulkarni', 'Ratnagiri, Maharashtra', 'IN', 1998,
   '{"summary":"Three generations of Alphonso orchards farmed without synthetic inputs since 1998."}',
   'med_farm_devika', 'published', 'Devika Organics — Ratnagiri Alphonso orchards',
   'Certified organic Alphonso mango orchards in Ratnagiri, farmed by the Kulkarni family.',
   '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z', 'usr_editor'),
  ('farm_anandvan', 'Anandvan Collective', 'anandvan-collective', 'Ravi Patil', 'Wardha, Maharashtra', 'IN', 2011,
   '{"summary":"A 40-family collective growing millets, pulses and cold-pressed oilseeds on regenerated soil."}',
   NULL, 'published', 'Anandvan Collective — regenerative millet farming',
   'A farmer collective in Wardha growing certified organic millets and pulses.',
   '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z', 'usr_editor'),
  ('farm_himgiri', 'Himgiri Terraces', 'himgiri-terraces', 'Tara Negi', 'Uttarkashi, Uttarakhand', 'IN', 2015,
   '{"summary":"High-altitude terraced farms growing rajma, amaranth and Himalayan spices."}',
   NULL, 'published', 'Himgiri Terraces — Himalayan hill farms',
   'High-altitude organic terraces in Uttarkashi growing rajma, amaranth and spices.',
   '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z', 'usr_editor');

INSERT INTO farm_certifications (id, farm_id, certification_id, certificate_reference, valid_from, valid_until, verification_status, verified_at, verified_by, created_at) VALUES
  ('fc_devika_npop', 'farm_devika', 'cert_india_organic', 'NPOP/RA/2024/1183', '2024-04-01', '2027-03-31', 'verified', '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z'),
  ('fc_anandvan_pgs', 'farm_anandvan', 'cert_pgs_india', 'PGS/MH/2023/0452', '2023-06-01', '2026-05-31', 'verified', '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z'),
  ('fc_himgiri_npop', 'farm_himgiri', 'cert_india_organic', 'NPOP/UK/2025/0261', '2025-01-01', '2027-12-31', 'verified', '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z');

-- Categories
INSERT INTO categories (id, internal_name, name, slug, parent_id, path, level, sort_order, status, visibility, short_description, hero_eyebrow, hero_title, hero_description, theme_key, season_label, product_assignment_mode, product_rule_json, created_at, created_by, updated_at, updated_by) VALUES
  ('cat_fresh_fruits', 'Fresh Fruits', 'Fresh Fruits', 'fresh-fruits', NULL, '/fresh-fruits', 0, 1, 'published', 'public',
   'Seasonal organic fruit, picked at peak ripeness and traced to the orchard.',
   'In season now', 'Fruit, at its honest best', 'Every fruit here is grown without synthetic inputs and travels from a verified farm within days of harvest.',
   'terracotta', 'Mango season', 'dynamic',
   '{"version":1,"operator":"and","conditions":[{"field":"product.status","operator":"equals","value":"published"},{"field":"product.type","operator":"equals","value":"fresh_fruit"}],"sort":[{"field":"name","direction":"asc"}],"limit":96}',
   '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z', 'usr_editor'),
  ('cat_vegetables', 'Organic Vegetables', 'Organic Vegetables', 'organic-vegetables', NULL, '/organic-vegetables', 0, 2, 'published', 'public',
   'Everyday vegetables from soil that is tested, rested and certified.',
   'From living soil', 'Vegetables with a story', 'Grown by partner farms that practice crop rotation, composting and zero synthetic pesticides.',
   'sage', NULL, 'dynamic',
   '{"version":1,"operator":"and","conditions":[{"field":"product.status","operator":"equals","value":"published"},{"field":"product.type","operator":"equals","value":"vegetable"}],"sort":[{"field":"name","direction":"asc"}],"limit":96}',
   '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z', 'usr_editor'),
  ('cat_grains', 'Grains and Millets', 'Grains & Millets', 'grains-and-millets', NULL, '/grains-and-millets', 0, 3, 'published', 'public',
   'Heritage grains and millets, stone-milled in small batches.',
   'Slow staples', 'The grains your grandmother knew', 'Single-origin millets, rice and pulses from regenerative collectives across India.',
   'forest', NULL, 'dynamic',
   '{"version":1,"operator":"and","conditions":[{"field":"product.status","operator":"equals","value":"published"},{"field":"product.type","operator":"equals","value":"grain"}],"sort":[{"field":"name","direction":"asc"}],"limit":96}',
   '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z', 'usr_editor'),
  ('cat_oils', 'Cold-Pressed Oils', 'Cold-Pressed Oils', 'cold-pressed-oils', NULL, '/cold-pressed-oils', 0, 4, 'published', 'public',
   'Wood-pressed and cold-pressed oils from single-origin oilseeds.',
   'Pressed, not processed', 'Oil the slow way', 'Small-batch oils pressed at low temperature to keep flavour and nutrition intact.',
   'charcoal', NULL, 'dynamic',
   '{"version":1,"operator":"and","conditions":[{"field":"product.status","operator":"equals","value":"published"},{"field":"product.type","operator":"equals","value":"oil"}],"sort":[{"field":"name","direction":"asc"}],"limit":96}',
   '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z', 'usr_editor');

-- Tags
INSERT INTO tags (id, key, label, tag_group, created_at) VALUES
  ('tag_high_protein', 'high-protein', 'High Protein', 'intention', '2026-07-01T00:00:00Z'),
  ('tag_plant_based', 'plant-based', 'Plant Based', 'diet', '2026-07-01T00:00:00Z'),
  ('tag_gluten_free', 'gluten-free', 'Gluten Free', 'diet', '2026-07-01T00:00:00Z'),
  ('tag_traditional', 'traditional-indian', 'Traditional Indian', 'intention', '2026-07-01T00:00:00Z');

-- Products
INSERT INTO products (id, internal_name, name, slug, product_type, farm_id, status, short_description, primary_media_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by) VALUES
  ('prd_alphonso', 'Alphonso Mangoes 2026', 'Organic Alphonso Mangoes', 'organic-alphonso-mangoes', 'fresh_fruit', 'farm_devika', 'published',
   'Ratnagiri Alphonso, tree-ripened and carbide-free, from Devika Organics.',
   'med_prod_mango', 'Organic Alphonso Mangoes — Ratnagiri, carbide-free',
   'Tree-ripened certified organic Alphonso mangoes from Devika Organics, Ratnagiri.',
   '2026-07-01T00:00:00Z', 'usr_pm', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_spinach', 'Baby Spinach', 'Organic Baby Spinach', 'organic-baby-spinach', 'vegetable', 'farm_anandvan', 'published',
   'Tender baby spinach, harvested at dawn and chilled within the hour.',
   NULL, 'Organic Baby Spinach — harvested at dawn',
   'Certified organic baby spinach from the Anandvan Collective.',
   '2026-07-01T00:00:00Z', 'usr_pm', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_ragi', 'Sprouted Ragi Flour', 'Sprouted Ragi Flour', 'sprouted-ragi-flour', 'grain', 'farm_anandvan', 'published',
   'Stone-milled finger millet, sprouted for easier digestion and deeper flavour.',
   NULL, 'Sprouted Ragi Flour — stone-milled finger millet',
   'Certified organic sprouted ragi flour from the Anandvan Collective.',
   '2026-07-01T00:00:00Z', 'usr_pm', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_groundnut_oil', 'Wood-Pressed Groundnut Oil', 'Wood-Pressed Groundnut Oil', 'wood-pressed-groundnut-oil', 'oil', 'farm_anandvan', 'published',
   'Single-origin groundnuts, wood-pressed at low RPM within a week of shelling.',
   NULL, 'Wood-Pressed Groundnut Oil — single origin',
   'Certified organic wood-pressed groundnut oil from the Anandvan Collective.',
   '2026-07-01T00:00:00Z', 'usr_pm', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_rajma', 'Himalayan Rajma', 'Himalayan Red Rajma', 'himalayan-red-rajma', 'grain', 'farm_himgiri', 'published',
   'Small red kidney beans from high-altitude terraces, famous for their quick cooking.',
   NULL, 'Himalayan Red Rajma — Uttarkashi terraces',
   'Certified organic red rajma grown at altitude by Himgiri Terraces.',
   '2026-07-01T00:00:00Z', 'usr_pm', '2026-07-01T00:00:00Z', 'usr_pm');

INSERT INTO product_categories (product_id, category_id, is_primary, sort_order, assigned_at, assigned_by) VALUES
  ('prd_alphonso', 'cat_fresh_fruits', 1, 1, '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_spinach', 'cat_vegetables', 1, 1, '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_ragi', 'cat_grains', 1, 1, '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_rajma', 'cat_grains', 1, 2, '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_groundnut_oil', 'cat_oils', 1, 1, '2026-07-01T00:00:00Z', 'usr_pm');

INSERT INTO product_tags (product_id, tag_id) VALUES
  ('prd_spinach', 'tag_plant_based'),
  ('prd_ragi', 'tag_gluten_free'),
  ('prd_ragi', 'tag_traditional'),
  ('prd_rajma', 'tag_high_protein'),
  ('prd_rajma', 'tag_plant_based');

INSERT INTO product_certifications (product_id, certification_id, claim_review_state) VALUES
  ('prd_alphonso', 'cert_india_organic', 'approved'),
  ('prd_spinach', 'cert_pgs_india', 'approved'),
  ('prd_ragi', 'cert_pgs_india', 'approved'),
  ('prd_groundnut_oil', 'cert_pgs_india', 'approved'),
  ('prd_rajma', 'cert_india_organic', 'approved');

-- Variants
INSERT INTO product_variants (id, product_id, sku, name, weight_value, weight_unit, status, sort_order, created_at, updated_at) VALUES
  ('var_alphonso_1kg', 'prd_alphonso', 'TRG-MNG-1KG', '1 kg box (3-4 mangoes)', 1, 'kg', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_alphonso_2kg', 'prd_alphonso', 'TRG-MNG-2KG', '2 kg box (7-8 mangoes)', 2, 'kg', 'active', 2, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_spinach_250g', 'prd_spinach', 'TRG-SPN-250', '250 g bunch', 250, 'g', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_ragi_500g', 'prd_ragi', 'TRG-RGI-500', '500 g pack', 500, 'g', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_ragi_1kg', 'prd_ragi', 'TRG-RGI-1KG', '1 kg pack', 1, 'kg', 'active', 2, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_oil_500ml', 'prd_groundnut_oil', 'TRG-GNO-500', '500 ml glass bottle', 500, 'ml', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_oil_1l', 'prd_groundnut_oil', 'TRG-GNO-1L', '1 L glass bottle', 1, 'l', 'active', 2, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_rajma_500g', 'prd_rajma', 'TRG-RJM-500', '500 g pack', 500, 'g', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');

-- Prices (INR paise)
INSERT INTO variant_prices (id, variant_id, market_code, currency_code, list_amount_minor, sale_amount_minor, status, created_at, created_by) VALUES
  ('prc_alphonso_1kg', 'var_alphonso_1kg', 'IN', 'INR', 89900, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_alphonso_2kg', 'var_alphonso_2kg', 'IN', 'INR', 169900, 149900, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_spinach_250g', 'var_spinach_250g', 'IN', 'INR', 6900, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_ragi_500g', 'var_ragi_500g', 'IN', 'INR', 14500, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_ragi_1kg', 'var_ragi_1kg', 'IN', 'INR', 26900, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_oil_500ml', 'var_oil_500ml', 'IN', 'INR', 42500, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_oil_1l', 'var_oil_1l', 'IN', 'INR', 79900, 74900, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_rajma_500g', 'var_rajma_500g', 'IN', 'INR', 19900, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm');

-- Inventory
INSERT INTO inventory_locations (id, code, name, location_type, timezone, active, created_at, updated_at) VALUES
  ('loc_mumbai', 'MUM-01', 'Mumbai Fulfilment Centre', 'warehouse', 'Asia/Kolkata', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');

INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at) VALUES
  ('var_alphonso_1kg', 'loc_mumbai', 120, 4, 20, 1, '2026-07-01T00:00:00Z'),
  ('var_alphonso_2kg', 'loc_mumbai', 60, 2, 10, 1, '2026-07-01T00:00:00Z'),
  ('var_spinach_250g', 'loc_mumbai', 200, 0, 40, 1, '2026-07-01T00:00:00Z'),
  ('var_ragi_500g', 'loc_mumbai', 340, 0, 50, 1, '2026-07-01T00:00:00Z'),
  ('var_ragi_1kg', 'loc_mumbai', 180, 0, 30, 1, '2026-07-01T00:00:00Z'),
  ('var_oil_500ml', 'loc_mumbai', 90, 1, 15, 1, '2026-07-01T00:00:00Z'),
  ('var_oil_1l', 'loc_mumbai', 45, 0, 10, 1, '2026-07-01T00:00:00Z'),
  ('var_rajma_500g', 'loc_mumbai', 8, 0, 25, 1, '2026-07-01T00:00:00Z');

INSERT INTO inventory_movements (id, variant_id, location_id, movement_type, quantity_delta, reference_type, reason_code, actor_id, created_at) VALUES
  ('mov_seed_1', 'var_alphonso_1kg', 'loc_mumbai', 'receipt', 120, 'manual', 'initial_stock', 'usr_ops', '2026-07-01T00:00:00Z'),
  ('mov_seed_2', 'var_rajma_500g', 'loc_mumbai', 'receipt', 8, 'manual', 'initial_stock', 'usr_ops', '2026-07-01T00:00:00Z');

-- Homepage page + published version
INSERT INTO pages (id, page_type, internal_name, title, slug, template_key, status, published_version_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by) VALUES
  ('pag_home', 'landing', 'Homepage', 'Food grown the way nature intended', 'home', 'editorial_landing', 'published', 'pgv_home_1',
   'True Grit — traceable organic food from verified farms',
   'Fresh organic produce, conscious pantry essentials and trusted local farms — delivered with complete transparency.',
   '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z', 'usr_editor');

INSERT INTO page_versions (id, page_id, version_number, content_json, workflow_state, created_at, created_by, approved_at, approved_by, published_at) VALUES
  ('pgv_home_1', 'pag_home', 1,
   '{"blocks":[{"id":"blk_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Certified organic. Fully traceable.","heading":"Food grown the way nature intended.","text":"Fresh organic produce, conscious pantry essentials and trusted local farms — delivered with complete transparency.","primaryAction":{"label":"Explore the market","href":"/shop"},"secondaryAction":{"label":"See what is in season","href":"/category/fresh-fruits"}}},{"id":"blk_categories","type":"category_collection","version":1,"enabled":true,"props":{"heading":"Shop by food type","categorySlugs":["fresh-fruits","organic-vegetables","grains-and-millets","cold-pressed-oils"]}},{"id":"blk_products","type":"product_collection","version":1,"enabled":true,"props":{"heading":"Fresh favourites","source":"manual","productSlugs":["organic-alphonso-mangoes","organic-baby-spinach","sprouted-ragi-flour","wood-pressed-groundnut-oil","himalayan-red-rajma"],"limit":5}},{"id":"blk_farmer","type":"farmer_story","version":1,"enabled":true,"props":{"farmSlug":"devika-organics","quote":"We never needed chemicals. We needed patience.","attribution":"Devika Kulkarni, Devika Organics"}},{"id":"blk_faq","type":"faq","version":1,"enabled":true,"props":{"heading":"Our standards","items":[{"question":"What does certified organic mean here?","answer":"Every farm holds a current NPOP or PGS-India certificate that we verify and re-check annually."},{"question":"How is traceability guaranteed?","answer":"Each lot is tagged at the farm and carries its harvest date, farm and route to your door."}]}}]}',
   'published', '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-02T00:00:00Z', 'usr_admin', '2026-07-02T00:00:00Z');

-- Article
INSERT INTO articles (id, internal_name, title, slug, excerpt, author_user_id, hero_media_id, reading_minutes, status, published_at, created_at, created_by, updated_at, updated_by) VALUES
  ('art_millets', 'Millet revival article', 'The quiet revival of Indian millets', 'quiet-revival-of-indian-millets',
   'How a generation of farmers is bringing climate-resilient grains back to the Indian table.',
   'usr_editor', NULL, 6, 'published', '2026-07-05T00:00:00Z', '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-05T00:00:00Z', 'usr_editor');

-- Recipe
INSERT INTO recipes (id, internal_name, title, slug, excerpt, prep_minutes, cook_minutes, servings, dietary_tags_json, status, published_at, created_at, created_by, updated_at, updated_by) VALUES
  ('rcp_ragi_dosa', 'Ragi dosa recipe', 'Crisp sprouted ragi dosa', 'crisp-sprouted-ragi-dosa',
   'A weekday dosa with the deep, nutty flavour of sprouted finger millet.',
   15, 20, 4, '["gluten-free","plant-based"]', 'published', '2026-07-06T00:00:00Z',
   '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-06T00:00:00Z', 'usr_editor');

INSERT INTO recipe_ingredients (id, recipe_id, label, quantity_text, product_id, sort_order) VALUES
  ('ing_ragi_flour', 'rcp_ragi_dosa', 'Sprouted ragi flour', '2 cups', 'prd_ragi', 1),
  ('ing_spinach', 'rcp_ragi_dosa', 'Baby spinach, chopped', '1 cup', 'prd_spinach', 2),
  ('ing_oil', 'rcp_ragi_dosa', 'Groundnut oil', '2 tbsp', 'prd_groundnut_oil', 3);

-- Navigation
INSERT INTO navigation_menus (id, key, name, updated_at, updated_by) VALUES
  ('nav_header', 'header', 'Header navigation', '2026-07-01T00:00:00Z', 'usr_editor'),
  ('nav_footer', 'footer', 'Footer navigation', '2026-07-01T00:00:00Z', 'usr_editor');

INSERT INTO navigation_items (id, menu_id, parent_id, label, destination_type, destination_reference, sort_order, visible) VALUES
  ('nit_shop', 'nav_header', NULL, 'Shop', 'internal_path', '/shop', 1, 1),
  ('nit_seasonal', 'nav_header', NULL, 'Seasonal', 'category', 'fresh-fruits', 2, 1),
  ('nit_farmers', 'nav_header', NULL, 'Farmers', 'internal_path', '/farms', 3, 1),
  ('nit_recipes', 'nav_header', NULL, 'Recipes', 'internal_path', '/recipes', 4, 1),
  ('nit_journal', 'nav_header', NULL, 'Journal', 'internal_path', '/journal', 5, 1),
  ('nit_standards', 'nav_header', NULL, 'Our Standards', 'internal_path', '/standards', 6, 1),
  ('nit_footer_about', 'nav_footer', NULL, 'About', 'internal_path', '/about', 1, 1),
  ('nit_footer_delivery', 'nav_footer', NULL, 'Delivery', 'internal_path', '/delivery', 2, 1),
  ('nit_footer_returns', 'nav_footer', NULL, 'Returns', 'internal_path', '/returns', 3, 1),
  ('nit_footer_contact', 'nav_footer', NULL, 'Contact', 'internal_path', '/contact', 4, 1),
  ('nit_footer_privacy', 'nav_footer', NULL, 'Privacy', 'internal_path', '/privacy', 5, 1),
  ('nit_footer_terms', 'nav_footer', NULL, 'Terms', 'internal_path', '/terms', 6, 1);

-- Announcement
INSERT INTO announcements (id, message, destination_path, active, created_at, created_by, updated_at) VALUES
  ('ann_launch', 'Alphonso season is here — orchard-fresh boxes ship every Tuesday.', '/category/fresh-fruits', 1, '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-01T00:00:00Z');

-- Search synonyms
INSERT INTO search_synonyms (id, term, synonym, created_at) VALUES
  ('syn_1', 'ragi', 'finger millet', '2026-07-01T00:00:00Z'),
  ('syn_2', 'rajma', 'kidney beans', '2026-07-01T00:00:00Z'),
  ('syn_3', 'groundnut', 'peanut', '2026-07-01T00:00:00Z');

-- FTS index rows for seeded products
INSERT INTO search_products (product_id, name, slug, brand_name, farm_name, category_names, keywords, short_description) VALUES
  ('prd_alphonso', 'Organic Alphonso Mangoes', 'organic-alphonso-mangoes', '', 'Devika Organics', 'Fresh Fruits', 'mango hapus alphonso fruit', 'Ratnagiri Alphonso, tree-ripened and carbide-free.'),
  ('prd_spinach', 'Organic Baby Spinach', 'organic-baby-spinach', '', 'Anandvan Collective', 'Organic Vegetables', 'spinach palak greens', 'Tender baby spinach, harvested at dawn.'),
  ('prd_ragi', 'Sprouted Ragi Flour', 'sprouted-ragi-flour', '', 'Anandvan Collective', 'Grains & Millets', 'ragi finger millet nachni flour', 'Stone-milled sprouted finger millet.'),
  ('prd_groundnut_oil', 'Wood-Pressed Groundnut Oil', 'wood-pressed-groundnut-oil', '', 'Anandvan Collective', 'Cold-Pressed Oils', 'groundnut peanut oil wood pressed', 'Single-origin wood-pressed groundnut oil.'),
  ('prd_rajma', 'Himalayan Red Rajma', 'himalayan-red-rajma', '', 'Himgiri Terraces', 'Grains & Millets', 'rajma kidney beans himalayan', 'Small red kidney beans from high-altitude terraces.');

INSERT INTO search_content (entity_type, entity_id, title, slug, excerpt, keywords) VALUES
  ('article', 'art_millets', 'The quiet revival of Indian millets', 'quiet-revival-of-indian-millets', 'How a generation of farmers is bringing climate-resilient grains back.', 'millets grains climate'),
  ('recipe', 'rcp_ragi_dosa', 'Crisp sprouted ragi dosa', 'crisp-sprouted-ragi-dosa', 'A weekday dosa with the deep, nutty flavour of sprouted finger millet.', 'dosa ragi breakfast'),
  ('farm', 'farm_devika', 'Devika Organics', 'devika-organics', 'Three generations of Alphonso orchards in Ratnagiri.', 'mango farm ratnagiri');

-- Sample customer and orders (synthetic — power the operations console Orders view)
INSERT INTO users (id, email, display_name, user_type, status, email_verified_at, created_at, updated_at) VALUES
  ('usr_cust_riya', 'riya@example.test', 'Riya Nair', 'customer', 'active', '2026-07-05T00:00:00Z', '2026-07-05T00:00:00Z', '2026-07-05T00:00:00Z');

INSERT INTO customer_profiles (user_id, marketing_email_consent, created_at, updated_at) VALUES
  ('usr_cust_riya', 1, '2026-07-05T00:00:00Z', '2026-07-05T00:00:00Z');

INSERT INTO orders (id, public_reference, customer_user_id, customer_email, currency_code, subtotal_minor, discount_minor, delivery_minor, tax_minor, total_minor, order_status, payment_status, fulfilment_status, delivery_status, placed_at, created_at, updated_at) VALUES
  ('ord_1001', 'TG-1001', 'usr_cust_riya', 'riya@example.test', 'INR', 89900, 0, 4900, 0, 94800, 'confirmed', 'paid', 'unfulfilled', 'not_ready', '2026-07-10T09:00:00Z', '2026-07-10T09:00:00Z', '2026-07-10T09:00:00Z'),
  ('ord_1002', 'TG-1002', 'usr_cust_riya', 'riya@example.test', 'INR', 149900, 0, 0, 0, 149900, 'pending_payment', 'pending', 'unfulfilled', 'not_ready', '2026-07-12T14:30:00Z', '2026-07-12T14:30:00Z', '2026-07-12T14:30:00Z');

INSERT INTO order_items (id, order_id, product_id, variant_id, product_name, variant_name, sku, quantity, unit_list_amount_minor, unit_effective_amount_minor, discount_minor, tax_minor, line_total_minor) VALUES
  ('oit_1001', 'ord_1001', 'prd_alphonso', 'var_alphonso_1kg', 'Organic Alphonso Mangoes', '1 kg box (3-4 mangoes)', 'TRG-MNG-1KG', 1, 89900, 89900, 0, 0, 89900),
  ('oit_1002', 'ord_1002', 'prd_alphonso', 'var_alphonso_2kg', 'Organic Alphonso Mangoes', '2 kg box (7-8 mangoes)', 'TRG-MNG-2KG', 1, 149900, 149900, 0, 0, 149900);

-- Farm membership (farms exist by now): the Devika owner is scoped to farm_devika,
-- whose catalogue includes prd_alphonso.
INSERT INTO farm_members (user_id, farm_id, created_at, created_by) VALUES
  ('usr_farmowner', 'farm_devika', '2026-07-01T00:00:00Z', 'usr_admin');

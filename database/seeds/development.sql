-- Development seed data for True Grit. Synthetic data only — never production customers.
PRAGMA foreign_keys = ON;

-- Staff users
INSERT INTO users (id, email, display_name, user_type, status, email_verified_at, created_at, updated_at) VALUES
  ('usr_admin', 'admin@truegrit.test', 'Asha Rao', 'staff', 'active', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('usr_editor', 'editor@truegrit.test', 'Kabir Mehta', 'staff', 'active', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('usr_pm', 'catalogue@truegrit.test', 'Meera Iyer', 'staff', 'active', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('usr_ops', 'ops@truegrit.test', 'Dev Sharma', 'staff', 'active', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('usr_blogger', 'blogger@truegrit.test', 'Naina Kapoor', 'staff', 'active', '2026-07-17T00:00:00Z', '2026-07-17T00:00:00Z', '2026-07-17T00:00:00Z'),
  ('usr_chef', 'chef@truegrit.test', 'Rohan Das', 'staff', 'active', '2026-07-17T00:00:00Z', '2026-07-17T00:00:00Z', '2026-07-17T00:00:00Z');

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
  -- orders.refund is now seeded by migration 0032, not here (same reason
  -- articles.*/recipes.*/etc. aren't in this list -- they're seeded by 0025).
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

-- Role permissions.
--
-- Migrations run before this seed, so every EXISTS-guarded grant in
-- 0041_role_permission_baseline.sql no-ops against a fresh local database:
-- the roles below do not exist yet when it runs. The grants are therefore
-- restated here, keyed by permission key rather than row id so the two stay
-- legible side by side. Keep them in step — a permission added to one belongs
-- in the other.

-- Super admin and Administrator both hold every permission. The super-admin-only
-- diagnostics pages are gated on the `super_admin` role itself, not on a
-- permission row, so this does not blur the two.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions;

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions;

-- Content Editor: drafts and edits content, including the media metadata that
-- goes with it. Approving and publishing are deliberately elsewhere.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_content_editor', id FROM permissions
WHERE key IN (
  'pages.view', 'pages.create', 'pages.edit',
  'articles.view', 'articles.create', 'articles.edit',
  'recipes.view', 'recipes.create', 'recipes.edit',
  'categories.view', 'categories.edit',
  'media.view', 'media.upload', 'media.edit', 'media.archive',
  'submissions.view', 'messages.use'
);

-- Publisher: approves and publishes. Needs the view grants for the lists it
-- works from, or it is approving content it cannot see.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_publisher', id FROM permissions
WHERE key IN (
  'pages.view', 'pages.approve', 'pages.publish',
  'categories.view', 'categories.approve', 'categories.publish',
  'articles.view', 'articles.approve', 'articles.publish',
  'recipes.view', 'recipes.approve', 'recipes.publish',
  'media.view',
  'submissions.view', 'submissions.review', 'messages.use'
);

-- Product Manager: owns the catalogue end to end, and can see the stock that
-- decides whether a product is sellable.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_product_manager', id FROM permissions
WHERE key IN (
  'products.view', 'products.create', 'products.edit',
  'products.publish', 'products.archive',
  'categories.view', 'categories.edit',
  'media.view', 'media.upload', 'media.edit',
  'inventory.view', 'messages.use'
);

-- Inventory Manager: adjusts stock; orders are what consume it.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_inventory_manager', id FROM permissions
WHERE key IN (
  'inventory.view', 'inventory.adjust',
  'products.view', 'categories.view', 'orders.view', 'messages.use'
);

-- Order Manager: fulfilment and post-delivery triage.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_order_manager', id FROM permissions
WHERE key IN (
  'orders.view', 'orders.cancel', 'customers.view',
  'products.view', 'inventory.view',
  'returns.view', 'returns.manage',
  'reviews.view', 'reviews.moderate', 'messages.use'
);

-- Manager: runs the shop day to day — catalogue, content, stock, orders, and
-- the community queues, plus the reads its console pages depend on (users.view
-- backs Farms and Contact Attempts). settings.* is deliberately withheld: Site
-- Control also holds the sign-in and payment kill-switches, which stay with the
-- owner.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN (
  'products.view', 'products.create', 'products.edit',
  'products.approve', 'products.publish', 'products.archive',
  'categories.view', 'categories.create', 'categories.edit',
  'categories.approve', 'categories.publish',
  'pages.view', 'pages.create', 'pages.edit', 'pages.approve', 'pages.publish',
  'articles.view', 'articles.create', 'articles.edit',
  'articles.approve', 'articles.publish',
  'recipes.view', 'recipes.create', 'recipes.edit',
  'recipes.approve', 'recipes.publish',
  'media.view', 'media.upload', 'media.edit', 'media.archive', 'media.delete',
  'orders.view', 'orders.cancel',
  'inventory.view', 'inventory.adjust',
  'returns.view', 'returns.manage',
  'customers.view', 'users.view', 'audit.view',
  'submissions.view', 'submissions.review',
  'discussions.view', 'discussions.moderate',
  'farm_requests.view', 'farm_requests.review',
  'reviews.view', 'reviews.moderate',
  'promotions.view', 'promotions.manage',
  'bundles.view', 'bundles.manage', 'messages.use', 'support_bot.manage'
);

-- Inventory: read-mostly monitoring sibling of Inventory Manager.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_inventory', id FROM permissions
WHERE key IN (
  'inventory.view', 'inventory.adjust',
  'products.view', 'categories.view', 'orders.view', 'messages.use'
);

-- Blogger / Chef: authoring roles that draft their own content type and help
-- clear the community queues, but never publish.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_blogger', id FROM permissions
WHERE key IN (
  'articles.view', 'articles.create', 'articles.edit',
  'media.view', 'media.upload',
  'submissions.view', 'submissions.review', 'discussions.view', 'messages.use'
);

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_chef', id FROM permissions
WHERE key IN (
  'recipes.view', 'recipes.create', 'recipes.edit',
  'media.view', 'media.upload',
  'submissions.view', 'submissions.review', 'discussions.view', 'messages.use'
);

-- Accounts: payments and refunds only. audit.view is what the "Payments &
-- Refunds" console is gated on, and returns are where most refunds start.
-- Catalogue, users and settings stay out of reach, as its description promises.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_accounts', id FROM permissions
WHERE key IN (
  'orders.view', 'orders.cancel', 'orders.refund',
  'returns.view', 'customers.view', 'audit.view', 'messages.use'
);

INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by) VALUES
  ('usr_admin', 'rol_super_admin', '2026-07-01T00:00:00Z', 'usr_admin'),
  ('usr_editor', 'rol_content_editor', '2026-07-01T00:00:00Z', 'usr_admin'),
  ('usr_pm', 'rol_product_manager', '2026-07-01T00:00:00Z', 'usr_admin'),
  ('usr_ops', 'rol_inventory_manager', '2026-07-01T00:00:00Z', 'usr_admin'),
  ('usr_ops', 'rol_order_manager', '2026-07-01T00:00:00Z', 'usr_admin'),
  ('usr_blogger', 'rol_blogger', '2026-07-17T00:00:00Z', 'usr_admin'),
  ('usr_chef', 'rol_chef', '2026-07-17T00:00:00Z', 'usr_admin');

-- Farm-owner sub-admin: a staff user scoped to a single farm (see 0009).
INSERT INTO roles (id, key, name, description, is_system, created_at) VALUES
  ('rol_farm_owner', 'farm_owner', 'Farm Owner', 'Manage own farm products and stock', 1, '2026-07-01T00:00:00Z');

-- Scoping to a single farm is enforced in the API (via `farm_members`), not by
-- these rows: orders.view here means "orders for my farm", not every order.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_farm_owner', id FROM permissions
WHERE key IN (
  'products.view', 'products.create', 'products.edit',
  'products.publish', 'products.archive',
  'categories.view',
  'media.view', 'media.upload',
  'inventory.view', 'inventory.adjust',
  'orders.view', 'messages.use'
);

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
INSERT OR IGNORE INTO farms (id, name, slug, farmer_name, region, country_code, established_year, story_json, hero_media_id, status, seo_title, seo_description, created_at, created_by, updated_at, updated_by) VALUES
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
INSERT OR IGNORE INTO categories (id, internal_name, name, slug, parent_id, path, level, sort_order, status, visibility, short_description, hero_eyebrow, hero_title, hero_description, theme_key, season_label, product_assignment_mode, product_rule_json, created_at, created_by, updated_at, updated_by) VALUES
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

UPDATE categories
SET hero_image_url = CASE id
      WHEN 'cat_fresh_fruits' THEN '/homepage-hero.png'
      WHEN 'cat_vegetables' THEN '/homepage-hero-greens.png'
      WHEN 'cat_grains' THEN '/homepage-hero-roots.png'
      WHEN 'cat_oils' THEN '/homepage-hero-citrus.png'
      ELSE hero_image_url
    END,
    hero_image_alt = CASE id
      WHEN 'cat_fresh_fruits' THEN 'Organic mangoes held in a sunlit orchard'
      WHEN 'cat_vegetables' THEN 'Fresh leafy greens and herbs held in a farm field'
      WHEN 'cat_grains' THEN 'Fresh roots and pulses from organic soil'
      WHEN 'cat_oils' THEN 'Seasonal fruit in an organic orchard'
      ELSE hero_image_alt
    END
WHERE id IN ('cat_fresh_fruits', 'cat_vegetables', 'cat_grains', 'cat_oils');

-- Tags
INSERT OR IGNORE INTO tags (id, key, label, tag_group, created_at) VALUES
  ('tag_high_protein', 'high-protein', 'High Protein', 'intention', '2026-07-01T00:00:00Z'),
  ('tag_plant_based', 'plant-based', 'Plant Based', 'diet', '2026-07-01T00:00:00Z'),
  ('tag_gluten_free', 'gluten-free', 'Gluten Free', 'diet', '2026-07-01T00:00:00Z'),
  ('tag_traditional', 'traditional-indian', 'Traditional Indian', 'intention', '2026-07-01T00:00:00Z');

-- Products
INSERT OR IGNORE INTO products (id, internal_name, name, slug, product_type, farm_id, status, short_description, primary_media_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by) VALUES
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

UPDATE products
SET image_url = CASE id
      WHEN 'prd_alphonso' THEN '/homepage-hero.png'
      WHEN 'prd_spinach' THEN '/homepage-hero-greens.png'
      WHEN 'prd_ragi' THEN '/homepage-hero-roots.png'
      WHEN 'prd_groundnut_oil' THEN '/homepage-hero-citrus.png'
      WHEN 'prd_rajma' THEN '/homepage-hero-roots.png'
      ELSE image_url
    END,
    image_alt = CASE id
      WHEN 'prd_alphonso' THEN 'Organic mangoes held in a sunlit orchard'
      WHEN 'prd_spinach' THEN 'Fresh leafy greens and herbs held in a farm field'
      WHEN 'prd_ragi' THEN 'Fresh roots and pulses from organic soil'
      WHEN 'prd_groundnut_oil' THEN 'Seasonal fruit in an organic orchard'
      WHEN 'prd_rajma' THEN 'Himalayan Red Rajma'
      ELSE image_alt
    END
WHERE id IN ('prd_alphonso', 'prd_spinach', 'prd_ragi', 'prd_groundnut_oil', 'prd_rajma');

INSERT OR IGNORE INTO product_categories (product_id, category_id, is_primary, sort_order, assigned_at, assigned_by) VALUES
  ('prd_alphonso', 'cat_fresh_fruits', 1, 1, '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_spinach', 'cat_vegetables', 1, 1, '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_ragi', 'cat_grains', 1, 1, '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_rajma', 'cat_grains', 1, 2, '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prd_groundnut_oil', 'cat_oils', 1, 1, '2026-07-01T00:00:00Z', 'usr_pm');

INSERT OR IGNORE INTO product_tags (product_id, tag_id) VALUES
  ('prd_spinach', 'tag_plant_based'),
  ('prd_ragi', 'tag_gluten_free'),
  ('prd_ragi', 'tag_traditional'),
  ('prd_rajma', 'tag_high_protein'),
  ('prd_rajma', 'tag_plant_based'),
  -- Migration 0081's expanded diet vocabulary: prd_alphonso, prd_spinach,
  -- prd_ragi, prd_rajma and prd_groundnut_oil are fruit/vegetable/grain/
  -- legume/oil products with no animal or dairy ingredients. Groundnut
  -- (peanut) oil is left off nut-free -- peanuts are commonly bucketed
  -- under "nut" in everyday allergen labelling even though they are
  -- botanically a legume.
  ('prd_alphonso', 'tag_vegan'),
  ('prd_alphonso', 'tag_vegetarian'),
  ('prd_alphonso', 'tag_dairy_free'),
  ('prd_alphonso', 'tag_nut_free'),
  ('prd_spinach', 'tag_vegan'),
  ('prd_spinach', 'tag_vegetarian'),
  ('prd_spinach', 'tag_dairy_free'),
  ('prd_spinach', 'tag_nut_free'),
  ('prd_ragi', 'tag_vegan'),
  ('prd_ragi', 'tag_vegetarian'),
  ('prd_ragi', 'tag_dairy_free'),
  ('prd_ragi', 'tag_nut_free'),
  ('prd_rajma', 'tag_vegan'),
  ('prd_rajma', 'tag_vegetarian'),
  ('prd_rajma', 'tag_dairy_free'),
  ('prd_rajma', 'tag_nut_free'),
  ('prd_groundnut_oil', 'tag_vegan'),
  ('prd_groundnut_oil', 'tag_vegetarian'),
  ('prd_groundnut_oil', 'tag_dairy_free');

INSERT OR IGNORE INTO product_certifications (product_id, certification_id, claim_review_state) VALUES
  ('prd_alphonso', 'cert_india_organic', 'approved'),
  -- Second approved certification on the same product -- regression
  -- coverage for the _certifications_for() bug (0081) that used to
  -- collapse every product down to a single certification.
  ('prd_alphonso', 'cert_pgs_india', 'approved'),
  ('prd_spinach', 'cert_pgs_india', 'approved'),
  ('prd_ragi', 'cert_pgs_india', 'approved'),
  ('prd_groundnut_oil', 'cert_pgs_india', 'approved'),
  ('prd_rajma', 'cert_india_organic', 'approved');

-- Variants
INSERT OR IGNORE INTO product_variants (id, product_id, sku, name, weight_value, weight_unit, status, sort_order, created_at, updated_at) VALUES
  ('var_alphonso_1kg', 'prd_alphonso', 'TRG-MNG-1KG', '1 kg box (3-4 mangoes)', 1, 'kg', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_alphonso_2kg', 'prd_alphonso', 'TRG-MNG-2KG', '2 kg box (7-8 mangoes)', 2, 'kg', 'active', 2, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_spinach_250g', 'prd_spinach', 'TRG-SPN-250', '250 g bunch', 250, 'g', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_ragi_500g', 'prd_ragi', 'TRG-RGI-500', '500 g pack', 500, 'g', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_ragi_1kg', 'prd_ragi', 'TRG-RGI-1KG', '1 kg pack', 1, 'kg', 'active', 2, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_oil_500ml', 'prd_groundnut_oil', 'TRG-GNO-500', '500 ml glass bottle', 500, 'ml', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_oil_1l', 'prd_groundnut_oil', 'TRG-GNO-1L', '1 L glass bottle', 1, 'l', 'active', 2, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'),
  ('var_rajma_500g', 'prd_rajma', 'TRG-RJM-500', '500 g pack', 500, 'g', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');

-- Prices (INR paise)
INSERT OR IGNORE INTO variant_prices (id, variant_id, market_code, currency_code, list_amount_minor, sale_amount_minor, status, created_at, created_by) VALUES
  ('prc_alphonso_1kg', 'var_alphonso_1kg', 'IN', 'INR', 89900, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_alphonso_2kg', 'var_alphonso_2kg', 'IN', 'INR', 169900, 149900, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_spinach_250g', 'var_spinach_250g', 'IN', 'INR', 6900, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_ragi_500g', 'var_ragi_500g', 'IN', 'INR', 14500, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_ragi_1kg', 'var_ragi_1kg', 'IN', 'INR', 26900, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_oil_500ml', 'var_oil_500ml', 'IN', 'INR', 42500, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_oil_1l', 'var_oil_1l', 'IN', 'INR', 79900, 74900, 'active', '2026-07-01T00:00:00Z', 'usr_pm'),
  ('prc_rajma_500g', 'var_rajma_500g', 'IN', 'INR', 19900, NULL, 'active', '2026-07-01T00:00:00Z', 'usr_pm');

-- Inventory
INSERT OR IGNORE INTO inventory_locations (id, code, name, location_type, timezone, active, created_at, updated_at) VALUES
  ('loc_mumbai', 'MUM-01', 'Mumbai Fulfilment Centre', 'warehouse', 'Asia/Kolkata', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');

INSERT OR IGNORE INTO inventory_levels (variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at) VALUES
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

INSERT INTO pages (id, page_type, internal_name, title, slug, template_key, status, published_version_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by) VALUES
  ('pag_about', 'content', 'About page', 'About True Grit', 'about', 'cms_static', 'published', 'pgv_about_1', 'About True Grit', 'A traceable organic market built around verified farms, seasonal harvests and honest food.', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'),
  ('pag_delivery', 'content', 'Delivery page', 'Delivery', 'delivery', 'cms_static', 'published', 'pgv_delivery_1', 'Delivery', 'How True Grit packs, dispatches and delivers seasonal organic food orders.', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'),
  ('pag_returns', 'content', 'Returns page', 'Returns and refunds', 'returns', 'cms_static', 'published', 'pgv_returns_1', 'Returns and refunds', 'True Grit replacement and refund guidance for fresh and pantry orders.', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'),
  ('pag_privacy', 'content', 'Privacy page', 'Privacy policy', 'privacy', 'cms_static', 'published', 'pgv_privacy_1', 'Privacy policy', 'How True Grit collects, uses and protects customer account and order data.', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'),
  ('pag_terms', 'content', 'Terms page', 'Terms of service', 'terms', 'cms_static', 'published', 'pgv_terms_1', 'Terms of service', 'Terms for using the True Grit organic food market and placing orders.', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'),
  ('pag_help', 'content', 'Help page', 'Help', 'help', 'cms_static', 'published', 'pgv_help_1', 'Help', 'Quick help for True Grit orders, delivery, returns, accounts and product questions.', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'),
  ('pag_standards', 'content', 'Standards page', 'Our standards', 'standards', 'cms_static', 'published', 'pgv_standards_1', 'Our standards', 'What certified, traceable, responsibly sourced and fairly traded mean at True Grit.', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor');

INSERT INTO page_versions (id, page_id, version_number, content_json, workflow_state, created_at, created_by, approved_at, approved_by, published_at) VALUES
  ('pgv_home_1', 'pag_home', 1,
   '{"blocks":[{"id":"blk_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Certified organic. Fully traceable.","heading":"Food grown the way nature intended.","text":"Fresh organic produce, conscious pantry essentials and trusted local farms — delivered with complete transparency.","imageUrl":"/homepage-hero.png","imageAlt":"Organic mangoes held in a sunlit orchard","slides":[{"imageUrl":"/homepage-hero.png","imageAlt":"Organic mangoes held in a sunlit orchard","href":"/shop","label":"Explore the market","enabled":true},{"imageUrl":"/homepage-hero-tomatoes.png","imageAlt":"Organic tomatoes harvested in a mountain field","href":"/category/organic-vegetables","label":"Shop vegetables","enabled":true},{"imageUrl":"/homepage-hero-roots.png","imageAlt":"Fresh carrots and beets pulled from organic soil","href":"/category/organic-vegetables","label":"Shop root vegetables","enabled":true},{"imageUrl":"/homepage-hero-greens.png","imageAlt":"Fresh leafy greens and herbs held in a farm field","href":"/category/organic-vegetables","label":"Shop fresh greens","enabled":true},{"imageUrl":"/homepage-hero-citrus.png","imageAlt":"Seasonal citrus and pears in an organic orchard","href":"/seasonal","label":"See seasonal fruit","enabled":true}],"primaryAction":{"label":"Explore the market","href":"/shop"},"secondaryAction":{"label":"See what is in season","href":"/seasonal"}}},{"id":"blk_categories","type":"category_collection","version":1,"enabled":true,"props":{"heading":"Shop by food type","categorySlugs":["fresh-fruits","organic-vegetables","grains-and-millets","cold-pressed-oils"]}},{"id":"blk_products","type":"product_collection","version":1,"enabled":true,"props":{"heading":"Fresh favourites","source":"manual","productSlugs":["organic-alphonso-mangoes","organic-baby-spinach","sprouted-ragi-flour","wood-pressed-groundnut-oil","himalayan-red-rajma"],"limit":5}},{"id":"blk_farmer","type":"farmer_story","version":1,"enabled":true,"props":{"farmSlug":"devika-organics","quote":"We never needed chemicals. We needed patience.","attribution":"Devika Kulkarni, Devika Organics"}},{"id":"blk_faq","type":"faq","version":1,"enabled":true,"props":{"heading":"Our standards","items":[{"question":"What does certified organic mean here?","answer":"Every farm holds a current NPOP or PGS-India certificate that we verify and re-check annually."},{"question":"How is traceability guaranteed?","answer":"Each lot is tagged at the farm and carries its harvest date, farm and route to your door."}]}}]}',
   'published', '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-02T00:00:00Z', 'usr_admin', '2026-07-02T00:00:00Z');

INSERT INTO page_versions (id, page_id, version_number, content_json, workflow_state, created_at, created_by, approved_at, approved_by, published_at) VALUES
  ('pgv_about_1', 'pag_about', 1,
   '{"blocks":[{"id":"blk_about_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"About","heading":"A market for food with a known origin.","text":"True Grit connects households with certified organic farms, small-batch processors and seasonal harvests that can be traced from source to delivery.","primaryAction":{"label":"Meet the farmers","href":"/farms"},"secondaryAction":{"label":"Shop the market","href":"/shop"}}},{"id":"blk_about_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["Organic food should not depend on vague claims. Every product in the market is tied to a verified farm, certification record, harvest or processing date, and a clear route to the customer.","The catalogue stays intentionally focused so the team can stay close to growers, inspect paperwork, manage freshness and publish the context customers need before buying."]}}]}',
   'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'),
  ('pgv_delivery_1', 'pag_delivery', 1,
   '{"blocks":[{"id":"blk_delivery_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Delivery","heading":"Harvest-led delivery, planned around freshness.","text":"Fresh produce ships on fixed dispatch days. Pantry goods usually leave the fulfilment centre within two working days, with careful handling where needed.","primaryAction":{"label":"Shop now","href":"/shop"},"secondaryAction":{"label":"Contact support","href":"/contact"}}},{"id":"blk_delivery_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["Serviceability is checked during checkout. Some fresh products are limited to routes that can preserve quality within the promised delivery window.","Orders are packed by product type, with ventilated crates for fruit, chilled handling for delicate greens and protective sleeves for glass bottles."]}}]}',
   'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'),
  ('pgv_returns_1', 'pag_returns', 1,
   '{"blocks":[{"id":"blk_returns_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Returns","heading":"If the food arrives wrong, damaged or below standard, we make it right.","text":"Fresh food is time-sensitive, so returns are handled through photos, batch details and a quick support review.","primaryAction":{"label":"Contact support","href":"/contact"},"secondaryAction":{"label":"Read delivery policy","href":"/delivery"}}},{"id":"blk_returns_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["Report fresh produce issues within 24 hours of delivery with clear photos of the product, label and outer packaging.","Report sealed pantry goods issues within 7 days of delivery. Keep the product and packaging until support confirms the resolution."]}}]}',
   'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'),
  ('pgv_privacy_1', 'pag_privacy', 1,
   '{"blocks":[{"id":"blk_privacy_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Privacy","heading":"Customer data is used to run the market, not to obscure it.","text":"This page explains the practical data collected for orders, accounts, delivery and support.","primaryAction":{"label":"Contact support","href":"/contact"},"secondaryAction":null}},{"id":"blk_privacy_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["We collect account details, delivery details, order history, payment status, contact messages and basic site diagnostics needed to run the market.","Payment details are handled by the configured payment provider. True Grit stores payment status and references, not full card numbers."]}}]}',
   'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'),
  ('pgv_terms_1', 'pag_terms', 1,
   '{"blocks":[{"id":"blk_terms_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Terms","heading":"The basic rules for buying from True Grit.","text":"These terms cover orders, availability, delivery, support and responsible use of the market.","primaryAction":{"label":"Shop now","href":"/shop"},"secondaryAction":{"label":"Contact support","href":"/contact"}}},{"id":"blk_terms_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["You agree to provide accurate account, delivery and contact information, and to use the site only for lawful personal or business purchases.","Fresh and small-batch products can sell out or change with harvest conditions. If a confirmed order cannot be fulfilled, support will offer a replacement, refund or credit."]}}]}',
   'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'),
  ('pgv_help_1', 'pag_help', 1,
   '{"blocks":[{"id":"blk_help_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Help","heading":"Fast answers for orders, delivery and product questions.","text":"Start with the common paths below. If your issue is tied to an order, include the order reference when contacting support.","primaryAction":{"label":"Contact support","href":"/contact"},"secondaryAction":{"label":"Delivery help","href":"/delivery"}}},{"id":"blk_help_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["For order questions, include the order reference, delivery city and the phone or email used at checkout.","For product questions, send the product name and city so support can check freshness, lot and serviceability details."]}}]}',
   'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'),
  ('pgv_standards_1', 'pag_standards', 1,
   '{"blocks":[{"id":"blk_standards_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Our standards","heading":"Trust is a checklist here.","text":"Certified, traceable, responsibly sourced and fairly traded are operational standards for every published product claim.","primaryAction":{"label":"Meet the farmers","href":"/farms"},"secondaryAction":{"label":"Shop the market","href":"/shop"}}},{"id":"blk_standards_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["Every partner farm holds a current organic certificate. We check the paperwork at onboarding, verify it with the issuing body and re-check annually.","Each lot is tagged at the farm with its harvest or milling date. That tag follows the food through quality checks, packing and dispatch."]}}]}',
   'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z');

-- Article
INSERT INTO articles (id, internal_name, title, slug, excerpt, author_user_id, hero_media_id, reading_minutes, status, published_version_id, published_at, created_at, created_by, updated_at, updated_by) VALUES
  ('art_millets', 'Millet revival article', 'The quiet revival of Indian millets', 'quiet-revival-of-indian-millets',
   'How a generation of farmers is bringing climate-resilient grains back to the Indian table.',
   'usr_editor', NULL, 6, 'published', 'arv_millets_1', '2026-07-05T00:00:00Z', '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-05T00:00:00Z', 'usr_editor');

INSERT INTO article_versions (id, article_id, version_number, content_json, workflow_state, created_at, created_by) VALUES
  ('arv_millets_1', 'art_millets', 1,
   '{"blocks":[{"id":"blk_millets_body","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["For most of the twentieth century, millets fed India. Then subsidised rice and wheat pushed them to the margins - hardy grains recast as poor man''s food, grown on the land nobody irrigated.","That story is reversing. Millets need a fraction of the water that rice demands, tolerate heat that wilts wheat, and grow on soil still recovering from decades of intensive farming. For collectives like Anandvan in Wardha, they are not nostalgia - they are the only crop that makes agronomic sense on regenerating land.","The revival is also a flavour story. [Sprouted ragi](/product/sprouted-ragi-flour) has a sweetness that refined flour never had. Little millet cooks into a pilaf with real bite. A generation of cooks is rediscovering grains their grandmothers never abandoned. Try it in our [crisp sprouted ragi dosa](/recipes/crisp-sprouted-ragi-dosa).","What the movement needs now is steady demand: buyers who return every month, not just when a headline celebrates ancient grains. That steadiness is what lets a farmer plant a rain-fed crop with confidence."]}},{"id":"blk_millets_products","type":"product_collection","version":1,"enabled":true,"props":{"heading":"Shop the grains in this story","source":"manual","productSlugs":["sprouted-ragi-flour","organic-baby-spinach"],"limit":4}}],"pullQuote":"Millets are not nostalgia - they are the only crop that makes sense on regenerating land."}',
   'published', '2026-07-05T00:00:00Z', 'usr_editor');

-- Recipe
INSERT INTO recipes (id, internal_name, title, slug, excerpt, prep_minutes, cook_minutes, servings, dietary_tags_json, status, published_version_id, published_at, created_at, created_by, updated_at, updated_by) VALUES
  ('rcp_ragi_dosa', 'Ragi dosa recipe', 'Crisp sprouted ragi dosa', 'crisp-sprouted-ragi-dosa',
   'A weekday dosa with the deep, nutty flavour of sprouted finger millet.',
   15, 20, 4, '["gluten-free","plant-based"]', 'published', 'rcv_ragi_dosa_1', '2026-07-06T00:00:00Z',
   '2026-07-01T00:00:00Z', 'usr_editor', '2026-07-06T00:00:00Z', 'usr_editor');

INSERT INTO recipe_versions (id, recipe_id, version_number, content_json, workflow_state, created_at, created_by) VALUES
  ('rcv_ragi_dosa_1', 'rcp_ragi_dosa', 1,
   '{"blocks":[{"id":"blk_dosa_intro","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["This dosa uses sprouted [ragi flour](/product/sprouted-ragi-flour) for a nutty batter that crisps fast and needs no overnight fermentation."]}},{"id":"blk_dosa_products","type":"product_collection","version":1,"enabled":true,"props":{"heading":"Shop this recipe","source":"manual","productSlugs":["sprouted-ragi-flour","organic-baby-spinach","wood-pressed-groundnut-oil"],"limit":4}}],"steps":["Whisk the ragi flour with 2 1/2 cups of water and salt into a thin, pourable batter. Rest 15 minutes.","Fold in the chopped spinach and cumin seeds.","Heat a cast-iron tawa until water beads dance. Wipe with a few drops of groundnut oil.","Pour a ladle of batter from the outside in, lace-style. Drizzle oil around the edge.","Cook 2-3 minutes until the edges lift and crisp. Serve hot with chutney."]}',
   'published', '2026-07-06T00:00:00Z', 'usr_editor');

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
  ('nit_seasonal', 'nav_header', NULL, 'Seasonal', 'internal_path', '/seasonal', 2, 1),
  ('nit_farmers', 'nav_header', NULL, 'Farmers', 'internal_path', '/farms', 3, 1),
  ('nit_recipes', 'nav_header', NULL, 'Recipes', 'internal_path', '/recipes', 4, 1),
  ('nit_journal', 'nav_header', NULL, 'Blog', 'internal_path', '/blog', 5, 1),
  ('nit_standards', 'nav_header', NULL, 'Our Standards', 'internal_path', '/standards', 6, 1),
  ('nit_footer_about', 'nav_footer', NULL, 'About', 'internal_path', '/about', 1, 1),
  ('nit_footer_delivery', 'nav_footer', NULL, 'Delivery', 'internal_path', '/delivery', 2, 1),
  ('nit_footer_returns', 'nav_footer', NULL, 'Returns', 'internal_path', '/returns', 3, 1),
  ('nit_footer_contact', 'nav_footer', NULL, 'Contact', 'internal_path', '/contact', 4, 1),
  ('nit_footer_privacy', 'nav_footer', NULL, 'Privacy', 'internal_path', '/privacy', 5, 1),
  ('nit_footer_terms', 'nav_footer', NULL, 'Terms', 'internal_path', '/terms', 6, 1),
  ('nit_footer_help', 'nav_footer', NULL, 'Help', 'internal_path', '/help', 7, 1);

-- Announcement
INSERT INTO announcements (id, message, destination_path, active, created_at, created_by, updated_at) VALUES
  ('ann_launch', 'Explore True Grit''s complete organic catalogue — traditional grains, pulses, seeds and oils.', '/shop', 1, '2026-07-01T00:00:00Z', 'usr_editor', '2026-08-09T12:00:00Z');

-- Search synonyms
INSERT INTO search_synonyms (id, term, synonym, created_at) VALUES
  ('syn_1', 'ragi', 'finger millet', '2026-07-01T00:00:00Z'),
  ('syn_2', 'rajma', 'kidney beans', '2026-07-01T00:00:00Z'),
  ('syn_3', 'groundnut', 'peanut', '2026-07-01T00:00:00Z');

-- FTS index rows for seeded products
DELETE FROM search_products
WHERE product_id IN ('prd_alphonso', 'prd_spinach', 'prd_ragi', 'prd_groundnut_oil', 'prd_rajma');
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
-- Riya has a verified mobile: checkout requires one (phone_required_at_checkout),
-- so a seeded customer without one could not place an order.
INSERT INTO users (id, email, display_name, user_type, status, email_verified_at, phone_e164, phone_verified_at, created_at, updated_at) VALUES
  ('usr_cust_riya', 'riya@example.test', 'Riya Nair', 'customer', 'active', '2026-07-05T00:00:00Z', '+919999900010', '2026-07-05T00:00:00Z', '2026-07-05T00:00:00Z', '2026-07-05T00:00:00Z');

INSERT INTO customer_profiles (user_id, phone_e164, marketing_email_consent, created_at, updated_at) VALUES
  ('usr_cust_riya', '+919999900010', 1, '2026-07-05T00:00:00Z', '2026-07-05T00:00:00Z');

INSERT INTO orders (id, public_reference, customer_user_id, customer_email, currency_code, subtotal_minor, discount_minor, delivery_minor, tax_minor, total_minor, order_status, payment_status, fulfilment_status, delivery_status, placed_at, created_at, updated_at) VALUES
  ('ord_1001', 'TG-1001', 'usr_cust_riya', 'riya@example.test', 'INR', 89900, 0, 4900, 0, 94800, 'confirmed', 'paid', 'unfulfilled', 'not_ready', '2026-07-10T09:00:00Z', '2026-07-10T09:00:00Z', '2026-07-10T09:00:00Z'),
  ('ord_1002', 'TG-1002', 'usr_cust_riya', 'riya@example.test', 'INR', 149900, 0, 0, 0, 149900, 'pending_payment', 'pending', 'unfulfilled', 'not_ready', '2026-07-12T14:30:00Z', '2026-07-12T14:30:00Z', '2026-07-12T14:30:00Z');

INSERT INTO order_items (id, order_id, product_id, variant_id, product_name, variant_name, sku, quantity, unit_list_amount_minor, unit_effective_amount_minor, discount_minor, tax_minor, line_total_minor, farm_id) VALUES
  ('oit_1001', 'ord_1001', 'prd_alphonso', 'var_alphonso_1kg', 'Organic Alphonso Mangoes', '1 kg box (3-4 mangoes)', 'TRG-MNG-1KG', 1, 89900, 89900, 0, 0, 89900, 'farm_devika'),
  ('oit_1002', 'ord_1002', 'prd_alphonso', 'var_alphonso_2kg', 'Organic Alphonso Mangoes', '2 kg box (7-8 mangoes)', 'TRG-MNG-2KG', 1, 149900, 149900, 0, 0, 149900, 'farm_devika');

-- Two more customers, purely so reviews below have more than one voice.
INSERT INTO users (id, email, display_name, user_type, status, email_verified_at, phone_e164, phone_verified_at, created_at, updated_at) VALUES
  ('usr_cust_arjun', 'arjun@example.test', 'Arjun Bhatia', 'customer', 'active', '2026-07-06T00:00:00Z', '+919999900011', '2026-07-06T00:00:00Z', '2026-07-06T00:00:00Z', '2026-07-06T00:00:00Z'),
  ('usr_cust_meher', 'meher@example.test', 'Meher Chandra', 'customer', 'active', '2026-07-07T00:00:00Z', '+919999900012', '2026-07-07T00:00:00Z', '2026-07-07T00:00:00Z', '2026-07-07T00:00:00Z');

INSERT INTO customer_profiles (user_id, phone_e164, marketing_email_consent, created_at, updated_at) VALUES
  ('usr_cust_arjun', '+919999900011', 1, '2026-07-06T00:00:00Z', '2026-07-06T00:00:00Z'),
  ('usr_cust_meher', '+919999900012', 0, '2026-07-07T00:00:00Z', '2026-07-07T00:00:00Z');

-- Completed orders backing the demo reviews below. `services.reviews.create_review`
-- only accepts a review against a completed order that actually contains the
-- product, so every review row here points at one of these rather than at
-- ord_1001/ord_1002 above (confirmed / pending_payment — not yet reviewable).
--
-- Deliberately never prd_alphonso: test_revenue.py hardcodes farm_devika as
-- having exactly one paid order (ord_1001, ₹899) across the whole seed, and a
-- second paid alphonso order here would double its computed revenue and break
-- that module. Every product below belongs to a different farm instead.
INSERT INTO orders (id, public_reference, customer_user_id, customer_email, currency_code, subtotal_minor, discount_minor, delivery_minor, tax_minor, total_minor, order_status, payment_status, fulfilment_status, delivery_status, placed_at, created_at, updated_at) VALUES
  ('ord_1003', 'TG-1003', 'usr_cust_riya', 'riya@example.test', 'INR', 13800, 0, 4900, 0, 18700, 'completed', 'paid', 'fulfilled', 'delivered', '2026-07-14T09:00:00Z', '2026-07-14T09:00:00Z', '2026-07-16T09:00:00Z'),
  ('ord_1004', 'TG-1004', 'usr_cust_arjun', 'arjun@example.test', 'INR', 14500, 0, 4900, 0, 19400, 'completed', 'paid', 'fulfilled', 'delivered', '2026-07-15T09:00:00Z', '2026-07-15T09:00:00Z', '2026-07-17T09:00:00Z'),
  ('ord_1005', 'TG-1005', 'usr_cust_meher', 'meher@example.test', 'INR', 6900, 0, 4900, 0, 11800, 'completed', 'paid', 'fulfilled', 'delivered', '2026-07-16T09:00:00Z', '2026-07-16T09:00:00Z', '2026-07-18T09:00:00Z'),
  ('ord_1006', 'TG-1006', 'usr_cust_riya', 'riya@example.test', 'INR', 12900, 0, 4900, 0, 17800, 'completed', 'paid', 'fulfilled', 'delivered', '2026-07-18T09:00:00Z', '2026-07-18T09:00:00Z', '2026-07-20T09:00:00Z'),
  ('ord_1007', 'TG-1007', 'usr_cust_arjun', 'arjun@example.test', 'INR', 32900, 0, 4900, 0, 37800, 'completed', 'paid', 'fulfilled', 'delivered', '2026-07-19T09:00:00Z', '2026-07-19T09:00:00Z', '2026-07-21T09:00:00Z');

INSERT INTO order_items (id, order_id, product_id, variant_id, product_name, variant_name, sku, quantity, unit_list_amount_minor, unit_effective_amount_minor, discount_minor, tax_minor, line_total_minor, farm_id) VALUES
  ('oit_1003', 'ord_1003', 'prd_spinach', 'var_spinach_250g', 'Organic Baby Spinach', '250 g bunch', 'TRG-SPN-250', 2, 6900, 6900, 0, 0, 13800, 'farm_anandvan'),
  ('oit_1004', 'ord_1004', 'prd_ragi', 'var_ragi_500g', 'Sprouted Ragi Flour', '500 g pack', 'TRG-RGI-500', 1, 14500, 14500, 0, 0, 14500, 'farm_anandvan'),
  ('oit_1005', 'ord_1005', 'prd_spinach', 'var_spinach_250g', 'Organic Baby Spinach', '250 g bunch', 'TRG-SPN-250', 1, 6900, 6900, 0, 0, 6900, 'farm_anandvan'),
  ('oit_1006', 'ord_1006', 'prd_rajma', 'var_rajma_500g', 'Himalayan Rajma', '500 g pack', 'TRG-RJM-500', 1, 12900, 12900, 0, 0, 12900, 'farm_himgiri'),
  ('oit_1007', 'ord_1007', 'prd_groundnut_oil', 'var_oil_1l', 'Wood-Pressed Groundnut Oil', '1 L glass bottle', 'TRG-GNO-1L', 1, 32900, 32900, 0, 0, 32900, 'farm_anandvan');

-- Product reviews (migration 0057). Four approved so the product pages and the
-- rule-based homepage showcase (minRating 4) have real content to render; one
-- left pending so the admin Reviews queue is not empty on a fresh checkout.
INSERT INTO reviews (id, product_id, customer_user_id, order_id, rating, title, body, status, created_at, updated_at, moderated_at, moderated_by) VALUES
  ('rev_spinach_1', 'prd_spinach', 'usr_cust_riya', 'ord_1003', 4, 'Fresh and lasted well', 'Noticeably fresher than what I find at the local market, and it kept for four days in the fridge without wilting.', 'approved', '2026-07-17T10:00:00Z', '2026-07-17T13:00:00Z', '2026-07-17T13:00:00Z', 'usr_admin'),
  ('rev_spinach_2', 'prd_spinach', 'usr_cust_meher', 'ord_1005', 5, 'The freshest greens I have had delivered', 'No wilting, no yellowing, straight from the field to the fridge. Genuinely better than anything from the local market.', 'approved', '2026-07-19T10:00:00Z', '2026-07-19T12:00:00Z', '2026-07-19T12:00:00Z', 'usr_admin'),
  ('rev_ragi_1', 'prd_ragi', 'usr_cust_arjun', 'ord_1004', 5, 'Great texture for dosas', 'Sprouted ragi makes a noticeably crisper dosa than the usual flour. Will reorder.', 'pending', '2026-07-18T09:30:00Z', '2026-07-18T09:30:00Z', NULL, NULL),
  ('rev_rajma_1', 'prd_rajma', 'usr_cust_riya', 'ord_1006', 4, 'Cooks evenly, good flavour', 'Holds its shape well after soaking and cooks in the usual time. Tastes noticeably better than the polished rajma I used to buy.', 'approved', '2026-07-21T08:00:00Z', '2026-07-21T11:00:00Z', '2026-07-21T11:00:00Z', 'usr_admin'),
  ('rev_oil_1', 'prd_groundnut_oil', 'usr_cust_arjun', 'ord_1007', 3, 'Good oil, strong smell at first', 'Flavour is good once it settles for a few days, but the bottle smells quite strong straight after opening.', 'approved', '2026-07-22T08:00:00Z', '2026-07-22T10:30:00Z', '2026-07-22T10:30:00Z', 'usr_admin');

-- Farm membership (farms exist by now): the Devika owner is scoped to farm_devika,
-- whose catalogue includes prd_alphonso.
INSERT INTO farm_members (user_id, farm_id, created_at, created_by) VALUES
  ('usr_farmowner', 'farm_devika', '2026-07-01T00:00:00Z', 'usr_admin');

-- Editorial library. These are ordinary CMS records, not hard-coded
-- storefront fixtures, so staff can revise, unpublish or archive every item
-- from the Recipes, Blog and Community sections of the admin panel.
CREATE TEMP TABLE seed_recipes (
  n INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  slug TEXT NOT NULL,
  excerpt TEXT NOT NULL,
  prep INTEGER NOT NULL,
  cook INTEGER NOT NULL,
  servings INTEGER NOT NULL,
  tags TEXT NOT NULL,
  ingredient_one TEXT NOT NULL,
  ingredient_two TEXT NOT NULL,
  ingredient_three TEXT NOT NULL,
  introduction TEXT NOT NULL,
  steps TEXT NOT NULL
);

INSERT INTO seed_recipes VALUES
  (1,'Aloo methi for a weeknight','aloo-methi-weeknight','Soft potatoes and fresh fenugreek cooked until the edges catch in the pan.',15,25,4,'["vegetarian","gluten-free"]','500 g potatoes','2 packed cups methi leaves','1 tsp cumin seeds','This is the dry aloo methi I make when dinner needs to be simple. The trick is to let the potatoes colour before the greens go in.','["Cut the potatoes into small even cubes.","Warm oil and crackle the cumin.","Add potatoes and salt, then cover for 12 minutes.","Fold in the methi and cook uncovered until dry.","Finish with lemon and serve with hot rotis."]'),
  (2,'Tomato rasam with crushed pepper','tomato-rasam-crushed-pepper','A bright rasam with ripe tomatoes, garlic and plenty of freshly crushed pepper.',10,25,4,'["plant-based","gluten-free"]','4 ripe tomatoes','3 garlic cloves','1 tsp peppercorns','This rasam is light enough to drink from a cup but still has the depth to spoon over rice. Use tomatoes that feel heavy and smell ripe.','["Crush the tomatoes by hand into a saucepan.","Pound garlic, cumin and pepper together.","Simmer tomatoes with tamarind water and salt.","Add the spice mixture and cooked dal water.","Temper mustard and curry leaves, then pour over."]'),
  (3,'Palak corn with cashew cream','palak-corn-cashew-cream','Sweet corn in a silky spinach gravy made without dairy.',20,25,4,'["plant-based","gluten-free"]','400 g spinach','1 cup sweet corn','12 soaked cashews','Cashews give this palak corn a quiet richness without hiding the taste of the spinach. Do not overcook the leaves or the colour turns dull.','["Blanch spinach for one minute and cool it quickly.","Blend spinach with soaked cashews and green chilli.","Sauté ginger and cumin in a wide pan.","Add corn and cook until tender.","Stir in the spinach puree and simmer for five minutes."]'),
  (4,'Lemon poha with peanuts','lemon-poha-peanuts','Fluffy poha with turmeric, curry leaves, roasted peanuts and a sharp squeeze of lemon.',10,15,3,'["plant-based","gluten-free"]','2 cups thick poha','1/3 cup roasted peanuts','1 large lemon','A good bowl of poha should be soft but never wet. Rinse it briefly, then leave it alone while the tempering comes together.','["Rinse poha in a colander and drain well.","Fry peanuts until crisp and set aside.","Temper mustard, chilli, onion and curry leaves.","Fold in turmeric, poha, salt and a splash of water.","Turn off the heat before adding lemon and peanuts."]'),
  (5,'Beetroot poriyal with coconut','beetroot-poriyal-coconut','Tender beetroot tossed with mustard seeds, urad dal and fresh coconut.',15,20,4,'["plant-based","gluten-free"]','3 medium beetroots','1/2 cup grated coconut','1 tbsp urad dal','This poriyal is earthy, gently sweet and especially good beside curd rice. Cutting the beetroot small helps it cook without losing all its bite.','["Peel and dice the beetroot into small cubes.","Temper mustard, urad dal and curry leaves.","Add beetroot, salt and three tablespoons of water.","Cover and cook until just tender.","Fold in coconut and cook for one minute."]'),
  (6,'Masala bhindi with browned onions','masala-bhindi-browned-onions','Okra fried until crisp at the edges with onions, coriander and amchur.',20,25,4,'["plant-based","gluten-free"]','500 g tender okra','2 red onions','1 tsp amchur','Drying the okra properly is half the recipe. Once it hits the hot pan, give it room and resist stirring every few seconds.','["Wash the okra and dry it completely.","Slice okra lengthwise and onions into thin wedges.","Cook onions until deeply golden, then remove.","Fry okra in a wide pan until the edges crisp.","Return onions with spices and amchur."]'),
  (7,'Carrot ginger soup with toasted seeds','carrot-ginger-soup-toasted-seeds','A clean, warming carrot soup finished with pumpkin and sunflower seeds.',15,30,4,'["plant-based","gluten-free"]','700 g carrots','25 g fresh ginger','1/4 cup mixed seeds','This soup relies on properly roasted carrots rather than cream for body. A small apple rounds out the ginger without making the bowl sweet.','["Roast carrots, onion and apple until lightly browned.","Toast the seeds in a dry pan.","Simmer the roasted vegetables with ginger and stock.","Blend until completely smooth.","Season with lime and scatter seeds over each bowl."]'),
  (8,'Bottle gourd kofta in tomato gravy','bottle-gourd-kofta-tomato-gravy','Tender lauki dumplings in a homestyle tomato and cumin gravy.',25,35,4,'["vegetarian"]','1 medium bottle gourd','1/2 cup besan','4 ripe tomatoes','Lauki kofta is worth the extra pan. Squeeze the grated gourd well, but save the liquid because it adds lovely flavour to the gravy.','["Grate lauki, salt it and squeeze out the liquid.","Mix with besan and spices, then shape small koftas.","Shallow fry the koftas until browned.","Cook tomato, ginger and cumin into a thick gravy.","Add reserved lauki liquid and slip in koftas before serving."]'),
  (9,'Green moong khichdi with vegetables','green-moong-khichdi-vegetables','A loose, comforting khichdi with whole green moong and seasonal vegetables.',15,40,4,'["plant-based","gluten-free"]','1 cup whole green moong','3/4 cup rice','2 cups mixed vegetables','Soaking whole moong keeps this khichdi easy on a weeknight. Keep the consistency loose because it thickens noticeably as it rests.','["Soak moong for four hours and rinse the rice.","Temper cumin, ginger and a pinch of asafoetida.","Add vegetables, moong, rice and turmeric.","Pressure cook with five cups of water until soft.","Beat lightly and finish with pepper and ghee or oil."]'),
  (10,'Ragi banana breakfast pancakes','ragi-banana-breakfast-pancakes','Soft ragi pancakes sweetened with banana and scented with cardamom.',10,15,3,'["vegetarian","gluten-free"]','1 cup ragi flour','2 ripe bananas','1/2 tsp cardamom','These are tender rather than cakey, with enough banana to skip added sugar. Cook them on medium low heat so the ragi has time to cook through.','["Mash bananas until nearly smooth.","Whisk in ragi flour, cardamom and milk.","Rest the batter for ten minutes.","Cook small pancakes on a lightly greased tawa.","Serve warm with fruit or a spoonful of curd."]'),
  (11,'Cucumber peanut kosambari','cucumber-peanut-kosambari','A cool cucumber salad with roasted peanuts, coconut and lime.',15,0,4,'["plant-based","gluten-free"]','3 cucumbers','1/2 cup roasted peanuts','1/3 cup grated coconut','This is a useful hot weather side because it is crunchy, cool and ready in minutes. Salt it only when everyone is sitting down.','["Dice the cucumbers and finely chop green chilli.","Crush the peanuts roughly.","Combine cucumber, coconut, coriander and peanuts.","Temper mustard and curry leaves in a teaspoon of oil.","Add the tempering, lime and salt just before serving."]'),
  (12,'Keralan pumpkin erissery','keralan-pumpkin-erissery','Pumpkin and cowpeas in a coconut cumin sauce with a crisp coconut topping.',20,35,5,'["plant-based","gluten-free"]','600 g pumpkin','1 cup cooked cowpeas','1 cup grated coconut','Erissery sits somewhere between a curry and a warm vegetable dish. The final toasted coconut is not decoration; it changes the whole flavour.','["Cook pumpkin with turmeric and a little water.","Grind half the coconut with cumin and chilli.","Add cowpeas and coconut paste to the pumpkin.","Simmer until thick and season with salt.","Brown the remaining coconut with mustard and curry leaves, then spoon over."]'),
  (13,'Chana saag with fresh spinach','chana-saag-fresh-spinach','Creamy chickpeas and spinach with ginger, tomato and garam masala.',15,30,4,'["plant-based","gluten-free"]','2 cups cooked chickpeas','350 g spinach','2 tomatoes','This chana saag keeps some texture in the greens. Chop the spinach instead of blending it and let the chickpeas simmer long enough to take on the gravy.','["Brown onion with cumin in a heavy pan.","Add ginger, tomato and ground spices.","Cook until the tomato looks glossy.","Stir in chickpeas and a cup of water.","Add chopped spinach and simmer uncovered for ten minutes."]'),
  (14,'Raw mango dal','raw-mango-dal','Toor dal sharpened with tart green mango and a garlicky chilli tempering.',10,30,4,'["plant-based","gluten-free"]','1 cup toor dal','1 small raw mango','4 garlic cloves','Raw mango gives dal a rounder sourness than lemon. Taste the mango first because every fruit brings a different level of tartness.','["Pressure cook dal with turmeric until soft.","Peel and simmer mango pieces in a separate pan.","Whisk the cooked dal and add it to the mango.","Adjust salt and simmer for five minutes.","Temper garlic, cumin and dried chilli over the dal."]'),
  (15,'Cabbage peas sabzi','cabbage-peas-sabzi','Everyday cabbage and peas cooked quickly with cumin and black pepper.',10,18,4,'["plant-based","gluten-free"]','1 small cabbage','1 cup green peas','1 tsp cumin','Cabbage is best here when it still has a little spring. Use a wide pan and cook uncovered once the peas are tender.','["Shred the cabbage finely.","Crackle cumin and add sliced ginger.","Add peas with two tablespoons of water.","Fold in cabbage, turmeric and salt.","Cook uncovered until just tender, then add pepper."]'),
  (16,'Sweet potato chaat with mint','sweet-potato-chaat-mint','Roasted sweet potato with mint chutney, lime and crunchy sev.',15,30,4,'["plant-based","gluten-free"]','700 g sweet potatoes','1 cup mint leaves','1/2 cup fine sev','Roasting concentrates the sweet potato and keeps the pieces from turning mushy. Assemble the chaat at the last minute so every bite stays lively.','["Roast sweet potato cubes until browned at the corners.","Blend mint, coriander, chilli and lime into a chutney.","Toss the warm potato with chaat masala.","Spoon over mint chutney and a little tamarind.","Finish with onion, coriander and sev."]'),
  (17,'Pepper mushroom fry','pepper-mushroom-fry','Mushrooms, shallots and curry leaves tossed with a coarse pepper masala.',15,20,3,'["plant-based","gluten-free"]','400 g mushrooms','12 shallots','2 tsp black pepper','Use a pan large enough to let the mushrooms brown. If they are crowded, they steam and the pepper masala never clings properly.','["Pound pepper, fennel and cumin coarsely.","Brown shallots with curry leaves.","Add mushrooms and cook over high heat.","Sprinkle in the ground masala and salt.","Cook until dry and finish with a squeeze of lime."]'),
  (18,'Methi thepla with sesame','methi-thepla-sesame','Soft whole wheat flatbreads packed with fenugreek, sesame and yoghurt.',20,25,4,'["vegetarian"]','2 cups whole wheat flour','2 cups chopped methi','2 tbsp sesame seeds','A little yoghurt keeps these theplas soft long after they leave the tawa. They travel well with pickle and a small pot of curd.','["Mix flour, methi, sesame, spices and yoghurt.","Knead with just enough water for a soft dough.","Rest covered for twenty minutes.","Roll into thin rounds.","Cook on a hot tawa with a few drops of oil per side."]'),
  (19,'Jackfruit pepper pulao','jackfruit-pepper-pulao','Fragrant rice with young jackfruit, whole spices and a peppery finish.',25,40,5,'["plant-based","gluten-free"]','500 g young jackfruit','2 cups basmati rice','1 tbsp black pepper','Young jackfruit gives this pulao real substance. Boil it briefly first so it absorbs the masala rather than tasting raw at the centre.','["Parboil jackfruit with salt and turmeric.","Soak rice for twenty minutes.","Brown onions with whole spices.","Add jackfruit, mint and crushed pepper.","Fold in rice and cook by absorption until fluffy."]'),
  (20,'Turai chana dal','turai-chana-dal','Ridge gourd and chana dal simmered with tomato, cumin and green chilli.',15,35,4,'["plant-based","gluten-free"]','2 ridge gourds','3/4 cup chana dal','2 tomatoes','Ridge gourd melts into the dal and makes a light gravy without much effort. Keep the dal intact rather than cooking it to a paste.','["Soak chana dal for thirty minutes.","Peel the ridges from the gourds and cut into chunks.","Cook onion, cumin, tomato and chilli.","Add dal, gourd and two cups of water.","Cover until tender, then finish with coriander."]'),
  (21,'Mango overnight oats with pistachio','mango-overnight-oats-pistachio','Creamy oats layered with ripe mango, yoghurt and pistachios.',10,0,2,'["vegetarian"]','1 cup rolled oats','1 large ripe mango','1/4 cup pistachios','Make the oat base the night before and cut the mango in the morning. The fruit stays brighter and the pistachios keep their crunch.','["Stir oats, milk, yoghurt and cardamom together.","Cover and refrigerate overnight.","Dice the mango just before serving.","Loosen the oats with a splash of milk.","Layer with mango and finish with pistachios."]'),
  (22,'Kadai cauliflower and capsicum','kadai-cauliflower-capsicum','Charred cauliflower and peppers in a rough coriander chilli masala.',20,25,4,'["plant-based","gluten-free"]','1 large cauliflower','2 green capsicums','2 tbsp coriander seeds','Roast the cauliflower separately before it meets the gravy. That small step keeps the florets firm and gives the finished dish a smoky edge.','["Toast coriander and dried chilli, then grind coarsely.","Roast cauliflower florets until spotted brown.","Cook onion, ginger and tomato until thick.","Add capsicum and the ground kadai masala.","Fold in cauliflower and cook for five minutes."]'),
  (23,'Rajma stuffed capsicum','rajma-stuffed-capsicum','Roasted peppers filled with spiced rajma, rice and a little melted cheese.',20,35,4,'["vegetarian","gluten-free"]','4 large capsicums','2 cups cooked rajma','1 cup cooked rice','Leftover rajma and rice make an excellent filling for peppers. Choose broad capsicums that will sit steadily in the baking dish.','["Halve capsicums and remove the seeds.","Mix rajma, rice, coriander and a spoonful of tomato chutney.","Fill each pepper and top lightly with cheese.","Bake until the peppers soften and blister.","Rest for five minutes before serving."]'),
  (24,'Lauki raita with roasted cumin','lauki-raita-roasted-cumin','Cooling yoghurt with tender bottle gourd, mint and roasted cumin.',10,15,4,'["vegetarian","gluten-free"]','400 g bottle gourd','2 cups plain yoghurt','1 tsp cumin seeds','This mild raita is particularly good with a spicy pulao. Let the cooked lauki cool completely before mixing it into the yoghurt.','["Grate the lauki and simmer it with a pinch of salt.","Drain and cool completely.","Whisk yoghurt until smooth.","Fold in lauki, mint and roasted cumin.","Chill for twenty minutes before serving."]'),
  (25,'Masoor dal with caramelised garlic','masoor-dal-caramelised-garlic','Red lentils cooked soft and finished with slow browned garlic.',10,25,4,'["plant-based","gluten-free"]','1 cup red lentils','8 garlic cloves','2 dried red chillies','The dal itself is deliberately plain so the garlic tempering can lead. Slice the garlic evenly and keep the heat low until it turns golden.','["Rinse lentils and simmer with turmeric and tomato.","Whisk once the lentils are soft.","Season with salt and adjust the consistency.","Slowly brown sliced garlic in oil.","Add chilli and cumin, then pour everything over the dal."]'),
  (26,'Spinach paneer paratha','spinach-paneer-paratha','Green spinach dough wrapped around a peppery paneer filling.',30,25,4,'["vegetarian"]','3 cups whole wheat flour','250 g paneer','200 g spinach','Blending spinach into the dough makes these parathas easier to roll than a leafy filling. Keep the paneer mixture dry and finely crumbled.','["Blanch and puree the spinach.","Knead flour with spinach puree into a soft dough.","Mix crumbled paneer with pepper, chilli and salt.","Stuff and gently roll each paratha.","Cook on a hot tawa until golden on both sides."]'),
  (27,'Tamarind sesame eggplant','tamarind-sesame-eggplant','Small eggplants in a tangy sesame, peanut and tamarind sauce.',25,35,4,'["plant-based","gluten-free"]','8 small eggplants','1/3 cup sesame seeds','2 tbsp tamarind pulp','This gravy is bold enough for plain rice and a spoon of curd. Slit the eggplants without cutting through the stem so they hold together.','["Toast sesame, peanuts and coconut, then grind.","Slit eggplants and brown them in a wide pan.","Cook onion and the ground paste until fragrant.","Add tamarind water and return the eggplants.","Cover and simmer until the centres are tender."]'),
  (28,'Coconut vegetable stew','coconut-vegetable-stew','A gentle Kerala style stew with vegetables, ginger and coconut milk.',20,30,5,'["plant-based","gluten-free"]','4 cups mixed vegetables','400 ml coconut milk','30 g fresh ginger','This is a quiet curry with no ground chilli or tomato. Green chilli, ginger and whole pepper give it warmth without overpowering the vegetables.','["Cook potato, carrot and beans with ginger and green chilli.","Add thin coconut milk and simmer until tender.","Stir in thick coconut milk without boiling hard.","Temper curry leaves, shallots and whole pepper.","Spoon the tempering over and serve with appam."]'),
  (29,'Roasted tomato coconut chutney','roasted-tomato-coconut-chutney','Smoky tomato chutney with coconut, dried chilli and curry leaves.',10,15,6,'["plant-based","gluten-free"]','4 tomatoes','1 cup grated coconut','4 dried red chillies','Charring the cut side of the tomatoes adds more depth than simply boiling them. This chutney is lovely with dosa, idli or a plain bowl of rice.','["Place tomatoes cut side down in a hot oiled pan.","Toast dried chilli and urad dal separately.","Blend tomato, coconut, chilli and dal with salt.","Keep the texture slightly coarse.","Temper mustard and curry leaves over the chutney."]'),
  (30,'Green bean potato usal','green-bean-potato-usal','Green beans and potatoes with a fresh coconut coriander masala.',15,25,4,'["plant-based","gluten-free"]','350 g green beans','2 medium potatoes','3/4 cup grated coconut','The fresh masala makes this everyday usal taste especially bright. Add it near the end so the coriander does not lose all its character.','["Cut beans and potatoes into small even pieces.","Cook mustard, asafoetida and curry leaves.","Add vegetables, turmeric, salt and a splash of water.","Grind coconut, coriander and green chilli coarsely.","Fold in the masala and cook uncovered for five minutes."]'),
  (31,'Amaranth leaf dal','amaranth-leaf-dal','Toor dal with earthy amaranth leaves and a mustard garlic tempering.',15,30,4,'["plant-based","gluten-free"]','1 bunch amaranth leaves','1 cup toor dal','5 garlic cloves','Amaranth leaves soften quickly and bring a deeper flavour than spinach. Wash them in two changes of water because soil collects around the stems.','["Pressure cook dal with turmeric.","Chop the amaranth leaves and tender stems.","Simmer leaves with tomato and green chilli.","Add whisked dal and season with salt.","Finish with browned garlic, mustard and cumin."]'),
  (32,'Sprouted moong bhel','sprouted-moong-bhel','A fresh bhel of sprouted moong, tomato, herbs and crisp puffed rice.',20,5,4,'["plant-based"]','2 cups sprouted moong','3 cups puffed rice','1/2 cup mint chutney','Blanching the sprouts briefly takes off their raw edge while keeping the crunch. Mix in the puffed rice only when you are ready to eat.','["Blanch sprouts for two minutes and cool.","Chop tomato, onion, cucumber and coriander.","Combine vegetables with sprouts and chaat masala.","Add mint and tamarind chutneys.","Fold through puffed rice and sev at the table."]'),
  (33,'Cauliflower leaf stir fry','cauliflower-leaf-stir-fry','Tender cauliflower leaves cooked with garlic, chilli and crushed peanuts.',15,15,3,'["plant-based","gluten-free"]','Leaves from 2 cauliflowers','4 garlic cloves','1/3 cup roasted peanuts','The inner cauliflower leaves are sweet and perfectly edible. Slice the thicker ribs finely so everything becomes tender at the same time.','["Wash the leaves well and separate thick ribs.","Slice ribs finely and leaves into ribbons.","Fry garlic and chilli until fragrant.","Add ribs first, followed by the leaves.","Cook until tender and finish with crushed peanuts."]'),
  (34,'Foxtail millet lemon rice','foxtail-millet-lemon-rice','Fluffy foxtail millet with lemon, peanuts and a classic mustard tempering.',10,20,4,'["plant-based","gluten-free"]','1 1/2 cups foxtail millet','1/3 cup peanuts','2 lemons','Cook and cool the millet before seasoning it, just as you would with leftover rice. This keeps the grains separate and light.','["Rinse millet and cook with two and a half cups of water.","Spread on a tray to cool.","Fry peanuts, then temper mustard, dal and curry leaves.","Fold the tempering and turmeric through the millet.","Add lemon juice and salt once off the heat."]'),
  (35,'Tomato peanut rice','tomato-peanut-rice','Tangy tomato rice with roasted peanuts and warming whole spices.',15,25,4,'["plant-based","gluten-free"]','3 cups cooked rice','5 ripe tomatoes','1/2 cup roasted peanuts','This is the lunchbox tomato rice my family asks for. Reduce the tomatoes until jammy before adding rice or the grains will turn soggy.','["Cook mustard, cinnamon, onion and curry leaves.","Add chopped tomatoes, chilli and turmeric.","Reduce until the oil begins to separate.","Fold in cold cooked rice and salt.","Finish with peanuts and chopped coriander."]'),
  (36,'Pumpkin seed coriander pesto pasta','pumpkin-seed-coriander-pesto-pasta','Coriander and pumpkin seed pesto tossed with pasta, peas and lime.',15,15,4,'["vegetarian"]','350 g pasta','2 cups coriander leaves','1/2 cup pumpkin seeds','Pumpkin seeds make a creamy pesto without the heaviness of too much cheese. Coriander and lime take it in a fresher, greener direction.','["Toast pumpkin seeds until they begin to pop.","Blend seeds, coriander, garlic, lime and olive oil.","Boil pasta and peas in well salted water.","Reserve a cup of cooking water before draining.","Toss pasta with pesto, cheese and enough water to loosen."]'),
  (37,'Roasted radish and greens','roasted-radish-and-greens','Whole radishes roasted with cumin, then tossed with their garlicky tops.',10,25,3,'["plant-based","gluten-free"]','2 bunches radishes with tops','1 tsp cumin seeds','3 garlic cloves','Roasting softens the peppery bite of radish and makes it almost juicy. The fresh tops become a quick saag in the same pan.','["Separate radishes from their leafy tops.","Halve radishes and roast with cumin and salt.","Wash and roughly chop the greens.","Sauté garlic, then wilt the greens.","Toss roasted radishes through the greens with lemon."]'),
  (38,'Chickpea flour vegetable cheela','chickpea-flour-vegetable-cheela','Crisp besan pancakes full of grated vegetables and coriander.',15,20,4,'["plant-based","gluten-free"]','2 cups besan','2 cups grated vegetables','1 tsp ajwain','Cheela is forgiving, fast and ideal for using the last carrot or courgette in the drawer. Keep the batter thinner than pakora batter.','["Whisk besan, spices and water into a smooth batter.","Fold in grated vegetables and coriander.","Rest for ten minutes.","Spread thin rounds on a hot greased tawa.","Cook both sides until spotted and crisp."]'),
  (39,'Braised turnips with peas','braised-turnips-with-peas','Sweet young turnips and peas in a light ginger tomato masala.',15,25,4,'["plant-based","gluten-free"]','500 g young turnips','1 cup green peas','2 tomatoes','Small turnips become buttery when braised and are much milder than their raw smell suggests. Leave a little stem attached if the greens are fresh.','["Peel turnips and cut them into wedges.","Brown the wedges lightly in oil.","Cook ginger, cumin and tomato in the same pan.","Return turnips with peas and half a cup of water.","Cover until tender, then reduce the gravy."]'),
  (40,'Dates and sesame panjiri','dates-sesame-panjiri','A crumbly whole wheat panjiri with dates, sesame and toasted nuts.',10,25,10,'["vegetarian"]','2 cups whole wheat flour','1 cup chopped dates','1/2 cup sesame seeds','Dates sweeten this panjiri without turning it sticky. Let the flour roast patiently until the kitchen smells nutty, then lower the heat.','["Toast sesame and nuts separately.","Roast whole wheat flour slowly in ghee.","Add chopped dates and stir until they soften.","Fold in sesame, nuts and cardamom.","Cool completely before storing in a clean jar."]'),
  (41,'Garlic greens with white beans','garlic-greens-white-beans','Seasonal greens and creamy white beans with garlic, chilli and lemon.',15,20,4,'["plant-based","gluten-free"]','2 bunches mixed greens','2 cups cooked white beans','6 garlic cloves','This pan works with mustard greens, chard, spinach or a mixture. The beans catch the garlicky juices and turn it into a full meal.','["Slice stems finely and tear the leafy parts.","Brown sliced garlic with chilli.","Cook stems for three minutes.","Add beans and leaves with a splash of stock.","Cover briefly, then finish uncovered with lemon."]'),
  (42,'Curd millet with pomegranate','curd-millet-pomegranate','Cooling cooked millet folded with yoghurt, ginger and pomegranate.',10,20,4,'["vegetarian","gluten-free"]','1 cup little millet','2 cups plain yoghurt','1 cup pomegranate seeds','Think of this as curd rice with a little more texture. Cook the millet softer than usual and let it cool fully before adding yoghurt.','["Cook millet with three cups of water until soft.","Mash lightly and cool completely.","Mix with yoghurt, salt and grated ginger.","Temper mustard, chilli and curry leaves.","Fold in the tempering and pomegranate seeds."]'),
  (43,'Tandoori carrots with coriander yoghurt','tandoori-carrots-coriander-yoghurt','Spiced roasted carrots over cool coriander yoghurt.',15,30,4,'["vegetarian","gluten-free"]','700 g young carrots','1 cup thick yoghurt','1 cup coriander leaves','Carrots stand up surprisingly well to a tandoori marinade. Roast them hard enough to darken the tips while the centres stay sweet and tender.','["Mix half the yoghurt with ginger, garlic and spices.","Coat carrots and leave for twenty minutes.","Roast at high heat until charred at the edges.","Blend coriander into the remaining yoghurt.","Spoon yoghurt on a plate and arrange carrots over it."]'),
  (44,'Masala oats with garden vegetables','masala-oats-garden-vegetables','Savoury oats cooked with vegetables, ginger and a tomato masala.',10,15,2,'["plant-based"]','1 cup rolled oats','2 cups chopped vegetables','1 tomato','These oats are closer to a soft vegetable upma than breakfast porridge. Toasting the oats first keeps the bowl from becoming gluey.','["Dry toast oats for three minutes and set aside.","Temper cumin and cook ginger, onion and tomato.","Add vegetables and cook until nearly tender.","Pour in water, salt and the toasted oats.","Simmer for four minutes and finish with coriander."]'),
  (45,'Lentil and pumpkin hand pies','lentil-pumpkin-hand-pies','Flaky baked parcels filled with spiced pumpkin and brown lentils.',35,40,6,'["vegetarian"]','500 g pumpkin','2 cups cooked brown lentils','500 g shortcrust pastry','The filling can be made a day ahead and should be completely cool before the pies are shaped. A spoon of pickle in the mixture adds welcome sharpness.','["Roast pumpkin until dry and caramelised.","Cook onion, spices and lentils together.","Fold in pumpkin and pickle, then cool.","Fill pastry circles and crimp the edges.","Brush with milk and bake until deeply golden."]'),
  (46,'Kohlrabi coconut curry','kohlrabi-coconut-curry','Tender kohlrabi and leaves in a mild coconut, cumin and chilli curry.',20,30,4,'["plant-based","gluten-free"]','3 kohlrabi with leaves','1 cup grated coconut','1 tsp cumin seeds','Kohlrabi tastes somewhere between cabbage heart and turnip. Use the young leaves too, adding them once the cubes are almost tender.','["Peel the tough skin from the kohlrabi and cube it.","Simmer cubes with turmeric and salt.","Grind coconut, cumin and green chilli.","Add the paste and chopped leaves.","Finish with a mustard and curry leaf tempering."]'),
  (47,'Mango ginger lime cooler','mango-ginger-lime-cooler','Ripe mango blended with fresh ginger, lime and chilled sparkling water.',10,0,4,'["plant-based","gluten-free"]','2 ripe mangoes','20 g fresh ginger','3 limes','This cooler tastes of fruit first, with ginger arriving at the end. Keep the puree thick and add sparkling water in each glass.','["Blend mango flesh with ginger and lime juice.","Pass through a sieve if the mango is fibrous.","Chill the puree for at least an hour.","Spoon puree into ice filled glasses.","Top with sparkling water and stir once."]'),
  (48,'Warm guava chilli salad','warm-guava-chilli-salad','Seared guava with chilli, lime, mint and roasted peanuts.',10,10,4,'["plant-based","gluten-free"]','4 firm guavas','1 fresh red chilli','1/3 cup roasted peanuts','Firm, just ripe guavas are best because they hold their shape in the pan. The warmth wakes up their perfume and makes the chilli taste rounder.','["Cut guavas into thick wedges.","Sear the cut sides in a lightly oiled pan.","Slice chilli and tear the mint leaves.","Toss warm guava with lime and a pinch of salt.","Scatter peanuts, chilli and mint over the top."]'),
  (49,'Rice flour banana appam','rice-flour-banana-appam','Small soft appams with banana, jaggery, coconut and cardamom.',15,20,5,'["vegetarian","gluten-free"]','2 ripe bananas','1 1/2 cups rice flour','3/4 cup grated jaggery','These quick appams need no fermentation and are best eaten warm. A very ripe banana gives the softest centre and deepest flavour.','["Melt jaggery with a little water and strain.","Mash bananas and mix with jaggery syrup.","Stir in rice flour, coconut and cardamom.","Rest the thick batter for fifteen minutes.","Cook spoonfuls in an appam pan until browned on both sides."]'),
  (50,'One pot spinach tomato rice','one-pot-spinach-tomato-rice','An easy rice pot with spinach, tomato, whole spices and toasted cashews.',15,30,4,'["plant-based","gluten-free"]','2 cups basmati rice','300 g spinach','4 ripe tomatoes','This is generous enough for dinner and packs well for lunch the next day. Chop the spinach rather than pureeing it for better texture.','["Soak rice for twenty minutes.","Brown cashews and set them aside.","Cook whole spices, onion and tomato until soft.","Add chopped spinach, rice and measured water.","Cook covered until fluffy and finish with cashews."]');

INSERT INTO recipes (
  id, internal_name, title, slug, excerpt, prep_minutes, cook_minutes, servings,
  dietary_tags_json, status, published_version_id, published_at, seo_title,
  seo_description, created_at, created_by, updated_at, updated_by
)
SELECT
  printf('rcp_library_%03d', n), title || ' recipe', title, slug, excerpt, prep,
  cook, servings, tags, 'published', printf('rcv_library_%03d_1', n),
  printf('2026-05-%02dT08:00:00Z', ((n - 1) % 28) + 1), title || ' recipe',
  excerpt, '2026-04-01T08:00:00Z', 'usr_chef',
  printf('2026-05-%02dT08:00:00Z', ((n - 1) % 28) + 1), 'usr_chef'
FROM seed_recipes;

INSERT INTO recipe_versions (
  id, recipe_id, version_number, content_json, workflow_state, created_at,
  created_by, approved_at, approved_by, published_at
)
SELECT
  printf('rcv_library_%03d_1', n), printf('rcp_library_%03d', n), 1,
  json_object(
    'blocks', json_array(
      json_object(
        'id', printf('blk_recipe_%03d_intro', n), 'type', 'rich_text',
        'version', 1, 'enabled', json('true'),
        'props', json_object('paragraphs', json_array(introduction))
      ),
      json_object(
        'id', printf('blk_recipe_%03d_products', n),
        'type', 'product_collection', 'version', 1, 'enabled', json('true'),
        'props', json_object(
          'heading', 'Ingredients from the market',
          'source', 'manual',
          'productSlugs', CASE (n % 5)
            WHEN 0 THEN json_array('organic-baby-spinach','wood-pressed-groundnut-oil')
            WHEN 1 THEN json_array('sprouted-ragi-flour','wood-pressed-groundnut-oil')
            WHEN 2 THEN json_array('himalayan-red-rajma','organic-baby-spinach')
            WHEN 3 THEN json_array('organic-alphonso-mangoes','wood-pressed-groundnut-oil')
            ELSE json_array('organic-baby-spinach','himalayan-red-rajma')
          END,
          'limit', 4
        )
      )
    ),
    'steps', json(steps)
  ),
  'published', '2026-04-01T08:00:00Z', 'usr_chef',
  printf('2026-05-%02dT07:30:00Z', ((n - 1) % 28) + 1), 'usr_admin',
  printf('2026-05-%02dT08:00:00Z', ((n - 1) % 28) + 1)
FROM seed_recipes;

INSERT INTO recipe_ingredients (id, recipe_id, label, quantity_text, product_id, sort_order)
SELECT printf('ing_library_%03d_1', n), printf('rcp_library_%03d', n),
       substr(ingredient_one, instr(ingredient_one, ' ') + 1),
       substr(ingredient_one, 1, instr(ingredient_one, ' ') - 1), NULL, 1
FROM seed_recipes
UNION ALL
SELECT printf('ing_library_%03d_2', n), printf('rcp_library_%03d', n),
       ingredient_two, NULL, NULL, 2 FROM seed_recipes
UNION ALL
SELECT printf('ing_library_%03d_3', n), printf('rcp_library_%03d', n),
       ingredient_three, NULL, NULL, 3 FROM seed_recipes;

INSERT INTO search_content (entity_type, entity_id, title, slug, excerpt, keywords)
SELECT 'recipe', printf('rcp_library_%03d', n), title, slug, excerpt,
       replace(slug, '-', ' ')
FROM seed_recipes;

DROP TABLE seed_recipes;

CREATE TEMP TABLE seed_articles (
  n INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  slug TEXT NOT NULL,
  excerpt TEXT NOT NULL,
  opening TEXT NOT NULL,
  middle TEXT NOT NULL,
  closing TEXT NOT NULL
);

INSERT INTO seed_articles VALUES
  (1,'Why spinach tastes sweeter in winter','why-spinach-tastes-sweeter-in-winter','Cold nights change more than the texture of leafy greens.','A winter bunch of spinach often tastes noticeably sweeter than one cut in humid weather. That is not imagination. When nights turn cold, the plant stores more soluble sugars in its leaves, which helps protect its cells.','The difference is easiest to notice when spinach is cooked simply. A quick wilt with garlic lets its mineral sweetness come through, while long boiling washes away both flavour and colour. Look for crisp stems and leaves that feel dry, not slick.','Keep the bunch unwashed in a cloth lined box in the fridge. Wash just before cooking, and use the tender stems as well as the leaves.'),
  (2,'The patient work behind a good tomato','patient-work-behind-good-tomato','A flavourful tomato begins with variety, soil and a farmer willing to wait.','Tomatoes are often judged by colour, but a deep red skin tells only part of the story. Variety, daytime heat, cool nights and the point of harvest all decide whether a tomato tastes lively or merely looks ready.','Farmers growing for nearby markets can leave fruit on the vine longer. That final stretch matters because aroma compounds continue to develop while the fruit is attached. It also makes the tomato softer, which is why careful packing is part of the job.','At home, keep ripe tomatoes on the counter and use them within a few days. Refrigerate only when they threaten to spoil, then bring them back to room temperature before eating.'),
  (3,'What crop rotation looks like on a small farm','crop-rotation-small-farm','Rotation is less a diagram and more a season by season negotiation.','A neat crop rotation plan might show legumes followed by leafy vegetables, roots and grains. On a working small farm, the idea has to bend around rainfall, seed availability, labour and what families nearby will actually buy.','The principle remains useful. Different plant families draw and return different nutrients, root at different depths and interrupt the life cycles of pests. A pulse crop can leave useful nitrogen behind, while a deep rooted crop opens compacted soil.','Good rotation rarely produces a dramatic before and after photograph. Its value appears slowly in steadier yields, fewer disease flare ups and soil that is easier to work after rain.'),
  (4,'A practical guide to storing fresh herbs','storing-fresh-herbs-practical-guide','A few small habits can buy coriander, mint and dill several useful days.','Most herbs fail in the fridge for one of two reasons: they dry out or they sit in trapped moisture and become slimy. The right balance depends on whether the stems are sturdy or delicate.','Coriander and mint do well with their stem ends in a small jar of water, loosely covered. Tender dill and leafy greens prefer a dry cloth inside a lidded box. In every case, remove damaged leaves before storage.','Do not wash herbs until you plan to use them unless you can dry them thoroughly. If a bunch is already tired, trim the stems and stand it in cold water for twenty minutes.'),
  (5,'Why old varieties still matter','why-old-vegetable-varieties-matter','Local seed lines carry flavour, memory and useful resilience.','An old vegetable variety survives because someone keeps choosing its seed. Often that choice is based on qualities that do not appear in a supermarket specification: how it handles a short monsoon, the taste of its tender leaves or how well it cooks in a family dish.','Modern hybrids can be productive and valuable, but relying on a narrow genetic base makes the food system brittle. Locally adapted lines give growers more options when rainfall shifts or a familiar pest becomes harder to manage.','Buying these vegetables when they appear is one quiet way to support seed keeping. Ask the grower what the variety is called and how people in the region cook it.'),
  (6,'The truth about imperfect fruit','truth-about-imperfect-fruit','Scars, freckles and uneven shapes often say little about eating quality.','A mango rubbed by a branch can carry a dark mark while the flesh beneath remains perfect. Citrus may show wind scarring. Guava grown without cosmetic sprays can be freckled and still smell wonderful.','Sorting is important when damage signals rot or insect entry. Cosmetic variation is different. Rejecting every marked fruit wastes part of a harvest that took the same soil, water and labour to grow.','Use your senses. A sound fruit feels right for its variety, smells fresh and has no spreading soft patch. A clean scar on the skin is usually only a record of weather.'),
  (7,'Reading an organic certificate without getting lost','reading-organic-certificate','The useful details are simpler than the paperwork first suggests.','An organic certificate should identify the operator, the certifying body, the scope of certification and the period for which it is valid. The farm name on a website is not always identical to the legal operator name, so the address and reference number matter too.','Scope is especially important. A certificate may cover crop production, processing or handling, and it may list particular fields or products. Certification is not a blanket claim that automatically follows every item a business sells.','When something seems unclear, ask for the current certificate and the product schedule. A responsible seller should be able to explain the chain in plain language.'),
  (8,'How to build a useful seasonal pantry','build-useful-seasonal-pantry','A flexible pantry helps fresh produce become dinner instead of waste.','Seasonal cooking becomes much easier when the cupboard holds a few reliable partners for whatever comes in the basket. Lentils, rice, millet, coconut, peanuts and a good cooking oil can carry greens, roots or tomatoes in different directions.','The point is not to stock every spice and grain. Choose ingredients you already enjoy and replenish them in sensible quantities. A smaller pantry turns over faster, so oils stay fresh and pulses are less likely to be forgotten.','Once a week, look at what needs using first. Pick the vegetable, then choose the grain or pulse that will make it a meal.'),
  (9,'Why leafy vegetables need gentle washing','washing-leafy-vegetables-gently','Clean greens thoroughly without bruising them into an early decline.','Leafy vegetables often carry soil where stems meet and along curled leaf edges. Running a tight bunch under the tap rarely reaches those places, while aggressive rubbing damages the leaves.','Fill a large bowl with cool water, separate the leaves and swish them gently. Lift the greens out rather than pouring the bowl away, because grit settles at the bottom. Repeat with fresh water until no soil remains.','Dry in a spinner or between clean cloths. If the greens are not being cooked immediately, excess water is the enemy of good storage.'),
  (10,'The case for cooking vegetable stems','case-for-cooking-vegetable-stems','Many stems are ingredients, not scraps.','Coriander stems hold more flavour than the leaves and disappear beautifully into chutney. Cauliflower ribs become sweet in a stir fry. Tender amaranth and spinach stems add welcome texture to dal.','The question is tenderness. Bend or cut a stem and notice whether it snaps cleanly or feels stringy. Tough outer fibres can sometimes be peeled, and thicker pieces simply need a head start in the pan.','Separate stems from leaves while chopping. Cook the stems first, then add the delicate leaves near the end.'),
  (11,'What makes cold pressed oil taste fresh','what-makes-cold-pressed-oil-fresh','Seed quality and careful storage matter as much as the press.','Cold pressing cannot rescue stale or poorly stored seeds. Fresh oil begins with a clean crop that has been dried correctly and protected from moisture before it reaches the mill.','After pressing, heat, air and light become the main enemies. Nut and seed oils should smell clearly of their source, never like crayons, varnish or old cupboards. A slight sediment can be normal in an unrefined oil.','Buy a bottle size your kitchen will finish in a reasonable time. Close it promptly and keep it away from the stove and direct sun.'),
  (12,'A closer look at rain fed farming','closer-look-rain-fed-farming','Farming without irrigation is skilled work shaped by timing and soil.','Rain fed does not mean a crop is simply planted and left to chance. Farmers watch the arrival of the monsoon, choose varieties suited to the expected season and prepare land to slow water rather than let it rush away.','Mulch, contour bunds and healthy organic matter help rain enter the soil and remain available between showers. Crop choice matters too. Millets and pulses can cope with dry intervals that would seriously damage paddy.','The risk is real, especially as rainfall becomes less predictable. Paying a fair price for rain fed crops helps recognise that risk and the knowledge required to manage it.'),
  (13,'Why freshly milled flour behaves differently','freshly-milled-flour-behaves-differently','Fresh flour carries more aroma and sometimes asks for a different hand with water.','Whole grain flour changes after milling. Its natural oils meet air, aromatic compounds fade and the bran gradually loses freshness. A recently milled flour often smells grassy, nutty or faintly sweet.','It can also absorb water differently from a familiar packaged flour. Start with slightly less water, rest the dough for fifteen minutes, then adjust. The bran needs time to hydrate before the final texture becomes clear.','Store flour cool and airtight. If your kitchen is hot or you buy more than a few weeks at a time, the refrigerator is a sensible place.'),
  (14,'Compost is not a single recipe','compost-is-not-single-recipe','Good compost reflects the materials, climate and farm where it is made.','There is no universal pile that suits every farm. A grower may work with crop residue, cattle dung, leaf litter, market waste or pressed oil cake, depending on what is clean and locally available.','The essentials are balance, air and moisture. A pile that is too wet turns sour and airless. One that is too dry stops breaking down. Regular observation matters more than a rigid calendar.','Finished compost should look dark and crumbly, smell earthy and no longer resemble most of its starting materials.'),
  (15,'How farmers choose when to harvest','how-farmers-choose-harvest-time','Ripeness, weather, distance and the next morning market all shape one decision.','Harvest time is a compromise between peak eating quality and the journey ahead. A tomato for a town market can stay on the vine longer than one travelling across several states. Tender greens may be cut before sunrise to hold their moisture.','Weather can overrule the plan. Rain before harvest may split ripe fruit, while a hot windy afternoon can wilt leaves in minutes. Farmers constantly read the field and the forecast together.','When produce arrives with a little variation in ripeness, that can be a sign it was picked in several careful passes rather than stripped from the plant at once.'),
  (16,'Meet the small but mighty cowpea','small-mighty-cowpea','Cowpea feeds people, covers soil and handles heat with uncommon calm.','Cowpea appears as a dry pulse, a tender green pod and even an edible leaf. In the field, its spreading growth can shade bare soil and its relationship with soil bacteria helps bring nitrogen into the system.','The plant tolerates heat and short dry spells better than many common beans. That makes it valuable to farms working with uncertain rain, though no crop is immune to prolonged drought.','Cook the dry peas until creamy but intact, then use them in sundal, curries or a warm salad with coconut and lime.'),
  (17,'A better way to use a weekly vegetable box','use-weekly-vegetable-box-better','Start with the most fragile produce and let the sturdy vegetables wait.','The easiest mistake with a vegetable box is cooking the familiar items first. By the time the weekend arrives, coriander has wilted and tender greens have become a rescue project while the pumpkin sits untouched.','Sort the box when it arrives. Plan leafy greens, herbs, mushrooms and ripe fruit for the first days. Beans and gourds come next. Roots, cabbage and pumpkin usually give you more time.','Keep one flexible meal in the week for odds and ends. Khichdi, soup, a tray roast or a mixed sabzi can absorb small quantities gracefully.'),
  (18,'Why soil should not stay bare','why-soil-should-not-stay-bare','Cover protects soil from sun, wind and the hard strike of rain.','Bare soil can heat dramatically under direct sun. Rain hits the surface, breaks small aggregates and carries fine particles away. Wind lifts dry topsoil, which is often the part richest in organic matter.','Farmers protect the ground with crop residue, living cover crops or mulch brought from elsewhere. Each method has tradeoffs around labour, pests, moisture and the availability of material.','Covered ground is not untidy ground. It is soil with armour, and often with a living root beneath it feeding the organisms below.'),
  (19,'The many lives of a raw mango','many-lives-of-raw-mango','Long before mangoes turn sweet, kitchens put their tartness to work.','A hard green mango brings acidity, fragrance and body at the same time. It can sharpen dal, become a quick grated salad, soften into panna or preserve a season in a jar of pickle.','Different preparations ask for different stages. Very young fruit has a tender stone and sharp flesh. A fuller green mango carries more aroma and may be better for cooking. Sap near the stem can irritate skin, so wash it away.','Treat raw mango as a souring ingredient rather than an unripe version of dessert fruit. Its role in the kitchen is entirely its own.'),
  (20,'What a farmer means by soil structure','what-farmer-means-soil-structure','Healthy soil is arranged into crumbs, pores and channels that roots can use.','Two soils can contain similar amounts of sand, silt and clay yet behave very differently. Structure describes how those particles gather into aggregates and how water, air and roots move between them.','Organic matter, fungal threads, roots and soil animals all help create and maintain those spaces. Heavy traffic when soil is wet can squash them, leaving a dense layer that drains poorly.','A simple sign is how the ground responds to rain. Well structured soil accepts water steadily and breaks into crumbs in the hand rather than forming a hard sealed crust.'),
  (21,'Cooking with mustard greens beyond saag','mustard-greens-beyond-saag','Their peppery leaves work in far more than one beloved slow cooked dish.','Mustard greens have a confident bitterness that softens with heat and fat. Young leaves can be sliced into dal, added to a stir fry or folded through a robust grain salad.','Older leaves benefit from longer cooking. Remove especially tough ribs, blanch if the flavour is fierce, then braise with garlic, tomato or coconut. A little acidity at the end keeps the taste open.','Mix mustard with milder spinach when introducing it to the table. Over time, the bitterness often becomes the part people look forward to.'),
  (22,'Why pulses foam when they cook','why-pulses-foam-when-cooking','The froth is normal, manageable and not a sign that the pot has spoiled.','Pulses release starch and proteins into cooking water. Agitation traps air in that mixture, creating a pale foam that can rise quickly in a crowded saucepan.','Rinsing helps remove surface starch, and a larger pot gives the foam room. Lower the heat once the water boils. You may skim the surface for a clearer broth, but it is generally harmless.','Never fill a pressure cooker beyond its recommended level, especially with foods that foam. Follow the appliance instructions and keep the vent path clean.'),
  (23,'How to tell when jaggery is fresh','how-to-tell-jaggery-is-fresh','Good jaggery smells clean and complex, not merely sweet.','Fresh jaggery can carry notes of caramel, grass and the cane juice it came from. Colour varies with the cane, season and process, so a pale block is not automatically better than a dark one.','Avoid pieces with a chemical smell, visible mould or wet leaking patches. Crystalline white specks may be sugar bloom, but fuzzy growth is not. Taste should be rounded, without a harsh salty or metallic finish.','Store jaggery airtight because it draws moisture from the air. In humid weather, smaller packs are easier to keep well.'),
  (24,'The quiet value of hedges on farms','value-of-farm-hedges','A living boundary can shelter crops, insects, birds and soil.','Farm hedges are sometimes treated as land that could have carried another crop. In practice, a mixed boundary can slow wind, catch drifting soil and give beneficial insects a place to feed and breed.','Native shrubs and flowering plants are especially useful when they bloom at different times. The design still needs care so hedges do not shade crops excessively or host unmanaged weeds.','A productive field is part of a wider habitat. Leaving room for that habitat can support the pollination and pest balance on which the crop depends.'),
  (25,'Why some cucumbers turn bitter','why-cucumbers-turn-bitter','Heat, water stress and genetics can all concentrate a cucumber''s bitter compounds.','Cucumbers naturally produce compounds called cucurbitacins. They are usually concentrated in the leaves and stem, but stress can increase bitterness in the fruit, often near the stem end and skin.','Consistent watering and varieties suited to local heat reduce the risk. In the kitchen, taste a thin slice from the stem end before committing the whole cucumber to a salad.','A slightly bitter end can sometimes be trimmed and peeled. If bitterness runs through the fruit or tastes unusually strong, it is better not to eat it.'),
  (26,'A field guide to tender okra','field-guide-tender-okra','Size helps, but touch and the tip tell you more.','Tender okra feels firm without being woody and has a fresh green cap. The narrow tip should snap with gentle pressure. Very large pods can still be tender, though small to medium ones are a safer bet.','Store the pods dry and loosely wrapped. Water on the surface speeds darkening and decay. Wash just before cooking, then dry thoroughly if you want crisp edges.','Do not worry about a little natural fuzz. Look instead for deep bruises, wet patches or pods that bend like rubber.'),
  (27,'Millet is a family, not one grain','millet-is-a-family','Ragi, jowar, bajra and the small millets behave differently in the field and pot.','The word millet groups several grains with distinct plants, flavours and cooking habits. Pearl millet makes a robust roti, finger millet mills into dark aromatic flour and little millet can cook much like rice.','Their nutrition also varies. Broad claims about all millets hide useful differences in fibre, minerals and how the grain has been processed. Whole grain, polished grain, flour and malt are not interchangeable.','Start with the dish you want to cook, then choose the millet that suits it. Respecting their differences is more useful than treating them as a single fashionable substitute.'),
  (28,'What happens at a farm packhouse','what-happens-at-farm-packhouse','The short journey from field crate to dispatch asks for careful decisions.','At a small packhouse, produce is received by lot, checked, sorted and prepared for travel. The work may look simple, but speed matters because harvested vegetables continue losing moisture and generating heat.','Not every crop should be washed. Some roots travel better with dry soil brushed away, while leafy greens may need rapid cooling. Damaged pieces are separated so one soft item does not spoil a whole crate.','Good packing protects without pretending produce is identical. The goal is to deliver sound food and preserve a traceable link to where and when it was harvested.'),
  (29,'The best use for overripe tomatoes','best-use-overripe-tomatoes','Soft tomatoes may be past salad stage but exactly right for the pot.','When a tomato becomes soft yet still smells clean and shows no mould, its concentrated flavour is useful. Grate it into a quick masala, roast it for soup or simmer several into a freezer friendly base.','Cut every tomato open before using it. Discard fruit with fuzzy growth, a fermented smell or liquid rot. Trimming is not enough when mould has taken hold in a soft, watery food.','A hot oven is excellent for a mixed tray of ripe tomatoes. Add garlic and oil, roast until collapsed, then blend or freeze in small portions.'),
  (30,'Why farm work starts before sunrise','why-farm-work-starts-before-sunrise','Cool early hours protect both people and delicate produce.','Before sunrise, temperatures are lower, leaves are well hydrated and wind is often gentle. Those conditions make it easier to cut greens, herbs and flowers without immediate wilting.','The timing also protects workers from the harshest heat. Harvest is only the first task; produce still needs sorting, packing and transport, often in time for a morning collection.','An early harvest is not automatically superior for every crop, but for tender leafy vegetables it can make a visible difference by the time the bunch reaches a kitchen.'),
  (31,'How to revive tired leafy greens','revive-tired-leafy-greens','Cold water can restore leaves that have lost moisture, within reason.','A bunch that has gone limp but remains green and clean may simply be dehydrated. Trim the stem ends and soak the leaves in very cold water for fifteen to thirty minutes.','Lift them out, dry well and use soon. The treatment cannot reverse yellowing, slime or decay, and repeated soaking will not make old greens fresh again.','If the leaves remain too soft for salad, cook them promptly in dal, soup or a stir fry. Rescue is useful, but prevention through good storage is better.'),
  (32,'The difference between mulch and compost','mulch-and-compost-difference','Both use organic material, but they do different jobs in the field.','Compost is decomposed material added mainly to support soil fertility and biology. Mulch is a protective layer laid on the surface to shade soil, slow evaporation and soften the impact of rain.','A material can move from one role to the other over time. Straw mulch gradually breaks down, while finished compost can also be spread as a surface layer. The intention and stage of decomposition are different.','Farmers choose based on what the soil needs, what material is available and whether pests or heavy rain change the risks.'),
  (33,'A cook''s guide to pumpkin varieties','cooks-guide-pumpkin-varieties','Dry, dense pumpkins and moist, sweet ones belong in different dishes.','Some pumpkins cook into firm, floury cubes that hold beautifully in a curry. Others collapse into a silky mash and are ideal for soup, halwa or erissery. Skin colour alone does not reliably tell you which is which.','Ask the grower, or test a small wedge. Dense flesh feels heavy and often releases less water in the pan. Many thin skinned varieties can be cooked without peeling.','Once cut, wrap the pumpkin and refrigerate it. Remove the seed cavity if it is very moist, and use any good seeds for roasting.'),
  (34,'Why bees need farms after flowering','why-bees-need-farms-after-flowering','Pollinators require food and shelter beyond the few weeks a crop is in bloom.','A field can be rich with flowers during one crop and become a food desert immediately afterward. Bees and other pollinators need overlapping blooms across seasons, along with water and places to nest.','Hedges, uncultivated corners and flowering cover crops help bridge the gaps. Avoiding broad insecticide use during bloom is crucial, but habitat matters throughout the year.','Pollination is not a service that can be switched on only when the crop needs it. It depends on living populations supported over time.'),
  (35,'The pleasure of a slower onion','pleasure-of-slow-cooked-onion','Time turns a sharp onion into the deep base of countless dishes.','Onions release water before they begin to brown. A crowded pan or high heat can scorch the edges while the middle stays raw, so use a broad vessel and enough patience.','Salt draws out moisture, and regular stirring prevents hot spots. For a brown masala base, wait until the onions are evenly golden before adding wet tomato or yoghurt.','The exact shade depends on the dish. Pale and soft suits a gentle stew; dark amber brings sweetness and weight to rajma, korma and pulao.'),
  (36,'Why local food still needs good logistics','local-food-needs-good-logistics','Shorter distance helps, but careful handling decides what arrives well.','A farm may be only a few hours away, yet leafy vegetables can wilt if they sit in sun after harvest. Tomatoes can bruise in an overfilled crate. Local food is not automatically fresh without a disciplined chain.','Harvest timing, shade, clean crates, rapid sorting and sensible route planning all matter. Chilling is valuable for some crops, while tropical fruit can be damaged by temperatures that are too low.','Good logistics is mostly invisible when it works. The customer sees a crisp bunch, not the series of small decisions that protected it.'),
  (37,'Saving seeds from the kitchen garden','saving-seeds-kitchen-garden','Begin with open pollinated plants and a clear idea of what may cross.','Seed saving starts before harvest. Choose healthy plants that show the qualities you want, and allow their fruit or seed heads to reach full maturity. That stage is often later than eating ripeness.','Open pollinated varieties generally reproduce more predictably than hybrids. Crops such as gourds and brassicas can cross with nearby relatives, so isolation or hand pollination may be needed.','Dry seed thoroughly, label it with variety and year, and store it cool. Even a small notebook helps turn one season of saving into useful knowledge.'),
  (38,'A gentle introduction to fermented batters','introduction-fermented-batters','Time, temperature and clean tools turn grain and dal into a lively batter.','Dosa and idli batters ferment through microorganisms already present on the ingredients and in the environment. Soaking, grinding and warmth give them the conditions to multiply.','A good batter smells pleasantly sour and looks aerated. Fermentation moves faster in warm weather, so the clock is only a guide. Salt timing, grain ratio and grinding texture all affect the result.','Use clean containers with room for expansion. If the batter smells rotten, shows coloured mould or feels strangely slimy, discard it rather than tasting.'),
  (39,'How shade changes a cup of coffee','how-shade-changes-coffee-farm','Trees above coffee influence temperature, water, wildlife and the pace of ripening.','Coffee evolved as an understory plant, and many farms grow it beneath a canopy. Shade can moderate heat, slow moisture loss and give cherries more time to mature.','The kind of canopy matters. A diverse mix of native and useful trees offers different habitat from a uniform stand. Too much shade can increase humidity and disease pressure, so farmers prune and adjust it.','When a coffee is described as shade grown, ask what that means on the particular farm. The practice is a spectrum, not a single fixed standard.'),
  (40,'Why freshly dug potatoes need care','freshly-dug-potatoes-need-care','New potatoes have delicate skins and a different place in the kitchen.','A newly harvested potato has a thin skin that rubs away easily. It holds more moisture than a cured storage potato and has a clean, waxy texture that suits boiling, roasting and quick curries.','Because the skin has not toughened, new potatoes bruise and lose water faster. Keep them cool, dark and ventilated, and use them sooner rather than expecting months of storage.','Scrub gently instead of peeling. The fragile skin is part of their appeal and helps the potatoes hold together in the pot.'),
  (41,'The overlooked flavour of curry leaves','overlooked-flavour-curry-leaves','Fresh curry leaves offer citrus, resin and warmth that dried leaves rarely match.','Curry leaves are often described as a garnish, but their flavour is built through hot fat. When fresh leaves hit oil, aromatic compounds spread through the tempering and into the whole dish.','Dry the leaves before frying because water spits in hot oil. Add them after mustard seeds crackle and stand back. They should turn glossy and crisp at the edge without blackening.','Freeze extra leaves in a well sealed bag if necessary. They soften on thawing but keep more aroma than leaves left to dry slowly in the fridge.'),
  (42,'What regenerative farming asks us to notice','what-regenerative-farming-asks-us-to-notice','The useful questions concern outcomes, context and time.','Regenerative farming is used to describe many practices: cover crops, reduced tillage, compost, grazing or agroforestry. A list of practices alone does not show whether soil and farm livelihoods are actually improving.','Ask what changed and how it was measured. Is water entering the soil more readily? Is erosion lower? Are inputs falling without pushing risk onto workers? Has the farm become more financially stable?','No farm begins in the same place. Honest accounts include tradeoffs, failed trials and the years required for ecological change.'),
  (43,'How to shop for fragrant coriander','shop-for-fragrant-coriander','Aromatic stems and dry, lively leaves make the best bunch.','Lift a coriander bunch and smell near the cut stems. Fresh coriander should be immediately recognisable. Leaves may be small or large depending on variety, but they should not feel slimy.','A few yellow outer leaves are easy to remove. Blackened stems, sour odour and wet decay travel quickly through a tied bunch. Loosen the bundle when you get home and check the centre.','Use the stems in chutney, curry paste and soup. Save the prettiest leaves for finishing the plate.'),
  (44,'Why biodiversity belongs in a food conversation','biodiversity-food-conversation','What grows around and between crops affects the resilience of a farm.','A productive farm is more than rows of the crop being sold. Soil organisms, pollinators, birds, hedges, water channels and uncultivated patches all take part in how the place functions.','Diversity does not remove every pest or guarantee a harvest. It can create more relationships and response options, making the system less dependent on one crop, one input or one narrow season.','Food choices cannot manage a farm from afar, but supporting growers who protect habitat gives that work economic room.'),
  (45,'The right way to cool cooked grains','cool-cooked-grains-safely','Fast cooling protects both texture and food safety.','Cooked rice and other grains should not sit warm for hours. Bacterial spores can survive cooking and multiply as the food lingers through warm temperatures.','Spread leftovers in a shallow container so steam escapes, then refrigerate promptly. Large deep pots cool slowly at the centre. Keep the fridge cold and use the grain within a short, sensible window.','Reheat only the portion you need until it is steaming throughout. Good leftover cooking begins with good cooling.'),
  (46,'Why a lemon can feel heavy for its size','why-juicy-lemon-feels-heavy','Weight, skin and fragrance offer useful clues to the juice inside.','A lemon that feels heavy relative to its size usually contains more juice. Thin, smooth skin can also suggest a less pithy fruit, though variety and season create plenty of exceptions.','Roll a room temperature lemon firmly under your palm before cutting. This breaks some internal membranes and makes juicing easier. Zest it first if the peel is clean and unwaxed.','Store lemons in the fridge for a longer life, but bring them to room temperature when you want the most juice.'),
  (47,'The work hidden in hand weeding','work-hidden-in-hand-weeding','Removing weeds without herbicide requires timing, judgement and many hours.','A weed is easiest to manage when it is young and the soil has the right moisture. Wait too long and roots strengthen, seed forms and the job multiplies. Work when soil is too wet and footsteps can cause compaction.','Hand tools allow precision around a crop, but they demand labour that is often underestimated in the price of food. Mulch, crop spacing and cover crops can reduce the burden without eliminating it.','When a farm avoids synthetic herbicide, weed control does not disappear. It becomes a visible part of skilled field work.'),
  (48,'Cooking a mixed harvest without a recipe','cooking-mixed-harvest-without-recipe','A few reliable methods turn uneven handfuls into a generous meal.','Small quantities are common at the end of a market week: two carrots, half a cabbage, a few beans and a tired bunch of herbs. Start by grouping them by how long they need to cook.','Dense roots go into the pan first, followed by firm green vegetables and finally leaves. Choose one flavour direction rather than adding every spice. Coconut and mustard, tomato and cumin, or garlic and pepper are enough.','Taste for salt and acidity at the end. A squeeze of lime or spoon of curd often makes a mixed dish feel intentional.'),
  (49,'Why good food labels use plain language','good-food-labels-use-plain-language','Clarity helps shoppers compare products and hold claims to account.','A useful label tells you what the food is, what it contains, how much is present, who made it and how to store it. Decorative language should not bury those basics.','Claims such as natural, farm fresh or wholesome can sound reassuring without having a fixed meaning. Certification marks, ingredient lists, dates and traceable producer details offer more to evaluate.','The best label does not ask for blind trust. It gives enough clear information for a person to make a choice and ask a sensible follow up question.'),
  (50,'A season ends before the appetite does','when-produce-season-ends','The final harvest is a reminder that real abundance has a rhythm.','At the height of a season, mangoes, peas or tomatoes can seem endless. Then size varies, supply thins and the last lot arrives. A genuine harvest cannot be extended indefinitely without changing where or how the crop is grown.','Preserving is one answer: pickle green mango, freeze tomato base, dry chillies or bottle fruit pulp. Another is simply to wait and let anticipation return.','Seasonal eating is not a rule of purity. It is a way of noticing time, weather and the limits that make a favourite ingredient feel special.');

INSERT INTO articles (
  id, internal_name, title, slug, excerpt, author_user_id, hero_media_id,
  reading_minutes, status, published_version_id, published_at, seo_title,
  seo_description, created_at, created_by, updated_at, updated_by
)
SELECT
  printf('art_library_%03d', n), title || ' article', title, slug, excerpt,
  'usr_blogger', NULL, 4 + (n % 4), 'published',
  printf('arv_library_%03d_1', n),
  printf('2026-06-%02dT09:00:00Z', ((n - 1) % 28) + 1), title, excerpt,
  '2026-04-01T09:00:00Z', 'usr_blogger',
  printf('2026-06-%02dT09:00:00Z', ((n - 1) % 28) + 1), 'usr_blogger'
FROM seed_articles;

INSERT INTO article_versions (
  id, article_id, version_number, content_json, workflow_state, created_at,
  created_by, approved_at, approved_by, published_at
)
SELECT
  printf('arv_library_%03d_1', n), printf('art_library_%03d', n), 1,
  json_object(
    'blocks', json_array(
      json_object(
        'id', printf('blk_article_%03d_body', n), 'type', 'rich_text',
        'version', 1, 'enabled', json('true'),
        'props', json_object('paragraphs', json_array(opening, middle, closing))
      ),
      json_object(
        'id', printf('blk_article_%03d_products', n),
        'type', 'product_collection', 'version', 1, 'enabled', json('true'),
        'props', json_object(
          'heading', 'From this story',
          'source', 'manual',
          'productSlugs', CASE (n % 5)
            WHEN 0 THEN json_array('organic-baby-spinach','sprouted-ragi-flour')
            WHEN 1 THEN json_array('organic-baby-spinach','wood-pressed-groundnut-oil')
            WHEN 2 THEN json_array('sprouted-ragi-flour','himalayan-red-rajma')
            WHEN 3 THEN json_array('organic-alphonso-mangoes','wood-pressed-groundnut-oil')
            ELSE json_array('himalayan-red-rajma','organic-baby-spinach')
          END,
          'limit', 4
        )
      )
    )
  ),
  'published', '2026-04-01T09:00:00Z', 'usr_blogger',
  printf('2026-06-%02dT08:30:00Z', ((n - 1) % 28) + 1), 'usr_admin',
  printf('2026-06-%02dT09:00:00Z', ((n - 1) % 28) + 1)
FROM seed_articles;

INSERT INTO search_content (entity_type, entity_id, title, slug, excerpt, keywords)
SELECT 'article', printf('art_library_%03d', n), title, slug, excerpt,
       replace(slug, '-', ' ')
FROM seed_articles;

DROP TABLE seed_articles;

-- A small cast of established community members makes the seeded threads read
-- like an actual neighbourhood rather than one account talking to itself.
INSERT INTO users (
  id, email, display_name, user_type, status, email_verified_at, created_at, updated_at
) VALUES
  ('usr_community_anita','anita.k@example.test','Anita Kulkarni','customer','active','2024-02-11T00:00:00Z','2024-02-11T00:00:00Z','2026-06-01T00:00:00Z'),
  ('usr_community_farhan','farhan.m@example.test','Farhan Mirza','customer','active','2023-11-05T00:00:00Z','2023-11-05T00:00:00Z','2026-06-01T00:00:00Z'),
  ('usr_community_leela','leela.s@example.test','Leela Shah','customer','active','2024-04-19T00:00:00Z','2024-04-19T00:00:00Z','2026-06-01T00:00:00Z'),
  ('usr_community_nikhil','nikhil.r@example.test','Nikhil Rao','customer','active','2023-08-22T00:00:00Z','2023-08-22T00:00:00Z','2026-06-01T00:00:00Z'),
  ('usr_community_jo','jo.thomas@example.test','Jo Thomas','customer','active','2024-01-14T00:00:00Z','2024-01-14T00:00:00Z','2026-06-01T00:00:00Z'),
  ('usr_community_maya','maya.p@example.test','Maya Prasad','customer','active','2023-12-02T00:00:00Z','2023-12-02T00:00:00Z','2026-06-01T00:00:00Z'),
  ('usr_community_aman','aman.g@example.test','Aman Gill','customer','active','2024-03-08T00:00:00Z','2024-03-08T00:00:00Z','2026-06-01T00:00:00Z'),
  ('usr_community_saira','saira.k@example.test','Saira Khan','customer','active','2023-09-17T00:00:00Z','2023-09-17T00:00:00Z','2026-06-01T00:00:00Z');

CREATE TEMP TABLE seed_discussion_topics (
  n INTEGER PRIMARY KEY,
  subject TEXT NOT NULL,
  question TEXT NOT NULL,
  follow_up_title TEXT NOT NULL,
  follow_up TEXT NOT NULL
);

INSERT INTO seed_discussion_topics VALUES
  (1,'spinach storage','How do you keep a large bunch of spinach crisp beyond two days? Mine is dry when it arrives, but the leaves still soften quickly in the vegetable drawer.','The cloth lined box worked for my spinach','A quick update after trying the suggestions here. I removed the ties, picked out two bruised leaves and used a dry cotton cloth inside a shallow box. Day four and the stems still have a snap.'),
  (2,'foxtail millet texture','I have cooked foxtail millet twice and both times it clumped. What water ratio gives separate grains for lemon millet? I am using a regular saucepan.','Cooling millet on a steel plate made the difference','The ratio helped, but spreading the cooked millet out was the real change. It stopped steaming itself and the tempering coated the grains instead of turning into one soft mass.'),
  (3,'using cauliflower leaves','The cauliflower in my box came with a lot of fresh inner leaves. Has anyone cooked them without ending up with tough ribs? I would rather not compost half the bundle.','Cauliflower leaves are now going into our stir fry','I sliced the ribs very thin, started them five minutes ahead and added the leaves with garlic. They were sweeter than I expected. Thank you to everyone who said not to throw them away.'),
  (4,'raw mango pickle','Does anyone have a small batch raw mango pickle that does not need weeks in the sun? I only have two mangoes and would like something for the fridge.','My two mango fridge pickle report','Mustard, fenugreek, chilli and warm oil did the job. It was sharp on day one and much rounder by day three. The little jar is already half gone.'),
  (5,'ragi roti cracking','My ragi rotis crack around the edge while I pat them out. Is the dough too dry, or am I letting it cool too much before shaping?','Hot water fixed my ragi roti dough','I poured boiling water gradually and covered the bowl for ten minutes before kneading. The dough finally held together, and wetting my fingers was easier than adding extra flour.'),
  (6,'tomato glut','We have more ripe tomatoes than we can eat this week. What would you preserve if freezer space is limited and you do not own canning equipment?','A tray of slow roasted tomatoes was the answer','I roasted two kilos with garlic until they were almost jammy. They shrank enough to fit in one small container, and we have already used a spoonful in dal and pasta.'),
  (7,'bitter cucumber','One cucumber in today''s delivery tastes bitter near the stem. The rest of it seems fine. Do you trim that end or skip the whole cucumber?','I tasted from both ends and played it safe','The bitterness ran further than I first thought, so I discarded that cucumber and used the others. Support also asked for the lot label, which was reassuring.'),
  (8,'curry leaf plant','My potted curry leaf plant is growing tall with very few side shoots. When and where should I prune it without setting the plant back?','The curry leaf plant is branching at last','I pinched the growing tip just above a healthy set of leaves and moved the pot into stronger morning light. Two new shoots appeared below the cut.'),
  (9,'pressure cooking rajma','Even after an overnight soak, my rajma sometimes stays firm. Could old beans be the reason, or does salt at the start make a bigger difference?','Fresh rajma solved the hard bean mystery','I cooked a newer pack in the same water and with the same salt. It softened much faster, so age really was the issue rather than my pressure cooker.'),
  (10,'compost smell','Our balcony compost bin has started smelling sour after several rainy days. What is the quickest way to bring it back without emptying everything?','Dry leaves rescued the compost bin','I mixed in shredded dry leaves and a little torn cardboard, then left the lid ajar under cover. The sour smell was nearly gone after two days.'),
  (11,'okra slime','How are you getting bhindi crisp without using a lot of oil? Mine releases water even when I wash it well ahead of cooking.','A wider pan gave me properly crisp bhindi','I had been crowding nearly 600 grams into a small kadai. Cooking in two batches felt fussy, but it browned in half the time and never became sticky.'),
  (12,'coriander stems','I save coriander stems for chutney, but I still end up with more than I can use. Can they be frozen without making everything taste grassy?','Frozen coriander stem paste is genuinely handy','I pulsed the stems with ginger and a little water, then froze teaspoons on a plate before bagging them. One goes straight into the pan for dal now.'),
  (13,'sourdough with atta','Has anyone maintained a sourdough starter using only stone ground atta? Mine is active but the bread comes out much denser than I expect.','My atta starter needed more water','Increasing the hydration made the starter easier to read and much more active. The loaf is still hearty, but it no longer feels heavy or under fermented.'),
  (14,'washing leeks','There is soil deep between the layers of the small leeks I bought. Is it better to split them before washing or soak them whole?','Splitting the leeks saved a lot of rinsing','I cut them lengthwise while leaving the root end attached, then fanned the layers under water. Much easier, and no grit in dinner.'),
  (15,'pumpkin seeds','The pumpkin seeds from my last two pumpkins are plump and clean. What is your method for roasting them so the centre cooks before the outside burns?','Low and slow worked for the pumpkin seeds','After simmering the cleaned seeds in salted water, I dried and roasted them at a lower temperature. They turned crisp all the way through.'),
  (16,'methi bitterness','Fresh methi is sometimes pleasantly bitter and sometimes too strong for my family. Does salting the leaves help, or does it wash away the flavour?','Potatoes balanced the strong methi nicely','I skipped squeezing the leaves and used small browned potatoes instead. A little lemon at the end made the bitterness feel deliberate rather than harsh.'),
  (17,'coconut milk splitting','My coconut vegetable stew tastes good but the thick coconut milk separates at the end. Am I adding it while the pan is too hot?','No more split coconut stew','I lowered the heat completely before adding the thick milk and did not let it return to a hard boil. The sauce stayed smooth.'),
  (18,'storing jaggery','How do you store a large block of jaggery through humid weather? Mine becomes wet around the edges even in a closed steel tin.','Smaller jars kept the jaggery dry','I chopped the block and divided it between two truly airtight jars. Keeping only a small working jar near the stove has stopped the whole batch picking up moisture.'),
  (19,'balcony mint','My mint keeps getting long bare stems and tiny leaves. It receives about four hours of sun. Should I cut it right back or feed it first?','A hard trim brought the mint back','I cut the stems just above low leaf nodes, refreshed the top layer of soil and kept it evenly damp. The new growth is much bushier.'),
  (20,'red rice cooking','I love the nutty flavour of red rice but struggle to get the bran tender before the inside goes soft. Would soaking it for several hours help?','A long soak improved the red rice','Four hours of soaking and cooking it like pasta gave me the texture I wanted. I drained it when the grains were tender and let it steam covered.'),
  (21,'vegetable stock scraps','Which vegetable trimmings actually improve stock? I have learned that cabbage and too much beetroot can take over the whole pot.','My freezer stock bag is more selective now','I kept onion ends, carrot peel, mushroom stems, celery and coriander roots. Leaving out brassicas produced a much cleaner stock.'),
  (22,'ripening guava','The guavas arrived firm and fragrant but are still too hard to eat. Do they ripen better in a paper bag, and should I add a banana?','The paper bag ripened guava overnight','One banana and two guavas in a paper bag worked faster than expected. I moved them to the fridge as soon as they softened.'),
  (23,'chana dal soaking','Is soaking chana dal worth it for an ordinary weeknight dal? I notice a shorter cooking time, but I am curious whether the texture changes too.','Soaked chana dal held its shape better','A thirty minute soak shortened the pressure cooking and gave me tender dal that was not blown apart. I will keep doing it when I remember.'),
  (24,'reviving carrots','A forgotten bunch of carrots has gone bendy but has no bad smell or soft rot. Can cold water bring back enough crunch for a salad?','The cold water carrot trick actually works','I trimmed the ends and left the carrots in ice water for an hour. They were crisp enough to grate, though I used them the same day.'),
  (25,'mustard oil smoke','Do you always heat mustard oil until it just begins to smoke before cooking? I enjoy the flavour but do not want the kitchen filled with fumes.','Gentler mustard oil heating tasted better to me','I warmed it until it shimmered and the sharp raw smell softened, without pushing it to a cloud of smoke. The finished sabzi still had plenty of character.'),
  (26,'beet greens','The beetroot bunch has beautiful leaves with red stems. Should I cook them like spinach, or do the stems need a separate start?','Beet stems went into the pan first','I chopped the stems small and cooked them with garlic for five minutes before adding the leaves. Nothing was tough, and the colour was lovely.'),
  (27,'homemade paneer yield','How much paneer do you usually get from two litres of full fat milk? My last batch was tasty but much smaller than recipes suggest.','A gentler drain improved my paneer yield','I had been pressing while the curds were still very hot and squeezing out too much moisture. Hanging briefly before a light press gave a softer, larger block.'),
  (28,'lemon pickle salt','My lemon pickle has plenty of juice but a few pieces are still firm after three weeks. Does it need more salt, more time or warmer light?','A few more sunny afternoons softened the lemons','The salt level was fine. I shook the jar daily and gave it four more afternoons in gentle sun, and the peel finally relaxed.'),
  (29,'millet flour storage','Should ragi and bajra flour always be refrigerated? Our kitchen is warm, but I usually finish a one kilo bag within a month.','The fridge kept my bajra flour noticeably fresher','I moved half the bag into an airtight container in the fridge and compared it with the cupboard portion. The chilled flour kept its sweet nutty smell longer.'),
  (30,'green chilli abundance','A neighbour gave me far more green chillies than we can use fresh. What preserves their clean flavour without turning them into a very salty pickle?','Frozen whole chillies were the easiest solution','I washed, dried and froze them on a tray before bagging. They soften after thawing but slice cleanly straight from frozen for cooked dishes.'),
  (31,'soft dosa batter','My dosa batter ferments well and smells right, but the dosas stay soft even on a hot cast iron tawa. Could the batter simply be too thick?','Thinner batter and less oil made crisp dosas','I loosened the batter until it spread easily and wiped the pan with barely any oil. The edges finally crisped instead of frying into softness.'),
  (32,'pea shoots','Has anyone eaten the tender shoots from garden pea plants? I am pruning a crowded patch and do not want to waste them if they are good.','Pea shoots were excellent in a quick stir fry','I used only the soft tips, washed them carefully and cooked them for a minute with garlic. They tasted like a gentler version of peas.'),
  (33,'onion sprouting','Several onions in my basket have green shoots but are still firm. Are they fine to cook, and can the shoots be used like spring onion?','The sprouted onions went into soup','I removed the slightly bitter centre shoot from two and used the rest of the bulbs. The tender green tops were good as a garnish.'),
  (34,'rice weevils','I found a few tiny weevils in an old jar of rice. How do you clean the cupboard and stop them spreading to unopened grains?','The pantry is clean and everything is in jars now','I discarded the badly affected rice, vacuumed every shelf edge and washed the containers. Freezing new grain for a few days before storage is my next precaution.'),
  (35,'radish leaves','Radish leaves taste prickly when raw. Does blanching help, or is there a better way to cook them without losing the peppery flavour?','Radish leaf dal was the winning idea','Chopping the leaves finely and simmering them with moong dal softened the prickly texture. Garlic and lemon kept their character alive.'),
  (36,'thick yoghurt','Can regular homemade dahi be strained into something thick enough for a dip, or does it need a special culture?','Overnight hung curd made a great dip','I lined a sieve with clean cotton and left the yoghurt in the fridge overnight. It was thick by morning, and the whey went into roti dough.'),
  (37,'ginger skin','Do you peel young ginger? The skin on this week''s bunch is so thin that scraping it feels like wasting more than it removes.','I stopped peeling the young ginger','A good scrub was enough. I grated it skin and all into chai and could not notice any toughness.'),
  (38,'mushroom browning','My mushrooms release a pool of water before they brown. Is salting late more important than pan temperature, or do I simply cook too many at once?','Batch cooking solved the mushroom puddle','The pan was hot enough, but I had doubled the quantity. Two uncrowded batches browned quickly, and I salted after they took on colour.'),
  (39,'freezing coconut','What is the best way to freeze fresh grated coconut so it stays loose enough to take a handful at a time? Mine freezes into one solid brick.','A flat freezer bag fixed the coconut brick','I spread the grated coconut thin in a zip bag and scored portions with a ruler before freezing. Pieces now snap off cleanly.'),
  (40,'amaranth grain popping','I am trying to pop amaranth in a dry kadai, but half the grains burn while the rest stay raw. How small should each batch be?','One spoon at a time finally popped the amaranth','The pan needed to be very hot and each batch only a teaspoon. It takes attention, but nearly every grain pops before the first ones scorch.'),
  (41,'sweet lime peel','Is sweet lime peel useful for anything in the kitchen? It smells lovely but has much more white pith than orange peel.','Sweet lime peel made a gentle cleaning vinegar','The pith was too bitter for the preserve I tried, but steeping the clean peels in vinegar made a fragrant kitchen cleaner.'),
  (42,'watering basil','My basil looks fine in the morning and droops every afternoon, even though the soil still feels damp. Could the pot be getting too hot?','Moving the basil out of afternoon sun helped','The black pot was almost hot to touch by three o''clock. Morning sun and bright afternoon shade stopped the daily collapse.'),
  (43,'dal without tomato','Tomatoes are between seasons here. What gives everyday toor dal enough brightness without trying to imitate tomato flavour?','Raw mango gave the dal exactly what it needed','A few green mango pieces cooked separately and added to the dal brought a lovely clean sourness. Tamarind worked well in the next batch too.'),
  (44,'bread ends','I have accumulated a bag of bread heels in the freezer. Beyond breadcrumbs, what do you make that actually uses a useful amount?','Savoury bread pudding cleared the freezer bag','I soaked the pieces with eggs, milk, spinach and leftover cheese, then baked the whole dish. It used nearly the entire bag and made a proper lunch.'),
  (45,'cooking kohlrabi','This is my first kohlrabi and I am not sure how much of the outer skin to remove. Is the leafy top worth cooking too?','Kohlrabi was much easier than it looked','I peeled until the fibrous layer was gone, cubed the bulb and added the chopped young leaves near the end. It tasted like a sweet cabbage stem.'),
  (46,'tamarind storage','Do you refrigerate a block of seedless tamarind after opening? Our pantry is dry, but it takes us several months to finish one.','Refrigerated tamarind stayed softer and cleaner','I wrapped the block well and put it in an airtight box in the fridge. It is easy to pinch off and has not darkened as quickly.'),
  (47,'fenugreek seeds','I accidentally soaked too many methi seeds. Can the extras be sprouted for eating, and how do you keep the bitterness pleasant?','The methi sprouts were strong but good','I sprouted them for only two days and used a small handful with cucumber, curd and lemon. More than that would have taken over the bowl.'),
  (48,'leftover coconut milk','What do you do with half a can of coconut milk after making curry? I would like ideas that are not another full pot of curry.','Coconut milk went into breakfast oats','I used it with water to cook oats and added banana and cardamom. The rest froze well in an ice cube tray for future chutneys.'),
  (49,'keeping potatoes dark','Our kitchen has no cool pantry and potatoes start sprouting quickly. Is a ventilated basket inside a lower cupboard dark enough?','A smaller weekly potato order works best for us','The cupboard helped, but buying less made the biggest difference. I also moved the onions to a separate basket after learning they speed each other along.'),
  (50,'first balcony tomato harvest','I picked the first three tomatoes from our balcony plant today. They are small, slightly uneven and smell better than anything I have bought in weeks. What should I cook that will not hide them?','We ate the tomatoes on toast with salt','No elaborate recipe in the end. I rubbed warm toast with garlic, added thick tomato slices, salt and groundnut oil, and understood why everyone said to keep it simple.');

WITH member_ids(position, user_id) AS (
  VALUES
    (0,'usr_community_anita'),(1,'usr_community_farhan'),
    (2,'usr_community_leela'),(3,'usr_community_nikhil'),
    (4,'usr_community_jo'),(5,'usr_community_maya'),
    (6,'usr_community_aman'),(7,'usr_community_saira')
)
INSERT INTO discussions (
  id, author_user_id, title, body, status, comment_count, last_activity_at,
  created_at, updated_at
)
SELECT
  printf('dsc_library_%03d_a', topics.n), members.user_id,
  upper(substr(topics.subject, 1, 1)) || substr(topics.subject, 2) || ': what works for you?',
  topics.question, 'visible', 10,
  printf('2026-06-%02dT10:30:00Z', ((topics.n - 1) % 28) + 1),
  printf('2026-06-%02dT09:00:00Z', ((topics.n - 1) % 28) + 1),
  printf('2026-06-%02dT10:30:00Z', ((topics.n - 1) % 28) + 1)
FROM seed_discussion_topics topics
JOIN member_ids members ON members.position = ((topics.n - 1) % 8)
UNION ALL
SELECT
  printf('dsc_library_%03d_b', topics.n), members.user_id,
  topics.follow_up_title, topics.follow_up, 'visible', 10,
  printf('2026-07-%02dT11:15:00Z', ((topics.n - 1) % 22) + 1),
  printf('2026-07-%02dT10:00:00Z', ((topics.n - 1) % 22) + 1),
  printf('2026-07-%02dT11:15:00Z', ((topics.n - 1) % 22) + 1)
FROM seed_discussion_topics topics
JOIN member_ids members ON members.position = (topics.n % 8);

WITH
  comment_numbers(comment_number) AS (
    VALUES (1),(2),(3),(4),(5),(6),(7),(8),(9),(10)
  ),
  member_ids(position, user_id) AS (
    VALUES
      (0,'usr_community_anita'),(1,'usr_community_farhan'),
      (2,'usr_community_leela'),(3,'usr_community_nikhil'),
      (4,'usr_community_jo'),(5,'usr_community_maya'),
      (6,'usr_community_aman'),(7,'usr_community_saira')
  ),
  thread_kinds(kind, date_month, hour) AS (
    VALUES ('a','06','10'),('b','07','11')
  )
INSERT INTO discussion_comments (
  id, discussion_id, author_user_id, body, status, created_at, updated_at
)
SELECT
  printf(
    'dcm_library_%03d_%s_%02d',
    topics.n,
    thread_kinds.kind,
    comment_numbers.comment_number
  ),
  printf('dsc_library_%03d_%s', topics.n, thread_kinds.kind),
  members.user_id,
  CASE comment_numbers.comment_number
    WHEN 1 THEN 'I ran into something similar last season. Starting with a small batch made it much easier to see what needed changing.'
    WHEN 2 THEN 'This is useful. Please share how it turns out after a few days because storage and resting time can change the result.'
    WHEN 3 THEN 'My experience was slightly different in humid weather. I needed less water and a little more time in an open pan.'
    WHEN 4 THEN 'A wide pan and moderate heat usually work better for me than rushing it over a high flame.'
    WHEN 5 THEN 'I learned this from my mother: check the ingredient itself before following the clock. Tenderness and ripeness vary from one batch to another.'
    WHEN 6 THEN 'The suggestion about keeping everything dry is important. One damp spoon or cloth has spoiled more than one batch in our kitchen.'
    WHEN 7 THEN 'I tried this today with what arrived in my vegetable box. The flavour was good, though I added a squeeze of lime at the end.'
    WHEN 8 THEN 'Would this method work with a smaller quantity? There are only two of us, and I would rather make it fresh than keep leftovers.'
    WHEN 9 THEN 'This thread has answered a question I did not know how to phrase. I am saving the details for the weekend.'
    ELSE 'Thanks for writing down the result. Practical follow ups like this are what make the community genuinely helpful.'
  END,
  'visible',
  printf(
    '2026-%s-%02dT%s:%02d:00Z',
    thread_kinds.date_month,
    CASE
      WHEN thread_kinds.kind = 'a' THEN ((topics.n - 1) % 28) + 1
      ELSE ((topics.n - 1) % 22) + 1
    END,
    thread_kinds.hour,
    5 + (comment_numbers.comment_number * 4)
  ),
  printf(
    '2026-%s-%02dT%s:%02d:00Z',
    thread_kinds.date_month,
    CASE
      WHEN thread_kinds.kind = 'a' THEN ((topics.n - 1) % 28) + 1
      ELSE ((topics.n - 1) % 22) + 1
    END,
    thread_kinds.hour,
    5 + (comment_numbers.comment_number * 4)
  )
FROM seed_discussion_topics topics
CROSS JOIN thread_kinds
CROSS JOIN comment_numbers
JOIN member_ids members
  ON members.position = (
    (topics.n + comment_numbers.comment_number
      + CASE thread_kinds.kind WHEN 'a' THEN 0 ELSE 3 END) % 8
  );

DROP TABLE seed_discussion_topics;

-- Large editorial expansion requested for the public library. The rows below
-- use the same CMS/version/community tables as admin-created content. Dates and
-- community activity are deliberately distributed rather than clustered on a
-- single import day.
CREATE TEMP TABLE expansion_recipe_ingredients (
  n INTEGER PRIMARY KEY,
  family TEXT NOT NULL,
  ingredient TEXT NOT NULL,
  slug TEXT NOT NULL,
  partner TEXT NOT NULL,
  note TEXT NOT NULL
);

INSERT INTO expansion_recipe_ingredients VALUES
  (1,'vegetable','cauliflower','cauliflower','coriander','Roast until the small florets are deeply browned'),
  (2,'vegetable','aubergine','aubergine','tamarind','Salt briefly, then cook until the centre is silky'),
  (3,'vegetable','potato','potato','fresh fenugreek','Keep the pieces even so they colour together'),
  (4,'vegetable','sweet potato','sweet-potato','lime','Balance its sweetness with heat and acidity'),
  (5,'vegetable','pumpkin','pumpkin','coconut','Choose a dense pumpkin that will not turn watery'),
  (6,'vegetable','bottle gourd','bottle-gourd','roasted cumin','Squeeze grated gourd only when the recipe needs a dry mixture'),
  (7,'vegetable','ridge gourd','ridge-gourd','chana dal','Peel only the tough ridges and keep the tender skin'),
  (8,'vegetable','okra','okra','black pepper','Dry every pod before it reaches the pan'),
  (9,'vegetable','green beans','green-beans','sesame','Cook just until tender so the beans keep their snap'),
  (10,'vegetable','beetroot','beetroot','fresh coconut','Cut small and evenly to shorten the cooking time'),
  (11,'pulse','chickpeas','chickpeas','spinach','Let the beans simmer in the masala long enough to take on flavour'),
  (12,'pulse','kidney beans','kidney-beans','smoked chilli','Use fully tender beans and keep some cooking liquor'),
  (13,'pulse','black chickpeas','black-chickpeas','raw mango','Soak overnight for an even, creamy centre'),
  (14,'pulse','whole green moong','green-moong','ginger','Cook until tender while keeping the skins intact'),
  (15,'pulse','red lentils','red-lentils','caramelised garlic','Watch the pot because split lentils soften quickly'),
  (16,'pulse','toor dal','toor-dal','tomato','Whisk only after the lentils are completely soft'),
  (17,'pulse','chana dal','chana-dal','dill','Soak briefly so the grains cook through without collapsing'),
  (18,'pulse','cowpeas','cowpeas','mustard seeds','Keep a little bite for a more satisfying finished dish'),
  (19,'pulse','white peas','white-peas','mint','Soak well and skim the cooking water for a clean broth'),
  (20,'pulse','horse gram','horse-gram','pepper','Give this firm pulse a long soak and patient simmer'),
  (21,'grain','ragi','ragi','banana','Rest ragi batter so the flour hydrates fully'),
  (22,'grain','jowar','jowar','spring onion','Use hot water when shaping jowar dough'),
  (23,'grain','bajra','bajra','garlic','Serve bajra warm while its nutty aroma is strongest'),
  (24,'grain','foxtail millet','foxtail-millet','lemon','Cool cooked millet before seasoning for separate grains'),
  (25,'grain','little millet','little-millet','curd','Cook a little softer when the grain will be mixed with yoghurt'),
  (26,'grain','red rice','red-rice','peanuts','A long soak helps the bran turn tender'),
  (27,'grain','brown rice','brown-rice','mushrooms','Cook by absorption and rest covered before fluffing'),
  (28,'grain','rolled oats','rolled-oats','garden vegetables','Toast the oats first for a less sticky finish'),
  (29,'grain','thick poha','thick-poha','lemon','Rinse briefly and allow the flakes to soften off the heat'),
  (30,'grain','amaranth grain','amaranth-grain','dates','Toast gently to bring out its warm, earthy aroma'),
  (31,'greens','spinach','spinach','corn','Cook the leaves briefly to preserve their colour'),
  (32,'greens','mustard greens','mustard-greens','white beans','Longer cooking mellows the leaves without flattening their character'),
  (33,'greens','amaranth leaves','amaranth-leaves','garlic','Wash around the stems carefully where soil collects'),
  (34,'greens','fresh fenugreek','fresh-fenugreek','potato','Use the tender stems and balance the pleasant bitterness'),
  (35,'greens','radish leaves','radish-leaves','moong dal','Chop finely to soften their prickly raw texture'),
  (36,'greens','beet greens','beet-greens','sesame','Start the red stems several minutes before the leaves'),
  (37,'greens','dill leaves','dill-leaves','chana dal','Add dill late enough to keep its fragrance'),
  (38,'greens','colocasia leaves','colocasia-leaves','tamarind','Cook thoroughly and include enough souring ingredient'),
  (39,'greens','coriander','coriander','pumpkin seeds','Use the stems as well as the leaves for deeper flavour'),
  (40,'greens','curry leaves','curry-leaves','coconut','Bloom dry leaves in hot fat without blackening them'),
  (41,'fruit','raw mango','raw-mango','mustard','Taste the fruit first and adjust souring accordingly'),
  (42,'fruit','ripe mango','ripe-mango','pistachio','Keep ripe fruit chilled and add it at the last moment'),
  (43,'fruit','guava','guava','red chilli','Use firm guava so the wedges hold their shape'),
  (44,'fruit','banana','banana','cardamom','Very ripe bananas give the softest texture'),
  (45,'fruit','pineapple','pineapple','black pepper','A hot pan concentrates the fruit without making it jammy'),
  (46,'fruit','papaya','papaya','lime','Choose just-ripe fruit for savoury preparations'),
  (47,'fruit','sweet lime','sweet-lime','ginger','Add the juice away from direct heat to keep it bright'),
  (48,'fruit','pomegranate','pomegranate','mint','Fold the seeds in last so they remain crisp'),
  (49,'fruit','apple','apple','fennel','Leave the peel on when it is clean and tender'),
  (50,'fruit','pear','pear','walnuts','Use fruit that is fragrant but still firm');

CREATE TEMP TABLE expansion_recipe_styles (
  style INTEGER PRIMARY KEY,
  label TEXT NOT NULL
);

INSERT INTO expansion_recipe_styles VALUES
  (1,'weeknight'),(2,'roasted'),(3,'breakfast'),(4,'one-pot'),(5,'street-style');

INSERT INTO recipes (
  id, internal_name, title, slug, excerpt, prep_minutes, cook_minutes, servings,
  dietary_tags_json, status, published_version_id, published_at, seo_title,
  seo_description, created_at, created_by, updated_at, updated_by
)
SELECT
  printf('rcp_expansion_%03d', ((ingredients.n - 1) * 5) + styles.style),
  ingredients.ingredient || ' ' || styles.label || ' recipe',
  CASE styles.style
    WHEN 1 THEN 'Weeknight ' || ingredients.ingredient || ' with ' || ingredients.partner
    WHEN 2 THEN 'Roasted ' || ingredients.ingredient || ' and ' || ingredients.partner
    WHEN 3 THEN ingredients.ingredient || ' breakfast bowl with ' || ingredients.partner
    WHEN 4 THEN 'One-pot ' || ingredients.ingredient || ' and ' || ingredients.partner
    ELSE 'Street-style ' || ingredients.ingredient || ' with ' || ingredients.partner
  END,
  styles.label || '-' || ingredients.slug || '-' || replace(ingredients.partner, ' ', '-'),
  CASE styles.style
    WHEN 1 THEN 'A practical ' || ingredients.ingredient || ' supper with ' || ingredients.partner || ' and everyday spices.'
    WHEN 2 THEN ingredients.ingredient || ' cooked until deeply flavoured and finished with ' || ingredients.partner || '.'
    WHEN 3 THEN 'A filling morning bowl of ' || ingredients.ingredient || ', ' || ingredients.partner || ' and toasted spices.'
    WHEN 4 THEN ingredients.ingredient || ' and ' || ingredients.partner || ' cooked together for a low-fuss family meal.'
    ELSE 'A lively ' || ingredients.ingredient || ' plate with ' || ingredients.partner || ', herbs and a sharp finish.'
  END,
  8 + ((ingredients.n * 3 + styles.style * 5) % 23),
  10 + ((ingredients.n * 7 + styles.style * 4) % 36),
  2 + ((ingredients.n + styles.style) % 5),
  CASE
    WHEN ingredients.family IN ('vegetable','pulse','greens') THEN '["plant-based","gluten-free"]'
    WHEN ingredients.family = 'fruit' THEN '["vegetarian","gluten-free"]'
    ELSE '["vegetarian"]'
  END,
  'published',
  printf('rcv_expansion_%03d_1', ((ingredients.n - 1) * 5) + styles.style),
  datetime('2025-08-01T08:00:00Z', printf('+%d days', ((ingredients.n * 37 + styles.style * 19) % 360))),
  CASE styles.style
    WHEN 1 THEN 'Weeknight ' || ingredients.ingredient || ' with ' || ingredients.partner
    WHEN 2 THEN 'Roasted ' || ingredients.ingredient || ' and ' || ingredients.partner
    WHEN 3 THEN ingredients.ingredient || ' breakfast bowl with ' || ingredients.partner
    WHEN 4 THEN 'One-pot ' || ingredients.ingredient || ' and ' || ingredients.partner
    ELSE 'Street-style ' || ingredients.ingredient || ' with ' || ingredients.partner
  END || ' recipe',
  'A tested recipe built around ' || ingredients.ingredient || ' and ' || ingredients.partner || '.',
  '2025-07-20T08:00:00Z', 'usr_editor',
  datetime('2025-08-01T08:00:00Z', printf('+%d days', ((ingredients.n * 37 + styles.style * 19) % 360))),
  'usr_editor'
FROM expansion_recipe_ingredients ingredients
CROSS JOIN expansion_recipe_styles styles;

INSERT INTO recipe_versions (
  id, recipe_id, version_number, content_json, workflow_state, created_at,
  created_by, approved_at, approved_by, published_at
)
SELECT
  printf('rcv_expansion_%03d_1', ((ingredients.n - 1) * 5) + styles.style),
  printf('rcp_expansion_%03d', ((ingredients.n - 1) * 5) + styles.style),
  1,
  json_object(
    'blocks', json_array(
      json_object(
        'id', printf('blk_expansion_recipe_%03d_intro', ((ingredients.n - 1) * 5) + styles.style),
        'type', 'rich_text', 'version', 1, 'enabled', json('true'),
        'props', json_object('paragraphs', json_array(
          ingredients.note || '. This version pairs it with ' || ingredients.partner || ' and keeps the seasoning measured.',
          CASE styles.style
            WHEN 1 THEN 'Designed for an ordinary evening, it uses one wide pan and ingredients that are easy to keep at home.'
            WHEN 2 THEN 'High heat builds browned edges while the centre stays tender, so give the pieces room on the tray.'
            WHEN 3 THEN 'The components can be prepared ahead, but assemble the bowl shortly before eating for the best texture.'
            WHEN 4 THEN 'Add ingredients in the order they soften, then rest the covered pot before serving.'
            ELSE 'Keep the final herbs, crunch and souring ingredient separate until the plate reaches the table.'
          END
        ))
      ),
      json_object(
        'id', printf('blk_expansion_recipe_%03d_products', ((ingredients.n - 1) * 5) + styles.style),
        'type', 'product_collection', 'version', 1, 'enabled', json('true'),
        'props', json_object(
          'heading', 'Shop ingredients for this recipe', 'source', 'manual',
          'productSlugs', CASE (ingredients.n % 5)
            WHEN 0 THEN json_array('organic-baby-spinach','wood-pressed-groundnut-oil')
            WHEN 1 THEN json_array('sprouted-ragi-flour','wood-pressed-groundnut-oil')
            WHEN 2 THEN json_array('himalayan-red-rajma','organic-baby-spinach')
            WHEN 3 THEN json_array('organic-alphonso-mangoes','wood-pressed-groundnut-oil')
            ELSE json_array('organic-baby-spinach','himalayan-red-rajma')
          END,
          'limit', 4
        )
      )
    ),
    'steps', json_array(
      'Prepare the ' || ingredients.ingredient || ' and measure the ' || ingredients.partner || ' before heating the pan.',
      CASE styles.style
        WHEN 2 THEN 'Heat the oven and spread everything in a single layer.'
        WHEN 3 THEN 'Toast the dry spices and prepare the base until fragrant.'
        ELSE 'Warm a wide pan and bloom the whole spices in a little oil.'
      END,
      'Add the ' || ingredients.ingredient || ' and cook patiently, following this cue: ' || lower(ingredients.note) || '.',
      'Fold in the ' || ingredients.partner || ', season with salt and adjust the consistency with a splash of water if needed.',
      'Rest for five minutes, taste again and finish with fresh herbs or lime before serving.'
    )
  ),
  'published', '2025-07-20T08:00:00Z', 'usr_editor',
  datetime('2025-08-01T07:30:00Z', printf('+%d days', ((ingredients.n * 37 + styles.style * 19) % 360))),
  'usr_admin',
  datetime('2025-08-01T08:00:00Z', printf('+%d days', ((ingredients.n * 37 + styles.style * 19) % 360)))
FROM expansion_recipe_ingredients ingredients
CROSS JOIN expansion_recipe_styles styles;

INSERT INTO recipe_ingredients (id, recipe_id, label, quantity_text, product_id, sort_order)
SELECT
  printf('ing_expansion_%03d_1', ((ingredients.n - 1) * 5) + styles.style),
  printf('rcp_expansion_%03d', ((ingredients.n - 1) * 5) + styles.style),
  ingredients.ingredient, CASE ingredients.family WHEN 'grain' THEN '1 1/2 cups' WHEN 'pulse' THEN '2 cups cooked' ELSE '500 g' END,
  NULL, 1
FROM expansion_recipe_ingredients ingredients CROSS JOIN expansion_recipe_styles styles
UNION ALL
SELECT
  printf('ing_expansion_%03d_2', ((ingredients.n - 1) * 5) + styles.style),
  printf('rcp_expansion_%03d', ((ingredients.n - 1) * 5) + styles.style),
  ingredients.partner, 'to taste', NULL, 2
FROM expansion_recipe_ingredients ingredients CROSS JOIN expansion_recipe_styles styles
UNION ALL
SELECT
  printf('ing_expansion_%03d_3', ((ingredients.n - 1) * 5) + styles.style),
  printf('rcp_expansion_%03d', ((ingredients.n - 1) * 5) + styles.style),
  'Cooking oil and everyday spices', 'as needed', NULL, 3
FROM expansion_recipe_ingredients ingredients CROSS JOIN expansion_recipe_styles styles;

INSERT INTO search_content (entity_type, entity_id, title, slug, excerpt, keywords)
SELECT
  'recipe',
  printf('rcp_expansion_%03d', ((ingredients.n - 1) * 5) + styles.style),
  CASE styles.style
    WHEN 1 THEN 'Weeknight ' || ingredients.ingredient || ' with ' || ingredients.partner
    WHEN 2 THEN 'Roasted ' || ingredients.ingredient || ' and ' || ingredients.partner
    WHEN 3 THEN ingredients.ingredient || ' breakfast bowl with ' || ingredients.partner
    WHEN 4 THEN 'One-pot ' || ingredients.ingredient || ' and ' || ingredients.partner
    ELSE 'Street-style ' || ingredients.ingredient || ' with ' || ingredients.partner
  END,
  styles.label || '-' || ingredients.slug || '-' || replace(ingredients.partner, ' ', '-'),
  'A practical recipe featuring ' || ingredients.ingredient || ' and ' || ingredients.partner || '.',
  ingredients.ingredient || ' ' || ingredients.partner || ' ' || styles.label
FROM expansion_recipe_ingredients ingredients
CROSS JOIN expansion_recipe_styles styles;

DROP TABLE expansion_recipe_styles;
DROP TABLE expansion_recipe_ingredients;

CREATE TEMP TABLE expansion_blog_topics (
  n INTEGER PRIMARY KEY,
  subject TEXT NOT NULL,
  slug TEXT NOT NULL,
  observation TEXT NOT NULL,
  practice TEXT NOT NULL,
  takeaway TEXT NOT NULL
);

INSERT INTO expansion_blog_topics VALUES
  (1,'morning harvests','morning-harvests','Tender crops hold more moisture before the day becomes hot.','Growers plan cutting, shade and packing as one continuous job.','Freshness depends on handling after harvest as much as the hour of picking.'),
  (2,'seed selection','seed-selection','Saving seed begins by noticing healthy plants long before harvest.','Farmers mark plants with the flavour, vigour and timing they want to keep.','A seed line survives through repeated observation, not nostalgia alone.'),
  (3,'monsoon sowing','monsoon-sowing','The first rain is not always the right rain for sowing.','Farmers check soil depth and the forecast before committing valuable seed.','Timing is a practical judgement shaped by local memory and current weather.'),
  (4,'soil organic matter','soil-organic-matter','Organic matter affects water, nutrients and the way soil holds together.','Compost, roots and retained crop residue rebuild it gradually.','The useful change is steady resilience rather than an overnight transformation.'),
  (5,'farm ponds','farm-ponds','A well-placed pond slows water that would otherwise leave the farm.','Design must account for soil, overflow, safety and downstream users.','Water storage works best as part of a wider landscape plan.'),
  (6,'mixed cropping','mixed-cropping','Different crops can share light, rooting depth and risk.','Useful mixtures are chosen for compatible timing and manageable harvest work.','Diversity in a field should solve a real agronomic or livelihood problem.'),
  (7,'natural pest control','natural-pest-control','Predatory insects need habitat before a pest outbreak begins.','Flowering borders and careful spraying decisions protect useful species.','Ecological pest control is patient management, not the absence of intervention.'),
  (8,'seasonal labour','seasonal-labour','Harvest quality depends on people arriving at the right moment.','Fair planning includes safe hours, drinking water and predictable payment.','The human work behind fresh food belongs in every conversation about quality.'),
  (9,'field mulching','field-mulching','A surface cover can reduce heat and soften the impact of rain.','Farmers choose straw, leaves or living cover according to local risks.','Mulch is most useful when its source and side effects are considered.'),
  (10,'compost maturity','compost-maturity','Finished compost smells earthy and no longer heats dramatically.','Growers watch moisture, air and the breakdown of the original materials.','Applying immature material can move a problem from the pile into the field.'),
  (11,'tomato ripeness','tomato-ripeness','Aroma develops while fruit remains attached to a healthy vine.','Shorter supply routes allow farmers to pick closer to eating ripeness.','Colour alone cannot tell the full story of flavour.'),
  (12,'leafy green storage','leafy-green-storage','Leaves lose moisture quickly and decay when held wet.','Dry cloth, loose packing and prompt cooling create a useful balance.','Good storage begins by removing damaged leaves before they affect the bunch.'),
  (13,'pulse soaking','pulse-soaking','Water reaches the centre of older, denser pulses slowly.','A planned soak shortens cooking and often improves texture.','The age and variety of a pulse matter as much as the clock.'),
  (14,'whole grain milling','whole-grain-milling','Natural oils and aromas begin changing as soon as grain is milled.','Small batches and cool airtight storage protect fresh flour.','Buy at a pace that matches how quickly the kitchen actually cooks.'),
  (15,'cold pressed oils','cold-pressed-oils','The press cannot improve stale or poorly dried seed.','Millers protect raw seed from moisture, heat and contamination.','Fresh oil starts with good agriculture and ends with careful storage.'),
  (16,'market grading','market-grading','Sorting separates damage from harmless differences in shape and size.','Clear grades help match produce to fresh sale, processing or quick use.','Good grading should reduce waste without pretending every crop is identical.'),
  (17,'reusable crates','reusable-crates','Rigid crates prevent crushing better than overfilled sacks.','Cleaning, return routes and ownership must be organised for reuse to work.','Packaging is a system, not simply a material choice.'),
  (18,'cooling fresh produce','cooling-fresh-produce','Harvested vegetables continue to respire and generate heat.','Shade and crop-appropriate cooling slow water loss.','Temperature decisions must suit the crop rather than follow one rule.'),
  (19,'farm traceability','farm-traceability','A useful lot record connects food to place, date and handling.','Labels remain meaningful only when each transfer preserves the link.','Traceability should help answer practical questions, not decorate a package.'),
  (20,'organic inspections','organic-inspections','Certification reviews records, fields, inputs and handling systems.','Farmers maintain evidence throughout the year, not only on inspection day.','A certificate is one part of trust and should be readable by customers.'),
  (21,'rain-fed millets','rain-fed-millets','Millets tolerate conditions that make many grains unreliable.','Variety choice, sowing date and soil cover still decide the harvest.','Resilient crops reduce risk but do not remove it.'),
  (22,'legumes in rotation','legumes-in-rotation','Legume roots work with bacteria that can add nitrogen to the system.','Farmers place them where the following crop can benefit.','Rotation value includes soil cover, income and pest interruption.'),
  (23,'hedgerows','hedgerows','Living boundaries slow wind and provide food for useful insects.','Mixed native species offer more than a single uniform hedge.','Productive land can make room for habitat without becoming unmanaged.'),
  (24,'pollinator seasons','pollinator-seasons','Bees need food before and after the main crop flowers.','Overlapping blooms and nesting places support resident populations.','Pollination depends on year-round habitat, not a rented moment.'),
  (25,'hand weeding','hand-weeding','Young weeds are easier to remove before roots and seed develop.','Timing work after light moisture reduces effort and soil disturbance.','Avoiding herbicide replaces a product with skilled, repeated labour.'),
  (26,'cover crops','cover-crops','Living roots feed soil organisms between cash crops.','Species are chosen for rainfall, duration and the next planting window.','A cover crop must fit the farm calendar to deliver its promise.'),
  (27,'reduced tillage','reduced-tillage','Every pass with machinery changes pores and soil aggregates.','Growers reduce disturbance while managing weeds and crop residue.','The right level of tillage depends on soil, climate and available tools.'),
  (28,'agroforestry','agroforestry','Trees can moderate heat, hold soil and diversify farm income.','Spacing and pruning prevent harmful competition with crops.','A useful tree system is designed for decades as well as seasons.'),
  (29,'shade-grown coffee','shade-grown-coffee','Canopy changes temperature, ripening speed and wildlife habitat.','Farmers adjust shade to balance quality with disease pressure.','The words shade grown describe a spectrum that deserves specifics.'),
  (30,'orchard floor care','orchard-floor-care','Bare orchard soil heats quickly and loses structure under hard rain.','Mown cover, mulch and managed grazing each offer different options.','The ground between trees is part of the crop system.'),
  (31,'mango flowering','mango-flowering','Warmth, humidity and wind affect flowers before fruit is visible.','Orchardists monitor bloom health and avoid unnecessary disturbance.','A mango season begins months before the first crate.'),
  (32,'banana circles','banana-circles','Bananas use steady moisture and abundant organic material.','Circular planting basins can collect biomass and household greywater safely.','A good design matches water supply, sanitation and available space.'),
  (33,'coconut diversity','coconut-diversity','Tall and dwarf coconut lines differ in timing, stature and use.','Farmers choose material for local wind, water and market needs.','One familiar crop contains more diversity than a shop shelf suggests.'),
  (34,'kitchen herb gardens','kitchen-herb-gardens','Frequently cut herbs earn their place close to the kitchen.','Regular pinching, drainage and morning light keep plants productive.','A small useful garden can matter more than a large neglected one.'),
  (35,'balcony composting','balcony-composting','Small bins turn sour when wet scraps overwhelm dry material.','Chopped browns, airflow and modest portions restore balance.','Successful composting is mostly observation of moisture and smell.'),
  (36,'saving cooking water','saving-cooking-water','Unsalted vegetable and pulse water can carry flavour and starch.','Cooks cool and reuse it in soups, doughs or the next pot of dal.','Reuse is helpful when food safety and excess salt are considered.'),
  (37,'root-to-leaf cooking','root-to-leaf-cooking','Many tender stems and leaves are ingredients rather than waste.','Separate parts by cooking time and taste before using unfamiliar greens.','Whole-plant cooking begins with judgement, not a rule to eat everything.'),
  (38,'seasonal meal planning','seasonal-meal-planning','Fragile produce should be scheduled before sturdy roots and pumpkins.','A weekly sort makes the order of cooking visible.','Planning around perishability saves more food than collecting recipes.'),
  (39,'pantry turnover','pantry-turnover','Large stores of flour, oil and spices lose quality slowly.','Smaller containers and dated purchases reveal what the kitchen uses.','A useful pantry is active, not merely full.'),
  (40,'safe grain cooling','safe-grain-cooling','Deep pots of cooked grain cool slowly at the centre.','Shallow containers release heat before prompt refrigeration.','Good leftovers begin with safe cooling, not reheating alone.'),
  (41,'fermented batters','fermented-batters','Warmth, grain ratio and grinding texture shape fermentation.','Cooks watch aroma and rise instead of trusting the clock alone.','A living batter needs clean tools and room to expand.'),
  (42,'pickling seasons','pickling-seasons','Preserving starts when produce is abundant, firm and full of flavour.','Salt, acidity, dryness and clean jars each control a different risk.','A reliable pickle method respects both tradition and food safety.'),
  (43,'sun drying','sun-drying','Drying succeeds when moisture leaves faster than spoilage can begin.','Thin even pieces, clean screens and protection from night humidity matter.','Sun is only one part of a controlled drying process.'),
  (44,'jaggery making','jaggery-making','Cane juice changes flavour as it is clarified and concentrated.','Experienced makers judge foam, heat and finishing point by sight and feel.','Colour varies naturally and should not replace questions about process.'),
  (45,'small dairy herds','small-dairy-herds','Milk quality begins with animal health, feed and clean handling.','Cooling and traceable collection protect work done at the farm.','Scale alone does not determine care or quality.'),
  (46,'farm-gate pricing','farm-gate-pricing','The price at the farm must cover more than visible harvest work.','Seed, failed crops, certification, packing and delayed payment all matter.','Fair pricing starts by recognising risk across the season.'),
  (47,'short supply chains','short-supply-chains','Fewer kilometres do not guarantee careful handling.','Clear orders, reusable crates and reliable collection keep local trade fresh.','Distance and logistics must be judged together.'),
  (48,'community seed banks','community-seed-banks','Shared seed collections protect access to locally adapted varieties.','Records, regeneration plots and agreed borrowing rules keep seed viable.','A seed bank succeeds when seed continues to grow in fields.'),
  (49,'farm weather records','farm-weather-records','Local rainfall and temperature can differ from a distant station.','Simple daily notes become useful when kept consistently.','Farm decisions improve when memory is supported by a record.'),
  (50,'eating with the seasons','eating-with-the-seasons','Availability changes with weather, place and the limits of a harvest.','Cooks preserve some abundance and allow other ingredients to disappear.','Seasonality is a practice of attention rather than a purity test.');

CREATE TEMP TABLE expansion_blog_angles (
  angle INTEGER PRIMARY KEY,
  prefix TEXT NOT NULL,
  suffix TEXT NOT NULL
);

INSERT INTO expansion_blog_angles VALUES
  (1,'A closer look at ',''),
  (2,'What cooks should know about ',''),
  (3,'Notes from the field: ','');

INSERT INTO articles (
  id, internal_name, title, slug, excerpt, author_user_id, hero_media_id,
  reading_minutes, status, published_version_id, published_at, seo_title,
  seo_description, created_at, created_by, updated_at, updated_by
)
SELECT
  printf('art_expansion_%03d', ((topics.n - 1) * 3) + angles.angle),
  topics.subject || ' article ' || angles.angle,
  angles.prefix || topics.subject || angles.suffix,
  CASE angles.angle WHEN 1 THEN 'closer-look-' WHEN 2 THEN 'cooks-guide-' ELSE 'field-notes-' END || topics.slug,
  topics.observation,
  'usr_editor', NULL, 4 + ((topics.n + angles.angle) % 5), 'published',
  printf('arv_expansion_%03d_1', ((topics.n - 1) * 3) + angles.angle),
  datetime('2025-08-01T09:00:00Z', printf('+%d days', ((topics.n * 43 + angles.angle * 29) % 360))),
  angles.prefix || topics.subject || angles.suffix,
  topics.observation,
  '2025-07-20T09:00:00Z', 'usr_editor',
  datetime('2025-08-01T09:00:00Z', printf('+%d days', ((topics.n * 43 + angles.angle * 29) % 360))),
  'usr_editor'
FROM expansion_blog_topics topics CROSS JOIN expansion_blog_angles angles;

INSERT INTO article_versions (
  id, article_id, version_number, content_json, workflow_state, created_at,
  created_by, approved_at, approved_by, published_at
)
SELECT
  printf('arv_expansion_%03d_1', ((topics.n - 1) * 3) + angles.angle),
  printf('art_expansion_%03d', ((topics.n - 1) * 3) + angles.angle),
  1,
  json_object(
    'blocks', json_array(
      json_object(
        'id', printf('blk_expansion_article_%03d_body', ((topics.n - 1) * 3) + angles.angle),
        'type', 'rich_text', 'version', 1, 'enabled', json('true'),
        'props', json_object('paragraphs',
          CASE angles.angle
            WHEN 1 THEN json_array(
              topics.observation,
              topics.practice || ' The details vary with farm size, climate and the people doing the work.',
              topics.takeaway || ' Looking closely makes the ordinary parts of food production easier to value.'
            )
            WHEN 2 THEN json_array(
              topics.observation || ' That difference often reaches the kitchen in flavour, texture or storage life.',
              topics.takeaway || ' For a cook, the practical response is to buy thoughtfully, store carefully and taste before following a fixed time.',
              topics.practice || ' Asking how an ingredient was grown or handled can be more useful than relying on a broad label.'
            )
            ELSE json_array(
              topics.practice || ' On a working farm, the decision sits alongside weather, labour and the next crop.',
              topics.observation || ' It is the kind of change that becomes visible through repeated seasons rather than one photograph.',
              topics.takeaway || ' The field offers fewer simple answers than a slogan, but far more useful ones.'
            )
          END
        )
      ),
      json_object(
        'id', printf('blk_expansion_article_%03d_products', ((topics.n - 1) * 3) + angles.angle),
        'type', 'product_collection', 'version', 1, 'enabled', json('true'),
        'props', json_object(
          'heading', 'Products connected to this story', 'source', 'manual',
          'productSlugs', CASE (topics.n % 5)
            WHEN 0 THEN json_array('organic-baby-spinach','sprouted-ragi-flour')
            WHEN 1 THEN json_array('organic-baby-spinach','wood-pressed-groundnut-oil')
            WHEN 2 THEN json_array('sprouted-ragi-flour','himalayan-red-rajma')
            WHEN 3 THEN json_array('organic-alphonso-mangoes','wood-pressed-groundnut-oil')
            ELSE json_array('himalayan-red-rajma','organic-baby-spinach')
          END,
          'limit', 4
        )
      )
    )
  ),
  'published', '2025-07-20T09:00:00Z', 'usr_editor',
  datetime('2025-08-01T08:30:00Z', printf('+%d days', ((topics.n * 43 + angles.angle * 29) % 360))),
  'usr_admin',
  datetime('2025-08-01T09:00:00Z', printf('+%d days', ((topics.n * 43 + angles.angle * 29) % 360)))
FROM expansion_blog_topics topics CROSS JOIN expansion_blog_angles angles;

INSERT INTO search_content (entity_type, entity_id, title, slug, excerpt, keywords)
SELECT
  'article',
  printf('art_expansion_%03d', ((topics.n - 1) * 3) + angles.angle),
  angles.prefix || topics.subject || angles.suffix,
  CASE angles.angle WHEN 1 THEN 'closer-look-' WHEN 2 THEN 'cooks-guide-' ELSE 'field-notes-' END || topics.slug,
  topics.observation,
  topics.subject || ' farming food season'
FROM expansion_blog_topics topics CROSS JOIN expansion_blog_angles angles;

DROP TABLE expansion_blog_angles;

-- The 50 editorial subjects create two genuinely different community prompts
-- each: one practical question and one experience-sharing thread.
WITH
  member_ids(position, user_id) AS (
    VALUES
      (0,'usr_community_anita'),(1,'usr_community_farhan'),
      (2,'usr_community_leela'),(3,'usr_community_nikhil'),
      (4,'usr_community_jo'),(5,'usr_community_maya'),
      (6,'usr_community_aman'),(7,'usr_community_saira')
  ),
  thread_kinds(kind, title_prefix, body_prefix) AS (
    VALUES
      (1,'How are you handling ','I would like practical advice on '),
      (2,'What have you noticed about ','I am curious about first-hand experiences with ')
  )
INSERT INTO discussions (
  id, author_user_id, title, body, status, comment_count, last_activity_at,
  created_at, updated_at
)
SELECT
  printf('dsc_expansion_%03d', ((topics.n - 1) * 2) + kinds.kind),
  members.user_id,
  kinds.title_prefix || topics.subject || '?',
  kinds.body_prefix || topics.subject || '. ' ||
    CASE kinds.kind
      WHEN 1 THEN topics.practice || ' What has worked reliably for you, and what would you change next time?'
      ELSE topics.observation || ' I would especially value details about season, place and what you observed over time.'
    END,
  'visible',
  20 + ((((topics.n - 1) * 2) + kinds.kind) * 7 % 11),
  datetime('2026-01-01T12:00:00Z', printf('+%d days', ((((topics.n - 1) * 2) + kinds.kind) * 31) % 205)),
  datetime('2025-10-01T09:00:00Z', printf('+%d days', ((((topics.n - 1) * 2) + kinds.kind) * 17) % 250)),
  datetime('2026-01-01T12:00:00Z', printf('+%d days', ((((topics.n - 1) * 2) + kinds.kind) * 31) % 205))
FROM expansion_blog_topics topics
CROSS JOIN thread_kinds kinds
JOIN member_ids members ON members.position = ((((topics.n - 1) * 2) + kinds.kind) % 8);

WITH RECURSIVE
  comment_numbers(comment_number) AS (
    SELECT 1
    UNION ALL
    SELECT comment_number + 1 FROM comment_numbers WHERE comment_number < 30
  ),
  member_ids(position, user_id) AS (
    VALUES
      (0,'usr_community_anita'),(1,'usr_community_farhan'),
      (2,'usr_community_leela'),(3,'usr_community_nikhil'),
      (4,'usr_community_jo'),(5,'usr_community_maya'),
      (6,'usr_community_aman'),(7,'usr_community_saira')
  )
INSERT INTO discussion_comments (
  id, discussion_id, author_user_id, body, status, created_at, updated_at
)
SELECT
  printf('dcm_expansion_%03d_%02d', thread_number, numbers.comment_number),
  printf('dsc_expansion_%03d', thread_number),
  members.user_id,
  CASE (numbers.comment_number % 12)
    WHEN 0 THEN 'Coming back with an update: the smaller batch was easier to manage and the result held up well after a few days.'
    WHEN 1 THEN 'We tried this last season. The timing mattered more than the exact quantity, especially once the weather turned humid.'
    WHEN 2 THEN 'My family handles it a little differently, but the principle is the same: start gently and adjust after tasting.'
    WHEN 3 THEN 'This is useful context. I would keep one variable the same and change only the step you are unsure about.'
    WHEN 4 THEN 'The local variety behaved differently for me, so it may help to note where yours came from and how mature it was.'
    WHEN 5 THEN 'A wider vessel and a little patience made the biggest difference in my kitchen. Crowding caused most of my earlier trouble.'
    WHEN 6 THEN 'I appreciate the detail about storage. That is often where a good ingredient loses quality before we even begin cooking.'
    WHEN 7 THEN 'Would love to hear a follow-up after the next attempt. Results over two or three batches are much easier to trust.'
    WHEN 8 THEN 'We use the tender stems and leaves separately because their cooking times are not the same. It also reduces waste.'
    WHEN 9 THEN 'The advice about observing rather than following the clock exactly is spot on. Each harvest arrives a little different.'
    WHEN 10 THEN 'I made a half quantity and it worked well. The final seasoning needed less than half, so tasting at the end helped.'
    ELSE 'Thanks for starting this discussion. I have added the main suggestion to my notes for the next market delivery.'
  END,
  'visible',
  datetime(
    '2026-01-01T08:00:00Z',
    printf('+%d days', (thread_number * 31) % 205),
    printf('+%d minutes', numbers.comment_number * 43)
  ),
  datetime(
    '2026-01-01T08:00:00Z',
    printf('+%d days', (thread_number * 31) % 205),
    printf('+%d minutes', numbers.comment_number * 43)
  )
FROM (
  SELECT ((topics.n - 1) * 2) + kinds.kind AS thread_number
  FROM expansion_blog_topics topics
  CROSS JOIN (SELECT 1 AS kind UNION ALL SELECT 2) kinds
) threads
CROSS JOIN comment_numbers numbers
JOIN member_ids members ON members.position = ((threads.thread_number + numbers.comment_number * 3) % 8)
WHERE numbers.comment_number <= 20 + ((threads.thread_number * 7) % 11);

-- Bring the original 100 library discussions up from 10 comments to a varied
-- 20-30 comments. The deterministic spread keeps development databases
-- reproducible while avoiding identical activity counts.
WITH RECURSIVE
  extra_numbers(comment_number) AS (
    SELECT 11
    UNION ALL
    SELECT comment_number + 1 FROM extra_numbers WHERE comment_number < 30
  ),
  original_threads AS (
    SELECT
      id,
      row_number() OVER (ORDER BY id) AS thread_number,
      20 + ((row_number() OVER (ORDER BY id) * 7) % 11) AS target_count,
      created_at
    FROM discussions
    WHERE id LIKE 'dsc_library_%'
  ),
  member_ids(position, user_id) AS (
    VALUES
      (0,'usr_community_anita'),(1,'usr_community_farhan'),
      (2,'usr_community_leela'),(3,'usr_community_nikhil'),
      (4,'usr_community_jo'),(5,'usr_community_maya'),
      (6,'usr_community_aman'),(7,'usr_community_saira')
  )
INSERT INTO discussion_comments (
  id, discussion_id, author_user_id, body, status, created_at, updated_at
)
SELECT
  printf('dcm_growth_%03d_%02d', threads.thread_number, numbers.comment_number),
  threads.id,
  members.user_id,
  CASE (numbers.comment_number % 8)
    WHEN 0 THEN 'I tested this with the latest delivery and the result was consistent. Keeping the pieces even was the key.'
    WHEN 1 THEN 'One more detail that helped here was letting everything rest before making the final adjustment.'
    WHEN 2 THEN 'Our climate is quite humid, so I used a little less water and kept the container more open.'
    WHEN 3 THEN 'This worked at half quantity too. I shortened the cooking time but kept the resting time unchanged.'
    WHEN 4 THEN 'The ingredient itself made a difference. A fresher batch needed less cooking and had a cleaner flavour.'
    WHEN 5 THEN 'I would recommend writing down the timing once it works. It is surprisingly easy to forget by next season.'
    WHEN 6 THEN 'A useful thread. The comments about temperature explain why my earlier attempt behaved so differently.'
    ELSE 'Reporting back after a second try: the simpler method was more reliable and there was less washing up.'
  END,
  'visible',
  datetime(threads.created_at, printf('+%d minutes', numbers.comment_number * 47)),
  datetime(threads.created_at, printf('+%d minutes', numbers.comment_number * 47))
FROM original_threads threads
CROSS JOIN extra_numbers numbers
JOIN member_ids members ON members.position = ((threads.thread_number + numbers.comment_number) % 8)
WHERE numbers.comment_number <= threads.target_count;

UPDATE discussions
SET
  comment_count = (
    SELECT COUNT(*) FROM discussion_comments comments
    WHERE comments.discussion_id = discussions.id AND comments.status = 'visible'
  ),
  last_activity_at = COALESCE(
    (
      SELECT MAX(created_at) FROM discussion_comments comments
      WHERE comments.discussion_id = discussions.id AND comments.status = 'visible'
    ),
    last_activity_at
  ),
  updated_at = COALESCE(
    (
      SELECT MAX(created_at) FROM discussion_comments comments
      WHERE comments.discussion_id = discussions.id AND comments.status = 'visible'
    ),
    updated_at
  )
WHERE id LIKE 'dsc_library_%' OR id LIKE 'dsc_expansion_%';

DROP TABLE expansion_blog_topics;

-- Comprehensive organic-market catalogue expansion
-- Keep migrated fixture search rows singular during development seeding.
DELETE FROM search_products
WHERE product_id LIKE 'prd_market_%' OR product_id LIKE 'prd_extra_%';

-- Twenty departments and
-- eighty focused subcategories cover food, pantry, wellbeing, home and garden.
-- Each subcategory carries eight real catalogue products with variants, prices,
-- stock, search data and editable published versions.
CREATE TEMP TABLE market_catalogue_sections (
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
  'usr_editor',
  '2026-07-30T08:00:00Z',
  'usr_editor'
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
  'usr_editor',
  '2026-07-30T08:00:00Z',
  'usr_editor'
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
  'usr_editor',
  '2026-07-30T07:30:00Z',
  'usr_admin',
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
  'usr_editor',
  '2026-07-30T07:30:00Z',
  'usr_admin',
  '2026-07-30T08:00:00Z'
FROM market_catalogue_sections;

CREATE TEMP TABLE market_catalogue_products AS
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
  CASE
    WHEN department_order BETWEEN 1 AND 3 THEN
      CASE (product_number % 3) WHEN 0 THEN 'farm_devika' WHEN 1 THEN 'farm_anandvan' ELSE 'farm_himgiri' END
    WHEN department_order BETWEEN 4 AND 10 THEN
      CASE (product_number % 2) WHEN 0 THEN 'farm_anandvan' ELSE 'farm_himgiri' END
    ELSE NULL
  END,
  'published',
  product_name || ' selected for dependable quality, clear provenance and everyday use.',
  printf('pvr_market_%04d_1', product_number),
  'Organic ' || product_name || ' | Buy Online',
  'Shop organic ' || lower(product_name) || ' with transparent sourcing, current stock and secure delivery.',
  datetime('2025-07-01T08:00:00Z', printf('+%d days', (product_number * 17) % 365)),
  'usr_pm',
  datetime('2025-07-01T08:00:00Z', printf('+%d days', (product_number * 17) % 365)),
  'usr_pm'
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
  'usr_pm',
  datetime('2025-07-01T08:30:00Z', printf('+%d days', (product_number * 17) % 365)),
  'usr_admin',
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
  'usr_pm'
FROM market_catalogue_products
UNION ALL
SELECT
  printf('prd_market_%04d', product_number),
  'cat_market_' || department_slug,
  0,
  product_number,
  '2026-07-30T08:00:00Z',
  'usr_pm'
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
  'usr_pm'
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

INSERT OR IGNORE INTO product_certifications (
  product_id, certification_id, claim_review_state
)
SELECT
  printf('prd_market_%04d', product_number),
  CASE (product_number % 3)
    WHEN 0 THEN 'cert_india_organic'
    WHEN 1 THEN 'cert_jaivik_bharat'
    ELSE 'cert_pgs_india'
  END,
  'approved'
FROM market_catalogue_products
WHERE department_order <= 17;

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
-- four focused subcategories. Product cards use only product-specific media.
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
CREATE TEMP TABLE extra_catalogue_sections (
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
  '2026-01-15T08:00:00Z', 'usr_editor', '2026-07-30T10:00:00Z', 'usr_editor'
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
  '2026-01-15T08:00:00Z', 'usr_editor', '2026-07-30T10:00:00Z', 'usr_editor'
FROM extra_catalogue_sections;

INSERT OR IGNORE INTO category_versions (
  id, category_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  'ctv_extra_' || department_slug || '_1', 'cat_extra_' || department_slug,
  1, json_object('blocks', json_array()), 'Initial expanded department',
  'published', '2026-01-15T08:00:00Z', 'usr_editor',
  '2026-07-30T09:30:00Z', 'usr_admin', '2026-07-30T10:00:00Z'
FROM extra_catalogue_sections GROUP BY department_slug
UNION ALL
SELECT
  'ctv_extra_' || section_slug || '_1', 'cat_extra_' || section_slug,
  1, json_object('blocks', json_array()), 'Initial expanded category',
  'published', '2026-01-15T08:00:00Z', 'usr_editor',
  '2026-07-30T09:30:00Z', 'usr_admin', '2026-07-30T10:00:00Z'
FROM extra_catalogue_sections;

CREATE TEMP TABLE extra_catalogue_products AS
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
  'usr_pm',
  datetime('2026-01-15T08:00:00Z', printf('+%d days', (product_number * 13) % 190)),
  'usr_pm'
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
  '2026-07-30T09:00:00Z', 'usr_pm', '2026-07-30T09:30:00Z',
  'usr_admin', '2026-07-30T10:00:00Z'
FROM extra_catalogue_products;

INSERT OR IGNORE INTO product_categories (
  product_id, category_id, is_primary, sort_order, assigned_at, assigned_by
)
SELECT printf('prd_extra_%04d', product_number), 'cat_extra_' || section_slug,
       1, product_order, '2026-07-30T10:00:00Z', 'usr_pm'
FROM extra_catalogue_products
UNION ALL
SELECT printf('prd_extra_%04d', product_number), 'cat_extra_' || department_slug,
       0, product_number, '2026-07-30T10:00:00Z', 'usr_pm'
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
  1, 'active', '2026-07-30T10:00:00Z', 'usr_pm'
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
  AND id NOT LIKE 'prd_catalogue_%'
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

-- Keep the development seed aligned with migration 0046. A fresh
-- database runs migrations before synthetic users exist, so the curated
-- editorial fixture is replayed after the rest of the seed and removes the
-- legacy generated article catalogue.
DELETE FROM search_content
WHERE entity_type = 'article'
  AND (
    entity_id = 'art_millets'
    OR entity_id LIKE 'art_library_%'
    OR entity_id LIKE 'art_expansion_%'
    OR entity_id LIKE 'art_guide_%'
  );

DELETE FROM articles
WHERE id = 'art_millets'
   OR id LIKE 'art_library_%'
   OR id LIKE 'art_expansion_%'
   OR id LIKE 'art_guide_%';

CREATE TEMP TABLE curated_blog_articles (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  slug TEXT NOT NULL,
  excerpt TEXT NOT NULL,
  reading_minutes INTEGER NOT NULL,
  published_at TEXT NOT NULL,
  seo_title TEXT NOT NULL,
  seo_description TEXT NOT NULL,
  keywords TEXT NOT NULL,
  image_alt TEXT NOT NULL,
  content_json TEXT NOT NULL
);

INSERT INTO curated_blog_articles VALUES
  (
    'art_guide_organic_label',
    'How to read an organic food label in India',
    'how-to-read-organic-food-label-india',
    'A five-minute label check that separates verifiable organic certification from attractive but vague packaging.',
    7,
    '2026-07-31T09:00:00Z',
    'How to read an organic food label in India',
    'Learn which marks, licence details, certification scope and batch information make an organic claim useful before you buy.',
    'organic label India Jaivik Bharat NPOP PGS certification buying guide',
    'Certified organic is a claim you should be able to verify, not a mood created by green packaging.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_organic_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'An organic label is useful only when it lets you answer three questions: who is making the claim, which certification system supports it, and whether the specific product you are holding is covered. Words such as natural, clean, farm fresh and residue conscious may describe an intention, but they are not substitutes for certification.',
            'In India, FSSAI recognises the NPOP and PGS-India certification systems for organic food. The official [FSSAI organic food guidance](https://fssai.gov.in/cms/standards-organic-food.php) explains the framework, while the Jaivik Bharat identity helps customers recognise certified products. Here is how to turn those marks into a practical buying check.'
          ))
        ),
        json_object(
          'id', 'blk_guide_organic_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'The five checks that matter',
            'items', json_array(
              json_object(
                'question', '1. Is there a recognised certification mark?',
                'answer', 'Look for the Jaivik Bharat mark and the FSSAI logo with a licence number on packaged certified organic food. Depending on the certification route, you may also see the India Organic mark for NPOP or the PGS-India Organic mark. A leaf illustration designed by the brand is not the same thing. If a marketplace page calls a product organic, the certification details should also be available in text rather than hidden in a lifestyle photograph.'
              ),
              json_object(
                'question', '2. Does the certificate cover this product and this operator?',
                'answer', 'A certificate is not a blanket badge for everything a farm, processor or seller handles. Check the named operator, covered products or scope, certification body or group, and validity period. A farm may have certified mangoes but also trade produce from elsewhere; a processor may be certified for grain handling but not every packaged mix. Ask for the current scope certificate when the listing is unclear.'
              ),
              json_object(
                'question', '3. Can the pack be traced to a batch?',
                'answer', 'Useful labels include a batch or lot number, packed-on or processing date, best-before information where applicable, net quantity and the responsible food business operator. These details do not prove farming practice by themselves, but they connect the pack to records that can be checked. A complaint without a batch number is harder to investigate; a seller that records lots can isolate a problem instead of making guesses about every pack.'
              ),
              json_object(
                'question', '4. Are the marketing claims more precise than the evidence?',
                'answer', 'Treat chemical-free, pesticide-free and 100 percent natural as separate claims that need their own explanation. Organic standards govern a production system; they do not promise that food is nutritionally superior, perfectly shaped or free from every environmental contaminant. Good sellers state what they verified and avoid turning certification into medical advice or an all-purpose purity claim.'
              ),
              json_object(
                'question', '5. What should you ask when buying loose produce?',
                'answer', 'Ask for the farm or producer-group name, certification system, current validity, and how certified stock is kept separate from conventional stock during collection and sale. A direct answer is more valuable than a long farm story. If the seller cannot connect the loose produce to a certified operator or lot, buy it on its visible quality and provenance, but do not pay an organic premium solely on trust.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_organic_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'A sensible check takes less than a minute once you know where to look: recognised mark, licence details, named operator, valid scope and batch identity. Save a photo of the label for pantry products you buy repeatedly. It gives you something concrete to compare when the supplier or packaging changes.',
            'True Grit product pages surface the farm and certification record alongside the food. If any record is missing, expired or too broad to support the product claim, ask us before ordering. The useful answer is evidence, not reassurance.'
          ))
        ),
        json_object(
          'id', 'blk_guide_organic_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Practise the label check', 'source', 'manual',
            'productSlugs', json_array('organic-alphonso-mangoes','organic-baby-spinach','sprouted-ragi-flour','wood-pressed-groundnut-oil'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'Certified organic is a claim you should be able to verify, not a mood created by green packaging.'
    )
  ),
  (
    'art_guide_produce_storage',
    'The 20-minute produce reset that prevents a week of waste',
    '20-minute-produce-storage-reset',
    'What to wash, what to keep dry and what to use first when a fresh produce order reaches your kitchen.',
    7,
    '2026-07-29T09:00:00Z',
    'A practical fresh produce storage reset',
    'Use a 20-minute unpacking routine to store leafy greens, herbs, fruit, roots and damaged produce with less waste.',
    'fresh produce storage leafy greens herbs fruit reduce food waste',
    'The best storage plan begins with an order of use, not a collection of containers.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_storage_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Most produce waste is decided on unpacking day. A wet spinach bunch is pushed behind a cabbage, one bruised mango disappears at the bottom of a bag, and every vegetable is treated as though it wants the same temperature and humidity. By the time a meal plan notices the problem, the most fragile food has already lost.',
            'Set a timer for twenty minutes when the order arrives. You are not meal-prepping the whole week. You are finding damage, removing trapped moisture, giving delicate items the right conditions and deciding what must be cooked first.'
          ))
        ),
        json_object(
          'id', 'blk_guide_storage_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'A five-step unpacking routine',
            'items', json_array(
              json_object(
                'question', '1. Empty every bag and make a use-first group',
                'answer', 'Put bruised fruit, split tomatoes, wilted greens and anything unusually ripe in one visible group. Separate produce with mould, slime, leaking rot or a fermented smell; do not let it touch sound food. A cosmetic mark belongs in tonight''s dinner, not automatically in the bin. The point is to make urgency visible before sturdy roots and pantry items hide it.'
              ),
              json_object(
                'question', '2. Keep leafy greens dry but not exposed',
                'answer', 'Remove ties, damaged leaves and any wet packing. If the leaves are gritty, wash in a bowl of cool water, lift them away from the settled soil and dry them thoroughly; otherwise, washing just before use is simpler. Wrap loosely in a clean dry cloth or absorbent paper and place in a container or bag with a little room. Check the cloth after a day and replace it if it is wet.'
              ),
              json_object(
                'question', '3. Treat herbs by the kind of stem they have',
                'answer', 'Coriander and mint often keep well with trimmed stems in a small jar of water, loosely covered in the refrigerator; remove leaves below the waterline and change cloudy water. Woody herbs prefer to stay dry and loosely wrapped. Whichever method you use, inspect the centre of the bunch. A tight elastic and one decaying stem can spoil leaves that looked fine from the outside.'
              ),
              json_object(
                'question', '4. Give ripening fruit its own zone',
                'answer', 'Mangoes, bananas, tomatoes and similar ripening produce are easier to manage when visible at room temperature until ready, then moved or eaten promptly. Keep them away from delicate greens when possible because ripening fruit releases ethylene, which can speed yellowing and ageing in sensitive produce. Never seal warm or damp fruit in an airtight box; trapped moisture turns a small bruise into decay.'
              ),
              json_object(
                'question', '5. Write a three-line cooking order',
                'answer', 'Line one is today or tomorrow: damaged-but-sound produce, herbs and very ripe fruit. Line two is the next few days: leafy greens, tender vegetables and ripe tomatoes. Line three is later: cabbage, gourds, roots and firm fruit. Put the note on the refrigerator or in the family chat. Planning perishability first is more effective than choosing seven ambitious recipes that use the same sturdy vegetables.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_storage_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Storage advice is never a guarantee because variety, harvest maturity, handling and refrigerator conditions differ. Inspect food instead of trusting a fixed number of days. Clean smell, sound texture and absence of decay matter more than a calendar copied from a generic chart.',
            'If something arrives below standard, photograph the product, label and outer packaging before trimming or cooking it. Keep the batch details and contact support promptly. That evidence helps distinguish delivery damage from normal ripening and lets the affected lot be checked.'
          ))
        ),
        json_object(
          'id', 'blk_guide_storage_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Fresh produce to plan first', 'source', 'manual',
            'productSlugs', json_array('organic-baby-spinach','organic-alphonso-mangoes'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'The best storage plan begins with an order of use, not a collection of containers.'
    )
  ),
  (
    'art_guide_pantry_sizes',
    'Buy less, eat better: a pantry sizing guide for Indian kitchens',
    'pantry-sizing-guide-indian-kitchens',
    'A realistic way to choose pack sizes for flour, pulses and cooking oil based on how your household actually cooks.',
    6,
    '2026-07-27T09:00:00Z',
    'A pantry sizing guide for Indian kitchens',
    'Choose practical pack sizes for flour, pulses and cooking oil using household consumption, climate and storage space.',
    'pantry planning pack size flour pulses cooking oil freshness',
    'The economical pack is the one you finish while the ingredient still tastes the way it should.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_pantry_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'A large pack can lower the price per kilogram and still be the expensive choice. Whole-grain flour loses aroma, cooking oil sits open near a hot stove, and a pulse bought for one recipe occupies the cupboard until nobody remembers its age. The waste is often gradual: food remains edible but becomes harder to cook or less enjoyable to eat.',
            'Instead of stocking an idealised pantry, measure the kitchen you actually run. One week of observation is enough to make a better first estimate, and a marker pen does more useful work than another matching storage jar.'
          ))
        ),
        json_object(
          'id', 'blk_guide_pantry_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Five decisions before choosing a pack size',
            'items', json_array(
              json_object(
                'question', '1. How many meals does this pack represent?',
                'answer', 'Start with your own recipes, not a universal serving chart. Note how much atta, rice, dal or oil goes into a usual meal, then multiply by how often that meal appears. If a 500 g bag of a speciality flour makes four breakfasts and you cook it twice a month, a larger bargain pack is probably not a bargain. Leave room for travel, eating out and the weeks when plans change.'
              ),
              json_object(
                'question', '2. Which foods lose quality fastest after opening?',
                'answer', 'Whole-grain and freshly milled flours deserve smaller, faster-moving packs because bran and natural oils are exposed to air after milling. Unrefined oils also benefit from protection from heat, light and repeated long storage. Whole dry pulses are more forgiving, but older beans can take longer to soften. Buy the smallest pack for slow-use aromatic or oily ingredients; use larger packs for staples with proven turnover.'
              ),
              json_object(
                'question', '3. Is the storage place cooler than the sales shelf?',
                'answer', 'A hot, humid kitchen changes the calculation. Keep dry foods airtight and away from the cooker, sink and direct sun. If refrigerator space is available, it can help protect whole-grain flour in warm weather; use a well-sealed container so the flour does not absorb moisture or odours, and let the amount you need lose its chill while still covered. Do not buy a sack that has no genuinely suitable home.'
              ),
              json_object(
                'question', '4. Can you track two open packs without mixing them?',
                'answer', 'Write the opened date and batch number on the container or keep the original label. Finish the older batch before adding a new one, rather than topping up indefinitely. Mixing makes age, allergens and complaint tracing harder to understand. Decant only when the container is clean and completely dry, and keep the label until the food is finished.'
              ),
              json_object(
                'question', '5. When does bulk buying make sense?',
                'answer', 'Bulk works when consumption is steady, the price difference is meaningful, storage is appropriate and the purchase does not crowd out variety. It can also work when neighbours intentionally split sealed packs at purchase. It makes less sense for a new ingredient, a seasonal enthusiasm or a product you are buying mainly to reach a delivery threshold. Test a smaller pack before committing cupboard space and money.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_pantry_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'For the next four weeks, write the opened date on every flour, pulse and oil pack. When each one finishes, you have your household''s real consumption rate. Choose the next pack to cover that interval with a modest buffer, not six imaginary months.',
            'A smaller active pantry makes changes easier to notice. You smell when a fresh oil is especially good, learn which pulse cooks reliably and buy enough flour to enjoy its aroma. That is a better return than saving a few rupees on food that spends a year fading in the cupboard.'
          ))
        ),
        json_object(
          'id', 'blk_guide_pantry_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Build a faster-moving pantry', 'source', 'manual',
            'productSlugs', json_array('sprouted-ragi-flour','himalayan-red-rajma','wood-pressed-groundnut-oil'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'The economical pack is the one you finish while the ingredient still tastes the way it should.'
    )
  ),
  (
    'art_guide_imperfect_produce',
    'Imperfect, ripe or spoiled? A practical produce triage guide',
    'imperfect-ripe-or-spoiled-produce-guide',
    'How to tell harmless variation from damage that needs quick cooking, a support claim or the compost bin.',
    7,
    '2026-07-25T09:00:00Z',
    'Imperfect, ripe or spoiled produce?',
    'Use sight, smell and texture to sort cosmetic variation, usable damage and clear spoilage in fresh produce deliveries.',
    'imperfect produce ripe spoiled bruised vegetables food waste delivery quality',
    'Ugly is not unsafe, and beautiful is not proof of freshness. Condition matters more than symmetry.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_triage_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Fresh produce is allowed to look alive. A mango can carry a sap mark, spinach leaves vary in size and a carrot may fork around a stone. Rejecting every variation wastes good food; accepting leaking, mouldy or heat-damaged produce excuses poor handling. Customers need a clearer line than supermarket perfection on one side and eat everything on the other.',
            'Use three groups: sound, use first, and do not use. Work with clean hands and good light, and judge the whole item rather than one dramatic photograph of a harmless scar.'
          ))
        ),
        json_object(
          'id', 'blk_guide_triage_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Five ways to make the call',
            'items', json_array(
              json_object(
                'question', '1. What is usually cosmetic?',
                'answer', 'Uneven shape, superficial soil, healed skin scars, colour variation and leaves of different sizes are often cosmetic. So are small pressure marks that remain dry and firm. Wash or trim as the ingredient normally requires, then use it on its own merits. Organic production does not cause every blemish, and a spotless surface does not reveal how something was grown; appearance and certification are separate questions.'
              ),
              json_object(
                'question', '2. What belongs in the use-first group?',
                'answer', 'A soft but clean tomato, a wilted but unslimy bunch, a split root with dry edges or a bruised ripe fruit may still be useful if handled promptly. Cut the item open and inspect it. Use sound portions in cooked dishes where texture is less important. Do not store damaged pieces beside pristine produce, and do not preserve or pickle questionable ingredients in the hope that salt, spice or heat will erase poor quality.'
              ),
              json_object(
                'question', '3. Which signs mean do not use?',
                'answer', 'Visible fuzzy mould, slime, leaking rot, a fermented or putrid smell, extensive internal browning, pest contamination or flesh that has become unexpectedly fizzy are clear reasons to stop. With soft, high-moisture produce, cutting a small margin around mould is not a reliable rescue because growth can extend beyond what is visible. When in doubt about a strongly altered smell or texture, discard the item.'
              ),
              json_object(
                'question', '4. When is the seller responsible?',
                'answer', 'Report produce that arrives crushed, overheated, leaking, mouldy, materially underweight or inconsistent with the listing. Also report repeated premature decay from the same lot. Take one photo showing the full quantity, one close view of the problem, and one of the label or batch details. Include the delivery time and whether the outer packaging was damaged. This is more actionable than a close-up with no scale or order reference.'
              ),
              json_object(
                'question', '5. How should a fair resolution work?',
                'answer', 'The goal is to restore the value of the affected portion, not force a customer to return decaying food through the post. Depending on the issue, a replacement, refund or credit may be appropriate. Keep the product and packaging only until support confirms what evidence is needed. A responsible seller should also check the lot, packing process and route so the next customer does not receive the same problem.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_triage_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'This approach leaves room for normal agricultural variation without lowering the standard for sound food. The test is not whether a vegetable could appear in an advertisement. It is whether it is clean, honestly described, usable for its intended purpose and delivered with reasonable shelf life remaining.',
            'Build one use-first meal into delivery day: tomato base, mixed sabzi, soup, chutney or fruit compote. It turns minor transit damage into dinner while keeping clear spoilage out of the kitchen. Waste less, but never let an anti-waste slogan pressure you into eating food you do not trust.'
          ))
        ),
        json_object(
          'id', 'blk_guide_triage_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Fresh produce with clear provenance', 'source', 'manual',
            'productSlugs', json_array('organic-alphonso-mangoes','organic-baby-spinach'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'Ugly is not unsafe, and beautiful is not proof of freshness. Condition matters more than symmetry.'
    )
  ),
  (
    'art_guide_traceability',
    'What food traceability should tell you before and after a purchase',
    'what-food-traceability-should-tell-you',
    'The records that turn a farm story into something useful when you are choosing a product or reporting a problem.',
    6,
    '2026-07-23T09:00:00Z',
    'What useful food traceability looks like',
    'Learn which farm, lot, harvest, processing and delivery records make food traceability useful to customers.',
    'food traceability farm lot harvest date batch supply chain customer guide',
    'Traceability earns its keep when it can answer a specific question about a specific pack.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_trace_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'A photograph of a farmer is not traceability. Neither is a map pin with no connection to the item in your basket. Traceability is the preserved link between a particular quantity of food and the records created as it moved through growing, harvest or processing, packing and sale.',
            'Customers do not need every internal spreadsheet. They do need enough information to choose intelligently, verify important claims and identify the affected lot when something goes wrong.'
          ))
        ),
        json_object(
          'id', 'blk_guide_trace_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Five records that make provenance useful',
            'items', json_array(
              json_object(
                'question', '1. Who produced it, and where?',
                'answer', 'The record should name the farm, grower group or processor responsible for the product, with a location more meaningful than simply India. For a blended or aggregated product, the seller should say so rather than presenting one photogenic farm as the only source. The producer name helps you connect certification, farming method and previous purchases to the correct operation.'
              ),
              json_object(
                'question', '2. Which lot is this item part of?',
                'answer', 'A lot or batch groups food handled under shared conditions. It may relate to a harvest date, milling run, collection route or packing session. The code does not need to be friendly, but it must remain attached to the item and to internal records. When quality varies, the lot lets a seller investigate the narrowest sensible group instead of blaming the customer or recalling everything.'
              ),
              json_object(
                'question', '3. Which dates actually matter?',
                'answer', 'For fresh produce, harvest and dispatch timing can help explain maturity and expected condition. For flour and oil, milling or pressing and packing dates are often more useful than a romantic harvest season alone. Best-before information serves a different purpose and should not be presented as proof of freshness. Useful pages label each date clearly instead of displaying one unexplained timestamp.'
              ),
              json_object(
                'question', '4. Which claims are connected to documents?',
                'answer', 'Certification, variety, processing method and single-origin claims should point to records that cover the relevant product and period. A certificate for the farm does not automatically prove a separate processor''s handling claim. Good traceability preserves the chain across hand-offs: producer to collector, processor, packer, fulfilment centre and customer.'
              ),
              json_object(
                'question', '5. Can support retrieve the record from your order?',
                'answer', 'The final test happens after purchase. Give support the order reference and product name; the team should be able to identify the dispatched batch without asking you to reconstruct the supply chain. A label photo is still valuable when packaging is damaged or lots were split. If the business collects traceability data but cannot use it during a complaint, it is decoration rather than an operating system.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_trace_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Before buying, look for a named source, meaningful dates, a certification or method record where relevant, and an explanation of mixed sourcing. After buying, retain the batch label until the food has been checked. Those habits take seconds and make provenance far more useful.',
            'Traceability cannot guarantee flavour or prevent every mistake. It shortens the distance between a question and an accountable answer. That is why a plain lot code can matter more than a page of storytelling.'
          ))
        ),
        json_object(
          'id', 'blk_guide_trace_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'See traceability in the catalogue', 'source', 'manual',
            'productSlugs', json_array('organic-alphonso-mangoes','sprouted-ragi-flour','wood-pressed-groundnut-oil','himalayan-red-rajma'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'Traceability earns its keep when it can answer a specific question about a specific pack.'
    )
  ),
  (
    'art_guide_millets',
    'Ragi, jowar, bajra or little millet: choose the grain for the meal',
    'choose-ragi-jowar-bajra-little-millet',
    'A cooking-first guide to four different millets, without treating them as one fashionable substitute for rice and wheat.',
    7,
    '2026-07-21T09:00:00Z',
    'How to choose a millet for the meal',
    'Compare ragi, jowar, bajra and little millet by flavour, form and cooking use so you can choose the right grain for a dish.',
    'ragi jowar bajra little millet cooking guide flour whole grain',
    'Millet is a family of grains, not a single ingredient waiting to replace wheat or rice.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_millet_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Millet advice often begins with a list of health claims and ends by asking one grain to replace every familiar staple. That is a poor introduction. Finger millet, sorghum, pearl millet and the small millets have different flavours, structures and forms. The useful question is not which millet is best, but which one suits the meal you want to cook.',
            'Start with one recurring dish and learn the ingredient there. A grain becomes part of a household through reliable breakfasts and dinners, not through a bag purchased after a headline and forgotten behind the rice.'
          ))
        ),
        json_object(
          'id', 'blk_guide_millet_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Choose by form, flavour and technique',
            'items', json_array(
              json_object(
                'question', '1. When does ragi make sense?',
                'answer', 'Ragi, or finger millet, is commonly sold as flour because the tiny grain is difficult to use like rice at home. Its earthy, gently malty flavour works in dosa, roti blended with other flours, porridge and baked snacks. Ragi contains no gluten, so a 100 percent ragi dough will not stretch like wheat dough. Use a recipe designed for it instead of making a straight swap and blaming the grain for crumbling.'
              ),
              json_object(
                'question', '2. What is jowar good at?',
                'answer', 'Jowar, or sorghum, has a mild flavour that sits comfortably beside vegetables and dal. Its flour is used for bhakri and roti, while pearled or whole forms can be cooked for salads, bowls and pilafs when available. Jowar dough also lacks gluten; warm water, careful patting and practice matter more than adding excess dry flour. Begin with a small roti or a flour blend while learning the feel.'
              ),
              json_object(
                'question', '3. Where does bajra fit?',
                'answer', 'Bajra, or pearl millet, is robust, nutty and especially good with assertive winter foods: greens, garlic, sesame, jaggery and slow-cooked pulses. The flour can develop stale flavours during long storage, so buy an amount you will finish and keep it cool and airtight. Bajra roti is meant to be tender and rustic, not an imitation of a thin elastic wheat phulka.'
              ),
              json_object(
                'question', '4. Can little millet replace rice in a dish?',
                'answer', 'Little millet and other small millets are often the easiest place to start when you want a separate cooked grain. Rinse well, use the package ratio as a starting point and rest the covered pot after cooking. The exact water need changes with polishing and age. Use it first in a familiar lemon rice, pulao or curd-rice style dish so only one part of the meal is new.'
              ),
              json_object(
                'question', '5. How do you make the change last?',
                'answer', 'Choose one millet, one form and one weekly meal. Record the water, resting time and result on the pack. Adjust the next batch instead of switching grains immediately. Keep rice and wheat in the kitchen if they serve you well; variety is a more realistic goal than purity. Repetition builds skill, creates steady demand and tells you whether the family genuinely enjoys the ingredient.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_millet_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'For a first purchase, decide the dish before the pack size. Choose ragi flour for dosa or porridge, jowar flour for bhakri, bajra flour for a robust winter roti, or a small millet for a rice-style preparation. Then buy enough for two or three attempts, because technique rarely becomes comfortable in one meal.',
            'The best grain is the one that earns a regular place at the table. Respecting the differences between millets leads to better food and more durable demand than treating all of them as a single miracle ingredient.'
          ))
        ),
        json_object(
          'id', 'blk_guide_millet_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Start with ragi in a familiar dish', 'source', 'manual',
            'productSlugs', json_array('sprouted-ragi-flour'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'Millet is a family of grains, not a single ingredient waiting to replace wheat or rice.'
    )
  ),
  (
    'art_guide_weekly_plan',
    'Plan five dinners from one seasonal produce order',
    'plan-five-dinners-seasonal-produce-order',
    'A flexible meal-planning method that uses fragile vegetables first, carries prep forward and leaves room for real life.',
    7,
    '2026-07-19T09:00:00Z',
    'Plan five dinners from seasonal produce',
    'Turn one mixed produce order into five flexible dinners by planning perishability, shared preparation and one rescue meal.',
    'seasonal meal planning vegetables weekly dinner plan food waste',
    'A useful meal plan organises perishability and effort; it does not pretend Thursday will obey Monday.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_plan_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Seasonal shopping becomes frustrating when the order is treated as a collection of unrelated recipes. Every dish needs a new list, the tender greens wait for inspiration and the cook runs out of energy before the vegetables run out of life. A better plan starts with perishability and shared preparation.',
            'You do not need to predict five exact dinners. Build five meal roles, assign the most fragile produce to the earliest role and prepare one component that can move through the week without making every plate taste the same.'
          ))
        ),
        json_object(
          'id', 'blk_guide_plan_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Five dinner roles for a mixed order',
            'items', json_array(
              json_object(
                'question', 'Dinner 1: the fragile meal',
                'answer', 'Use spinach, tender herbs, mushrooms, flowers, very ripe tomatoes or any sound item bruised in transit. Keep the method fast: dal with greens, a herb-heavy egg dish, stir-fry or tomato toast beside leftovers. While chopping, wash and dry the remaining herbs and cook one neutral base such as plain dal, beans or grain for later meals.'
              ),
              json_object(
                'question', 'Dinner 2: the two-texture vegetable meal',
                'answer', 'Pair a vegetable that needs longer cooking with one that needs almost none. Roast roots and fold in greens at the end; cook a gourd curry and finish with fresh coriander; make millet or rice and top it with a crisp cucumber salad. This keeps the meal varied without running two elaborate recipes. Prepare double the sturdy component if tomorrow is busy.'
              ),
              json_object(
                'question', 'Dinner 3: the pantry bridge',
                'answer', 'Use pulses, flour or grain to stretch the smaller quantities left in the produce drawer. Rajma can carry roasted pumpkin, ragi dosa can hold a quick spinach filling and khichdi can absorb beans, carrots or gourds. The pantry is not a fallback after fresh food; it is what turns seasonal variation into a complete, repeatable meal.'
              ),
              json_object(
                'question', 'Dinner 4: the planned leftover',
                'answer', 'Transform one prepared component rather than reheating the entire previous plate. Cooked beans become a chaat or wrap filling, roasted vegetables join a grain bowl, and extra dal thickens into a pancake batter or soup base. Cool and refrigerate cooked food promptly in shallow containers, label it and reheat only what you need. If storage was uncertain, do not build a new meal around it.'
              ),
              json_object(
                'question', 'Dinner 5: the rescue meal',
                'answer', 'Reserve a forgiving format for the end of the cycle: mixed sabzi, soup, tray roast, fried rice, khichdi or a clean-out-the-drawer pasta. Inspect every ingredient and keep incompatible flavours separate rather than emptying everything into one pot. The rescue meal is planned capacity for small amounts and changed schedules, not permission to use spoiled food.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_plan_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Keep the plan on one screen: five roles, the produce assigned to each and one component to carry forward. If dinner out appears, move the fragile ingredient into breakfast or lunch and push a sturdy role back. The structure bends because it was never dependent on five perfect evenings.',
            'After a month, notice what repeatedly survives to rescue night. Buy less of it, choose a smaller pack or learn one preparation the household actually requests. A seasonal plan improves by listening to the waste, not by collecting more recipes.'
          ))
        ),
        json_object(
          'id', 'blk_guide_plan_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Build this week''s flexible order', 'source', 'manual',
            'productSlugs', json_array('organic-baby-spinach','himalayan-red-rajma','sprouted-ragi-flour','wood-pressed-groundnut-oil'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'A useful meal plan organises perishability and effort; it does not pretend Thursday will obey Monday.'
    )
  );

-- Production databases do not necessarily contain the development editor. The
-- SELECT guard makes this a no-op there; seeded environments have usr_editor,
-- and the development seed mirrors this curated set for a fresh database.
INSERT INTO articles (
  id, internal_name, title, slug, excerpt, author_user_id, hero_media_id,
  reading_minutes, status, published_version_id, published_at, seo_title,
  seo_description, created_at, created_by, updated_at, updated_by, seo_keywords,
  indexing_policy, hero_image_url, hero_image_alt
)
SELECT
  id, 'Customer guide: ' || slug, title, slug, excerpt,
  CASE id
    WHEN 'art_guide_organic_label' THEN 'usr_author_buying'
    WHEN 'art_guide_produce_storage' THEN 'usr_author_food_care'
    WHEN 'art_guide_pantry_sizes' THEN 'usr_author_kitchen'
    WHEN 'art_guide_imperfect_produce' THEN 'usr_author_food_care'
    WHEN 'art_guide_traceability' THEN 'usr_author_farms'
    WHEN 'art_guide_millets' THEN 'usr_author_kitchen'
    ELSE 'usr_author_kitchen'
  END,
  NULL,
  reading_minutes, 'published', 'arv_' || id || '_1', published_at, seo_title,
  seo_description, published_at, 'usr_editor', published_at, 'usr_editor', keywords,
  'index', '/banners/content/blog-editorial-guides.webp', image_alt
FROM curated_blog_articles
WHERE EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO article_versions (
  id, article_id, version_number, content_json, workflow_state, created_at,
  created_by, approved_at, approved_by, published_at
)
SELECT
  'arv_' || id || '_1', id, 1, content_json, 'published', published_at,
  'usr_editor', published_at, 'usr_editor', published_at
FROM curated_blog_articles
WHERE EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO search_content (entity_type, entity_id, title, slug, excerpt, keywords)
SELECT 'article', id, title, slug, excerpt, keywords
FROM curated_blog_articles
WHERE EXISTS (SELECT 1 FROM articles WHERE articles.id = curated_blog_articles.id);

DROP TABLE curated_blog_articles;

-- Migration 0050 runs before development fixtures exist, so its community
-- case-note backfill is intentionally empty on a fresh database. Replay that
-- small, deterministic projection now that the 50 useful problem/outcome
-- thread pairs exist. The 144 field guides already came from the migration;
-- these 50 notes plus the seven long guides restore 201 published articles.
WITH paired_threads AS (
  SELECT
    CAST(substr(question.id, 13, 3) AS INTEGER) AS n,
    question.body AS problem,
    outcome.title AS title,
    outcome.body AS outcome
  FROM discussions question
  JOIN discussions outcome
    ON outcome.id = substr(question.id, 1, length(question.id) - 1) || 'b'
  WHERE question.id LIKE 'dsc_library_%_a'
)
INSERT OR IGNORE INTO articles (
  id, internal_name, title, slug, excerpt, author_user_id, hero_media_id,
  reading_minutes, status, published_version_id, published_at, seo_title,
  seo_description, created_at, created_by, updated_at, updated_by, seo_keywords,
  indexing_policy, hero_image_url, hero_image_alt
)
SELECT
  printf('art_case_%03d', n),
  'Community-tested kitchen note ' || n,
  title,
  'community-tested-kitchen-note-' || printf('%03d', n),
  problem,
  CASE n % 5
    WHEN 0 THEN 'usr_author_community'
    WHEN 1 THEN 'usr_author_food_care'
    WHEN 2 THEN 'usr_author_kitchen'
    WHEN 3 THEN 'usr_author_buying'
    ELSE 'usr_author_farms'
  END,
  NULL,
  3,
  'published',
  printf('arv_case_%03d_1', n),
  datetime('2026-02-01T09:00:00Z', printf('+%d days', n)),
  title,
  problem,
  '2026-01-20T09:00:00Z',
  'usr_author_community',
  datetime('2026-02-01T09:00:00Z', printf('+%d days', n)),
  'usr_author_community',
  'community tested kitchen storage cooking troubleshooting',
  'index',
  '/banners/content/blog-editorial-guides.webp',
  'A practical True Grit community kitchen test and its result'
FROM paired_threads;

WITH paired_threads AS (
  SELECT
    CAST(substr(question.id, 13, 3) AS INTEGER) AS n,
    question.body AS problem,
    outcome.body AS outcome
  FROM discussions question
  JOIN discussions outcome
    ON outcome.id = substr(question.id, 1, length(question.id) - 1) || 'b'
  WHERE question.id LIKE 'dsc_library_%_a'
)
INSERT OR IGNORE INTO article_versions (
  id, article_id, version_number, content_json, workflow_state, created_at,
  created_by, approved_at, approved_by, published_at
)
SELECT
  printf('arv_case_%03d_1', n),
  printf('art_case_%03d', n),
  1,
  json_object(
    'blocks', json_array(
      json_object(
        'id', printf('blk_case_%03d_story', n), 'type', 'rich_text',
        'version', 1, 'enabled', json('true'),
        'props', json_object('paragraphs', json_array(
          problem,
          outcome,
          'Treat this as a tested starting point, not a universal guarantee. Variety, maturity, room temperature, refrigerator conditions and equipment can change the result. Try the smallest useful batch, record what you changed and keep the part that works in your kitchen.',
          'Before repeating the method, inspect the food and the storage conditions again. Do not use a successful texture result to overrule mould, leaking decay, a rotten smell, unsafe holding time or appliance guidance. Quality experiments are useful only inside clear food-safety boundaries.'
        ))
      ),
      json_object(
        'id', printf('blk_case_%03d_checklist', n), 'type', 'faq',
        'version', 1, 'enabled', json('true'),
        'props', json_object(
          'heading', 'Use the result without losing the context',
          'items', json_array(
            json_object('question','What was the starting problem?','answer',problem),
            json_object('question','What changed in the successful attempt?','answer',outcome),
            json_object('question','How should I test it?','answer','Change one factor, keep the batch small and note the time, temperature and result before repeating it.'),
            json_object('question','When should I discard rather than rescue?','answer','Discard food with mould, leaking rot, an unmistakably rotten smell or a storage history that makes safety uncertain. A useful waste-reduction habit never depends on talking yourself past a warning sign.'),
            json_object('question','Which details help other readers?','answer','Share the ingredient variety or form, approximate quantity, room or refrigerator conditions, timing and the result. Those details explain why two honest attempts may differ.')
          )
        )
      )
    ),
    'pullQuote', outcome
  ),
  'published',
  '2026-01-20T09:00:00Z',
  'usr_author_community',
  datetime('2026-02-01T08:30:00Z', printf('+%d days', n)),
  'usr_author_buying',
  datetime('2026-02-01T09:00:00Z', printf('+%d days', n))
FROM paired_threads;

INSERT OR IGNORE INTO search_content (entity_type, entity_id, title, slug, excerpt, keywords)
SELECT 'article', id, title, slug, excerpt, seo_keywords
FROM articles
WHERE id LIKE 'art_case_%';

-- Keep the 100 specific problem/outcome threads. Remove only the 100 old
-- expansion prompts; migration 0050 supplied 100 evidence-led replacements.
DELETE FROM discussions WHERE id LIKE 'dsc_expansion_%';

-- Keep repository-backed banner paths and the database carousel identical
-- after a development reseed.
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

-- Homepage directory of the rest of the site (migration 0049). Repeated here
-- because migrations run against an empty database before this seed inserts
-- the homepage row, so the seed has to carry the current desired state itself.
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

-- Promotions banner (migration 0060), directly under the hero. Repeated here
-- for the same reason as blk_page_links above: migrations run against an
-- empty database before this seed inserts the homepage row.
-- Uses json_group_array (not json_insert) to splice into an already-occupied
-- index -- see the matching comment in 0060_coupons_and_promotions.sql.
UPDATE page_versions
SET content_json = json_set(
  content_json,
  '$.blocks',
  (
    SELECT json_group_array(json(item))
    FROM (
      SELECT block.value AS item, block.key * 2 AS ord
      FROM json_each(page_versions.content_json, '$.blocks') AS block
      WHERE block.key = 0
      UNION ALL
      SELECT '{"id":"blk_promotion_banner","type":"promotion_banner","version":1,"enabled":true,"props":{"source":"rule"}}' AS item, 1 AS ord
      UNION ALL
      SELECT block.value AS item, block.key * 2 + 2 AS ord
      FROM json_each(page_versions.content_json, '$.blocks') AS block
      WHERE block.key >= 1
      ORDER BY ord
    )
  )
)
WHERE page_id = 'pag_home'
  AND NOT EXISTS (
    SELECT 1
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'promotion_banner'
  );

-- "What customers are saying" (migration 0057). Repeated here for the same
-- reason as blk_page_links above.
UPDATE page_versions
SET content_json = json_insert(
  content_json,
  '$.blocks[#]',
  json('{
    "id": "blk_reviews_showcase",
    "type": "reviews_showcase",
    "version": 1,
    "enabled": true,
    "props": {
      "heading": "What customers are saying",
      "subheading": "Real ratings from verified purchases.",
      "source": "rule",
      "reviewIds": [],
      "limit": 8,
      "minRating": 4
    }
  }')
)
WHERE page_id = 'pag_home'
  AND NOT EXISTS (
    SELECT 1
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'reviews_showcase'
  );

-- Real bestsellers, computed live from order_items (migration 0063). Repeated
-- here for the same reason as blk_page_links above.
UPDATE page_versions
SET content_json = json_insert(
  content_json,
  '$.blocks[#]',
  json('{
    "id": "blk_recommendations",
    "type": "recommendations",
    "version": 1,
    "enabled": true,
    "props": {
      "heading": "Customer favourites",
      "subheading": "Picked by shoppers",
      "limit": 8
    }
  }')
)
WHERE page_id = 'pag_home'
  AND NOT EXISTS (
    SELECT 1
    FROM json_each(page_versions.content_json, '$.blocks') AS block
    WHERE json_extract(block.value, '$.type') = 'recommendations'
  );

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
  '2026-08-02T06:00:00Z', 'usr_editor', '2026-08-02T06:00:00Z', 'usr_editor'
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
  '2026-08-02T06:00:00Z', 'usr_editor', '2026-08-02T06:00:00Z', 'usr_editor'
FROM catalogue_completion_sections;

INSERT OR IGNORE INTO category_versions (
  id, category_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  'ctv_complete_' || department_slug || '_1',
  'cat_complete_' || department_slug, 1,
  json_object('blocks', json_array()), 'Complete-market department added',
  'published', '2026-08-02T05:30:00Z', 'usr_editor',
  '2026-08-02T05:45:00Z', 'usr_admin', '2026-08-02T06:00:00Z'
FROM catalogue_completion_sections GROUP BY department_slug
UNION ALL
SELECT
  'ctv_complete_' || section_slug || '_1',
  'cat_complete_' || section_slug, 1,
  json_object('blocks', json_array()), 'Complete-market category added',
  'published', '2026-08-02T05:30:00Z', 'usr_editor',
  '2026-08-02T05:45:00Z', 'usr_admin', '2026-08-02T06:00:00Z'
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
  'usr_pm', '2026-08-02T06:00:00Z', 'usr_pm'
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
  '2026-08-02T05:30:00Z', 'usr_pm', '2026-08-02T05:45:00Z',
  'usr_admin', '2026-08-02T06:00:00Z'
FROM catalogue_completion_products;

INSERT OR IGNORE INTO product_categories (
  product_id, category_id, is_primary, sort_order, assigned_at, assigned_by
)
SELECT printf('prd_complete_%04d', product_number),
       'cat_complete_' || section_slug, 1, product_order,
       '2026-08-02T06:00:00Z', 'usr_pm'
FROM catalogue_completion_products
UNION ALL
SELECT printf('prd_complete_%04d', product_number),
       'cat_complete_' || department_slug, 0, product_number,
       '2026-08-02T06:00:00Z', 'usr_pm'
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
  1, 'active', '2026-08-02T06:00:00Z', 'usr_pm'
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
  '2026-08-02T07:00:00Z', 'usr_editor', '2026-08-02T07:00:00Z', 'usr_editor'
FROM mass_catalogue_sections;

INSERT OR IGNORE INTO category_versions (
  id, category_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  'ctv_mass_' || section_slug || '_1', 'cat_mass_' || section_slug, 1,
  json_object('blocks', json_array()), 'High-volume category added',
  'published', '2026-08-02T06:30:00Z', 'usr_editor',
  '2026-08-02T06:45:00Z', 'usr_admin', '2026-08-02T07:00:00Z'
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
  'usr_pm', '2026-08-02T07:00:00Z', 'usr_pm'
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
  '2026-08-02T06:30:00Z', 'usr_pm', '2026-08-02T06:45:00Z',
  'usr_admin', '2026-08-02T07:00:00Z'
FROM mass_catalogue_products;

INSERT OR IGNORE INTO product_categories (
  product_id, category_id, is_primary, sort_order, assigned_at, assigned_by
)
SELECT printf('prd_mass_%04d', product_number), 'cat_mass_' || section_slug,
       1, product_order, '2026-08-02T07:00:00Z', 'usr_pm'
FROM mass_catalogue_products
UNION ALL
SELECT printf('prd_mass_%04d', product_number), 'cat_complete_' || department_slug,
       0, product_number, '2026-08-02T07:00:00Z', 'usr_pm'
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
       1, 'active', '2026-08-02T07:00:00Z', 'usr_pm'
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

-- Product cards must never borrow department artwork: it is visually
-- misleading for individual foods. The UI renders an explicit product-name
-- placeholder until an owner uploads a product-specific photograph.
UPDATE products
SET image_url = NULL
WHERE image_url LIKE '/banners/categories/%'
   OR image_url LIKE '/homepage-hero%.png';

UPDATE products
SET image_url = CASE id
      WHEN 'prd_alphonso' THEN '/products/organic-alphonso-mangoes.png'
      WHEN 'prd_spinach' THEN '/products/organic-baby-spinach.png'
      WHEN 'prd_ragi' THEN '/products/sprouted-ragi-flour.png'
      WHEN 'prd_groundnut_oil' THEN '/products/wood-pressed-groundnut-oil.png'
      WHEN 'prd_rajma' THEN '/products/himalayan-red-rajma.png'
      ELSE image_url
    END,
    image_alt = CASE id
      WHEN 'prd_alphonso' THEN 'Crate of ripe organic Alphonso mangoes'
      WHEN 'prd_spinach' THEN 'Tender organic baby spinach leaves'
      WHEN 'prd_ragi' THEN 'Sprouted ragi flour with finger millet heads'
      WHEN 'prd_groundnut_oil' THEN 'Wood-pressed groundnut oil with peanuts'
      WHEN 'prd_rajma' THEN 'Himalayan red rajma in a cloth pouch and bowl'
      ELSE image_alt
    END
WHERE id IN ('prd_alphonso', 'prd_spinach', 'prd_ragi', 'prd_groundnut_oil', 'prd_rajma');

UPDATE products
SET image_url = '/products/' || slug || '.png',
    image_alt = CASE id
      WHEN 'prd_market_0001' THEN 'Crate of ripe organic Kesar mangoes'
      WHEN 'prd_market_0033' THEN 'Fresh bunch of organic mature spinach'
      WHEN 'prd_market_0097' THEN 'Organic brown basmati rice in a bowl and cloth pouch'
      WHEN 'prd_market_0130' THEN 'Organic yellow moong dal with whole green mung beans'
      WHEN 'prd_market_0161' THEN 'Organic whole wheat atta with golden wheat heads'
      WHEN 'prd_market_0193' THEN 'Cold-pressed mustard oil with mustard seeds'
      WHEN 'prd_market_0233' THEN 'Organic turmeric powder with fresh turmeric rhizomes'
      WHEN 'prd_market_0265' THEN 'Organic wild forest honey with honeycomb and dipper'
      WHEN 'prd_market_0289' THEN 'Organic Kashmiri almonds in a wooden bowl'
      WHEN 'prd_market_0321' THEN 'Organic rolled oats with oat stalks'
      WHEN 'prd_market_0385' THEN 'Organic roasted makhana in a wooden bowl'
      WHEN 'prd_market_0417' THEN 'Organic Assam black tea leaves with brewed tea'
      ELSE image_alt
    END
WHERE id IN (
  'prd_market_0001', 'prd_market_0033', 'prd_market_0097', 'prd_market_0130',
  'prd_market_0161', 'prd_market_0193', 'prd_market_0233', 'prd_market_0265',
  'prd_market_0289', 'prd_market_0321', 'prd_market_0385', 'prd_market_0417'
);

-- Additional reviewed product photographs. Keep this aligned with migration
-- 0071 so a fresh seed and an upgraded database expose the same catalogue.
UPDATE products
SET image_url = '/products/' || slug || '.jpg',
    image_alt = CASE id
      WHEN 'prd_mass_0001' THEN 'Assorted hen eggs in a metal bowl'
      WHEN 'prd_mass_0002' THEN 'Assorted farm eggs in a woven basket'
      WHEN 'prd_mass_0003' THEN 'Brown country hen eggs on a white background'
      WHEN 'prd_mass_0004' THEN 'Speckled quail eggs'
      WHEN 'prd_mass_0005' THEN 'Brown hen eggs on a white background'
      WHEN 'prd_mass_0006' THEN 'Assorted farm eggs in a woven basket'
      WHEN 'prd_mass_0007' THEN 'Assorted farm eggs in a woven basket'
      WHEN 'prd_mass_0008' THEN 'Speckled quail eggs'
      WHEN 'prd_complete_0129' THEN 'Dark chocolate pieces with almonds and sea salt'
      WHEN 'prd_complete_0130' THEN 'Dark chocolate pieces with almonds and sea salt'
      ELSE image_alt
    END
WHERE id IN (
  'prd_mass_0001', 'prd_mass_0002', 'prd_mass_0003', 'prd_mass_0004',
  'prd_mass_0005', 'prd_mass_0006', 'prd_mass_0007', 'prd_mass_0008',
  'prd_complete_0129', 'prd_complete_0130'
);

-- The live catalogue migration intentionally replaces the former editorial
-- and farm records. Keep development aligned after this legacy seed has run.
--
-- The prefix list is an allow-list of content the migrations own, not just the
-- 0095 set: `rcp_world_%` (migration 0105) is published content too, and
-- leaving it out of these clauses silently deleted all twelve rows in
-- development while production kept them.
DELETE FROM search_content
WHERE (entity_type = 'article' AND entity_id NOT LIKE 'art_truegrit_%')
   OR (
     entity_type = 'recipe'
     AND entity_id NOT LIKE 'rcp_truegrit_%'
     AND entity_id NOT LIKE 'rcp_world_%'
   );
DELETE FROM articles WHERE id NOT LIKE 'art_truegrit_%';
DELETE FROM recipes WHERE id NOT LIKE 'rcp_truegrit_%' AND id NOT LIKE 'rcp_world_%';
UPDATE products SET farm_id = NULL
WHERE farm_id IS NOT NULL
  AND farm_id NOT IN (
    'farm_bagi_1', 'farm_bagi_2', 'farm_sajerah_1', 'farm_sajerah_2',
    'farm_najirpur_1', 'farm_najirpur_2', 'farm_khutmili_1', 'farm_khutmili_2'
  );
UPDATE order_items SET farm_id = NULL
WHERE farm_id IS NOT NULL
  AND farm_id NOT IN (
    'farm_bagi_1', 'farm_bagi_2', 'farm_sajerah_1', 'farm_sajerah_2',
    'farm_najirpur_1', 'farm_najirpur_2', 'farm_khutmili_1', 'farm_khutmili_2'
  );
UPDATE farm_partnership_requests SET linked_farm_id = NULL
WHERE linked_farm_id IS NOT NULL
  AND linked_farm_id NOT IN (
    'farm_bagi_1', 'farm_bagi_2', 'farm_sajerah_1', 'farm_sajerah_2',
    'farm_najirpur_1', 'farm_najirpur_2', 'farm_khutmili_1', 'farm_khutmili_2'
  );
DELETE FROM farms
WHERE id NOT IN (
  'farm_bagi_1', 'farm_bagi_2', 'farm_sajerah_1', 'farm_sajerah_2',
  'farm_najirpur_1', 'farm_najirpur_2', 'farm_khutmili_1', 'farm_khutmili_2'
);

-- The legacy seed builds an older twelve-slide carousel above. Finish with the
-- same four-slide live homepage that migration 0106 publishes in production.
UPDATE page_versions
SET content_json = json_set(
  content_json,
  '$.blocks[0].props.imageUrl', '/banners/home/catalogue/00-our-farms.webp',
  '$.blocks[0].props.imageAlt', 'Partner farmers walking between varied crop fields',
  '$.blocks[0].props.slides', json('[
    {"imageUrl":"/banners/home/catalogue/00-our-farms.webp","imageAlt":"Partner farmers walking between varied crop fields","href":"/farms","label":"Meet our farms","enabled":true},
    {"imageUrl":"/banners/home/catalogue/01-complete-organic-range.webp","imageAlt":"True Grit traditional grains, pulses, seeds and cold-pressed oils","href":"/shop","label":"Explore the complete organic range","enabled":true},
    {"imageUrl":"/banners/home/catalogue/03-traditional-small-batch.webp","imageAlt":"Traditional small-batch flour and grain processing","href":"/blog/from-farm-to-flour-how-true-grit-products-are-made","label":"See how your food is made","enabled":true},
    {"imageUrl":"/banners/home/catalogue/04-cook-with-true-grit.webp","imageAlt":"A traditional Indian meal prepared with True Grit pantry staples","href":"/recipes","label":"Cook with True Grit","enabled":true}
  ]'),
  '$.blocks[2].props.categorySlugs', json('["wheat-flour","cold-pressed-oils","seeds","black-gram","red-lentils","daliya","semolina","whole-wheat-pasta","whole-wheat-vermicelli","white-field-peas"]'),
  '$.blocks[3].props.productSlugs', json('["kathiya-wheat-flour","banshi-wheat-flour","paigambari-wheat-flour","black-mustard-oil","yellow-mustard-oil","linseed-flax-seed-oil","roasted-flax-seeds","plain-flax-seed","sesame-seed","sesame-oil","roasted-sesame-seeds","black-gram-whole"]'),
  '$.blocks[4].props.farmSlug', 'bagi-farm-i',
  '$.blocks[4].props.quote', 'Traditional food begins with careful farming and clear field-to-pack records.',
  '$.blocks[4].props.attribution', 'Bagi Farm I'
)
WHERE id = 'pgv_home_1';

UPDATE pages SET published_version_id = 'pgv_home_1' WHERE id = 'pag_home';

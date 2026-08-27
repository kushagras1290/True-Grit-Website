-- 0116_organic_catalogue_labels_language_media: organic catalogue aliases,
-- product label images, and owner switches for English-only storefront mode.
--
-- D1-safe: no explicit transaction, no temp tables. Inserts are idempotent.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('i18n.english_only.enabled', '0', '2026-08-20T00:00:00Z'),
  ('email.category.ai_quota.enabled', '1', '2026-08-20T00:00:00Z');

INSERT INTO products (
  id, internal_name, name, slug, product_type, brand_id, farm_id, status,
  short_description, published_version_id, primary_media_id, seo_title,
  seo_description, canonical_url, indexing_policy, created_at, created_by,
  updated_at, updated_by, archived_at, image_url, image_alt, release_scope,
  return_eligible, accepts_orders, payments_override, harvest_note,
  growing_method, storage_guidance
)
SELECT
  replace(p.id, 'prd_catalogue_', 'prd_organic_catalogue_'),
  'Organic ' || p.internal_name,
  'Organic ' || p.name,
  'organic-' || p.slug,
  p.product_type, p.brand_id, p.farm_id, p.status,
  'Organic ' || p.name || ' from Vikas Farms, prepared in small batches using traditional methods and packed for everyday home cooking.',
  replace(p.published_version_id, 'pdv_catalogue_', 'pdv_organic_catalogue_'),
  p.primary_media_id,
  'Organic ' || p.name || ' - Buy Online | True Grit',
  'Organic ' || p.name || ' from Vikas Farms, prepared in small batches using traditional methods and packed for everyday home cooking.',
  p.canonical_url, p.indexing_policy,
  '2026-08-20T00:00:00Z', 'usr_catalogue_system',
  '2026-08-20T00:00:00Z', 'usr_catalogue_system',
  NULL,
  p.image_url,
  COALESCE(p.image_alt, 'Organic ' || p.name || ' product image'),
  p.release_scope, p.return_eligible, p.accepts_orders, p.payments_override,
  p.harvest_note,
  CASE
    WHEN lower(coalesce(p.growing_method, '')) LIKE '%organic%' THEN p.growing_method
    ELSE 'Organic cultivation. ' || coalesce(p.growing_method, '')
  END,
  p.storage_guidance
FROM products p
WHERE p.id LIKE 'prd_catalogue_%'
  AND p.archived_at IS NULL
  AND p.status = 'published'
  AND lower(p.name) NOT LIKE 'organic %'
  AND NOT EXISTS (
    SELECT 1 FROM products existing WHERE existing.slug = 'organic-' || p.slug
  );

INSERT INTO product_versions (
  id, product_id, version_number, content_json, change_summary, workflow_state,
  created_at, created_by, approved_at, approved_by, published_at
)
SELECT
  replace(v.id, 'pdv_catalogue_', 'pdv_organic_catalogue_'),
  replace(v.product_id, 'prd_catalogue_', 'prd_organic_catalogue_'),
  v.version_number,
  replace(v.content_json, p.name, 'Organic ' || p.name),
  'Organic catalogue alias for dual traffic targeting',
  v.workflow_state,
  '2026-08-20T00:00:00Z', 'usr_catalogue_system',
  '2026-08-20T00:00:00Z', 'usr_catalogue_system',
  '2026-08-20T00:00:00Z'
FROM product_versions v
JOIN products p ON p.id = v.product_id
JOIN products organic ON organic.id = replace(v.product_id, 'prd_catalogue_', 'prd_organic_catalogue_')
WHERE v.product_id LIKE 'prd_catalogue_%'
  AND NOT EXISTS (
    SELECT 1 FROM product_versions existing
    WHERE existing.id = replace(v.id, 'pdv_catalogue_', 'pdv_organic_catalogue_')
  );

INSERT OR IGNORE INTO product_categories (product_id, category_id, is_primary, sort_order, assigned_at, assigned_by)
SELECT
  replace(product_id, 'prd_catalogue_', 'prd_organic_catalogue_'),
  category_id, is_primary, sort_order + 100,
  '2026-08-20T00:00:00Z', 'usr_catalogue_system'
FROM product_categories
WHERE product_id LIKE 'prd_catalogue_%';

INSERT OR IGNORE INTO product_tags (product_id, tag_id)
SELECT replace(product_id, 'prd_catalogue_', 'prd_organic_catalogue_'), tag_id
FROM product_tags
WHERE product_id LIKE 'prd_catalogue_%';

INSERT OR IGNORE INTO product_certifications (product_id, certification_id, evidence_media_id, claim_review_state)
SELECT replace(product_id, 'prd_catalogue_', 'prd_organic_catalogue_'), certification_id, evidence_media_id, claim_review_state
FROM product_certifications
WHERE product_id LIKE 'prd_catalogue_%';

INSERT INTO product_variants (
  id, product_id, sku, barcode, name, option_values_json, weight_value,
  weight_unit, package_description, status, sort_order, created_at, updated_at,
  is_default
)
SELECT
  replace(v.id, 'var_catalogue_', 'var_organic_catalogue_'),
  replace(v.product_id, 'prd_catalogue_', 'prd_organic_catalogue_'),
  'ORG-' || v.sku,
  v.barcode,
  v.name,
  v.option_values_json,
  v.weight_value,
  v.weight_unit,
  v.package_description,
  v.status,
  v.sort_order,
  '2026-08-20T00:00:00Z',
  '2026-08-20T00:00:00Z',
  v.is_default
FROM product_variants v
WHERE v.product_id LIKE 'prd_catalogue_%'
  AND NOT EXISTS (
    SELECT 1 FROM product_variants existing
    WHERE existing.id = replace(v.id, 'var_catalogue_', 'var_organic_catalogue_')
  );

INSERT INTO variant_prices (
  id, variant_id, market_code, currency_code, list_amount_minor, sale_amount_minor,
  starts_at, ends_at, tax_inclusive, status, created_at, created_by
)
SELECT
  replace(vp.id, 'vpr_catalogue_', 'vpr_organic_catalogue_'),
  replace(vp.variant_id, 'var_catalogue_', 'var_organic_catalogue_'),
  vp.market_code, vp.currency_code, vp.list_amount_minor, vp.sale_amount_minor,
  '2026-08-20T00:00:00Z', vp.ends_at, vp.tax_inclusive, vp.status,
  '2026-08-20T00:00:00Z', 'usr_catalogue_system'
FROM variant_prices vp
WHERE vp.variant_id LIKE 'var_catalogue_%'
  AND NOT EXISTS (
    SELECT 1 FROM variant_prices existing
    WHERE existing.id = replace(vp.id, 'vpr_catalogue_', 'vpr_organic_catalogue_')
  );

INSERT OR IGNORE INTO inventory_levels (variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at)
SELECT
  replace(variant_id, 'var_catalogue_', 'var_organic_catalogue_'),
  location_id, on_hand, reserved, reorder_threshold, version,
  '2026-08-20T00:00:00Z'
FROM inventory_levels
WHERE variant_id LIKE 'var_catalogue_%';

INSERT INTO search_products (product_id, name, slug, brand_name, farm_name, category_names, keywords, short_description)
SELECT
  replace(sp.product_id, 'prd_catalogue_', 'prd_organic_catalogue_'),
  'Organic ' || sp.name,
  'organic-' || sp.slug,
  sp.brand_name,
  sp.farm_name,
  sp.category_names,
  trim('organic ' || coalesce(sp.keywords, '')),
  'Organic ' || sp.short_description
FROM search_products sp
WHERE sp.product_id LIKE 'prd_catalogue_%'
  AND NOT EXISTS (
    SELECT 1 FROM search_products existing
    WHERE existing.product_id = replace(sp.product_id, 'prd_catalogue_', 'prd_organic_catalogue_')
  );

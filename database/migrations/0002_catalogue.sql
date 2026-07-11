-- 0002_catalogue: media, brands, farms, certifications, categories, products, variants, prices
PRAGMA foreign_keys = ON;

CREATE TABLE media_assets (
  id TEXT PRIMARY KEY,
  object_key TEXT NOT NULL UNIQUE,
  original_filename TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
  width_px INTEGER,
  height_px INTEGER,
  alt_text TEXT,
  caption TEXT,
  focal_x REAL,
  focal_y REAL,
  visibility TEXT NOT NULL CHECK (visibility IN ('private', 'public')),
  processing_status TEXT NOT NULL CHECK (
    processing_status IN ('pending', 'ready', 'failed', 'quarantined')
  ),
  checksum_sha256 TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  archived_at TEXT,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_media_assets_status
  ON media_assets(processing_status, created_at DESC);

CREATE TABLE brands (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  description_json TEXT,
  logo_media_id TEXT,
  status TEXT NOT NULL CHECK (status IN ('draft', 'published', 'archived')),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (logo_media_id) REFERENCES media_assets(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE farms (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  farmer_name TEXT,
  region TEXT,
  country_code TEXT NOT NULL DEFAULT 'IN',
  latitude REAL,
  longitude REAL,
  established_year INTEGER,
  story_json TEXT,
  methods_json TEXT,
  seasonal_calendar_json TEXT,
  hero_media_id TEXT,
  status TEXT NOT NULL CHECK (
    status IN ('draft', 'in_review', 'published', 'unpublished', 'archived')
  ),
  seo_title TEXT,
  seo_description TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (hero_media_id) REFERENCES media_assets(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE certifications (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  issuing_body TEXT,
  slug TEXT NOT NULL UNIQUE,
  description_json TEXT,
  logo_media_id TEXT,
  verification_url_template TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (logo_media_id) REFERENCES media_assets(id) ON DELETE SET NULL
);

CREATE TABLE farm_certifications (
  id TEXT PRIMARY KEY,
  farm_id TEXT NOT NULL,
  certification_id TEXT NOT NULL,
  certificate_reference TEXT,
  valid_from TEXT,
  valid_until TEXT,
  evidence_media_id TEXT,
  verification_status TEXT NOT NULL CHECK (
    verification_status IN ('unverified', 'verified', 'expired', 'rejected')
  ),
  verified_at TEXT,
  verified_by TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(farm_id, certification_id, certificate_reference),
  FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
  FOREIGN KEY (certification_id) REFERENCES certifications(id) ON DELETE RESTRICT,
  FOREIGN KEY (evidence_media_id) REFERENCES media_assets(id) ON DELETE SET NULL,
  FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE categories (
  id TEXT PRIMARY KEY,
  internal_name TEXT NOT NULL,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  parent_id TEXT,
  path TEXT NOT NULL UNIQUE,
  level INTEGER NOT NULL DEFAULT 0 CHECK (level >= 0),
  sort_order INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL CHECK (
    status IN ('draft', 'in_review', 'approved', 'scheduled', 'published', 'unpublished', 'archived')
  ),
  visibility TEXT NOT NULL DEFAULT 'public' CHECK (
    visibility IN ('public', 'hidden', 'private')
  ),
  short_description TEXT,
  long_description_json TEXT,
  hero_eyebrow TEXT,
  hero_title TEXT,
  hero_description TEXT,
  hero_media_id TEXT,
  mobile_hero_media_id TEXT,
  theme_key TEXT,
  season_label TEXT,
  product_assignment_mode TEXT NOT NULL DEFAULT 'dynamic' CHECK (
    product_assignment_mode IN ('manual', 'dynamic', 'hybrid')
  ),
  product_rule_json TEXT,
  published_version_id TEXT,
  seo_title TEXT,
  seo_description TEXT,
  social_media_id TEXT,
  canonical_url TEXT,
  indexing_policy TEXT NOT NULL DEFAULT 'index' CHECK (
    indexing_policy IN ('index', 'noindex')
  ),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  archived_at TEXT,
  FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE RESTRICT,
  FOREIGN KEY (hero_media_id) REFERENCES media_assets(id) ON DELETE SET NULL,
  FOREIGN KEY (mobile_hero_media_id) REFERENCES media_assets(id) ON DELETE SET NULL,
  FOREIGN KEY (social_media_id) REFERENCES media_assets(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_categories_parent_sort
  ON categories(parent_id, sort_order, name);

CREATE INDEX idx_categories_public
  ON categories(status, visibility, path);

CREATE TABLE category_versions (
  id TEXT PRIMARY KEY,
  category_id TEXT NOT NULL,
  version_number INTEGER NOT NULL CHECK (version_number > 0),
  content_json TEXT NOT NULL,
  change_summary TEXT,
  workflow_state TEXT NOT NULL CHECK (
    workflow_state IN ('draft', 'in_review', 'changes_requested', 'approved', 'scheduled', 'published')
  ),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  approved_at TEXT,
  approved_by TEXT,
  published_at TEXT,
  UNIQUE(category_id, version_number),
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE products (
  id TEXT PRIMARY KEY,
  internal_name TEXT NOT NULL,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  product_type TEXT NOT NULL,
  brand_id TEXT,
  farm_id TEXT,
  status TEXT NOT NULL CHECK (
    status IN ('draft', 'in_review', 'approved', 'scheduled', 'published', 'unpublished', 'discontinued', 'archived')
  ),
  short_description TEXT,
  published_version_id TEXT,
  primary_media_id TEXT,
  seo_title TEXT,
  seo_description TEXT,
  canonical_url TEXT,
  indexing_policy TEXT NOT NULL DEFAULT 'index' CHECK (
    indexing_policy IN ('index', 'noindex')
  ),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  archived_at TEXT,
  FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
  FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE SET NULL,
  FOREIGN KEY (primary_media_id) REFERENCES media_assets(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_products_public
  ON products(status, updated_at DESC);

CREATE INDEX idx_products_farm
  ON products(farm_id, status);

CREATE TABLE product_versions (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL,
  version_number INTEGER NOT NULL CHECK (version_number > 0),
  content_json TEXT NOT NULL,
  change_summary TEXT,
  workflow_state TEXT NOT NULL CHECK (
    workflow_state IN ('draft', 'in_review', 'changes_requested', 'approved', 'scheduled', 'published')
  ),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  approved_at TEXT,
  approved_by TEXT,
  published_at TEXT,
  UNIQUE(product_id, version_number),
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE product_variants (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL,
  sku TEXT NOT NULL UNIQUE,
  barcode TEXT,
  name TEXT NOT NULL,
  option_values_json TEXT NOT NULL DEFAULT '{}',
  weight_value INTEGER,
  weight_unit TEXT CHECK (weight_unit IN ('g', 'kg', 'ml', 'l', 'unit')),
  package_description TEXT,
  status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'discontinued')),
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE INDEX idx_variants_product
  ON product_variants(product_id, status, sort_order);

CREATE TABLE product_categories (
  product_id TEXT NOT NULL,
  category_id TEXT NOT NULL,
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
  sort_order INTEGER NOT NULL DEFAULT 0,
  assigned_at TEXT NOT NULL,
  assigned_by TEXT NOT NULL,
  PRIMARY KEY (product_id, category_id),
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
  FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_product_categories_category
  ON product_categories(category_id, sort_order, product_id);

CREATE TABLE tags (
  id TEXT PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  tag_group TEXT NOT NULL CHECK (tag_group IN ('diet', 'intention', 'attribute', 'general')),
  created_at TEXT NOT NULL
);

CREATE TABLE product_tags (
  product_id TEXT NOT NULL,
  tag_id TEXT NOT NULL,
  PRIMARY KEY (product_id, tag_id),
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE product_certifications (
  product_id TEXT NOT NULL,
  certification_id TEXT NOT NULL,
  evidence_media_id TEXT,
  claim_review_state TEXT NOT NULL DEFAULT 'pending' CHECK (
    claim_review_state IN ('pending', 'approved', 'rejected')
  ),
  PRIMARY KEY (product_id, certification_id),
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (certification_id) REFERENCES certifications(id) ON DELETE RESTRICT,
  FOREIGN KEY (evidence_media_id) REFERENCES media_assets(id) ON DELETE SET NULL
);

CREATE TABLE product_media (
  product_id TEXT NOT NULL,
  media_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('primary', 'gallery', 'nutrition', 'certification', 'video_poster')),
  sort_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (product_id, media_id, role),
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (media_id) REFERENCES media_assets(id) ON DELETE RESTRICT
);

CREATE TABLE variant_prices (
  id TEXT PRIMARY KEY,
  variant_id TEXT NOT NULL,
  market_code TEXT NOT NULL DEFAULT 'IN',
  currency_code TEXT NOT NULL DEFAULT 'INR',
  list_amount_minor INTEGER NOT NULL CHECK (list_amount_minor >= 0),
  sale_amount_minor INTEGER CHECK (sale_amount_minor IS NULL OR sale_amount_minor >= 0),
  starts_at TEXT,
  ends_at TEXT,
  tax_inclusive INTEGER NOT NULL DEFAULT 1 CHECK (tax_inclusive IN (0, 1)),
  status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'inactive')),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  CHECK (sale_amount_minor IS NULL OR sale_amount_minor <= list_amount_minor),
  CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at),
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_variant_prices_resolution
  ON variant_prices(variant_id, market_code, currency_code, status, starts_at, ends_at);

CREATE TABLE collections (
  id TEXT PRIMARY KEY,
  internal_name TEXT NOT NULL,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (
    status IN ('draft', 'in_review', 'approved', 'scheduled', 'published', 'unpublished', 'archived')
  ),
  published_version_id TEXT,
  seo_title TEXT,
  seo_description TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE collection_versions (
  id TEXT PRIMARY KEY,
  collection_id TEXT NOT NULL,
  version_number INTEGER NOT NULL CHECK (version_number > 0),
  content_json TEXT NOT NULL,
  workflow_state TEXT NOT NULL CHECK (
    workflow_state IN ('draft', 'in_review', 'changes_requested', 'approved', 'scheduled', 'published')
  ),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  UNIQUE(collection_id, version_number),
  FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE collection_products (
  collection_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
  excluded INTEGER NOT NULL DEFAULT 0 CHECK (excluded IN (0, 1)),
  sort_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (collection_id, product_id),
  FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

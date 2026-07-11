-- 0003_cms: pages, articles, recipes, navigation, redirects, announcements
PRAGMA foreign_keys = ON;

CREATE TABLE pages (
  id TEXT PRIMARY KEY,
  page_type TEXT NOT NULL,
  internal_name TEXT NOT NULL,
  title TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  parent_id TEXT,
  template_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK (
    status IN ('draft', 'in_review', 'approved', 'scheduled', 'published', 'unpublished', 'archived')
  ),
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
  FOREIGN KEY (parent_id) REFERENCES pages(id) ON DELETE RESTRICT,
  FOREIGN KEY (social_media_id) REFERENCES media_assets(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE page_versions (
  id TEXT PRIMARY KEY,
  page_id TEXT NOT NULL,
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
  UNIQUE(page_id, version_number),
  FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE articles (
  id TEXT PRIMARY KEY,
  internal_name TEXT NOT NULL,
  title TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  excerpt TEXT,
  author_user_id TEXT,
  hero_media_id TEXT,
  reading_minutes INTEGER CHECK (reading_minutes IS NULL OR reading_minutes > 0),
  status TEXT NOT NULL CHECK (
    status IN ('draft', 'in_review', 'approved', 'scheduled', 'published', 'unpublished', 'archived')
  ),
  published_version_id TEXT,
  published_at TEXT,
  seo_title TEXT,
  seo_description TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (author_user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (hero_media_id) REFERENCES media_assets(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE article_versions (
  id TEXT PRIMARY KEY,
  article_id TEXT NOT NULL,
  version_number INTEGER NOT NULL CHECK (version_number > 0),
  content_json TEXT NOT NULL,
  workflow_state TEXT NOT NULL CHECK (
    workflow_state IN ('draft', 'in_review', 'changes_requested', 'approved', 'scheduled', 'published')
  ),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  UNIQUE(article_id, version_number),
  FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE recipes (
  id TEXT PRIMARY KEY,
  internal_name TEXT NOT NULL,
  title TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  excerpt TEXT,
  hero_media_id TEXT,
  prep_minutes INTEGER CHECK (prep_minutes IS NULL OR prep_minutes >= 0),
  cook_minutes INTEGER CHECK (cook_minutes IS NULL OR cook_minutes >= 0),
  servings INTEGER CHECK (servings IS NULL OR servings > 0),
  dietary_tags_json TEXT,
  status TEXT NOT NULL CHECK (
    status IN ('draft', 'in_review', 'approved', 'scheduled', 'published', 'unpublished', 'archived')
  ),
  published_version_id TEXT,
  published_at TEXT,
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

CREATE TABLE recipe_versions (
  id TEXT PRIMARY KEY,
  recipe_id TEXT NOT NULL,
  version_number INTEGER NOT NULL CHECK (version_number > 0),
  content_json TEXT NOT NULL,
  workflow_state TEXT NOT NULL CHECK (
    workflow_state IN ('draft', 'in_review', 'changes_requested', 'approved', 'scheduled', 'published')
  ),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  UNIQUE(recipe_id, version_number),
  FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE recipe_ingredients (
  id TEXT PRIMARY KEY,
  recipe_id TEXT NOT NULL,
  label TEXT NOT NULL,
  quantity_text TEXT,
  product_id TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE INDEX idx_recipe_ingredients_recipe
  ON recipe_ingredients(recipe_id, sort_order);

CREATE TABLE navigation_menus (
  id TEXT PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE navigation_items (
  id TEXT PRIMARY KEY,
  menu_id TEXT NOT NULL,
  parent_id TEXT,
  label TEXT NOT NULL,
  destination_type TEXT NOT NULL CHECK (
    destination_type IN ('category', 'collection', 'page', 'article', 'recipe', 'farm', 'external', 'internal_path')
  ),
  destination_reference TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  visible INTEGER NOT NULL DEFAULT 1 CHECK (visible IN (0, 1)),
  FOREIGN KEY (menu_id) REFERENCES navigation_menus(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_id) REFERENCES navigation_items(id) ON DELETE CASCADE
);

CREATE INDEX idx_navigation_items_menu
  ON navigation_items(menu_id, parent_id, sort_order);

CREATE TABLE redirects (
  id TEXT PRIMARY KEY,
  source_path TEXT NOT NULL UNIQUE,
  destination_path TEXT NOT NULL,
  status_code INTEGER NOT NULL CHECK (status_code IN (301, 302, 307, 308)),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  CHECK (source_path <> destination_path)
);

CREATE TABLE announcements (
  id TEXT PRIMARY KEY,
  message TEXT NOT NULL,
  destination_path TEXT,
  starts_at TEXT,
  ends_at TEXT,
  active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at)
);

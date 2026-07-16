-- 0017_geo_release_links_highlights: per-country product release, owner-curated
-- product links (product page slots) and site-wide highlighted products (search
-- page slots).
PRAGMA foreign_keys = ON;

-- Where a product may be sold/shown. 'global' (default) keeps today's
-- behaviour; 'selected' limits the product to the countries listed in
-- product_release_countries.
ALTER TABLE products ADD COLUMN release_scope TEXT NOT NULL DEFAULT 'global'
  CHECK (release_scope IN ('global', 'selected'));

CREATE TABLE product_release_countries (
  product_id TEXT NOT NULL,
  country_code TEXT NOT NULL CHECK (length(country_code) = 2),
  added_at TEXT NOT NULL,
  added_by TEXT NOT NULL,
  PRIMARY KEY (product_id, country_code),
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_product_release_countries_country
  ON product_release_countries(country_code, product_id);

-- Owner-curated "goes well with" links shown on the product page. Fully
-- manual: the owner adds, removes and reorders (swaps) them in the admin.
CREATE TABLE product_links (
  product_id TEXT NOT NULL,
  linked_product_id TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  PRIMARY KEY (product_id, linked_product_id),
  CHECK (product_id <> linked_product_id),
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (linked_product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_product_links_product
  ON product_links(product_id, sort_order);

-- Site-wide highlighted products box (search page). One curated, ordered list
-- managed from Site Control; products can be swapped in and out at any time.
CREATE TABLE highlighted_products (
  product_id TEXT PRIMARY KEY,
  sort_order INTEGER NOT NULL DEFAULT 0,
  added_at TEXT NOT NULL,
  added_by TEXT NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_highlighted_products_order
  ON highlighted_products(sort_order, product_id);

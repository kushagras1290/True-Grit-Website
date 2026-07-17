-- 0026_category_geo_release: per-country release scoping for categories,
-- mirroring the product release model from 0017_geo_release_links_highlights
-- exactly, so a category page can be limited to selected countries the same
-- way a product can.
PRAGMA foreign_keys = ON;

ALTER TABLE categories ADD COLUMN release_scope TEXT NOT NULL DEFAULT 'global'
  CHECK (release_scope IN ('global', 'selected'));

CREATE TABLE category_release_countries (
  category_id TEXT NOT NULL,
  country_code TEXT NOT NULL CHECK (length(country_code) = 2),
  added_at TEXT NOT NULL,
  added_by TEXT NOT NULL,
  PRIMARY KEY (category_id, country_code),
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
  FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_category_release_countries_country
  ON category_release_countries(country_code, category_id);

-- 0006_search_fts: D1 FTS5 search indexes and synonyms
PRAGMA foreign_keys = ON;

CREATE VIRTUAL TABLE search_products USING fts5(
  product_id UNINDEXED,
  name,
  slug UNINDEXED,
  brand_name,
  farm_name,
  category_names,
  keywords,
  short_description,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE search_content USING fts5(
  entity_type UNINDEXED,
  entity_id UNINDEXED,
  title,
  slug UNINDEXED,
  excerpt,
  keywords,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE search_synonyms (
  id TEXT PRIMARY KEY,
  term TEXT NOT NULL COLLATE NOCASE,
  synonym TEXT NOT NULL COLLATE NOCASE,
  created_at TEXT NOT NULL,
  UNIQUE(term, synonym)
);

CREATE TABLE search_queries (
  id TEXT PRIMARY KEY,
  normalized_query TEXT NOT NULL,
  result_count INTEGER NOT NULL CHECK (result_count >= 0),
  searched_at TEXT NOT NULL
);

CREATE INDEX idx_search_queries_time
  ON search_queries(searched_at DESC);

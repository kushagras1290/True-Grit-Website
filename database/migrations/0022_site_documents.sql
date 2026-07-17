-- 0022_site_documents: owner-managed sitemap, robots.txt and llms.txt
PRAGMA foreign_keys = ON;

CREATE TABLE site_documents (
  key TEXT PRIMARY KEY CHECK (key IN ('robots_txt', 'sitemap_xml', 'llms_txt')),
  content TEXT NOT NULL,
  content_type TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT
);

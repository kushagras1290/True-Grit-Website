-- 0091_translation_hub: runtime-editable language registry and fine-grained
-- translations for every customer-facing string.
--
-- `translation_entries` deliberately stores one string per row. Editorial
-- documents (article blocks, recipe steps, discussion comments) change shape
-- over time; stable field paths let the translation console report stale or
-- missing strings without replacing a whole translated document blindly.
-- `source_hash` is refreshed whenever an operator opens/translates an item and
-- makes source edits visible as stale work instead of silently presenting an
-- old translation as current.
--
-- `supported_locales` contains runtime additions only. The 100 shipped locales
-- remain in @truegrit/i18n and are merged with these rows by the storefront.
-- This keeps the migration compact and preserves the existing catalogue while
-- allowing a new BCP-47 language to go live without a code deployment.
PRAGMA foreign_keys = ON;

CREATE TABLE supported_locales (
  code TEXT PRIMARY KEY COLLATE NOCASE,
  native_name TEXT NOT NULL,
  english_name TEXT NOT NULL,
  direction TEXT NOT NULL DEFAULT 'ltr' CHECK (direction IN ('ltr', 'rtl')),
  group_name TEXT NOT NULL DEFAULT 'world' CHECK (group_name IN ('indian', 'world')),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE translation_entries (
  resource_type TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  field_key TEXT NOT NULL,
  locale TEXT NOT NULL COLLATE NOCASE,
  source_text TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  translated_text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'machine' CHECK (status IN ('machine', 'reviewed')),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  PRIMARY KEY (resource_type, resource_id, field_key, locale),
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_translation_entries_locale_resource
  ON translation_entries(locale, resource_type, resource_id);

CREATE INDEX idx_translation_entries_resource
  ON translation_entries(resource_type, resource_id, locale);

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_translations_manage', 'translations.manage',
   'Manage languages and all customer-facing translations');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, 'prm_translations_manage'
FROM roles r
WHERE r.key IN ('admin', 'super_admin');

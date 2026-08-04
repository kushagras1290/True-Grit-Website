-- 0072_bundle_entity_translations: allow 'bundle' in entity_translations.
--
-- Migration 0068 pinned entity_type to the six types that existed when the
-- registry was written. Bundles carry a customer-facing name and description
-- and are rendered on /bundles and /bundles/:slug, so they belong in the same
-- per-locale override table as every other database-sourced string. SQLite
-- cannot widen a CHECK constraint in place, so the table is rebuilt --
-- the standard twelve-step ALTER recipe, minus the steps that do not apply
-- (no triggers, no views on this table).
--
-- Rows are preserved: the new constraint is a superset of the old one, so
-- every existing row satisfies it.

PRAGMA foreign_keys = OFF;

CREATE TABLE entity_translations_new (
  entity_type TEXT NOT NULL CHECK (
    entity_type IN (
      'navigation_item', 'category', 'farm', 'product', 'article', 'recipe', 'bundle'
    )
  ),
  entity_id TEXT NOT NULL,
  locale TEXT NOT NULL,
  fields_json TEXT NOT NULL,
  auto_translated INTEGER NOT NULL DEFAULT 0 CHECK (auto_translated IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  PRIMARY KEY (entity_type, entity_id, locale),
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

INSERT INTO entity_translations_new (
  entity_type, entity_id, locale, fields_json, auto_translated, updated_at, updated_by
)
SELECT entity_type, entity_id, locale, fields_json, auto_translated, updated_at, updated_by
FROM entity_translations;

DROP TABLE entity_translations;

ALTER TABLE entity_translations_new RENAME TO entity_translations;

CREATE INDEX idx_entity_translations_entity
  ON entity_translations(entity_type, entity_id);

PRAGMA foreign_keys = ON;

-- 0068_entity_translations: per-locale field overrides for database-sourced
-- content that migration 0067 does not cover -- navigation labels, category
-- names/descriptions, and (as the same pattern extends) farms, products,
-- articles and recipes.
--
-- WHY ONE GENERIC TABLE, NOT ONE PER ENTITY TYPE
-- Migration 0067 gave pages their own table because a page's content is one
-- big block tree that needs the SAME schema validation in every locale.
-- Navigation items, categories, farms, products, articles and recipes are
-- the opposite shape: a handful of independent flat string fields (a label,
-- a name, a short description) with no shared structure to validate against.
-- One (entity_type, entity_id, locale) row holding a small JSON object of
-- "field name -> translated value" covers all of them without a migration
-- per content type -- exactly how `audit_logs` already keys itself by
-- (entity_type, entity_id) rather than a table per entity (migration 0001).
--
-- WHY fields_json IS A LOOSE BLOB, NOT A FOREIGN KEY PER FIELD
-- Which fields are translatable is a decision that lives in application code
-- (`services.entity_translation.TRANSLATABLE_FIELDS`) and can grow --
-- widening it never needs a migration, only a code change, the same
-- trade-off migration 0067 already made for `content_json`.
--
-- WHY NO FOREIGN KEY ON (entity_type, entity_id)
-- entity_id points at a different table depending on entity_type (there is
-- no single table it could reference), the same constraint `audit_logs`
-- already accepts for its own polymorphic entity_id.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entity_translations (
  entity_type TEXT NOT NULL CHECK (
    entity_type IN ('navigation_item', 'category', 'farm', 'product', 'article', 'recipe')
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

CREATE INDEX idx_entity_translations_entity
  ON entity_translations(entity_type, entity_id);

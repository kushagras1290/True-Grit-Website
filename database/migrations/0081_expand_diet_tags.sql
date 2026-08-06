-- 0081_expand_diet_tags: round out the 'diet' tag_group (migration 0002
-- only ever seeded plant-based/gluten-free) so the storefront dietary
-- filter (Feature 3) has real vocabulary to filter by.
--
-- No allergen-specific schema exists anywhere in this codebase, and
-- building a second parallel system for allergen avoidance would be
-- over-engineering for what customers actually need here -- Dairy-Free
-- and Nut-Free are modeled as ordinary diet tags, same table, same UI.
--
-- Product assignments deliberately live in database/seeds/development.sql,
-- not here: migrations run before the seed file (SQLiteDatabase.from_
-- migrations), so a product_tags row referencing a seed-only product id
-- would violate its foreign key at migration time.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO tags (id, key, label, tag_group, created_at) VALUES
  ('tag_vegan', 'vegan', 'Vegan', 'diet', '2026-08-06T00:00:00Z'),
  ('tag_vegetarian', 'vegetarian', 'Vegetarian', 'diet', '2026-08-06T00:00:00Z'),
  ('tag_dairy_free', 'dairy-free', 'Dairy Free', 'diet', '2026-08-06T00:00:00Z'),
  ('tag_nut_free', 'nut-free', 'Nut Free', 'diet', '2026-08-06T00:00:00Z');

-- 0051_homepage_hero_slide_limit: make the banner carousel's slide cap an
-- admin setting instead of a number baked into the code.
--
-- WHY
-- The cap moved once already (eight to twelve, migration 0047's branded
-- library) and each move cost a deploy across three layers -- the block model,
-- the admin request schema and the console's own form -- with a live 422 in
-- between whenever one lagged. Growing the carousel is an editorial decision,
-- so it belongs in `app_settings` next to the other things Site Control edits.
--
-- TWO LIMITS, ON PURPOSE
-- This row is the number an operator works to. `HERO_SLIDES_HARD_LIMIT` in
-- `domain/blocks.py` is a separate structural ceiling that the block model
-- enforces whatever this row says, so a typo here can widen the carousel but
-- can never let a request store hundreds of slides in one block. Homepage
-- Settings shows both, and `services.feature_settings.clamp_hero_max_slides`
-- resolves a missing, non-numeric or out-of-range row to the shipped default
-- rather than raising -- the value is read on the very page you would need in
-- order to fix it.
--
-- 12 matches what migration 0047 actually seeds. A cap below the shipped
-- library would make the homepage unsaveable: the console loads twelve slides,
-- sends them back untouched, and gets a 422 for content it never edited.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, and the insert is idempotent.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('homepage.hero.max_slides', '12', '2026-08-01T00:00:00Z');

-- 0114_seo_schedule: make the SEO agent's auto-crawl cadence a dashboard
-- setting instead of a fixed daily cron.
--
-- The Worker's `0 3 * * *` cron trigger itself still fires daily (changing
-- a Cloudflare Cron Trigger needs a deploy, so that stays fixed) -- what
-- changes is the decision it makes when it fires. It now checks
-- `seo.schedule_days` against the last cron-queued run's timestamp before
-- actually queuing one, so "every 3 days" or "weekly" is a setting, not a
-- redeploy. `0` means manual-only: the daily tick checks in but never queues
-- anything on its own, matching the "Run crawl" button being the only way
-- to start one.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('seo.schedule_days', '1', '2026-08-19T00:00:00Z');

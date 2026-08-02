-- 0061_farm_banner_images: hero banner image for individual farm pages, same
-- URL + alt-text pattern as categories (0011) and articles/recipes (0036).
-- The admin editor uploads through /v1/admin/media/images and stores the
-- returned URL. The storefront renders the banner on /farms/{slug}, matching
-- the homepage/category/blog banner treatment. hero_media_id (0002) remains
-- for media-library delete protection. D1-safe: plain ADD COLUMN only.

ALTER TABLE farms ADD COLUMN hero_image_url TEXT;
ALTER TABLE farms ADD COLUMN hero_image_alt TEXT;

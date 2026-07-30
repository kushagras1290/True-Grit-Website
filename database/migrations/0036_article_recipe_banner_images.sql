-- 0036_article_recipe_banner_images: banner image for blog posts and recipes.
--
-- Articles and recipes gain the same URL + alt-text pattern categories use
-- (0011): the admin editor uploads through /v1/admin/media/images and stores
-- the returned URL. The storefront renders the banner on /blog/{slug} and
-- /recipes/{slug} and as listing thumbnails. hero_media_id (0003) remains for
-- media-library delete protection. D1-safe: plain ADD COLUMN only.

ALTER TABLE articles ADD COLUMN hero_image_url TEXT;
ALTER TABLE articles ADD COLUMN hero_image_alt TEXT;
ALTER TABLE recipes ADD COLUMN hero_image_url TEXT;
ALTER TABLE recipes ADD COLUMN hero_image_alt TEXT;

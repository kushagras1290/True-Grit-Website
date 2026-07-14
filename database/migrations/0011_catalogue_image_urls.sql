-- 0011_catalogue_image_urls: simple externally hosted customer-facing images.
-- Object-storage uploads can still use media_assets; these fields let admins
-- paste a CDN/image URL immediately in local and lightweight deployments.

ALTER TABLE products ADD COLUMN image_url TEXT;
ALTER TABLE products ADD COLUMN image_alt TEXT;

ALTER TABLE categories ADD COLUMN hero_image_url TEXT;
ALTER TABLE categories ADD COLUMN hero_image_alt TEXT;

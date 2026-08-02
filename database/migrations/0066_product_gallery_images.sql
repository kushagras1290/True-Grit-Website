-- 0066_product_gallery_images: additional photos for a product, beyond its
-- one required `primary_media_id`/`image_url` (the thumbnail used everywhere
-- a listing shows one image -- shop grid, bundles, recommendations, search).
--
-- WHY A SEPARATE TABLE, NOT A SECOND FK ON `products`
-- The main image is a single required field every listing query already
-- joins on; a gallery is optional, ordered, and unbounded in principle
-- (capped in `services.catalogue` for sanity). Modelling it as a one-to-many
-- table means every existing single-image query keeps working completely
-- unchanged -- this is purely additive, read only by the product detail page.
--
-- WHY PLAIN `image_url`/`image_alt` COLUMNS, NOT A `media_assets` FK
-- Mirrors `bundles.image_url`/`image_alt` (migration 0062) rather than
-- `products.primary_media_id`'s FK-and-resolve dance (see the WHY note in
-- `services.catalogue.update_product`) -- a plain URL is enough for a
-- gallery photo and reuses the exact same upload endpoint the main image
-- already does, no second resolution step needed.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS product_images (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL,
  image_url TEXT NOT NULL,
  image_alt TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_product_images_product
  ON product_images(product_id, sort_order);

-- 0039_default_content_images: ensure every blog post, recipe and discussion
-- has a customer-facing image while preserving custom admin-uploaded images.

ALTER TABLE discussions ADD COLUMN image_url TEXT
  DEFAULT '/content/default-discussion.webp';
ALTER TABLE discussions ADD COLUMN image_alt TEXT
  DEFAULT 'True Grit community table';

UPDATE articles
SET hero_image_url = '/content/default-blog.webp',
    hero_image_alt = COALESCE(
      NULLIF(TRIM(hero_image_alt), ''),
      'True Grit organic living journal'
    )
WHERE NULLIF(TRIM(hero_image_url), '') IS NULL;

UPDATE recipes
SET hero_image_url = '/content/default-recipe.webp',
    hero_image_alt = COALESCE(
      NULLIF(TRIM(hero_image_alt), ''),
      'Wholesome organic home-cooked meal'
    )
WHERE NULLIF(TRIM(hero_image_url), '') IS NULL;

UPDATE discussions
SET image_url = '/content/default-discussion.webp',
    image_alt = COALESCE(
      NULLIF(TRIM(image_alt), ''),
      'True Grit community table'
    )
WHERE NULLIF(TRIM(image_url), '') IS NULL;

CREATE TRIGGER articles_default_image_after_insert
AFTER INSERT ON articles
WHEN NULLIF(TRIM(NEW.hero_image_url), '') IS NULL
BEGIN
  UPDATE articles
  SET hero_image_url = '/content/default-blog.webp',
      hero_image_alt = COALESCE(
        NULLIF(TRIM(NEW.hero_image_alt), ''),
        'True Grit organic living journal'
      )
  WHERE id = NEW.id;
END;

CREATE TRIGGER recipes_default_image_after_insert
AFTER INSERT ON recipes
WHEN NULLIF(TRIM(NEW.hero_image_url), '') IS NULL
BEGIN
  UPDATE recipes
  SET hero_image_url = '/content/default-recipe.webp',
      hero_image_alt = COALESCE(
        NULLIF(TRIM(NEW.hero_image_alt), ''),
        'Wholesome organic home-cooked meal'
      )
  WHERE id = NEW.id;
END;

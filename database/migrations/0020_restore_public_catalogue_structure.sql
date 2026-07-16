-- 0020_restore_public_catalogue_structure: repair the core storefront catalogue.
--
-- The live dev catalogue had several seed categories/products archived, which
-- left navigation/category links broken and product grids visually hollow.
-- Keep this D1-safe: no BEGIN TRANSACTION or SAVEPOINT.

UPDATE categories
SET status = 'published',
    visibility = 'public',
    archived_at = NULL,
    hero_image_url = CASE id
      WHEN 'cat_fresh_fruits' THEN '/homepage-hero.png'
      WHEN 'cat_vegetables' THEN '/homepage-hero-greens.png'
      WHEN 'cat_grains' THEN '/homepage-hero-roots.png'
      WHEN 'cat_oils' THEN '/homepage-hero-citrus.png'
      ELSE hero_image_url
    END,
    hero_image_alt = CASE id
      WHEN 'cat_fresh_fruits' THEN 'Organic mangoes held in a sunlit orchard'
      WHEN 'cat_vegetables' THEN 'Fresh leafy greens and herbs held in a farm field'
      WHEN 'cat_grains' THEN 'Fresh roots and pulses from organic soil'
      WHEN 'cat_oils' THEN 'Seasonal fruit in an organic orchard'
      ELSE hero_image_alt
    END,
    updated_at = '2026-07-17T00:00:00Z'
WHERE id IN ('cat_fresh_fruits', 'cat_vegetables', 'cat_grains', 'cat_oils');

UPDATE products
SET status = 'published',
    archived_at = NULL,
    release_scope = 'global',
    image_url = COALESCE(
      image_url,
      CASE id
        WHEN 'prd_alphonso' THEN '/homepage-hero.png'
        WHEN 'prd_spinach' THEN '/homepage-hero-greens.png'
        WHEN 'prd_ragi' THEN '/homepage-hero-roots.png'
        WHEN 'prd_groundnut_oil' THEN '/homepage-hero-citrus.png'
        WHEN 'prd_rajma' THEN '/homepage-hero-roots.png'
        ELSE image_url
      END
    ),
    image_alt = COALESCE(
      image_alt,
      CASE id
        WHEN 'prd_alphonso' THEN 'Organic mangoes held in a sunlit orchard'
        WHEN 'prd_spinach' THEN 'Fresh leafy greens and herbs held in a farm field'
        WHEN 'prd_ragi' THEN 'Fresh roots and pulses from organic soil'
        WHEN 'prd_groundnut_oil' THEN 'Seasonal fruit in an organic orchard'
        WHEN 'prd_rajma' THEN 'Himalayan Red Rajma'
        ELSE image_alt
      END
    ),
    updated_at = '2026-07-17T00:00:00Z'
WHERE id IN ('prd_alphonso', 'prd_spinach', 'prd_ragi', 'prd_groundnut_oil', 'prd_rajma');

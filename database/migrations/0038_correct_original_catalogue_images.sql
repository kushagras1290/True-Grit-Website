-- 0038_correct_original_catalogue_images: replace the original catalogue's
-- generic homepage placeholders with correctly matched catalogue photography.

UPDATE categories
SET hero_image_url = CASE id
      WHEN 'cat_fresh_fruits' THEN '/media/catalogue/generated/fruits.webp'
      WHEN 'cat_vegetables' THEN '/media/catalogue/generated/vegetables.webp'
      WHEN 'cat_grains' THEN '/media/catalogue/generated/staple-grains.webp'
      WHEN 'cat_oils' THEN '/media/catalogue/generated/oils-cooking-fats.webp'
    END,
    hero_image_alt = CASE id
      WHEN 'cat_fresh_fruits' THEN 'Fresh organic fruit market selection'
      WHEN 'cat_vegetables' THEN 'Fresh organic vegetable market selection'
      WHEN 'cat_grains' THEN 'Organic grains and millets market selection'
      WHEN 'cat_oils' THEN 'Cold-pressed organic cooking oils'
    END,
    updated_at = '2026-07-30T12:00:00Z'
WHERE id IN ('cat_fresh_fruits', 'cat_vegetables', 'cat_grains', 'cat_oils');

UPDATE products
SET image_url = CASE id
      WHEN 'prd_alphonso' THEN '/media/catalogue/generated/fruits.webp'
      WHEN 'prd_spinach' THEN '/media/catalogue/generated/vegetables.webp'
      WHEN 'prd_ragi' THEN '/media/catalogue/generated/staple-grains.webp'
      WHEN 'prd_groundnut_oil' THEN '/media/catalogue/generated/oils-cooking-fats.webp'
      WHEN 'prd_rajma' THEN '/media/catalogue/generated/pulses-legumes.webp'
    END,
    image_alt = CASE id
      WHEN 'prd_alphonso' THEN 'Organic Alphonso mangoes'
      WHEN 'prd_spinach' THEN 'Fresh organic baby spinach'
      WHEN 'prd_ragi' THEN 'Organic sprouted ragi flour'
      WHEN 'prd_groundnut_oil' THEN 'Wood-pressed groundnut cooking oil'
      WHEN 'prd_rajma' THEN 'Organic Himalayan red rajma'
    END,
    updated_at = '2026-07-30T12:00:00Z'
WHERE id IN ('prd_alphonso', 'prd_spinach', 'prd_ragi', 'prd_groundnut_oil', 'prd_rajma');

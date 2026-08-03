-- Attach the reviewed product photographs added after the initial image
-- cleanup. These are product-specific assets, never category/banner fallbacks.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT.
PRAGMA foreign_keys = ON;

UPDATE products
SET image_url = '/products/' || slug || '.jpg',
    image_alt = CASE id
      WHEN 'prd_mass_0001' THEN 'Assorted hen eggs in a metal bowl'
      WHEN 'prd_mass_0002' THEN 'Assorted farm eggs in a woven basket'
      WHEN 'prd_mass_0003' THEN 'Brown country hen eggs on a white background'
      WHEN 'prd_mass_0004' THEN 'Speckled quail eggs'
      WHEN 'prd_mass_0005' THEN 'Brown hen eggs on a white background'
      WHEN 'prd_mass_0006' THEN 'Assorted farm eggs in a woven basket'
      WHEN 'prd_mass_0007' THEN 'Assorted farm eggs in a woven basket'
      WHEN 'prd_mass_0008' THEN 'Speckled quail eggs'
      WHEN 'prd_complete_0129' THEN 'Dark chocolate pieces with almonds and sea salt'
      WHEN 'prd_complete_0130' THEN 'Dark chocolate pieces with almonds and sea salt'
      ELSE image_alt
    END
WHERE id IN (
  'prd_mass_0001', 'prd_mass_0002', 'prd_mass_0003', 'prd_mass_0004',
  'prd_mass_0005', 'prd_mass_0006', 'prd_mass_0007', 'prd_mass_0008',
  'prd_complete_0129', 'prd_complete_0130'
);

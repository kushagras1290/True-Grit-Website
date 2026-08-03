-- Category hero banners describe a department, not an individual product.
-- Earlier demo-catalogue migrations copied those banners into product image
-- fields, which made unrelated products appear to share the same photograph.
-- Keep genuine media uploads and product-specific URLs untouched; products
-- without one now use the storefront's honest named placeholder.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT.
PRAGMA foreign_keys = ON;

UPDATE products
SET image_url = NULL
WHERE image_url LIKE '/banners/categories/%'
   OR image_url LIKE '/homepage-hero%.png';

UPDATE products
SET image_url = CASE id
      WHEN 'prd_alphonso' THEN '/products/organic-alphonso-mangoes.png'
      WHEN 'prd_spinach' THEN '/products/organic-baby-spinach.png'
      WHEN 'prd_ragi' THEN '/products/sprouted-ragi-flour.png'
      WHEN 'prd_groundnut_oil' THEN '/products/wood-pressed-groundnut-oil.png'
      WHEN 'prd_rajma' THEN '/products/himalayan-red-rajma.png'
      ELSE image_url
    END,
    image_alt = CASE id
      WHEN 'prd_alphonso' THEN 'Crate of ripe organic Alphonso mangoes'
      WHEN 'prd_spinach' THEN 'Tender organic baby spinach leaves'
      WHEN 'prd_ragi' THEN 'Sprouted ragi flour with finger millet heads'
      WHEN 'prd_groundnut_oil' THEN 'Wood-pressed groundnut oil with peanuts'
      WHEN 'prd_rajma' THEN 'Himalayan red rajma in a cloth pouch and bowl'
      ELSE image_alt
    END
WHERE id IN ('prd_alphonso', 'prd_spinach', 'prd_ragi', 'prd_groundnut_oil', 'prd_rajma');

UPDATE products
SET image_url = '/products/' || slug || '.png',
    image_alt = CASE id
      WHEN 'prd_market_0001' THEN 'Crate of ripe organic Kesar mangoes'
      WHEN 'prd_market_0033' THEN 'Fresh bunch of organic mature spinach'
      WHEN 'prd_market_0097' THEN 'Organic brown basmati rice in a bowl and cloth pouch'
      WHEN 'prd_market_0130' THEN 'Organic yellow moong dal with whole green mung beans'
      WHEN 'prd_market_0161' THEN 'Organic whole wheat atta with golden wheat heads'
      WHEN 'prd_market_0193' THEN 'Cold-pressed mustard oil with mustard seeds'
      WHEN 'prd_market_0233' THEN 'Organic turmeric powder with fresh turmeric rhizomes'
      WHEN 'prd_market_0265' THEN 'Organic wild forest honey with honeycomb and dipper'
      WHEN 'prd_market_0289' THEN 'Organic Kashmiri almonds in a wooden bowl'
      WHEN 'prd_market_0321' THEN 'Organic rolled oats with oat stalks'
      WHEN 'prd_market_0385' THEN 'Organic roasted makhana in a wooden bowl'
      WHEN 'prd_market_0417' THEN 'Organic Assam black tea leaves with brewed tea'
      ELSE image_alt
    END
WHERE id IN (
  'prd_market_0001', 'prd_market_0033', 'prd_market_0097', 'prd_market_0130',
  'prd_market_0161', 'prd_market_0193', 'prd_market_0233', 'prd_market_0265',
  'prd_market_0289', 'prd_market_0321', 'prd_market_0385', 'prd_market_0417'
);

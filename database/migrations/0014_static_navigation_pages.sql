-- 0014_static_navigation_pages: route seasonal/support navigation to built storefront pages
PRAGMA foreign_keys = ON;

UPDATE navigation_items
SET destination_type = 'internal_path',
    destination_reference = '/seasonal'
WHERE id = 'nit_seasonal';

INSERT OR IGNORE INTO navigation_items (
  id,
  menu_id,
  parent_id,
  label,
  destination_type,
  destination_reference,
  sort_order,
  visible
)
SELECT
  'nit_footer_help',
  'nav_footer',
  NULL,
  'Help',
  'internal_path',
  '/help',
  7,
  1
WHERE EXISTS (SELECT 1 FROM navigation_menus WHERE id = 'nav_footer');

UPDATE announcements
SET destination_path = '/seasonal'
WHERE destination_path = '/category/fresh-fruits';

UPDATE page_versions
SET content_json = replace(content_json, '"/category/fresh-fruits"', '"/seasonal"')
WHERE page_id = 'pag_home'
  AND content_json LIKE '%"/category/fresh-fruits"%';

-- 0023_static_info_cms_pages: seed editable CMS records for public info pages.
-- Existing deployments get records only when the standard seed editor exists.
PRAGMA foreign_keys = ON;

INSERT INTO pages (id, page_type, internal_name, title, slug, template_key, status, published_version_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by)
SELECT 'pag_about', 'content', 'About page', 'About True Grit', 'about', 'cms_static', 'published', 'pgv_about_1',
       'About True Grit',
       'A traceable organic market built around verified farms, seasonal harvests and honest food.',
       '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'
WHERE NOT EXISTS (SELECT 1 FROM pages WHERE slug = 'about')
  AND EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO pages (id, page_type, internal_name, title, slug, template_key, status, published_version_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by)
SELECT 'pag_delivery', 'content', 'Delivery page', 'Delivery', 'delivery', 'cms_static', 'published', 'pgv_delivery_1',
       'Delivery',
       'How True Grit packs, dispatches and delivers seasonal organic food orders.',
       '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'
WHERE NOT EXISTS (SELECT 1 FROM pages WHERE slug = 'delivery')
  AND EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO pages (id, page_type, internal_name, title, slug, template_key, status, published_version_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by)
SELECT 'pag_returns', 'content', 'Returns page', 'Returns and refunds', 'returns', 'cms_static', 'published', 'pgv_returns_1',
       'Returns and refunds',
       'True Grit replacement and refund guidance for fresh and pantry orders.',
       '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'
WHERE NOT EXISTS (SELECT 1 FROM pages WHERE slug = 'returns')
  AND EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO pages (id, page_type, internal_name, title, slug, template_key, status, published_version_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by)
SELECT 'pag_privacy', 'content', 'Privacy page', 'Privacy policy', 'privacy', 'cms_static', 'published', 'pgv_privacy_1',
       'Privacy policy',
       'How True Grit collects, uses and protects customer account and order data.',
       '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'
WHERE NOT EXISTS (SELECT 1 FROM pages WHERE slug = 'privacy')
  AND EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO pages (id, page_type, internal_name, title, slug, template_key, status, published_version_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by)
SELECT 'pag_terms', 'content', 'Terms page', 'Terms of service', 'terms', 'cms_static', 'published', 'pgv_terms_1',
       'Terms of service',
       'Terms for using the True Grit organic food market and placing orders.',
       '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'
WHERE NOT EXISTS (SELECT 1 FROM pages WHERE slug = 'terms')
  AND EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO pages (id, page_type, internal_name, title, slug, template_key, status, published_version_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by)
SELECT 'pag_help', 'content', 'Help page', 'Help', 'help', 'cms_static', 'published', 'pgv_help_1',
       'Help',
       'Quick help for True Grit orders, delivery, returns, accounts and product questions.',
       '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'
WHERE NOT EXISTS (SELECT 1 FROM pages WHERE slug = 'help')
  AND EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO pages (id, page_type, internal_name, title, slug, template_key, status, published_version_id, seo_title, seo_description, created_at, created_by, updated_at, updated_by)
SELECT 'pag_standards', 'content', 'Standards page', 'Our standards', 'standards', 'cms_static', 'published', 'pgv_standards_1',
       'Our standards',
       'What certified, traceable, responsibly sourced and fairly traded mean at True Grit.',
       '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_editor'
WHERE NOT EXISTS (SELECT 1 FROM pages WHERE slug = 'standards')
  AND EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO page_versions (id, page_id, version_number, content_json, change_summary, workflow_state, created_at, created_by, approved_at, approved_by, published_at)
SELECT 'pgv_about_1', 'pag_about', 1,
       '{"blocks":[{"id":"blk_about_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"About","heading":"A market for food with a known origin.","text":"True Grit connects households with certified organic farms, small-batch processors and seasonal harvests that can be traced from source to delivery.","primaryAction":{"label":"Meet the farmers","href":"/farms"},"secondaryAction":{"label":"Shop the market","href":"/shop"}}},{"id":"blk_about_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["Organic food should not depend on vague claims. Every product in the market is tied to a verified farm, certification record, harvest or processing date, and a clear route to the customer.","The catalogue stays intentionally focused so the team can stay close to growers, inspect paperwork, manage freshness and publish the context customers need before buying."]}},{"id":"blk_about_faq","type":"faq","version":1,"enabled":true,"props":{"heading":"What customers can expect","items":[{"question":"How are farms selected?","answer":"Farms must hold a current organic certificate, agree to lot-level traceability and work with seasonal availability."},{"question":"Why is the catalogue focused?","answer":"A smaller catalogue lets the team verify supply, freshness and source information before products are published."}]}}]}',
       'Seed editable about page.', 'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'
WHERE EXISTS (SELECT 1 FROM pages WHERE id = 'pag_about')
  AND NOT EXISTS (SELECT 1 FROM page_versions WHERE id = 'pgv_about_1');

INSERT INTO page_versions (id, page_id, version_number, content_json, change_summary, workflow_state, created_at, created_by, approved_at, approved_by, published_at)
SELECT 'pgv_delivery_1', 'pag_delivery', 1,
       '{"blocks":[{"id":"blk_delivery_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Delivery","heading":"Harvest-led delivery, planned around freshness.","text":"Fresh produce ships on fixed dispatch days. Pantry goods usually leave the fulfilment centre within two working days, with careful handling where needed.","primaryAction":{"label":"Shop now","href":"/shop"},"secondaryAction":{"label":"Contact support","href":"/contact"}}},{"id":"blk_delivery_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["Serviceability is checked during checkout. Some fresh products are limited to routes that can preserve quality within the promised delivery window.","Orders are packed by product type, with ventilated crates for fruit, chilled handling for delicate greens and protective sleeves for glass bottles."]}},{"id":"blk_delivery_faq","type":"faq","version":1,"enabled":true,"props":{"heading":"Delivery rules","items":[{"question":"When do fresh products ship?","answer":"Fresh produce follows planned dispatch windows tied to harvest and route quality."},{"question":"What if a delivery is missed?","answer":"Support will contact you with the next available attempt or a practical resolution based on product condition."}]}}]}',
       'Seed editable delivery page.', 'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'
WHERE EXISTS (SELECT 1 FROM pages WHERE id = 'pag_delivery')
  AND NOT EXISTS (SELECT 1 FROM page_versions WHERE id = 'pgv_delivery_1');

INSERT INTO page_versions (id, page_id, version_number, content_json, change_summary, workflow_state, created_at, created_by, approved_at, approved_by, published_at)
SELECT 'pgv_returns_1', 'pag_returns', 1,
       '{"blocks":[{"id":"blk_returns_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Returns","heading":"If the food arrives wrong, damaged or below standard, we make it right.","text":"Fresh food is time-sensitive, so returns are handled through photos, batch details and a quick support review.","primaryAction":{"label":"Contact support","href":"/contact"},"secondaryAction":{"label":"Read delivery policy","href":"/delivery"}}},{"id":"blk_returns_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["Report fresh produce issues within 24 hours of delivery with clear photos of the product, label and outer packaging.","Report sealed pantry goods issues within 7 days of delivery. Keep the product and packaging until support confirms the resolution."]}},{"id":"blk_returns_faq","type":"faq","version":1,"enabled":true,"props":{"heading":"Resolution options","items":[{"question":"Can I get a replacement?","answer":"Replacement is available when a product arrives damaged, missing, incorrect or visibly below the published quality standard."},{"question":"When is a refund issued?","answer":"Refunds are issued to the original payment method when replacement is not practical or the product is unavailable."}]}}]}',
       'Seed editable returns page.', 'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'
WHERE EXISTS (SELECT 1 FROM pages WHERE id = 'pag_returns')
  AND NOT EXISTS (SELECT 1 FROM page_versions WHERE id = 'pgv_returns_1');

INSERT INTO page_versions (id, page_id, version_number, content_json, change_summary, workflow_state, created_at, created_by, approved_at, approved_by, published_at)
SELECT 'pgv_privacy_1', 'pag_privacy', 1,
       '{"blocks":[{"id":"blk_privacy_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Privacy","heading":"Customer data is used to run the market, not to obscure it.","text":"This page explains the practical data collected for orders, accounts, delivery and support.","primaryAction":{"label":"Contact support","href":"/contact"},"secondaryAction":null}},{"id":"blk_privacy_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["We collect account details, delivery details, order history, payment status, contact messages and basic site diagnostics needed to run the market.","Payment details are handled by the configured payment provider. True Grit stores payment status and references, not full card numbers."]}},{"id":"blk_privacy_faq","type":"faq","version":1,"enabled":true,"props":{"heading":"Data choices","items":[{"question":"How is information used?","answer":"Information is used to process orders, support customers, prevent misuse, improve availability and communicate service updates."},{"question":"Can I request a correction?","answer":"You can ask support for access, correction or deletion where the request does not conflict with legal or fraud-prevention obligations."}]}}]}',
       'Seed editable privacy page.', 'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'
WHERE EXISTS (SELECT 1 FROM pages WHERE id = 'pag_privacy')
  AND NOT EXISTS (SELECT 1 FROM page_versions WHERE id = 'pgv_privacy_1');

INSERT INTO page_versions (id, page_id, version_number, content_json, change_summary, workflow_state, created_at, created_by, approved_at, approved_by, published_at)
SELECT 'pgv_terms_1', 'pag_terms', 1,
       '{"blocks":[{"id":"blk_terms_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Terms","heading":"The basic rules for buying from True Grit.","text":"These terms cover orders, availability, delivery, support and responsible use of the market.","primaryAction":{"label":"Shop now","href":"/shop"},"secondaryAction":{"label":"Contact support","href":"/contact"}}},{"id":"blk_terms_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["You agree to provide accurate account, delivery and contact information, and to use the site only for lawful personal or business purchases.","Fresh and small-batch products can sell out or change with harvest conditions. If a confirmed order cannot be fulfilled, support will offer a replacement, refund or credit."]}},{"id":"blk_terms_faq","type":"faq","version":1,"enabled":true,"props":{"heading":"Order terms","items":[{"question":"When are prices final?","answer":"Final taxes, delivery charges and discounts are confirmed during checkout."},{"question":"Who handles storage after delivery?","answer":"After delivery, storage and handling become the customer responsibility."}]}}]}',
       'Seed editable terms page.', 'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'
WHERE EXISTS (SELECT 1 FROM pages WHERE id = 'pag_terms')
  AND NOT EXISTS (SELECT 1 FROM page_versions WHERE id = 'pgv_terms_1');

INSERT INTO page_versions (id, page_id, version_number, content_json, change_summary, workflow_state, created_at, created_by, approved_at, approved_by, published_at)
SELECT 'pgv_help_1', 'pag_help', 1,
       '{"blocks":[{"id":"blk_help_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Help","heading":"Fast answers for orders, delivery and product questions.","text":"Start with the common paths below. If your issue is tied to an order, include the order reference when contacting support.","primaryAction":{"label":"Contact support","href":"/contact"},"secondaryAction":{"label":"Delivery help","href":"/delivery"}}},{"id":"blk_help_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["For order questions, include the order reference, delivery city and the phone or email used at checkout.","For product questions, send the product name and city so support can check freshness, lot and serviceability details."]}},{"id":"blk_help_faq","type":"faq","version":1,"enabled":true,"props":{"heading":"Common help paths","items":[{"question":"Can I change an order?","answer":"Contact support as soon as possible. Changes are usually possible before picking, packing or harvest allocation starts."},{"question":"Where do I see farm details?","answer":"Product pages include farm, certification, harvest and packing information."}]}}]}',
       'Seed editable help page.', 'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'
WHERE EXISTS (SELECT 1 FROM pages WHERE id = 'pag_help')
  AND NOT EXISTS (SELECT 1 FROM page_versions WHERE id = 'pgv_help_1');

INSERT INTO page_versions (id, page_id, version_number, content_json, change_summary, workflow_state, created_at, created_by, approved_at, approved_by, published_at)
SELECT 'pgv_standards_1', 'pag_standards', 1,
       '{"blocks":[{"id":"blk_standards_hero","type":"hero","version":1,"enabled":true,"props":{"layout":"editorial-split","eyebrow":"Our standards","heading":"Trust is a checklist here.","text":"Certified, traceable, responsibly sourced and fairly traded are operational standards for every published product claim.","primaryAction":{"label":"Meet the farmers","href":"/farms"},"secondaryAction":{"label":"Shop the market","href":"/shop"}}},{"id":"blk_standards_copy","type":"rich_text","version":1,"enabled":true,"props":{"paragraphs":["Every partner farm holds a current organic certificate. We check the paperwork at onboarding, verify it with the issuing body and re-check annually.","Each lot is tagged at the farm with its harvest or milling date. That tag follows the food through quality checks, packing and dispatch."]}},{"id":"blk_standards_faq","type":"faq","version":1,"enabled":true,"props":{"heading":"Standard checks","items":[{"question":"What does traceable mean?","answer":"The product record connects the lot to its farm, harvest or processing date and route to the customer."},{"question":"How are partners paid?","answer":"Farm relationships are set around seasonal supply, clear pricing and long-term reliability."}]}}]}',
       'Seed editable standards page.', 'published', '2026-07-17T00:00:00Z', 'usr_editor', '2026-07-17T00:00:00Z', 'usr_admin', '2026-07-17T00:00:00Z'
WHERE EXISTS (SELECT 1 FROM pages WHERE id = 'pag_standards')
  AND NOT EXISTS (SELECT 1 FROM page_versions WHERE id = 'pgv_standards_1');

-- 0076_support_bot_knowledge: admin-editable knowledge base for the admin
-- support bot (services/support_bot.py).
--
-- The bot's reference material started as a hardcoded Python list
-- (services/support_bot_knowledge.py); this moves it into the database so an
-- admin can add, edit, or remove entries from the admin panel as new pages
-- or workflows are added, without a code deploy. The 36 rows below are that
-- original list, carried over unchanged as the built-in starting set
-- (is_builtin = 1) -- an admin can edit or delete them like any other row;
-- the flag is informational only (lets the admin UI label "built-in" vs
-- "added"), not a protection.
--
-- `keywords` stays a plain space-separated TEXT column, matching
-- services.support_bot's existing keyword-overlap matching (split on
-- whitespace, lowercased) -- there is no FTS/embedding search here, the
-- corpus is small enough that this stays adequate.
PRAGMA foreign_keys = ON;

CREATE TABLE support_bot_knowledge (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  keywords TEXT NOT NULL,
  content TEXT NOT NULL,
  is_builtin INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_support_bot_knowledge_title ON support_bot_knowledge(title);

INSERT INTO support_bot_knowledge (id, title, keywords, content, is_builtin, created_at, updated_at) VALUES
  ('sbk_001', 'Dashboard', 'dashboard home live orders overview', 'Dashboard (/): the landing page after sign-in. Shows live-updating counts for recent orders, inventory alerts, and other at-a-glance figures. It refreshes automatically every few seconds; nothing here needs a manual reload.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_002', 'Analytics', 'analytics conversion report sales traffic', 'Analytics (/analytics): storefront traffic, conversion, and sales trends. Requires the analytics.view permission.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_003', 'Messages', 'chat conversation direct dm group messages staff talk team', 'Messages (/messages): internal staff chat -- groups and direct messages, WhatsApp-style. Only the super admin (owner) can create a conversation, rename a group, or add/remove participants; anyone already added to a conversation can read and send in it. Delivery is live over a WebSocket, not a page refresh.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_004', 'Products', 'catalogue create edit products publish sku variant', 'Products (/products): the product catalogue. Create, edit, publish, and archive products and their variants here. A product must be published before it appears on the storefront. Requires products.view to see the list, products.create/products.edit/products.publish for those actions.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_005', 'Categories', 'catalogue categories organize tree', 'Categories (/categories): the category tree products are organized under. Categories can be released globally or to selected countries.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_006', 'Sale & Discounts', 'adjustment discount off percent price sale', 'Sale & Discounts (/price-adjustments): time-bound percentage discount rules applied across products or categories, separate from one-off coupon codes.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_007', 'Coupons & Promotions', 'campaign code coupons discount promotions', 'Coupons & Promotions (/promotions): customer-facing discount codes and promotional campaigns. Off by default sitewide until a promotion is actually configured.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_008', 'Bundles', 'bundles combo kits multiple products together', 'Bundles (/bundles): fixed sets of products sold together as one catalogue item.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_009', 'Subscriptions', 'recurring renewal save subscribe subscriptions', 'Subscriptions (/subscriptions): Subscribe & Save recurring orders. A daily cron renews subscriptions that are due; the same logic can be triggered manually from this page.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_010', 'Inventory', 'inventory levels low reorder stock warehouse', 'Inventory (/inventory): stock levels per product variant, grouped by location. Each variant has on-hand, reserved, and a reorder threshold -- a variant is worth restocking once (on-hand minus reserved) drops to or below its threshold. Requires inventory.view; adjustments need inventory.adjust.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_011', 'Farms', 'farms growers partners suppliers', 'Farms (/farms): the partner farms supplying products, and which farm owns which product/stock.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_012', 'Farm Requests', 'applications approve farm partnership requests review', 'Farm Requests (/farm-requests): incoming applications from growers wanting to become a partner farm, awaiting review/approval.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_013', 'Orders', 'cancelled completed fulfilment orders pending processing status', 'Orders (/orders): every customer order. Order status moves through pending_payment -> confirmed -> processing -> completed (or cancelled at any point before completion). Click into an order for its line items and payment detail.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_014', 'Returns', 'back customer request returns send', 'Returns (/returns): customer return requests -- approve, reject, or resolve them here. This is the queue that feeds most refunds.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_015', 'Reviews', 'approve moderate product ratings reviews', 'Reviews (/reviews): customer product reviews awaiting moderation or already published.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_016', 'Payments & Refunds', 'audit back money payments refunds', 'Payments & Refunds (/refunds): issue and review refunds against orders. Gated on audit.view since every refund is also an audit-log event.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_017', 'Revenue', 'commission earnings farm payout revenue', 'Revenue (/revenue): revenue and payout figures per farm, including the commission split. Click into a farm for its own detail page.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_018', 'Archive', 'archive archived deleted removed restore', 'Archive (/archive): products, categories, users, and pages that have been archived rather than deleted -- restorable from here.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_019', 'Homepage Settings', 'banner hero homepage settings slides', 'Homepage Settings (/homepage-settings): the storefront home page''s hero banner, slides, and featured content.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_020', 'Colours & Effects', 'ambient appearance colours cursor effects theme', 'Colours & Effects (/appearance): storefront theme tokens, colour scheme, and ambient/cursor visual effects, optionally scoped per country.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_021', 'Site Settings', 'in payments registration settings sign site switch toggle', 'Site Settings (/site-control): sitewide switches -- sign-in methods, registration, whether payments are being accepted, and the payments-disabled notice shown to customers when they''re off.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_022', 'Blog', 'articles blog posts publish write', 'Blog (/blog): blog articles -- draft, review, approve, and publish from here.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_023', 'Recipes', 'content cook food recipes', 'Recipes (/recipes): recipe content, same draft/review/publish workflow as blog articles.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_024', 'Media Library', 'images library media photos upload', 'Media Library (/media): every uploaded image asset, with alt text and usage metadata. Upload needs media.upload; editing metadata needs media.edit.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_025', 'Image Size Guide', 'dimensions guide image recommended size', 'Image Size Guide (/image-guide): recommended image dimensions for each place an image is used across the site -- reference only, no permission required.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_026', 'Submissions', 'content generated pending review submissions user', 'Submissions (/submissions): content submitted by customers/growers (e.g. blog or recipe pitches) awaiting staff review.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_027', 'Contact Attempts', 'attempts contact customers from inquiries leads messages', 'Contact Attempts (/contact-attempts): inbound contact-form submissions from customers.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_028', 'Discussions', 'community discussions hide moderate threads', 'Discussions (/community): customer community discussion threads. Staff with discussions.moderate can hide, restore, archive, or delete a thread or comment.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_029', 'Post Comments', 'blog comments moderate post recipe', 'Post Comments (/content-comments): comments left on published blog articles and recipes -- moderated the same way as Discussions.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_030', 'Users & Roles', 'accounts invite permissions roles staff users', 'Users & Roles (/users): staff accounts -- invite new staff, assign roles, enable/disable accounts. Requires users.view; role changes need users.manage_roles.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_031', 'Scope Management', 'custom farm management owner permissions role scope', 'Scope Management (/scopes): create and edit custom roles and their permission sets, and manage farm-owner sub-admin scoping to a single farm.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_032', 'Audit Log', 'audit changed history log what who', 'Audit Log (/audit): a record of every sensitive admin action -- who did what, when, with a before/after summary.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_033', 'Owner Reports', 'data export owner query reports', 'Owner Reports (/reports): curated data-export report queries. Requires reports.query.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_034', 'Admin Logs', 'admin diagnostics logs only server super', 'Admin Logs (/admin-logs): raw server-side diagnostic logs. Super-admin (owner) only, regardless of what permissions a staff member otherwise holds.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_035', 'SQL Tables', 'browser database db raw sql tables', 'SQL Tables (/db-browser): a read-only browser over the raw database tables, for diagnostics.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_036', 'Your Account', 'account own password profile your', 'Your Account (/account): change your own password and profile details. Available to anyone signed in, including farm-owner sub-admins.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z');

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_support_bot_manage', 'support_bot.manage', 'Add, edit, and remove the support bot''s admin-panel knowledge base entries');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key = 'support_bot.manage'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key = 'support_bot.manage'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

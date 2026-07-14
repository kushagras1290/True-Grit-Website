-- 0013_users_roles_contact: soft-delete staff users, simplified roles, contact inbox
PRAGMA foreign_keys = ON;

ALTER TABLE users ADD COLUMN deleted_at TEXT;

CREATE TABLE contact_messages (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'read', 'archived')),
  created_at TEXT NOT NULL,
  handled_at TEXT
);

CREATE INDEX idx_contact_messages_status_time
  ON contact_messages(status, created_at DESC);

INSERT OR IGNORE INTO roles (id, key, name, description, is_system, created_at) VALUES
  (
    'rol_manager',
    'manager',
    'Manager',
    'Manage catalogue, content, inventory, orders, customers and media',
    1,
    '2026-07-14T00:00:00Z'
  ),
  (
    'rol_inventory',
    'inventory',
    'Inventory',
    'View products, manage stock and monitor orders',
    1,
    '2026-07-14T00:00:00Z'
  );

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id
FROM permissions
WHERE key IN (
  'products.view',
  'products.create',
  'products.edit',
  'products.publish',
  'products.archive',
  'categories.view',
  'categories.create',
  'categories.edit',
  'categories.publish',
  'pages.view',
  'pages.create',
  'pages.edit',
  'pages.publish',
  'media.view',
  'media.upload',
  'media.edit',
  'orders.view',
  'orders.cancel',
  'inventory.view',
  'inventory.adjust',
  'customers.view',
  'audit.view'
);

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_inventory', id
FROM permissions
WHERE key IN ('inventory.view', 'inventory.adjust', 'products.view', 'orders.view');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_farm_owner', id
FROM permissions
WHERE key IN ('media.view', 'media.upload')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_farm_owner');

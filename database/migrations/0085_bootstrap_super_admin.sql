-- 0085_bootstrap_super_admin: make fresh non-development environments operable.
--
-- Historically the founding owner and the super-admin role came from the
-- development seed (or were provisioned manually in production). A clean
-- staging database runs migrations without that seed, leaving the configured
-- ADMIN_LOGIN_* bootstrap credential with no account to adopt.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO roles (
  id, key, name, description, is_system, created_at
) VALUES (
  'rol_super_admin', 'super_admin', 'Super Administrator',
  'All permissions', 1, '2026-08-07T00:00:00Z'
);

-- Earlier permission migrations could not grant this role before it existed.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id
FROM permissions;

-- Established environments retain their existing owner. A fresh environment
-- gets an uncredentialed placeholder which ADMIN_LOGIN_EMAIL/PASSWORD adopts
-- on the first successful sign-in.
INSERT INTO users (
  id, email, display_name, user_type, status, email_verified_at, created_at, updated_at
)
SELECT
  'usr_bootstrap_owner', 'owner-bootstrap@truegrit.invalid', 'Owner',
  'staff', 'active', NULL, '2026-08-07T00:00:00Z', '2026-08-07T00:00:00Z'
WHERE NOT EXISTS (
  SELECT 1
  FROM users u
  JOIN user_roles ur ON ur.user_id = u.id
  JOIN roles r ON r.id = ur.role_id
  WHERE u.user_type = 'staff'
    AND u.status = 'active'
    AND r.key = 'super_admin'
);

INSERT OR IGNORE INTO user_roles (user_id, role_id, assigned_at, assigned_by)
SELECT
  'usr_bootstrap_owner', 'rol_super_admin',
  '2026-08-07T00:00:00Z', 'usr_bootstrap_owner'
WHERE EXISTS (SELECT 1 FROM users WHERE id = 'usr_bootstrap_owner');

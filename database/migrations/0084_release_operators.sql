-- 0084_release_operators: least-privilege access to process.truegritin.com
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_deployments_manage', 'deployments.manage', 'View, verify, and promote releases');

INSERT OR IGNORE INTO roles (id, key, name, description, is_system, created_at) VALUES
  ('rol_release_manager', 'release_manager', 'Release Manager',
   'Access to the standalone testing, staging, and production release cockpit', 1,
   '2026-08-07T00:00:00Z');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES
  ('rol_release_manager', 'prm_deployments_manage');

-- The owner always retains access. Ordinary admin roles are deliberately not
-- granted this permission: production promotion is a separate responsibility.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, 'prm_deployments_manage'
FROM roles r
WHERE r.key = 'super_admin';

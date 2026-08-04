-- 0073_staff_messaging: internal staff messaging (groups + direct messages).
--
-- Membership (who is in which group, who can DM whom) is provisioned by the
-- super administrator only. That is deliberately NOT modeled as a grantable
-- permission -- this codebase's convention is that Administrator ends up with
-- every ordinary permission (see the blanket `SELECT ... FROM permissions`
-- grants to rol_admin in database/seeds/development.sql and
-- 0041_role_permission_baseline.sql), so a `messages.manage`-style permission
-- would inevitably be swept into that "admin gets everything" grant the next
-- time someone follows the established pattern, quietly widening who can
-- reshape conversation membership. Instead, conversation-management endpoints
-- hard-gate on the `super_admin` role itself via `auth.dependencies.require_owner`
-- -- the same belt-and-suspenders technique already used for server logs /
-- DB browser (`api/admin.py`'s `_require_owner`, factored out to
-- `require_owner` by this change so both call sites share one definition).
--
-- Once added to a conversation, a participant reads and sends with
-- `messages.use`, which every seeded staff role holds: messaging itself is a
-- shared internal tool, not a privileged one. Per-conversation access is
-- still enforced independently by a `conversation_participants` row check in
-- the service layer, regardless of the permission.
--
-- Live delivery of new messages happens over a WebSocket to a per-conversation
-- Durable Object (see truegrit_api/realtime); this table set is the durable
-- source of truth history/backfill/unread-counts are read from.
PRAGMA foreign_keys = ON;

CREATE TABLE conversations (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('group', 'direct')),
  name TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  archived_at TEXT,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE conversation_participants (
  conversation_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  added_at TEXT NOT NULL,
  added_by TEXT NOT NULL,
  PRIMARY KEY (conversation_id, user_id),
  FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE RESTRICT
);

-- Reverse lookup: "which conversations is this user in" (conversation list,
-- and the realtime layer's participant check on the WebSocket handshake).
CREATE INDEX idx_conversation_participants_user
  ON conversation_participants(user_id, conversation_id);

CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  sender_id TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
  FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_messages_conversation_created
  ON messages(conversation_id, created_at);

-- One row per (conversation, participant): how far that participant has
-- read. Drives the sidebar unread badge without scanning `messages`.
CREATE TABLE conversation_reads (
  conversation_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  last_read_message_id TEXT,
  last_read_at TEXT NOT NULL,
  PRIMARY KEY (conversation_id, user_id),
  FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (last_read_message_id) REFERENCES messages(id) ON DELETE SET NULL
);

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  (
    'prm_messages_manage',
    'messages.manage',
    'Create and rename conversations, and add or remove participants'
  ),
  (
    'prm_messages_use',
    'messages.use',
    'Read and send messages in conversations you have been added to'
  );

-- messages.manage: super administrator only, matching how membership is
-- meant to be provisioned for this feature.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key = 'messages.manage'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

-- messages.use: every seeded staff role. Each grant is EXISTS-guarded because,
-- apart from rol_manager/rol_super_admin (created in 0013), these roles only
-- exist once database/seeds/development.sql has run -- a fresh database runs
-- migrations before the seed, so these no-op there and the seed must carry
-- the same grant itself (see services/access.py-adjacent seed file).
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE p.key = 'messages.use'
  AND r.key IN (
    'super_admin', 'admin', 'manager', 'publisher', 'content_editor',
    'blogger', 'chef', 'product_manager', 'inventory_manager',
    'order_manager', 'accounts', 'inventory', 'farm_owner'
  );

-- 0009_farm_members: farm-owner sub-admins.
--
-- A farm member is a staff user scoped to exactly one farm. When a member signs
-- in, the API restricts every catalogue and inventory operation to that farm's
-- products — they can never see or touch another farm's data. One row per user
-- (a user manages a single farm).
PRAGMA foreign_keys = ON;

CREATE TABLE farm_members (
  user_id TEXT PRIMARY KEY,
  farm_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_farm_members_farm ON farm_members(farm_id);

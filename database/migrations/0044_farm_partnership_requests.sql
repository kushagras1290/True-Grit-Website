-- 0044_farm_partnership_requests: growers apply from the storefront to join
-- the marketplace; staff triage the applications in the admin console.
--
-- WHY THIS IS NOT content_submissions
-- A blog or recipe submission is a draft of something we already publish, so
-- approving it promotes the row straight into `articles`/`recipes` (0033). A
-- partnership request is not a draft of a farm: onboarding a grower means a
-- site visit, certification papers, pricing and a contract. Approval here
-- therefore records a decision and nothing else -- no `farms` row is minted by
-- the workflow. `linked_farm_id` exists so that once a farm IS created by hand,
-- the application it came from can be attached to it for provenance, which is
-- the opposite direction of travel from 0033 and the reason the two tables do
-- not share a shape.
--
-- WHY NO ACCOUNT IS REQUIRED
-- Unlike content submissions, which are always tied to a signed-in customer, a
-- prospective grower is by definition not yet a customer. Requiring an account
-- would filter out most of the people this form exists to reach, so
-- `submitter_user_id` is nullable and set only when a signed-in visitor
-- happens to apply. Abuse is handled where it belongs -- durable per-IP rate
-- limiting on the route (`auth_rate_limits`, 0008) plus field validation --
-- rather than by a sign-up wall.
--
-- WHY THE PHONE IS NOT NULL
-- Every other contact column in this schema is optional because an account may
-- legitimately have only one channel. This one is not: the entire follow-up
-- for a farm application is a phone call, and an application nobody can ring
-- is an application nobody will action. The API normalises it to E.164 before
-- it ever reaches this column, so the stored form is comparable.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, every insert idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE farm_partnership_requests (
  id TEXT PRIMARY KEY,
  -- 'contacted' sits between review and a decision on purpose: most of these
  -- spend their life there, and collapsing it into 'under_review' would lose
  -- the one fact a second staff member needs -- whether anyone has rung yet.
  status TEXT NOT NULL DEFAULT 'submitted' CHECK (
    status IN ('submitted', 'under_review', 'contacted', 'approved', 'rejected')
  ),

  -- Who to talk to.
  contact_name TEXT NOT NULL,
  contact_email TEXT NOT NULL,
  contact_phone TEXT NOT NULL,

  -- The farm itself. Only the fields an operator needs to decide whether the
  -- conversation is worth having are mandatory; the rest are what a grower can
  -- reasonably answer without paperwork in front of them.
  farm_name TEXT NOT NULL,
  region TEXT NOT NULL,
  state TEXT,
  city TEXT,
  pincode TEXT,
  established_year INTEGER CHECK (
    established_year IS NULL OR (established_year >= 1800 AND established_year <= 2200)
  ),
  land_area_acres TEXT,
  certification TEXT,
  primary_produce TEXT,
  farming_practices TEXT,
  website_url TEXT,
  message TEXT NOT NULL,

  -- Set only when a signed-in customer applied; NULL is the normal case.
  submitter_user_id TEXT,

  reviewer_notes TEXT,
  reviewed_by TEXT,
  reviewed_at TEXT,
  -- Backfilled by hand once an approved application becomes a real farm.
  linked_farm_id TEXT,

  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,

  FOREIGN KEY (submitter_user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (linked_farm_id) REFERENCES farms(id) ON DELETE SET NULL
);

-- The queue view: open applications, newest first.
CREATE INDEX idx_farm_partnership_requests_status_time
  ON farm_partnership_requests(status, created_at DESC);

CREATE INDEX idx_farm_partnership_requests_created
  ON farm_partnership_requests(created_at DESC);

-- Cheap duplicate lookup: the same grower re-applying usually reuses one of
-- these two, and staff need to see the earlier application before replying.
CREATE INDEX idx_farm_partnership_requests_email
  ON farm_partnership_requests(contact_email);

CREATE INDEX idx_farm_partnership_requests_phone
  ON farm_partnership_requests(contact_phone);

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  (
    'prm_farm_requests_view',
    'farm_requests.view',
    'View farm partnership applications from the storefront'
  ),
  (
    'prm_farm_requests_review',
    'farm_requests.review',
    'Progress, approve or reject farm partnership applications'
  );

-- Owner, Admin and Manager. Deciding who supplies the marketplace is a
-- commercial call, so the content roles (Blogger, Chef) are deliberately not
-- included even though they review the other public-submission queue.
--
-- Guarded with EXISTS because, like every role these migrations touch besides
-- rol_manager (0013_users_roles_contact.sql), they exist only via the dev seed
-- -- a deployed database with no matching role must not error here.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('farm_requests.view', 'farm_requests.review')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('farm_requests.view', 'farm_requests.review')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('farm_requests.view', 'farm_requests.review')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

-- Whether the storefront shows the "partner with us" form at all. Switching it
-- off closes applications without a deploy; the API enforces the switch on the
-- route, so hiding the form is not the only thing stopping a replayed POST.
INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('farm_partnerships.enabled', 'true', '2026-08-01T00:00:00Z');

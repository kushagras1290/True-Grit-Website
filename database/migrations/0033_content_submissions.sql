-- 0033_content_submissions: public blog/recipe submissions from signed-in
-- customers, reviewed by staff and promoted straight into the existing
-- articles/recipes tables on approval -- reusing the same published-content
-- machinery rather than a parallel content model. A rejected or
-- changes-requested submission never touches articles/recipes at all, so
-- nothing half-reviewed can ever leak onto the storefront.
PRAGMA foreign_keys = ON;

CREATE TABLE content_submissions (
  id TEXT PRIMARY KEY,
  content_type TEXT NOT NULL CHECK (content_type IN ('article', 'recipe')),
  status TEXT NOT NULL DEFAULT 'submitted' CHECK (
    status IN ('submitted', 'under_review', 'changes_requested', 'approved', 'rejected')
  ),
  submitter_user_id TEXT NOT NULL,
  contact_name TEXT NOT NULL,
  contact_email TEXT NOT NULL,
  contact_phone TEXT,
  title TEXT NOT NULL,
  excerpt TEXT,
  body TEXT NOT NULL,
  prep_minutes INTEGER,
  cook_minutes INTEGER,
  servings INTEGER,
  dietary_tags_json TEXT,
  ingredients_json TEXT,
  steps_json TEXT,
  reviewer_notes TEXT,
  reviewed_by TEXT,
  reviewed_at TEXT,
  published_article_id TEXT,
  published_recipe_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (submitter_user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (published_article_id) REFERENCES articles(id) ON DELETE SET NULL,
  FOREIGN KEY (published_recipe_id) REFERENCES recipes(id) ON DELETE SET NULL
);

CREATE INDEX idx_content_submissions_status_time
  ON content_submissions(status, created_at DESC);

CREATE INDEX idx_content_submissions_type_status
  ON content_submissions(content_type, status);

CREATE INDEX idx_content_submissions_submitter
  ON content_submissions(submitter_user_id, created_at DESC);

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_submissions_view', 'submissions.view', 'View community blog/recipe submissions'),
  (
    'prm_submissions_review',
    'submissions.review',
    'Approve, reject or request changes on community submissions'
  );

-- Blogger and Chef already own articles/recipes respectively; submission
-- review is a single shared permission rather than one per content type, so
-- either can weigh in on both a blog post and a recipe pitched by the
-- community. Owner (super_admin) and Admin round out the reviewer set, per
-- the same roles named for the review workflow. All four grants are guarded
-- with EXISTS because, like every role these migrations touch besides
-- rol_manager (0013_users_roles_contact.sql), they exist only via the dev
-- seed -- a deployed database with no matching role must not error here.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_blogger', id FROM permissions
WHERE key IN ('submissions.view', 'submissions.review')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_blogger');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_chef', id FROM permissions
WHERE key IN ('submissions.view', 'submissions.review')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_chef');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('submissions.view', 'submissions.review')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('submissions.view', 'submissions.review')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

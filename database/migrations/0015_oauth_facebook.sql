-- 0015_oauth_facebook: allow Facebook as a storefront OAuth identity provider.
PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

DROP INDEX IF EXISTS idx_oauth_identities_user;

ALTER TABLE oauth_identities RENAME TO oauth_identities_old;

CREATE TABLE oauth_identities (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  provider TEXT NOT NULL CHECK (provider IN ('google', 'facebook')),
  provider_subject TEXT NOT NULL,
  email TEXT,
  created_at TEXT NOT NULL,
  last_login_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(provider, provider_subject)
);

INSERT INTO oauth_identities (
  id, user_id, provider, provider_subject, email, created_at, last_login_at
)
SELECT id, user_id, provider, provider_subject, email, created_at, last_login_at
FROM oauth_identities_old;

DROP TABLE oauth_identities_old;

CREATE INDEX idx_oauth_identities_user ON oauth_identities(user_id);

COMMIT;

PRAGMA foreign_keys = ON;

-- 0007_customer_auth: password credentials + external (OAuth) identities
--
-- Storefront customers authenticate with either an email + password pair or a
-- federated Google account. Credentials live in their own table so that
-- OAuth-only accounts never carry a password hash, and a single user may hold
-- both a password and one or more linked identities.
PRAGMA foreign_keys = ON;

CREATE TABLE user_credentials (
  user_id TEXT PRIMARY KEY,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE oauth_identities (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  provider TEXT NOT NULL CHECK (provider IN ('google')),
  provider_subject TEXT NOT NULL,
  email TEXT,
  created_at TEXT NOT NULL,
  last_login_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(provider, provider_subject)
);

CREATE INDEX idx_oauth_identities_user ON oauth_identities(user_id);

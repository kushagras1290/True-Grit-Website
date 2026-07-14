-- 0010_password_resets: single-use password reset tokens.
--
-- Only the SHA-256 hash of the token is stored; the raw token lives only in the
-- emailed link. Tokens are single-use (used_at) and time-boxed (expires_at).
PRAGMA foreign_keys = ON;

CREATE TABLE password_reset_tokens (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_password_reset_user ON password_reset_tokens(user_id, expires_at);

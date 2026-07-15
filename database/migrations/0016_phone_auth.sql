-- 0016_phone_auth: the mobile number as a verified, first-class identifier.
--
-- Additive on purpose. Making `users.email` nullable (so a phone-only account
-- needs no address) would require SQLite's table-rebuild dance — CREATE new,
-- copy, DROP TABLE users, RENAME. That is unsafe on D1: D1 rejects
-- `PRAGMA foreign_keys = OFF`, and `PRAGMA defer_foreign_keys` defers constraint
-- *checks* without disabling referential *actions*, so `DROP TABLE users` would
-- fire every ON DELETE CASCADE pointing at it and silently destroy profiles,
-- credentials, sessions, oauth links and orders. Phone-only accounts therefore
-- carry a reserved RFC 2606 `@phone.invalid` placeholder in `email`; the single
-- gate `services.contact.contactable_email` keeps anything from mailing one.
PRAGMA foreign_keys = ON;

-- Identity phone. Distinct from the per-order delivery number on
-- `orders.customer_phone_e164`: this one proves who the account holder is.
ALTER TABLE users ADD COLUMN phone_e164 TEXT;
ALTER TABLE users ADD COLUMN phone_verified_at TEXT;

-- One account per mobile. Partial so the many phone-less rows stay out of the
-- index entirely (SQLite already treats NULLs as distinct; being explicit keeps
-- the intent legible and the index small).
CREATE UNIQUE INDEX idx_users_phone_e164
  ON users(phone_e164)
  WHERE phone_e164 IS NOT NULL;

-- Short-lived one-time passcodes.
--
-- Only hashes are stored — of the passcode, and of the proof token minted once
-- the passcode is accepted — so a database leak yields neither a live OTP nor a
-- usable account-creation credential.
--
-- The row carries the whole challenge lifecycle:
--   created -> (resend*) -> verified_at -> redeemed_at
-- `attempt_count` caps guessing against one challenge, `resend_count` and
-- `last_sent_at` cap SMS spend and enforce the resend cooldown, and the
-- DB-backed auth_rate_limits table caps issuance per phone and per IP.
--
-- Why a separate proof token rather than reusing `id`: an account is created
-- only after the phone is proven, so verify has to hand the browser something it
-- can present back. `id` is an identifier that gets logged and passed around;
-- the token is a secret. Keeping them distinct means a leaked id proves nothing
-- (same reasoning as password_reset_tokens).
--
-- user_id is NULL for 'sign_in' and 'register' — the account may not exist yet,
-- and resolving it at issue time would leak which numbers are registered — and
-- set for 'add_phone', where the caller is already authenticated.
CREATE TABLE phone_otp_challenges (
  id TEXT PRIMARY KEY,
  phone_e164 TEXT NOT NULL,
  user_id TEXT,
  purpose TEXT NOT NULL CHECK (purpose IN ('sign_in', 'register', 'add_phone')),
  code_hash TEXT NOT NULL,
  attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  resend_count INTEGER NOT NULL DEFAULT 0 CHECK (resend_count >= 0),
  last_sent_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  verified_at TEXT,
  verification_token_hash TEXT,
  token_expires_at TEXT,
  redeemed_at TEXT,
  created_at TEXT NOT NULL,
  -- A token may exist only once the passcode has been accepted.
  CHECK (verification_token_hash IS NULL OR verified_at IS NOT NULL),
  -- Nothing may be redeemed that was never verified.
  CHECK (redeemed_at IS NULL OR verified_at IS NOT NULL),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Serves the hot path: the newest live challenge for a phone + purpose.
CREATE INDEX idx_phone_otp_live
  ON phone_otp_challenges(phone_e164, purpose, created_at DESC);

-- Serves token redemption.
CREATE UNIQUE INDEX idx_phone_otp_token
  ON phone_otp_challenges(verification_token_hash)
  WHERE verification_token_hash IS NOT NULL;

-- Serves expiry sweeps.
CREATE INDEX idx_phone_otp_expiry
  ON phone_otp_challenges(expires_at)
  WHERE verified_at IS NULL;

-- 0045_contact_message_phone: capture a phone number on the contact form.
--
-- Email alone loses the cases the contact form exists for. A customer chasing
-- a delivery, or a grower asking about supply, is answered in one call and ten
-- emails; and a phone-only account (0016) has no address we can reply to at
-- all, so an email-only inbox silently drops the very people the storefront
-- lets sign up with nothing but a mobile.
--
-- Nullable, not NOT NULL: `contact_messages` predates this column (0013) and
-- existing rows have no number to backfill. SQLite cannot add a NOT NULL
-- column without a constant default, and inventing a placeholder here would
-- put unringable strings in an inbox humans read. The API requires the field
-- on new submissions, so NULL means exactly one thing -- "sent before we
-- started asking" -- rather than "someone skipped it".
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT.
PRAGMA foreign_keys = ON;

-- E.164, normalised by the API before it lands here, so it is comparable with
-- `users.phone_e164` and with `farm_partnership_requests.contact_phone`.
ALTER TABLE contact_messages ADD COLUMN phone_e164 TEXT;

-- Finds every message from one number across subjects and dates -- the lookup
-- staff actually run when a caller says "I wrote in last week".
CREATE INDEX idx_contact_messages_phone
  ON contact_messages(phone_e164);

-- 0040_storefront_feature_settings: runtime switches for sign-in methods,
-- taking payments, and the blog banner — all editable from the admin console
-- so none of them needs a redeploy or an env-var change.
--
-- Values live in `app_settings` (created in 0034), the existing key/value store
-- for admin-editable settings that belong to no single entity. Booleans are
-- stored as '1'/'0' text; `services.feature_settings` parses them and treats
-- anything unreadable as the default below, so a hand-edited row can never
-- brick sign-in.
--
-- A toggle can only ever *hide* a capability, never conjure one: the API ANDs
-- every switch with its own configuration (`google_sign_in_enabled`,
-- `facebook_sign_in_enabled`, `sms_enabled`, `enabled_payment_methods`), which
-- is why the federated providers can default to on without advertising a button
-- that would dead-end for want of credentials.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, and every insert is idempotent.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  -- Sign-in methods. Each is ANDed with server configuration before it reaches
  -- a customer, so 'on' means "allowed", not "available".
  ('auth.google.enabled', '1', '2026-07-31T00:00:00Z'),
  ('auth.facebook.enabled', '1', '2026-07-31T00:00:00Z'),
  ('auth.phone_otp.enabled', '1', '2026-07-31T00:00:00Z'),
  ('auth.password.enabled', '1', '2026-07-31T00:00:00Z'),
  -- Self-service account creation. Kept separate from `auth.password.enabled`
  -- so an operator can freeze new sign-ups while existing customers keep
  -- signing in — the usual shape of an abuse response.
  ('auth.registration.enabled', '1', '2026-07-31T00:00:00Z'),

  -- Taking money. Off means checkout stops accepting orders and the storefront
  -- offers the contact form instead, so interest is still captured.
  ('commerce.payments.enabled', '1', '2026-07-31T00:00:00Z'),
  (
    'commerce.payments_disabled_notice',
    'We are not taking orders at the moment. Leave your details and we will get in touch as soon as ordering reopens.',
    '2026-07-31T00:00:00Z'
  ),

  -- Blog listing banner, rendered at the same size as the homepage hero.
  -- Empty falls back to the shipped hero image, so the banner space is never
  -- blank (see `PageBanner` in the storefront).
  ('banner.blog.image_url', '', '2026-07-31T00:00:00Z'),
  ('banner.blog.image_alt', '', '2026-07-31T00:00:00Z');

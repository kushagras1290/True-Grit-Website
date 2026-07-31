# True Grit Marketplace

Production implementation of the True Grit marketplace, CMS, admin console, and commerce
platform. True Grit connects customers with traceable organic food, verified farms,
responsible brands, seasonal harvests, and useful food knowledge.

## Architecture

A pnpm monorepo with three independently deployable applications targeting Cloudflare:

| App               | Stack                                                         | Deploys to                |
| ----------------- | ------------------------------------------------------------- | ------------------------- |
| `apps/storefront` | React 19 + React Router framework mode (SSR) + Tailwind CSS 4 | Cloudflare Workers        |
| `apps/admin`      | React 19 SPA + TanStack Query/Table + RHF + Zod + dnd-kit     | Cloudflare Workers        |
| `apps/api`        | Python FastAPI + Pydantic v2                                  | Cloudflare Python Workers |

Shared code lives in `packages/` (design tokens, API contracts, config, test utils). The
relational source of truth is Cloudflare D1 (`database/migrations`), object storage is R2, and
background work is handled by Cloudflare Queues.

```text
true-grit-marketplace/
├── apps/
│   ├── storefront/     # Public React storefront, SSR-capable
│   ├── admin/          # Private custom React admin application
│   └── api/            # Python FastAPI API for Cloudflare Workers
├── packages/
│   ├── ui/             # Shared design tokens and primitives
│   ├── contracts/      # TypeScript API contracts (mirrors Pydantic schemas)
│   ├── config/         # Shared TypeScript configuration
│   └── test-utils/     # Shared frontend test helpers
├── database/
│   ├── migrations/     # Ordered Cloudflare D1 migrations
│   ├── seeds/          # Development and staging seed data
│   └── fixtures/       # Deterministic test datasets
├── infrastructure/     # Cloudflare + GitHub delivery documentation
├── docs/               # Architecture, product (DESIGN.md), runbooks, ADRs
└── scripts/            # Migration validation, smoke tests
```

## Getting started

Prerequisites: Node 22+, pnpm 10 (via Corepack), Python 3.11+, [`uv`](https://docs.astral.sh/uv/).

```bash
pnpm install
pnpm typecheck && pnpm test && pnpm build

cd apps/api
uv sync
uv run ruff check . && uv run pytest
```

Run locally (three terminals):

```bash
pnpm --filter @truegrit/storefront dev   # http://localhost:5173 (auto-loads apps/storefront/.env)
pnpm --filter @truegrit/admin dev        # http://localhost:5174
cd apps/api && uv run uvicorn truegrit_api.main:app --port 8787 --env-file .env
```

Validate the D1 schema without Wrangler:

```bash
pnpm db:validate
```

Both frontends run in **demo-data mode** when `VITE_API_URL` / `PUBLIC_API_URL` is not set: they
render the deterministic fixture catalogue from `packages/contracts` so the full experience is
reviewable before Cloudflare resources exist. Point them at a deployed API to go live.

### Customer accounts and sign-in

The storefront header account menu supports **mobile + SMS passcode**, email + password
sign-up/sign-in, "Sign in with Google", and "Continue with Facebook". Passwords are PBKDF2-SHA256
hashed; Google ID tokens are verified server-side against Google's JWKS, and Facebook user access
tokens are verified server-side against Meta's Graph API. Relevant environment variables:

| Variable                                          | App        | Purpose                                                                                                     |
| ------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| `VITE_FACEBOOK_APP_ID` / `PUBLIC_FACEBOOK_APP_ID` | storefront | Public Facebook app id for the Facebook button. Unset => the button shows "not configured".                 |
| `FACEBOOK_APP_ID`                                 | api        | Same public Facebook app id; the API accepts only Facebook tokens issued to this app.                       |
| `FACEBOOK_APP_SECRET`                             | api        | Server-side Facebook app secret used to inspect access tokens. Empty => Facebook sign-in disabled.          |
| `VITE_API_URL`                                    | storefront | Browser calls the customer-auth API with cookies. Unset ⇒ demo mode (faked localStorage session).           |
| `VITE_GOOGLE_CLIENT_ID`                           | storefront | Public Google OAuth client id for the Google button. Unset ⇒ the button shows "not configured".             |
| `GOOGLE_CLIENT_ID`                                | api        | Same client id; the API accepts only Google tokens whose `aud` matches it. Empty ⇒ Google sign-in disabled. |
| `FAST2SMS_API_KEY`                                | api        | SMS provider key for passcodes. Empty ⇒ console sender in dev; **refused in staging/production**.           |

**Which methods customers actually see is an admin setting, not an env var.** Site Control →
_Storefront switches_ turns each of Google, Facebook, mobile passcodes, email/password and new
sign-ups on or off at runtime (`app_settings`, migration 0040), and the API enforces every switch on
the route itself — hiding a button stops the honest customer, not a replayed request. A switch can
only ever take a method away: it is ANDed with the configuration above, so turning Google on without
a `GOOGLE_CLIENT_ID` still shows nothing, and the console says why. Turning **every** method off is
allowed — it is a legitimate "close the doors" state — and the console warns loudly before you do.

Sign in with X (Twitter) is **not** implemented: X discontinued its free API tier on 6 February 2026
and routes new developers to pay-per-use only, so every sign-in would be a billed API call.

#### Mobile numbers and one-time passcodes

A customer can sign up and sign in with **nothing but a mobile number** — no email, no password.
Numbers are stored as E.164 on `users.phone_e164` (unique) and are only ever written once verified.
Registration through any route requires a verified number, and checkout enforces one, because a
courier and cash-on-delivery both depend on being able to ring the customer. Existing accounts are
prompted after sign-in and may skip; checkout is the backstop.

Passcodes are generated and verified by us — the provider only delivers — so swapping providers is
one class in `apps/api/src/truegrit_api/services/sms.py`. Only SHA-256 hashes of the passcode and of
the resulting proof token are stored.

**There is no free SMS in India.** With `FAST2SMS_API_KEY` blank, a console sender logs the passcode
instead of texting it, so the whole flow is exercisable locally at zero cost; `get_sms_sender`
**refuses** that fallback when `APP_ENV` is staging/production, since logging live passcodes would let
anyone with log access take over accounts. For production, Fast2SMS's `route=otp` rides the
provider's own approved DLT header, so no ₹5,900 TRAI DLT registration is needed — new accounts get
₹50 of free credit (~240 passcodes), then roughly ₹0.21–0.25 per SMS.

#### Payments

Cash on delivery (≤ ₹399, one open COD order per customer) and Razorpay (UPI, cards, netbanking,
wallets) are the domestic options. **Keys alone never expose a gateway.** Razorpay is the only one
with a finished checkout; PayPal sits behind `PAYMENT_PAYPAL_VISIBLE` and Stripe behind
`PAYMENT_STRIPE_VISIBLE`, both defaulting to `false`, so pasting a key into `.env` cannot advertise a
method that would strand a customer with an unpayable order. Configure first, reveal deliberately.

**Ordering has a kill-switch.** Site Control → _Storefront switches_ → "Accept orders and payments"
closes checkout without a deploy: `/v1/public/checkout` refuses (so no stock is ever reserved for an
order nobody can pay for), `/payment-methods` reports none, and the storefront shows a contact form
in place of checkout with an admin-editable message, so interest is still captured. Baskets are left
untouched, so nothing is lost when it is switched back on.

**PayPal is international-only.** PayPal closed its domestic India business on 1 April 2021 — an
Indian merchant cannot take INR from an Indian customer. The supported direction is an overseas buyer
paying an Indian merchant, i.e. the NRI case: pay from abroad, deliver to family in India. So orders
stay priced in INR while PayPal charges `PAYPAL_CURRENCY` (never INR), converted at the operator-set
`PAYPAL_INR_PER_UNIT`. That rate is a fixed number rather than a live FX lookup on purpose: an FX API
is another key, another dependency and another outage on the checkout path, and a silently moving
rate makes order totals unreproducible. Set it slightly in the store's favour and review it; `0`
disables PayPal, since the API refuses to offer a gateway it cannot price.

Razorpay verifies offline (it returns a signature we check with HMAC); PayPal does not — an approval
only becomes money when the API calls capture, so `/v1/public/payments/paypal/capture` captures
against the PayPal order id **we** stored and rejects any captured amount that does not match. Both
gateways pay in a dedicated popup (`/payment/razorpay`, `/payment/paypal`) that reports back to the
checkout tab via `postMessage`.

#### Contact details on phone-only accounts

A phone-only account has no email address, but `users.email` is `NOT NULL` and cannot be relaxed:
dropping the constraint needs a SQLite table rebuild, and D1 supports neither `PRAGMA foreign_keys =
OFF` nor cascade-free deferral, so `DROP TABLE users` would silently cascade-delete profiles,
sessions and orders. Those accounts therefore hold a reserved RFC 2606 `@phone.invalid` placeholder.
**Always read an account's address through `services.contact.contactable_email`**, which returns
`None` rather than a placeholder — never `users.email` directly.

No Google client secret is required — Google Identity Services returns a signed ID token to the
browser, which the API verifies.

Facebook sign-in requires a Facebook app secret on the API because the backend inspects the browser
user access token via Meta's Graph API before creating a session. Do not expose or commit
`FACEBOOK_APP_SECRET`; set it as a local `.env` value or Worker secret.

**Google Cloud setup (one-time):** in [console.cloud.google.com](https://console.cloud.google.com)
→ APIs & Services → Credentials → _Create OAuth client ID_ → **Web application**. Under
**Authorized JavaScript origins** add the exact storefront origins you browse to — for local dev
add **both** so either loopback host works:

```text
http://localhost:5173
http://127.0.0.1:5173
```

Leave _Authorized redirect URIs_ empty (the button returns the token to a JS callback). On the
OAuth consent screen, either add your Google account under **Test users** or **Publish** the app —
otherwise Google rejects sign-in even though the button renders. The `openid email profile` scopes
are non-sensitive, so no Google verification is needed.

Use the same origin in the browser that you registered (this repo's dev servers listen on both
`localhost` and `127.0.0.1`, and the API's CORS accepts both, but Google matches the origin
exactly).

**Meta setup (one-time):** in [developers.facebook.com](https://developers.facebook.com/) create an
app with Facebook Login for Web. Add the exact storefront origins you browse to under the app's
allowed domains / valid OAuth redirect settings, including `localhost` and `127.0.0.1` for local
development. Request `public_profile,email`; customers whose Facebook account does not return an
email cannot use Facebook sign-in until they grant or add an email.

Copy `apps/api/.env.example`, `apps/storefront/.env.example`, and `apps/admin/.env.example` to
`.env` and fill in values. `.env` files are git-ignored; only the `.env.example` templates are
committed.

### Rate limiting and session cookies

Two layers protect the API:

- **Global per-IP ceiling** — `RateLimitMiddleware` caps every route (in-memory fixed window,
  default 300 req / 60 s per IP; `/health/live` is exempt). It is a volumetric backstop and returns
  `429` with a `Retry-After` header. In-memory by design so a flood cannot amplify into DB load; on
  multi-isolate Workers, put Cloudflare edge rate limiting in front for a hard cap.
- **Auth-specific limits** — durable, DB-backed fixed-window counters (`auth_rate_limits` table) on
  register/login/Google/Facebook and admin login, keyed per-IP and per-account, so brute-force and
  credential-stuffing limits hold across isolates and deploys. Defaults: 5 login attempts /
  account / 15 min, 20 / IP / 15 min. Tune via `RATE_LIMIT_*`; set `RATE_LIMIT_ENABLED=false` only
  in controlled tests.

Session cookies are `HttpOnly`, `SameSite` per `SESSION_COOKIE_SAMESITE` (default `lax`), and
`Secure` in staging/production. When the storefront/admin and API are served from **different**
registrable domains, set `SESSION_COOKIE_SAMESITE=none` (the cookie is then forced `Secure`) so the
browser sends it on cross-site API calls.

## Environments and naming

Cloudflare resources use explicit environment suffixes (`truegrit-api-dev|staging|prod`,
`truegrit-dev|staging|prod` D1, `truegrit-media-*` R2, `truegrit-jobs-*` queues). See
`infrastructure/cloudflare/README.md` for the full resource map and provisioning commands, and
`docs/runbooks/` for deployment, migration, and incident procedures.

## Release scope

- **Release 1 (this codebase):** brand system, storefront shell, homepage, dynamic category
  engine, product detail, farms, recipes, journal, search foundation, admin console, RBAC,
  publishing workflows, media metadata, audit log.
- **Delivered on top of Release 1:**
  - **Customer accounts** — Google + Facebook + email/password + phone/OTP sign-in, order history.
  - **Operations console (real CRUD)** — products and categories create/edit/publish/archive with
    versioning + audit, persisted inventory adjustments, user/role management, order status
    transitions.
  - **Farm-owner sub-admins** — a staff role scoped (via `farm_members`) to one farm; they sign in
    with their own password and can only see and manage their own farm's products and stock.
    Provisioned **only from the main admin panel** (Users → Add farm owner). Seeded demo:
    `owner@devika.test` / `devikafarm1`.
  - **Checkout** — server-authoritative cart → order (price + stock revalidated, inventory
    reserved), cash-on-delivery plus a live Razorpay gateway; PayPal and Stripe are scaffolded
    behind explicit go-live flags pending a tested checkout flow for each.
  - **Transactional email** — pluggable sender (Resend in production, SMTP for local dev, or a
    console sender when unconfigured). Sign-up welcomes, order confirmations, farm-owner
    notifications, staff invitations, password resets, and community submission decisions all go
    through it. See `apps/api/.env.example` for the settings.

    The SMTP sender speaks both transports: STARTTLS on 587/25, and implicit TLS on 465, inferred
    from the port. Getting that wrong is silent — a plaintext client on 465 waits for a handshake
    that never arrives and dies at the timeout — which is why "the invite email just doesn't send"
    is usually a port, not a credential. Every message now also carries `Date` and a `Message-ID`
    rooted in the `EMAIL_FROM` domain, both of which providers score against.

    With **no** transport configured the console sender logs the message and reports success, so
    the admin console shows which transport handled an invitation or reset rather than a bare
    "sent" — otherwise an operator waits for mail that never left the process.

  - **Password reset** — self-service on all portals: "Forgot password?" on the storefront account
    menu and the admin sign-in, emailing a single-use, time-boxed link to `/reset-password`; a
    successful reset revokes existing sessions.
  - **Returns (RMA)** — customers file a return against their own order; staff with
    `returns.manage` triage (under review / approved / rejected) and resolve it (refund,
    replacement, store credit), with refunds ledgered against the order.
  - **Dynamic role management** — beyond the seeded roles, an owner can create, rename, re-scope
    and delete fully custom roles from the admin Scope Management page; permission changes revoke
    affected sessions immediately.
  - **Blogger / Chef authoring roles** — staff-side content contributors who can draft and edit
    articles/recipes but not approve or publish them; Manager/Publisher/Owner review and publish.
  - **Community blog/recipe submissions** — signed-in customers pitch a post or recipe from
    `/blog/submit` or `/recipes/submit` (contact name, email, phone optional, plus every field for
    the content type). Submissions are highlighted in the admin Submissions section (nav badge on
    the pending count); Owner/Admin/Blogger/Chef can approve (publishes immediately as a live
    blog post or recipe, credited to the submitter), reject, or request changes — each decision
    emails the submitter, and a "changes requested" submission can be revised and resubmitted from
    `/account/submissions`.
  - **Community discussions** — signed-in customers start threads and comment at `/community`.
    Starting a thread requires an account at least N months old (`discussions.min_account_age_months`,
    default 6, admin-editable); commenting has no tenure requirement. Staff with
    `discussions.moderate` get a dedicated admin section to hide, restore, archive or permanently
    delete any discussion or comment.
- **Still to come:** coupons/promotions, bundles, subscriptions, recommendations, reviews,
  analytics.

The defining capability: an admin creates a category, configures content and product rules,
previews, publishes — and the public storefront renders it automatically, with audit and cache
invalidation recorded. Everything else is an extension.

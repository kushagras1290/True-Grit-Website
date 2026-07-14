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

The storefront header account menu supports email + password sign-up/sign-in and "Sign in with
Google". Passwords are PBKDF2-SHA256 hashed; Google ID tokens are verified server-side against
Google's JWKS. Relevant environment variables:

| Variable | App | Purpose |
| --- | --- | --- |
| `VITE_API_URL` | storefront | Browser calls the customer-auth API with cookies. Unset ⇒ demo mode (faked localStorage session). |
| `VITE_GOOGLE_CLIENT_ID` | storefront | Public Google OAuth client id for the Google button. Unset ⇒ the button shows "not configured". |
| `GOOGLE_CLIENT_ID` | api | Same client id; the API accepts only Google tokens whose `aud` matches it. Empty ⇒ Google sign-in disabled. |

No Google client secret is required — Google Identity Services returns a signed ID token to the
browser, which the API verifies.

**Google Cloud setup (one-time):** in [console.cloud.google.com](https://console.cloud.google.com)
→ APIs & Services → Credentials → *Create OAuth client ID* → **Web application**. Under
**Authorized JavaScript origins** add the exact storefront origins you browse to — for local dev
add **both** so either loopback host works:

```text
http://localhost:5173
http://127.0.0.1:5173
```

Leave *Authorized redirect URIs* empty (the button returns the token to a JS callback). On the
OAuth consent screen, either add your Google account under **Test users** or **Publish** the app —
otherwise Google rejects sign-in even though the button renders. The `openid email profile` scopes
are non-sensitive, so no Google verification is needed.

Use the same origin in the browser that you registered (this repo's dev servers listen on both
`localhost` and `127.0.0.1`, and the API's CORS accepts both, but Google matches the origin
exactly).

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
  register/login/Google and admin login, keyed per-IP and per-account, so brute-force and
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
  - **Customer accounts** — Google + email/password sign-in, order history.
  - **Operations console (real CRUD)** — products and categories create/edit/publish/archive with
    versioning + audit, persisted inventory adjustments, user/role management, order status
    transitions.
  - **Farm-owner sub-admins** — a staff role scoped (via `farm_members`) to one farm; they sign in
    with their own password and can only see and manage their own farm's products and stock.
    Provisioned **only from the main admin panel** (Users → Add farm owner). Seeded demo:
    `owner@devika.test` / `devikafarm1`.
  - **Checkout** — server-authoritative cart → order (price + stock revalidated, inventory
    reserved), cash-on-delivery. A live payment gateway (intent + webhook) is the remaining piece.
  - **Transactional email** — pluggable sender (SMTP via `SMTP_*`, or a console sender when
    unconfigured). On checkout the customer gets a confirmation and each involved farm owner is
    notified. See `apps/api/.env.example` for the SMTP settings.
  - **Password reset** — self-service on all portals: "Forgot password?" on the storefront account
    menu and the admin sign-in, emailing a single-use, time-boxed link to `/reset-password`; a
    successful reset revokes existing sessions.
- **Still to come:** payment gateway, coupons/promotions, bundles, subscriptions, recommendations,
  reviews, analytics.

The defining capability: an admin creates a category, configures content and product rules,
previews, publishes — and the public storefront renders it automatically, with audit and cache
invalidation recorded. Everything else is an extension.

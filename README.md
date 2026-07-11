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
pnpm --filter @truegrit/storefront dev   # http://localhost:5173
pnpm --filter @truegrit/admin dev        # http://localhost:5174
cd apps/api && uv run uvicorn truegrit_api.main:app --port 8787
```

Validate the D1 schema without Wrangler:

```bash
pnpm db:validate
```

Both frontends run in **demo-data mode** when `VITE_API_URL` / `PUBLIC_API_URL` is not set: they
render the deterministic fixture catalogue from `packages/contracts` so the full experience is
reviewable before Cloudflare resources exist. Point them at a deployed API to go live.

## Environments and naming

Cloudflare resources use explicit environment suffixes (`truegrit-api-dev|staging|prod`,
`truegrit-dev|staging|prod` D1, `truegrit-media-*` R2, `truegrit-jobs-*` queues). See
`infrastructure/cloudflare/README.md` for the full resource map and provisioning commands, and
`docs/runbooks/` for deployment, migration, and incident procedures.

## Release scope

- **Release 1 (this codebase):** brand system, storefront shell, homepage, dynamic category
  engine, product detail, farms, recipes, journal, search foundation, admin console, RBAC,
  publishing workflows, media metadata, audit log.
- **Release 2:** cart, checkout, payments, orders, inventory reservation, coupons, accounts.
- **Release 3:** bundles, subscriptions, recommendations, reviews, analytics.

The defining capability: an admin creates a category, configures content and product rules,
previews, publishes — and the public storefront renders it automatically, with audit and cache
invalidation recorded. Everything else is an extension.

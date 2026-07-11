# Deployment runbook

## Order of operations (backward-compatible release)

1. Apply additive D1 migration: `pnpm dlx wrangler d1 migrations apply truegrit-<env> --remote`
2. Deploy API (`apps/api`), then run `GET /health/live` and contract smoke tests.
3. Deploy storefront (`apps/storefront`): `pnpm build && pnpm dlx wrangler deploy --env <env>`
4. Deploy admin (`apps/admin`): same pattern.
5. Run smoke tests (`scripts/` — home, category, product, search, admin protected, preview noindex).
6. Observe error and latency dashboards; mark the GitHub release.

Breaking changes use expand-contract across releases (see migrations runbook).

## Rollback

Cloudflare supports Worker version rollback, but **rollback does not revert D1 schema or
data**. Confirm binding compatibility before rolling back; prefer roll-forward corrective
migrations. Record incident and release metadata for every rollback.

## Release gates

No release proceeds if: a required CI check fails; a critical exploitable security issue is
open; the production migration lacks review; staging smoke fails; authorization tests fail.

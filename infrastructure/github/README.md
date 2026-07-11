# GitHub delivery configuration

## Branch strategy

Trunk-based: `main` is always releasable; short-lived `feature/<issue>-*`, `fix/<issue>-*`,
`chore/<issue>-*` branches. No permanent development/qa/release branches.

## Ruleset for `main`

Require PR + one approval, dismiss stale approvals, require status checks (frontend, backend,
database jobs from `.github/workflows/ci.yml`), require branches up to date, require
conversation resolution, block force pushes and deletion, restrict bypass.

## Environments

- `staging`: auto-deploy after merge to main; staging Cloudflare identifiers.
- `production`: required human approval; deployment branch restricted to `main`;
  production-only Cloudflare token.

Separate least-privilege tokens per environment: `CLOUDFLARE_API_TOKEN_STAGING`,
`CLOUDFLARE_API_TOKEN_PRODUCTION`, plus `CLOUDFLARE_ACCOUNT_ID`. Never one unrestricted token
for everything.

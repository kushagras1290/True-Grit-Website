# Cloudflare resource map

Never point local or staging code at production resources.

| Resource          | Development               | Staging                       | Production                 |
| ----------------- | ------------------------- | ----------------------------- | -------------------------- |
| API Worker        | `truegrit-api-dev`        | `truegrit-api-staging`        | `truegrit-api-prod`        |
| Storefront Worker | `truegrit-storefront-dev` | `truegrit-storefront-staging` | `truegrit-storefront-prod` |
| Admin Worker      | `truegrit-admin-dev`      | `truegrit-admin-staging`      | `truegrit-admin-prod`      |
| D1 database       | `truegrit-dev`            | `truegrit-staging`            | `truegrit-prod`            |
| R2 private media  | `truegrit-media-dev`      | `truegrit-media-staging`      | `truegrit-media-prod`      |
| R2 exports        | `truegrit-exports-dev`    | `truegrit-exports-staging`    | `truegrit-exports-prod`    |
| Queue             | `truegrit-jobs-dev`       | `truegrit-jobs-staging`       | `truegrit-jobs-prod`       |
| Dead-letter queue | `truegrit-dlq-dev`        | `truegrit-dlq-staging`        | `truegrit-dlq-prod`        |
| KV namespace      | `truegrit-cache-dev`      | `truegrit-cache-staging`      | `truegrit-cache-prod`      |

## Provisioning

```bash
pnpm dlx wrangler login && pnpm dlx wrangler whoami   # confirm the account first

pnpm dlx wrangler d1 create truegrit-dev              # repeat per environment
pnpm dlx wrangler r2 bucket create truegrit-media-dev
pnpm dlx wrangler r2 bucket create truegrit-exports-dev
pnpm dlx wrangler queues create truegrit-jobs-dev
pnpm dlx wrangler queues create truegrit-dlq-dev
pnpm dlx wrangler kv namespace create TRUEGRIT_CACHE
```

Record real IDs into each app's `wrangler.jsonc` — never guess IDs. Media buckets stay private;
public delivery is intentional via Cloudflare Images transformations.

## Secrets

Set via `wrangler secret put` per environment (`SESSION_SIGNING_KEY`, `PREVIEW_SIGNING_KEY`,
`OTP_PEPPER`, `PAYMENT_API_KEY`, `PAYMENT_WEBHOOK_SECRET`, `EMAIL_API_KEY`). Local development
uses `.dev.vars` (never committed; `.dev.vars.example` is the template).

## Domains

`www` / `api` / `admin` `.truegrit.example` in production, `-staging` variants in staging.
Admin domains sit behind Cloudflare Access; the application still enforces RBAC independently.

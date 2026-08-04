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

Repeat the commands with `staging` and `prod` suffixes before invoking the protected deployment
workflow. The workflow deliberately fails if the named D1, R2, or Queue resources do not already
exist. Wrangler creates the environment-specific KV binding on its first reviewed deployment and
writes the generated namespace ID back to the configuration; commit that ID before promotion.

Enable D1 read replication for staging and production under **D1 > database > Settings > Read
replication**. The API uses `first-unconstrained` Sessions only for anonymous public GET/HEAD requests;
writes, authenticated traffic, checkout, payments, and admin work begin on `first-primary`.

## Paid-plan edge controls

On the API zone, create a Cache Rule for anonymous `GET`/`HEAD` requests under `/v1/public/` that
respects the Worker response TTL and bypasses on `Cookie` or `Authorization`. Do not cache `/auth`,
`/orders`, `/addresses`, `/checkout`, `/payments`, `/submissions`, or `/subscriptions`. The Worker
also enforces this classification and emits `Cache-Tag` plus `x-cache-policy` as defense in depth.

Create WAF/rate-limit rules before increasing traffic:

- Challenge or block abusive login, registration, OTP, contact, submission, discussion, and checkout
  traffic before the API Worker executes.
- Base the origin key on Cloudflare's trusted client-IP field; never accept a client-supplied
  `X-Forwarded-For` value as authoritative.
- Start with monitoring, review shared-network false positives, then enable enforcement.
- Set Workers/D1/Queues usage notifications and a monthly account budget in Billing.

Turnstile widget creation and form insertion remain a separately confirmed operation because they
create account state and require production hostnames. The backend secret must be stored as
`TURNSTILE_SECRET`; never commit it.

## Secrets

Set via `wrangler secret put --env <environment>` for each isolated environment. At minimum,
production needs `ADMIN_LOGIN_PASSWORD` and `RESEND_API_KEY`; enabled providers additionally need
`FAST2SMS_API_KEY`, `FACEBOOK_APP_SECRET`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`,
`PAYPAL_SECRET`, or the corresponding Stripe secrets. Local development uses `.dev.vars` (never
committed; `.dev.vars.example` is the template). A deployment without `RESEND_API_KEY` retains email
jobs through retries and the DLQ instead of falsely acknowledging an undelivered message.

## Domains

`www` / `api` / `admin` `.truegrit.example` in production, `-staging` variants in staging.
Admin domains sit behind Cloudflare Access; the application still enforces RBAC independently.

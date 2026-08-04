# Scalability, capacity, and production-readiness assessment

- **Status:** Open engineering assessment
- **Last reviewed:** 2026-08-02
- **Audience:** Engineering, operations, and product owners
- **Scope:** Storefront, API, Cloudflare Workers, D1, R2, KV, Queues, checkout, and production operations

## Executive summary

True Grit has a sound edge-first foundation: the storefront and API run on Cloudflare Workers,
static assets can be served at the edge, media belongs in R2, relational data belongs in D1, and
the repository anticipates KV and Queues. That foundation does not currently prove or provide
support for millions of simultaneously active customers.

Moving to Workers Paid is the first prerequisite because it removes the Free plan's daily request
ceiling and raises the available CPU budget. It is not, by itself, a scaling solution. The main
remaining constraints are uncached public traffic, one single-threaded D1 database, non-atomic
inventory validation, incomplete queue processing, isolate-local global rate limiting, incomplete
production observability, and the absence of repeatable load tests.

The immediate objective should be safe and measurable scale, in this order:

1. Make checkout, inventory, payment callbacks, and retries concurrency-safe.
2. Provision isolated paid production resources with budgets and monitoring.
3. Serve nearly all anonymous reads from Cloudflare's cache rather than D1.
4. Move non-request work to durable queue consumers with retries and a dead-letter queue.
5. Optimize and replicate D1 reads, then partition or migrate write-heavy data when measurements
   show that one primary database is no longer sufficient.
6. Establish capacity through staged load tests and explicit service-level objectives.

## What “millions of users” means

Registered users, monthly visitors, concurrent sessions, and requests per second are different
capacity requirements. Capacity work must start with a workload model rather than an account-count
target.

For example:

- 1,000,000 connected customers making one request every 30 seconds produces about 33,333 requests
  per second.
- 1,000,000 connected customers making one request every 10 seconds produces 100,000 requests per
  second.
- A cached category page and a checkout request have radically different compute, consistency, and
  database costs even when each counts as one request.

Before approving a production capacity claim, define expected requests per second for anonymous
browsing, search, authentication, cart operations, checkout, payments, discussions, and admin work.

## Current strengths

- Static assets and public media can be distributed through Cloudflare and R2 rather than the
  transactional database.
- Storefront-to-API service bindings avoid a public network hop between Workers.
- D1 access is isolated behind a platform adapter, preserving the option to add Sessions or migrate
  selected workloads.
- Business writes commonly use D1 batches, audit records, and outbox records.
- The repository already defines environment naming for development, staging, and production in the
  [Cloudflare resource map](../../infrastructure/cloudflare/README.md).
- The API can also run under Uvicorn, which preserves a migration path away from Python Workers if
  runtime measurements require it. See [ADR-003](../adr/ADR-003-fastapi-python-workers.md).

## Priority definitions

| Priority | Meaning                                                                       |
| -------- | ----------------------------------------------------------------------------- |
| P0       | Required before accepting meaningful production order volume.                 |
| P1       | Required before deliberately increasing traffic or marketing spend.           |
| P2       | Required as measured usage and stored data approach an agreed threshold.      |
| P3       | Improvement that reduces cost or operational effort but does not gate launch. |

## Issue register

| ID       | Priority | Status                                | Issue                                                                                        | Primary risk                                                    |
| -------- | -------- | ------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| SCAL-001 | P0       | Code complete; benchmark pending      | Paid CPU limit and production PBKDF2 policy are configured                                   | CPU termination and daily request exhaustion                    |
| SCAL-002 | P0       | Code complete; edge rule pending      | Anonymous public API responses have a tested shared-cache policy and tags                    | Every visitor reaches Workers and D1                            |
| SCAL-004 | P0       | Suite complete; baseline pending      | Guarded k6 browse and final-unit checkout workloads are versioned                            | Capacity claims cannot be verified                              |
| SCAL-005 | P0       | Config complete; provisioning pending | Staging/production bindings and a protected deployment workflow are represented              | Development resources can become a deployment dependency        |
| SCAL-006 | P1       | Code complete; replication pending    | Request-scoped D1 Sessions and query telemetry are implemented                               | Database saturation and overload errors                         |
| SCAL-008 | P1       | Core path complete; expansion pending | Outbox dispatcher, idempotent consumer, retries, DLQ, and durable email jobs are implemented | Non-durable work and lost/repeated side effects                 |
| SCAL-009 | P1       | Edge configuration pending            | WAF/rate-limit controls are documented; Turnstile setup requires account/domain confirmation | Inconsistent protection during distributed traffic              |
| SCAL-010 | P1       | Code complete; alerts pending         | Logs/traces and D1/cache/queue correlation signals are configured                            | Slow detection and diagnosis of production failures             |
| SCAL-011 | P2       | Not applicable                        | Large-list APIs use counts and offset pagination                                             | Increasing query cost as tables grow                            |
| SCAL-012 | P2       | Resolved                              | Data tiers and measurable migration triggers are documented                                  | Emergency migration after a storage or write ceiling is reached |
| SCAL-013 | P2       | Benchmark pending                     | A repeatable Python Worker workload exists; measured comparison still requires staging       | Higher latency and compute cost than expected                   |

Implementation landed on 2026-08-04 in the API
[Wrangler configuration](../../apps/api/wrangler.jsonc),
[cache policy](../../apps/api/src/truegrit_api/middleware/cache_policy.py),
[D1 adapter](../../apps/api/src/truegrit_api/platform/d1.py),
[durable jobs service](../../apps/api/src/truegrit_api/services/jobs.py),
[capacity suite](../../tests/load/README.md), and
[capacity runbook](../runbooks/capacity.md). Account-side items remain explicitly pending until
their staging evidence exists; a repository implementation is not treated as a production capacity
claim.

## Detailed findings and recommendations

### SCAL-001 — Move the runtime to Workers Paid

**Evidence**

The active [API Wrangler configuration](../../apps/api/wrangler.jsonc) identifies the account as
Workers Free and documents CPU terminations caused by the 10 ms Free-plan CPU budget. The API runs
FastAPI through Python Workers/Pyodide, so serialization and framework work consume part of that
budget before business logic executes.

**Impact**

A request can be terminated even when the application logic is otherwise correct. The Free plan's
daily request allowance also makes it unsuitable for a public commerce workload.

**Recommendation**

- Upgrade the account to Workers Paid.
- Add a deliberate production CPU limit after measuring representative endpoints; do not simply set
  every invocation to the platform maximum.
- Configure usage notifications and a monthly budget.
- Benchmark Python Worker CPU for public catalogue, login, checkout, admin reports, and media paths.
- Do not copy the development-only reduced PBKDF2 configuration into production without a security
  and CPU benchmark.

**Done when**

- Production deployments no longer use Free-plan limits.
- No representative request terminates with `exceededCpu` during the target load test.
- CPU p50, p95, and p99 are visible by route family.

Cloudflare's current plan inclusions and overage rates are maintained in the
[Workers pricing documentation](https://developers.cloudflare.com/workers/platform/pricing/).
Verify them again before purchase because platform pricing and limits can change.

### SCAL-002 — Cache anonymous storefront traffic

**Evidence**

The API's [security header middleware](../../apps/api/src/truegrit_api/middleware/security_headers.py)
defaults responses to `Cache-Control: no-store`. The storefront
[root loader](../../apps/storefront/app/root.tsx) loads public bootstrap data and site settings on
each root request, while route loaders make additional API requests. Static assets and a few
explicit responses have their own caching behavior, but there is no broad cache policy for public
catalogue and CMS responses.

**Impact**

Repeated requests for identical home, category, product, article, and recipe content consume Worker
CPU and D1 queries. This converts an edge-cacheable workload into centralized database traffic.

**Recommendation**

- Classify routes as public-cacheable, private, or never-cacheable.
- Cache published home, category, product, blog, recipe, discussion-list, navigation, and public
  settings responses.
- Cache generated storefront HTML where the response does not contain customer-specific state.
- Keep authentication, account, cart, checkout, payments, previews, and admin responses private.
- Use `s-maxage` and `stale-while-revalidate` with values appropriate to the content type.
- Emit cache tags for products, categories, settings, articles, recipes, and navigation.
- Purge affected tags after a successful publish rather than clearing the entire site.
- Make country, currency, locale, and other representation-changing inputs part of the cache key.
- Prevent cookies and authorization headers from accidentally entering a shared cached response.

**Done when**

- Anonymous browsing achieves at least a 95% edge-cache hit ratio in a representative test.
- Cache-hit requests do not invoke the API Worker or query D1.
- Publishing changes become visible within the agreed freshness window.
- Automated tests prove that private customer data is never shared through the cache.

See [Workers caching configuration](https://developers.cloudflare.com/workers/cache/configuration/)
and [Cache Rules](https://developers.cloudflare.com/cache/how-to/cache-rules/).

### SCAL-004 — Build a capacity and regression test suite

**Evidence**

No k6, Artillery, Locust, or equivalent repository-level load-test suite was found during this
assessment. Unit and integration tests validate behavior, but they do not establish throughput,
tail latency, cache effectiveness, or saturation behavior.

**Recommendation**

Create load scenarios for:

- Cached and uncached home, category, product, article, and recipe reads.
- Search with common and worst-case terms.
- Registration, login, OTP, and account retrieval.
- Cart mutation and checkout with realistic line counts.
- Concurrent purchase of the final units of a product.
- Payment webhook delivery, duplication, and reordering.
- Admin publishing while customer traffic is active.
- Queue backlog, consumer failure, retry, and dead-letter behavior.

Run tests against isolated staging resources. Increase traffic gradually and stop when error rate,
latency, CPU, database queueing, or provider safety limits cross an agreed threshold. Never point a
stress test at production payment, email, or SMS providers.

**Done when**

- The suite runs repeatably in staging and records its workload version.
- Each release has a stored capacity report with Worker CPU, latency, errors, D1 metrics, cache hit
  ratio, and queue lag.
- A regression threshold fails CI or blocks promotion when capacity materially decreases.

### SCAL-005 — Provision isolated production resources

**Evidence**

The resource map defines development, staging, and production names, but the active
[API Wrangler configuration](../../apps/api/wrangler.jsonc) binds only development resources and
development URLs.

**Recommendation**

- Create explicit staging and production Wrangler environments or separate reviewed configuration
  files.
- Provision independent D1, R2, KV, queues, secrets, service bindings, and custom domains.
- Require an environment assertion during deployment so production code cannot bind development
  resources.
- Apply migrations through the documented deployment workflow and verify them before shifting
  traffic.
- Configure D1 Time Travel recovery and perform a restoration exercise.

**Done when**

- A configuration review shows no shared mutable resources across development, staging, and
  production.
- Deployment automation identifies the account and environment before making changes.
- A staging-to-production promotion has a verified rollback procedure.

### SCAL-006 — Protect the single D1 primary

**Evidence**

One `DB` binding currently serves catalogue, content, users, sessions, inventory, orders, payments,
audit records, and operational data. The [D1 adapter](../../apps/api/src/truegrit_api/platform/d1.py)
uses direct `prepare()` calls and does not implement D1 Sessions for read replication.

**Impact**

Each D1 database processes queries serially. Slow public reads, authentication rate-limit writes,
admin reports, and checkout writes therefore compete for the same primary database.

**Recommendation**

- Record D1 query duration, rows read, rows written, retries, and overload errors by operation.
- Enable read replication for safe read-heavy paths.
- Update the platform adapter to use the Sessions API and an explicit consistency policy.
- Keep inventory, checkout, payment, and immediately-after-write reads on the primary or use the
  required sequential-consistency bookmark.
- Cache catalogue and CMS data before attempting database sharding.
- Move analytical scans, long-term event data, and large exports away from the transactional primary.

**Done when**

- Public read traffic is primarily served by cache, then replicas on misses.
- Critical writes have documented consistency requirements.
- Alerts fire before D1 begins returning overload errors.

Each paid D1 database currently has a 10 GB maximum and processes queries one at a time. Cloudflare
describes horizontal partitioning across smaller databases as the intended scale-out model. See
[D1 limits](https://developers.cloudflare.com/d1/platform/limits/) and
[D1 read replication](https://developers.cloudflare.com/d1/best-practices/read-replication/).

### SCAL-008 — Implement durable queue processing

**Evidence**

The API Wrangler file configures `JOBS_QUEUE` only as a producer. No consumer or dead-letter queue is
configured there, and the application continues to schedule email work through FastAPI
`BackgroundTasks`. Outbox rows are written during several publishing flows, but a durable dispatcher
is not evident in the active Worker configuration.

**Recommendation**

- Add a queue consumer and a separately monitored dead-letter queue.
- Publish outbox events through a retry-safe dispatcher.
- Move email, SMS, notifications, search indexing, image processing, analytics, and reports out of
  customer request paths.
- Assign a stable idempotency key to every message.
- Make consumers safe under duplicate and out-of-order delivery.
- Monitor oldest-message age, retries, consumer failures, and dead-letter depth.

**Done when**

- Customer success does not depend on a non-durable background task completing.
- Retrying a message does not send duplicate customer communications or repeat a financial effect.
- Poison messages are retained and alert an operator instead of disappearing.

See [Cloudflare Queues dead-letter queues](https://developers.cloudflare.com/queues/configuration/dead-letter-queues/).

### SCAL-009 — Move global abuse controls to the edge

**Evidence**

The global middleware rate limiter stores IP buckets in process memory and explicitly describes
itself as a per-isolate guard in
[rate_limit.py](../../apps/api/src/truegrit_api/middleware/rate_limit.py). Authentication-specific
limits are durable in D1, but those writes also consume primary database capacity during abuse.

**Recommendation**

- Enforce coarse IP, ASN, country, and bot controls with Cloudflare WAF and Rate Limiting before the
  API Worker runs.
- Use Turnstile for suspicious registration, login, OTP, submission, and discussion activity.
- Retain application-level account and business limits as defense in depth.
- Avoid writing every obviously hostile request into the transactional database.
- Test trusted proxy and `CF-Connecting-IP` handling so attackers cannot choose their limiter key.

**Done when**

- Distributed traffic receives one consistent limit across Worker isolates.
- Blocked abusive traffic does not consume application CPU or D1 writes.
- Legitimate shared-network customers are not broadly locked out.

### SCAL-010 — Complete production observability

**Evidence**

The current API Wrangler configuration persists invocation logs but has top-level observability and
tracing disabled. Request IDs exist, but capacity-specific dashboards and alerts are not defined in
the repository.

**Recommendation**

Track and alert on:

- Request rate, response status, latency, CPU time, wall time, and `exceededCpu` by route family.
- D1 query duration, rows read/written, errors, overload events, and storage growth.
- Cache hit ratio, bypass reason, stale responses, and purge failures.
- Checkout attempts, stock conflicts, orders created, duplicate prevention, and oversell invariant.
- Payment creation, webhook age, signature failures, duplicate events, and reconciliation backlog.
- Queue depth, oldest-message age, retry count, consumer failures, and dead-letter depth.
- External provider latency and failure rates for payments, email, SMS, and identity.

Define alert ownership and link every alert to an operational procedure in the
[incident runbook](../runbooks/incidents.md).

**Done when**

- A failed checkout can be followed across storefront, API, database, queue, and payment provider
  using one request or correlation ID.
- Alerts identify customer impact before support reports it.
- Dashboards distinguish cache hits from requests that execute application logic.

### SCAL-011 — Replace large offsets and hot-path counts

**Status: not applicable to the current storefront** (reviewed 2026-08-02).

**Evidence**

Catalogue, article, recipe, discussion, order, user, media, audit, and other list queries use
`LIMIT ... OFFSET ...`; several execute an additional `COUNT(*)`. Large offsets require increasing
work as data grows, and exact totals are rarely necessary for public infinite-scroll or next-page
interfaces.

Every public storefront list page (`/shop`, `/category/:slug`, `/blog`, `/recipes`,
`/community`) uses explicit numbered `?page=` pagination, not infinite scroll — confirmed by
reading each route's loader. This recommendation's own text carves that case out: "Preserve offset
pagination only for bounded admin datasets **or explicit page-number requirements**." A numbered
page control also genuinely needs the exact total (to render "Page 3 of 12" and a last-page
control), which cursor/keyset pagination cannot provide without a separate count query of its own —
so switching would not remove the count, only complicate the pagination.

**Recommendation**

- Use stable cursor/keyset pagination for growing tables **if and when** a public list adopts
  infinite scroll or a "load more" pattern instead of numbered pages. Re-open this item at that
  point rather than converting a working, appropriate numbered-page UI for no benefit.
- Cache totals that do not require transaction-level freshness (still applicable; see SCAL-002's
  cache-tag approach).
- Preserve offset pagination for bounded admin datasets and every current public page-number UI.

**Done when**

- A public list page adopts infinite scroll or "load more" — at that point, apply cursor/keyset
  pagination to that specific endpoint and revisit this item's status.

### SCAL-012 — Establish data-growth and migration thresholds

**Recommendation**

Assign each class of data to the correct storage tier:

| Data                                                   | Recommended system of record                                                            |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| Products, customers, orders, inventory, payments       | D1 initially; partitioned D1 or managed relational database when thresholds are reached |
| Images, exports, generated reports                     | R2                                                                                      |
| Public derived responses and short-lived configuration | Workers Cache and/or KV                                                                 |
| Durable asynchronous work                              | Queues plus a dead-letter queue                                                         |
| High-volume analytics and immutable event history      | Analytics/event pipeline and R2 or an analytical store, not hot transactional tables    |

Create migration triggers before they are needed. Example triggers include:

- Sustained D1 utilization or overload despite caching and query optimization.
- Write latency or contention breaking the checkout service-level objective.
- Forecast storage crossing 60–70% of the applicable per-database limit within the migration lead
  time.
- Analytical or administrative workloads interfering with customer transactions.
- A partition boundary with clear ownership, such as tenant or customer, becoming available.

Do not split the catalogue prematurely. Cache it first; partitioning adds consistency, deployment,
backup, and reporting complexity.

### SCAL-013 — Benchmark the Python runtime and retain an exit path

**Evidence**

The Wrangler comments document meaningful Pyodide marshalling cost, and
[ADR-003](../adr/ADR-003-fastapi-python-workers.md) records Python Workers beta status and the
portable Uvicorn mitigation.

**Recommendation**

- Benchmark real payloads on Workers Paid before committing to capacity numbers.
- Profile framework, validation, serialization, password hashing, and application CPU separately.
- Keep platform bindings behind adapters and avoid introducing Worker-only behavior into business
  services.
- Establish a migration threshold for moving the API to a container or another Python runtime if
  cost, CPU, dependency support, or reliability misses the agreed objective.

**Done when**

- A measured cost and latency comparison supports keeping Python Workers.
- The local/Uvicorn runtime passes the same contract and integration suite as the Worker runtime.

## Suggested target request flow

```text
Customer
   |
   v
Cloudflare WAF / rate limiting / Turnstile
   |
   +--> Static assets and R2 media --------------------------> edge response
   |
   +--> Cached anonymous HTML/API --------------------------> edge response
   |
   v
Storefront Worker
   |
   v
API Worker
   |
   +--> Cache/KV for derived public data
   +--> D1 replicas for safe public reads
   +--> D1 primary for transactional truth
   +--> Queue for non-request work --> consumer --> provider
   |                                      |
   |                                      +--> dead-letter queue on repeated failure
   +--> R2 for media, exports, and large objects
```

## Delivery sequence

### Phase 0 — Define the target

1. Write the expected workload mix and peak requests per second.
2. Define latency, availability, freshness, recovery, and cost objectives.
3. Establish data-growth forecasts for users, orders, inventory events, audit logs, and content.

### Phase 1 — Make production safe

1. Upgrade to Workers Paid and provision isolated staging/production resources.
2. Fix atomic inventory, checkout idempotency, payment idempotency, and COD concurrency.
3. Enable production logs, traces, dashboards, alerts, and spending notifications.
4. Configure WAF, distributed rate limiting, and Turnstile protections.

### Phase 2 — Remove avoidable synchronous work

1. Introduce safe public API and storefront caching with targeted invalidation.
2. Implement queue consumers, retries, idempotency, and a dead-letter queue.
3. Reduce catalogue query amplification and replace hot-path offsets/counts.

### Phase 3 — Scale the data layer

1. Enable D1 read replication and Sessions-aware access.
2. Isolate analytics and large exports from the transactional primary.
3. Partition D1 or migrate write-heavy domains only when measured thresholds are reached.

### Phase 4 — Prove and maintain capacity

1. Run staged workload tests to the target and beyond it with a defined safety margin.
2. Test overload behavior, provider failure, queue backlog, restore, and rollback.
3. Run a smaller performance regression suite for releases that affect hot paths.
4. Review this assessment after major architecture changes or at least quarterly.

## Proposed production acceptance criteria

These are starting targets and must be approved against product requirements:

| Area                      | Proposed gate                                                                          |
| ------------------------- | -------------------------------------------------------------------------------------- |
| Anonymous cache hit ratio | At least 95% for representative browsing traffic                                       |
| Unexpected HTTP errors    | Less than 0.1% during the target test, excluding intentional 4xx responses             |
| Inventory correctness     | Zero oversells and zero negative availability under concurrent checkout                |
| Idempotency               | One order/payment effect for repeated identical requests and events                    |
| Database                  | No D1 overload responses at target load plus agreed safety margin                      |
| Queue                     | No unbounded growth; oldest-message age remains within the business objective          |
| Recovery                  | Successful tested database restore and deployment rollback                             |
| Observability             | Route, database, cache, queue, and provider failures are correlated and alerting works |

Latency targets should be set separately for cached pages, dynamic reads, authentication, and
checkout. A single site-wide latency number hides the operations that matter most.

## Capacity-review checklist

- [ ] Paid production account and explicit budget are active.
- [ ] Workload model and peak request rate are approved.
- [ ] Production resources are isolated from staging and development.
- [ ] Public/private cache classification is documented and tested.
- [ ] Anonymous cache hit ratio meets the target.
- [ ] Inventory reservation and checkout idempotency pass concurrency tests.
- [ ] Payment callbacks are signed, idempotent, and reconcilable.
- [ ] Queue consumers, retries, idempotency, and dead-letter handling are operational.
- [ ] Edge rate limiting and abuse controls are active.
- [ ] D1 indexes, query budgets, replication, and consistency rules are documented.
- [ ] Storage growth and database migration thresholds are monitored.
- [ ] Dashboards, alerts, incident procedures, restore, and rollback are verified.
- [ ] Load-test evidence supports every published capacity claim.

## Maintaining this document

When an issue is completed, update its status in the issue register and add the implementation or
decision link beside the detailed finding. Do not delete resolved findings; retain them as evidence
of why the control exists. Re-check all Cloudflare limits and pricing links before using numeric
values in budgeting or contractual capacity statements.

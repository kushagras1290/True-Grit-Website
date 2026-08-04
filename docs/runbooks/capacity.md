# Capacity and scaling runbook

## Starting objectives

Approve these against product forecasts before claiming capacity:

| Workload           |               Starting target | Gate                                                                             |
| ------------------ | ----------------------------: | -------------------------------------------------------------------------------- |
| Anonymous browsing | 25 requests/second in staging | p95 under 750 ms; errors under 0.1%; cache-hit ratio trends to 95% after warm-up |
| Authentication     |             5 requests/second | p95 under 1.5 s; no `exceededCpu`; durable account limits remain effective       |
| Checkout           |             2 requests/second | p95 under 2 s; zero oversells; repeat requests create one order effect           |
| Queue              |            10 messages/second | oldest-message age under 60 s; no unbounded backlog                              |

Run `tests/load/public-browse.js` for releases that affect public reads, serialization, D1 access,
or cache policy. Run `tests/load/checkout-race.js` only against staging data prepared with exactly one
available unit. Store the k6 summary, commit SHA, Wrangler deployment version, Worker CPU percentiles,
D1 metrics, cache ratio, and queue age together as the capacity report.

## Data-growth triggers

Review monthly and begin migration planning when any trigger is reached:

- D1 reaches 65% of its current per-database storage limit within the forecast migration lead time.
- Sustained D1 overload or checkout write contention remains after caching and query optimization.
- Checkout p95 exceeds its objective for three consecutive representative tests.
- Analytical scans or exports measurably increase customer request latency.
- Queue oldest-message age exceeds five minutes for 15 minutes.

Keep products, customers, orders, inventory, and payments in the transactional database initially.
Move media, exports, and generated reports to R2; immutable high-volume events to an analytical
pipeline/R2; public derived data to the edge cache/KV; asynchronous work to Queues. Cache catalogue
reads before considering D1 partitioning. A partition requires an ownership key and a tested plan for
deployments, reporting, backup, restore, and cross-partition reconciliation.

## Runtime exit trigger

Compare Python Workers with the portable Uvicorn runtime using identical payloads and contract tests.
Plan a container/runtime migration if representative p95 CPU, dependency support, reliability, or
cost misses the approved objective in two consecutive release baselines after application-level
optimization.

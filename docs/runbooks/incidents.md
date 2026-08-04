# Incident runbook

## Severity

- SEV-1: checkout unavailable, data corruption, security breach, widespread outage
- SEV-2: major feature unavailable, payment degraded, high error rate
- SEV-3: limited feature issue with workaround
- SEV-4: cosmetic or low-impact defect

## Workflow

1. Acknowledge. 2. Assign incident lead. 3. Stop risky deployments. 4. Establish impact and
   timeline. 5. Mitigate first. 6. Preserve evidence and logs (request IDs correlate everything).
2. Communicate known facts. 8. Recover and verify. 9. Monitor. 10. Blameless post-incident
   review (impact, timeline, root causes, detection gaps, corrective actions with owners).

## High-severity patterns

- **Overselling / negative availability:** check conditional inventory update, affected-row
  verification, idempotency scope, reservation release. Never repair only the visible count —
  reconcile movements, reservations, orders, and source events.
- **Paid at provider, pending internally:** check webhook delivery, signature validation,
  provider event id uniqueness, queue retries. Corrections go through the reconciliation tool
  and are audited.

## Queue backlog or dead letters

Alert when oldest-message age exceeds 60 seconds for five minutes, consumer failures exceed 1%, or
the dead-letter queue is non-empty. Correlate `idempotencyKey` with `outbox_events.id`, structured
Worker logs, and `job_failures.event_id`. Fix the underlying provider/configuration error before
replaying. Replays are safe only while `processed_queue_messages` is intact; never delete its row to
force a financial or customer-communication side effect without an explicit reconciliation record.

## D1 overload or latency

Alert on overload errors immediately and on route-family/query p95 regressions for 10 minutes.
Inspect `d1_query`/`d1_batch` events by query fingerprint, consistency, `served_by_primary`, rows read,
and rows written. First reduce/cache public reads and stop analytical/admin scans. Do not route
checkout, inventory, payment, or immediately-after-write reads to an unconstrained replica.

## Cache leakage or stale content

For suspected leakage, disable the API Cache Rule, purge `truegrit-public-api`, and preserve the
request/response evidence. Any response with cookies, authorization, private-route prefixes,
`Set-Cookie`, non-200 status, or a write method must report `x-cache-policy: bypass` and
`Cache-Control: no-store`. For stale content, inspect the publishing outbox row, queue delivery,
cache-version KV marker, and tag purge before reducing TTLs globally.

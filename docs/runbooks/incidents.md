# Incident runbook

## Severity

- SEV-1: checkout unavailable, data corruption, security breach, widespread outage
- SEV-2: major feature unavailable, payment degraded, high error rate
- SEV-3: limited feature issue with workaround
- SEV-4: cosmetic or low-impact defect

## Workflow

1. Acknowledge. 2. Assign incident lead. 3. Stop risky deployments. 4. Establish impact and
timeline. 5. Mitigate first. 6. Preserve evidence and logs (request IDs correlate everything).
7. Communicate known facts. 8. Recover and verify. 9. Monitor. 10. Blameless post-incident
review (impact, timeline, root causes, detection gaps, corrective actions with owners).

## High-severity patterns

- **Overselling / negative availability:** check conditional inventory update, affected-row
  verification, idempotency scope, reservation release. Never repair only the visible count —
  reconcile movements, reservations, orders, and source events.
- **Paid at provider, pending internally:** check webhook delivery, signature validation,
  provider event id uniqueness, queue retries. Corrections go through the reconciliation tool
  and are audited.

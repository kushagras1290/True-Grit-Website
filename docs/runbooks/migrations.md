# Database migration runbook

## Rules

- Monotonic numbering, descriptive names, committed with the code that understands them.
- Applied local -> staging -> production. Never edit an applied production migration; create a
  corrective one.
- `python3 scripts/validate_migrations.py` must pass in CI (applies all migrations + seed to a
  clean SQLite database and runs foreign-key/integrity checks).

## Expand-contract for risky changes

1. Add new nullable column/table. 2. Deploy code writing old + new. 3. Backfill in bounded
batches. 4. Deploy code reading the new form. 5. Verify. 6. Remove the old field in a later
release. Never rename/drop a production column in the same release as its replacement.

## Production failure

Stop deployment. Capture output. Do not retry destructive statements. Determine whether the
transaction rolled back; check `wrangler d1 migrations list`. Choose roll-forward correction or
an approved D1 Time Travel recovery, then reconcile queue/email/payment side effects.

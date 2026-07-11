# ADR-001: Monorepo

## Decision

Use a pnpm monorepo for storefront, admin, shared UI, contracts, and configuration, with the
Python API and database assets in the same repository.

## Reason

Atomic contract changes, shared design system, single CI policy, easier coordinated releases.

## Tradeoff

CI path filtering and tooling require care.

# ADR-004: D1 as relational source of truth

## Decision

Use Cloudflare D1 for catalogue, CMS, identity, inventory, and commerce relational data.

## Reason

Cloudflare-native, SQL relational model, migrations, batch transactions, Time Travel recovery.

## Tradeoff

The SQLite/D1 operational model differs from a long-running PostgreSQL server; query and write
design must respect platform limits.

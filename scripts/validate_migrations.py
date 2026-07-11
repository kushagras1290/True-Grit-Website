#!/usr/bin/env python3
"""Validate D1 migrations against a clean SQLite database.

Mirrors what `wrangler d1 migrations apply --local` will do, without requiring
Cloudflare credentials. Applies every migration in order, runs foreign-key and
integrity checks, then applies the development seed.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "database" / "migrations"
SEED = ROOT / "database" / "seeds" / "development.sql"


def main() -> int:
    migrations = sorted(MIGRATIONS.glob("*.sql"))
    if not migrations:
        print("No migrations found", file=sys.stderr)
        return 1

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")

    for migration in migrations:
        sql = migration.read_text(encoding="utf-8")
        try:
            conn.executescript(sql)
        except sqlite3.Error as exc:
            print(f"FAILED {migration.name}: {exc}", file=sys.stderr)
            return 1
        print(f"applied {migration.name}")

    violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
    if violations:
        print(f"foreign_key_check violations: {violations}", file=sys.stderr)
        return 1

    integrity = conn.execute("PRAGMA integrity_check;").fetchone()
    if integrity != ("ok",):
        print(f"integrity_check failed: {integrity}", file=sys.stderr)
        return 1

    if SEED.exists():
        try:
            conn.executescript(SEED.read_text(encoding="utf-8"))
        except sqlite3.Error as exc:
            print(f"FAILED seed {SEED.name}: {exc}", file=sys.stderr)
            return 1
        print(f"applied seed {SEED.name}")

        violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if violations:
            print(f"seed foreign_key_check violations: {violations}", file=sys.stderr)
            return 1

    tables = conn.execute(
        "SELECT count(*) FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
    ).fetchone()[0]
    print(f"OK: {len(migrations)} migrations, {tables} tables, foreign keys clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

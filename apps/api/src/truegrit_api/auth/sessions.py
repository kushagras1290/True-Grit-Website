"""Session resolution.

Session cookies carry an opaque random token; only its SHA-256 hash is stored.
Disabled users and expired or revoked sessions never authenticate.
"""

from __future__ import annotations

import hashlib

from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.util.timeutil import utc_now_iso


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def resolve_session(db: Database, token: str) -> Principal | None:
    row = await db.fetch_one(
        """
        SELECT u.id, u.display_name, u.email, u.user_type
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
          AND s.revoked_at IS NULL
          AND s.expires_at > ?
          AND u.status = 'active'
        """,
        (hash_token(token), utc_now_iso()),
    )
    if row is None:
        return None
    permission_rows = await db.fetch_all(
        """
        SELECT DISTINCT p.key
        FROM user_roles ur
        JOIN role_permissions rp ON rp.role_id = ur.role_id
        JOIN permissions p ON p.id = rp.permission_id
        WHERE ur.user_id = ?
        """,
        (row["id"],),
    )
    return Principal(
        user_id=row["id"],
        display_name=row["display_name"],
        email=row["email"],
        user_type=row["user_type"],
        permissions=frozenset(entry["key"] for entry in permission_rows),
    )

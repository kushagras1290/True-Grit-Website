"""Read-only queries for customer delivery addresses (`addresses`, migration
0005). Writes live in `services.addresses`, matching every other repository
in this codebase.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database

_COLUMNS = """
  id, user_id, label, recipient_name, phone_e164, line1, line2, city, state,
  postal_code, country_code, is_default_delivery, is_default_billing,
  created_at, updated_at
"""


class AddressRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_for_customer(self, user_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            f"""
            SELECT {_COLUMNS} FROM addresses
            WHERE user_id = ? AND archived_at IS NULL
            ORDER BY is_default_delivery DESC, created_at DESC
            """,
            (user_id,),
        )

    async def get_owned(self, address_id: str, user_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            f"""
            SELECT {_COLUMNS} FROM addresses
            WHERE id = ? AND user_id = ? AND archived_at IS NULL
            """,
            (address_id, user_id),
        )

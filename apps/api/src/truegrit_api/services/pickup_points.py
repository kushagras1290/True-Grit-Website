"""Local pickup points — an alternative to home delivery.

CRUD for admin, active-list for the storefront checkout. When pickup is
chosen, the delivery fee is waived. The existing fulfilment states are reused:
``packed`` means ready for pickup and ``fulfilled`` means collected.
"""

from __future__ import annotations

import json
from contextlib import suppress
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    address = {}
    with suppress(json.JSONDecodeError, TypeError):
        address = json.loads(row.get("address_json") or "{}")
    return {
        "id": row["id"],
        "name": row["name"],
        "address": address,
        "hours": row.get("hours"),
        "phone": row.get("phone"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "status": row["status"],
        "sortOrder": row.get("sort_order", 0),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


async def list_pickup_points(
    db: Database, *, active_only: bool = False, limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    where = " WHERE status = 'active'" if active_only else ""
    total_row = await db.fetch_one(
        f"SELECT COUNT(*) AS cnt FROM pickup_points{where}",
    )
    rows = await db.fetch_all(
        f"""
        SELECT * FROM pickup_points{where}
        ORDER BY sort_order ASC, created_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    return {
        "items": [_row_to_dict(row) for row in rows],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


async def get_pickup_point(db: Database, point_id: str) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM pickup_points WHERE id = ?", (point_id,))
    if row is None:
        raise NotFoundError("Pickup point not found.")
    return _row_to_dict(row)


async def create_pickup_point(
    db: Database, actor: Principal, request_id: str,
    *, name: str, address: dict[str, Any] | None = None,
    hours: str | None = None, phone: str | None = None,
    latitude: float | None = None, longitude: float | None = None,
    sort_order: int = 0,
) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValidationAppError("Pickup point name is required.")
    point_id = new_id("pup")
    now = utc_now_iso()
    address_json = json.dumps(address or {})
    await db.batch([
        (
            "INSERT INTO pickup_points"
            " (id, name, address_json, hours, phone, latitude, longitude,"
            "  status, sort_order, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)",
            (
                point_id, clean_name, address_json,
                (hours or "").strip() or None,
                (phone or "").strip() or None,
                latitude, longitude, sort_order, now, now,
            ),
        ),
        audit_statement(
            action="pickup_point.created",
            entity_type="pickup_point",
            entity_id=point_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"name": clean_name},
        ),
    ])
    return await get_pickup_point(db, point_id)


async def update_pickup_point(
    db: Database, actor: Principal, request_id: str,
    point_id: str, *, updates: dict[str, Any],
) -> dict[str, Any]:
    existing = await db.fetch_one("SELECT * FROM pickup_points WHERE id = ?", (point_id,))
    if existing is None:
        raise NotFoundError("Pickup point not found.")

    sets: list[str] = []
    params: list[Any] = []
    changed: dict[str, Any] = {}

    if "name" in updates:
        clean = str(updates["name"]).strip()
        if not clean:
            raise ValidationAppError("Pickup point name is required.")
        sets.append("name = ?")
        params.append(clean)
        changed["name"] = clean

    if "address" in updates:
        sets.append("address_json = ?")
        params.append(json.dumps(updates["address"] or {}))
        changed["address"] = updates["address"]

    if "hours" in updates:
        sets.append("hours = ?")
        params.append((str(updates["hours"]).strip()) or None)
        changed["hours"] = updates["hours"]

    if "phone" in updates:
        sets.append("phone = ?")
        params.append((str(updates["phone"]).strip()) or None)
        changed["phone"] = updates["phone"]

    if "latitude" in updates:
        sets.append("latitude = ?")
        params.append(updates["latitude"])
    if "longitude" in updates:
        sets.append("longitude = ?")
        params.append(updates["longitude"])

    if "status" in updates:
        status = updates["status"]
        if status not in ("active", "inactive"):
            raise ValidationAppError("Status must be 'active' or 'inactive'.")
        sets.append("status = ?")
        params.append(status)
        changed["status"] = status

    if "sortOrder" in updates:
        sets.append("sort_order = ?")
        params.append(int(updates["sortOrder"]))

    if not sets:
        return await get_pickup_point(db, point_id)

    now = utc_now_iso()
    sets.append("updated_at = ?")
    params.append(now)
    params.append(point_id)

    await db.batch([
        (f"UPDATE pickup_points SET {', '.join(sets)} WHERE id = ?", tuple(params)),
        audit_statement(
            action="pickup_point.updated",
            entity_type="pickup_point",
            entity_id=point_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after=changed,
        ),
    ])
    return await get_pickup_point(db, point_id)


async def delete_pickup_point(
    db: Database, actor: Principal, request_id: str, point_id: str,
) -> None:
    existing = await db.fetch_one("SELECT id FROM pickup_points WHERE id = ?", (point_id,))
    if existing is None:
        raise NotFoundError("Pickup point not found.")
    now = utc_now_iso()
    await db.batch([
        ("DELETE FROM pickup_points WHERE id = ?", (point_id,)),
        audit_statement(
            action="pickup_point.deleted",
            entity_type="pickup_point",
            entity_id=point_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"deleted": True},
        ),
    ])

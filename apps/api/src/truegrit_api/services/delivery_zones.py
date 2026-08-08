"""Delivery zones and time-slot management.

When enabled, checkout validates the customer's postal code against defined
zones.  Each zone can override the global delivery fee, set a lead time, and
define available delivery slots (day + time window).  Unserviceable postal
codes are rejected at checkout with a clear error.
"""

from __future__ import annotations

import datetime
import json
from contextlib import suppress
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def _zone_row(row: dict[str, Any]) -> dict[str, Any]:
    postal_codes: list[str] = []
    with suppress(json.JSONDecodeError, TypeError):
        postal_codes = json.loads(row.get("postal_codes_json") or "[]")
    return {
        "id": row["id"],
        "name": row["name"],
        "postalCodes": postal_codes,
        "feeOverrideMinor": row.get("fee_override_minor"),
        "freeThresholdOverrideMinor": row.get("free_threshold_override_minor"),
        "leadTimeHours": row.get("lead_time_hours", 24),
        "status": row["status"],
        "sortOrder": row.get("sort_order", 0),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _slot_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "zoneId": row["zone_id"],
        "dayOfWeek": row["day_of_week"],
        "dayName": _DAYS[row["day_of_week"]] if 0 <= row["day_of_week"] <= 6 else "?",
        "startTime": row["start_time"],
        "endTime": row["end_time"],
        "maxOrders": row["max_orders"],
        "status": row["status"],
    }


# ── Zone matching ──────────────────────────────────────────────────────────

def _matches_pattern(postal_code: str, pattern: str) -> bool:
    """Simple wildcard match: '560*' matches '560001', exact match otherwise."""
    clean_code = postal_code.strip().upper()
    clean_pattern = pattern.strip().upper()
    if clean_pattern.endswith("*"):
        return clean_code.startswith(clean_pattern[:-1])
    return clean_code == clean_pattern


async def find_zone_for_postal_code(
    db: Database, postal_code: str,
) -> dict[str, Any] | None:
    """Find the matching delivery zone for a postal code, or None."""
    zones = await db.fetch_all(
        "SELECT * FROM delivery_zones WHERE status = 'active' ORDER BY sort_order ASC",
    )
    for zone in zones:
        patterns: list[str] = []
        try:
            patterns = json.loads(zone.get("postal_codes_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        for pattern in patterns:
            if _matches_pattern(postal_code, pattern):
                return _zone_row(zone)
    return None


async def check_delivery(
    db: Database, postal_code: str,
) -> dict[str, Any]:
    """Public delivery check: returns zone info + available slots."""
    zone = await find_zone_for_postal_code(db, postal_code)
    if zone is None:
        return {
            "serviceable": False,
            "zone": None,
            "message": "Sorry, we don't deliver to this area yet.",
        }
    slots = await db.fetch_all(
        "SELECT * FROM delivery_slots WHERE zone_id = ? AND status = 'active'"
        " ORDER BY day_of_week ASC, start_time ASC",
        (zone["id"],),
    )
    return {
        "serviceable": True,
        "zone": zone,
        "slots": [_slot_row(s) for s in slots],
    }


async def get_available_slots(
    db: Database, zone_id: str, delivery_date: str,
) -> list[dict[str, Any]]:
    """Available slots for a zone on a given date, with capacity check."""
    # Parse the date to find day of week (0=Sunday)
    try:
        dt = datetime.date.fromisoformat(delivery_date)
        # Python: Monday=0..Sunday=6. Our schema: Sunday=0..Saturday=6
        day_of_week = (dt.weekday() + 1) % 7
    except ValueError:
        return []

    slots = await db.fetch_all(
        """
        SELECT ds.*,
               COALESCE((SELECT COUNT(*) FROM delivery_slot_bookings dsb
                         WHERE dsb.slot_id = ds.id AND dsb.delivery_date = ?), 0) AS booked
        FROM delivery_slots ds
        WHERE ds.zone_id = ? AND ds.day_of_week = ? AND ds.status = 'active'
        ORDER BY ds.start_time ASC
        """,
        (delivery_date, zone_id, day_of_week),
    )
    return [
        {
            **_slot_row(s),
            "booked": int(s["booked"]),
            "available": int(s["booked"]) < int(s["max_orders"]),
        }
        for s in slots
    ]


async def book_delivery_slot(
    db: Database, order_id: str, slot_id: str, delivery_date: str,
) -> str:
    """Book a delivery slot for an order. Returns the booking ID."""
    slot = await db.fetch_one(
        "SELECT * FROM delivery_slots WHERE id = ? AND status = 'active'",
        (slot_id,),
    )
    if slot is None:
        raise ValidationAppError("That delivery slot is not available.")

    booked = await db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM delivery_slot_bookings"
        " WHERE slot_id = ? AND delivery_date = ?",
        (slot_id, delivery_date),
    )
    if booked and int(booked["cnt"]) >= int(slot["max_orders"]):
        raise ValidationAppError("That delivery slot is fully booked for this date.")

    booking_id = new_id("dsb")
    now = utc_now_iso()
    await db.execute(
        "INSERT INTO delivery_slot_bookings"
        " (id, order_id, slot_id, delivery_date, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (booking_id, order_id, slot_id, delivery_date, now),
    )
    return booking_id


async def validate_slot_selection(
    db: Database,
    *,
    zone_id: str,
    slot_id: str,
    delivery_date: str,
) -> dict[str, Any]:
    """Validate ownership, weekday, lead time and remaining capacity."""
    try:
        selected_date = datetime.date.fromisoformat(delivery_date)
    except ValueError as exc:
        raise ValidationAppError("Delivery date must use YYYY-MM-DD.") from exc
    slot = await db.fetch_one(
        """
        SELECT ds.*, dz.lead_time_hours
        FROM delivery_slots ds
        JOIN delivery_zones dz ON dz.id = ds.zone_id
        WHERE ds.id = ? AND ds.zone_id = ?
          AND ds.status = 'active' AND dz.status = 'active'
        """,
        (slot_id, zone_id),
    )
    if slot is None:
        raise ValidationAppError("That delivery slot is not available in your area.")
    day_of_week = (selected_date.weekday() + 1) % 7
    if int(slot["day_of_week"]) != day_of_week:
        raise ValidationAppError("That delivery slot does not run on the selected date.")
    try:
        start_time = datetime.time.fromisoformat(str(slot["start_time"]))
    except ValueError as exc:
        raise ValidationAppError("That delivery slot is configured incorrectly.") from exc
    selected_start = datetime.datetime.combine(
        selected_date, start_time, tzinfo=datetime.UTC
    )
    earliest = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        hours=int(slot["lead_time_hours"])
    )
    if selected_start < earliest:
        raise ValidationAppError("That delivery slot is inside the required lead time.")
    booked = await db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM delivery_slot_bookings"
        " WHERE slot_id = ? AND delivery_date = ?",
        (slot_id, delivery_date),
    )
    if booked is not None and int(booked["cnt"]) >= int(slot["max_orders"]):
        raise ValidationAppError("That delivery slot is fully booked for this date.")
    return _slot_row(slot)


# ── Admin CRUD ─────────────────────────────────────────────────────────────

async def list_zones(
    db: Database, *, limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    total_row = await db.fetch_one("SELECT COUNT(*) AS cnt FROM delivery_zones")
    rows = await db.fetch_all(
        "SELECT * FROM delivery_zones ORDER BY sort_order ASC, created_at DESC"
        " LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return {
        "items": [_zone_row(row) for row in rows],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


async def get_zone(db: Database, zone_id: str) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM delivery_zones WHERE id = ?", (zone_id,))
    if row is None:
        raise NotFoundError("Delivery zone not found.")
    return _zone_row(row)


async def create_zone(
    db: Database, actor: Principal, request_id: str,
    *, name: str, postal_codes: list[str] | None = None,
    fee_override_minor: int | None = None,
    free_threshold_override_minor: int | None = None,
    lead_time_hours: int = 24, sort_order: int = 0,
) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValidationAppError("Zone name is required.")
    zone_id = new_id("dz")
    now = utc_now_iso()
    await db.batch([
        (
            "INSERT INTO delivery_zones"
            " (id, name, postal_codes_json, fee_override_minor,"
            "  free_threshold_override_minor, lead_time_hours,"
            "  status, sort_order, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)",
            (
                zone_id, clean_name,
                json.dumps(postal_codes or []),
                fee_override_minor, free_threshold_override_minor,
                lead_time_hours, sort_order, now, now,
            ),
        ),
        audit_statement(
            action="delivery_zone.created",
            entity_type="delivery_zone",
            entity_id=zone_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"name": clean_name},
        ),
    ])
    return await get_zone(db, zone_id)


async def update_zone(
    db: Database, actor: Principal, request_id: str,
    zone_id: str, *, updates: dict[str, Any],
) -> dict[str, Any]:
    existing = await db.fetch_one(
        "SELECT * FROM delivery_zones WHERE id = ?", (zone_id,),
    )
    if existing is None:
        raise NotFoundError("Delivery zone not found.")

    sets: list[str] = []
    params: list[Any] = []
    changed: dict[str, Any] = {}

    if "name" in updates:
        clean = str(updates["name"]).strip()
        if not clean:
            raise ValidationAppError("Zone name is required.")
        sets.append("name = ?")
        params.append(clean)
        changed["name"] = clean

    if "postalCodes" in updates:
        codes = updates["postalCodes"] if isinstance(updates["postalCodes"], list) else []
        sets.append("postal_codes_json = ?")
        params.append(json.dumps(codes))
        changed["postalCodes"] = codes

    if "feeOverrideMinor" in updates:
        sets.append("fee_override_minor = ?")
        params.append(updates["feeOverrideMinor"])
        changed["feeOverrideMinor"] = updates["feeOverrideMinor"]

    if "freeThresholdOverrideMinor" in updates:
        sets.append("free_threshold_override_minor = ?")
        params.append(updates["freeThresholdOverrideMinor"])
        changed["freeThresholdOverrideMinor"] = updates["freeThresholdOverrideMinor"]

    if "leadTimeHours" in updates:
        sets.append("lead_time_hours = ?")
        params.append(int(updates["leadTimeHours"]))
        changed["leadTimeHours"] = updates["leadTimeHours"]

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
        return await get_zone(db, zone_id)

    now = utc_now_iso()
    sets.append("updated_at = ?")
    params.append(now)
    params.append(zone_id)

    await db.batch([
        (f"UPDATE delivery_zones SET {', '.join(sets)} WHERE id = ?", tuple(params)),
        audit_statement(
            action="delivery_zone.updated",
            entity_type="delivery_zone",
            entity_id=zone_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after=changed,
        ),
    ])
    return await get_zone(db, zone_id)


async def delete_zone(
    db: Database, actor: Principal, request_id: str, zone_id: str,
) -> None:
    existing = await db.fetch_one(
        "SELECT id FROM delivery_zones WHERE id = ?", (zone_id,),
    )
    if existing is None:
        raise NotFoundError("Delivery zone not found.")
    now = utc_now_iso()
    await db.batch([
        ("DELETE FROM delivery_zones WHERE id = ?", (zone_id,)),
        audit_statement(
            action="delivery_zone.deleted",
            entity_type="delivery_zone",
            entity_id=zone_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"deleted": True},
        ),
    ])


# ── Slot CRUD ──────────────────────────────────────────────────────────────

async def list_slots(db: Database, zone_id: str) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        "SELECT * FROM delivery_slots WHERE zone_id = ?"
        " ORDER BY day_of_week ASC, start_time ASC",
        (zone_id,),
    )
    return [_slot_row(row) for row in rows]


async def create_slot(
    db: Database, actor: Principal, request_id: str,
    *, zone_id: str, day_of_week: int, start_time: str,
    end_time: str, max_orders: int = 20,
) -> dict[str, Any]:
    zone = await db.fetch_one(
        "SELECT id FROM delivery_zones WHERE id = ?", (zone_id,),
    )
    if zone is None:
        raise NotFoundError("Delivery zone not found.")
    if not (0 <= day_of_week <= 6):
        raise ValidationAppError("Day of week must be 0-6 (Sunday-Saturday).")
    if start_time >= end_time:
        raise ValidationAppError("Delivery slot start time must be before its end time.")
    if max_orders < 1:
        raise ValidationAppError("Delivery slot capacity must be at least one order.")
    slot_id = new_id("ds")
    now = utc_now_iso()
    await db.batch([
        (
            "INSERT INTO delivery_slots"
            " (id, zone_id, day_of_week, start_time, end_time, max_orders, status)"
            " VALUES (?, ?, ?, ?, ?, ?, 'active')",
            (slot_id, zone_id, day_of_week, start_time, end_time, max_orders),
        ),
        audit_statement(
            action="delivery_slot.created",
            entity_type="delivery_slot",
            entity_id=slot_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"zoneId": zone_id, "dayOfWeek": day_of_week,
                   "startTime": start_time, "endTime": end_time},
        ),
    ])
    row = await db.fetch_one("SELECT * FROM delivery_slots WHERE id = ?", (slot_id,))
    return _slot_row(row)  # type: ignore[arg-type]


async def update_slot(
    db: Database, actor: Principal, request_id: str,
    slot_id: str, *, updates: dict[str, Any],
) -> dict[str, Any]:
    existing = await db.fetch_one(
        "SELECT * FROM delivery_slots WHERE id = ?", (slot_id,),
    )
    if existing is None:
        raise NotFoundError("Delivery slot not found.")

    sets: list[str] = []
    params: list[Any] = []

    if "dayOfWeek" in updates:
        if not 0 <= int(updates["dayOfWeek"]) <= 6:
            raise ValidationAppError("Day of week must be 0-6 (Sunday-Saturday).")
        sets.append("day_of_week = ?")
        params.append(int(updates["dayOfWeek"]))
    if "startTime" in updates:
        sets.append("start_time = ?")
        params.append(updates["startTime"])
    if "endTime" in updates:
        sets.append("end_time = ?")
        params.append(updates["endTime"])
    if "maxOrders" in updates:
        if int(updates["maxOrders"]) < 1:
            raise ValidationAppError("Delivery slot capacity must be at least one order.")
        sets.append("max_orders = ?")
        params.append(int(updates["maxOrders"]))
    if "status" in updates:
        if updates["status"] not in ("active", "inactive"):
            raise ValidationAppError("Status must be 'active' or 'inactive'.")
        sets.append("status = ?")
        params.append(updates["status"])

    next_start = str(updates.get("startTime", existing["start_time"]))
    next_end = str(updates.get("endTime", existing["end_time"]))
    if next_start >= next_end:
        raise ValidationAppError("Delivery slot start time must be before its end time.")

    if not sets:
        return _slot_row(existing)

    params.append(slot_id)
    await db.execute(
        f"UPDATE delivery_slots SET {', '.join(sets)} WHERE id = ?",
        tuple(params),
    )
    row = await db.fetch_one("SELECT * FROM delivery_slots WHERE id = ?", (slot_id,))
    return _slot_row(row)  # type: ignore[arg-type]


async def delete_slot(
    db: Database, actor: Principal, request_id: str, slot_id: str,
) -> None:
    existing = await db.fetch_one(
        "SELECT id FROM delivery_slots WHERE id = ?", (slot_id,),
    )
    if existing is None:
        raise NotFoundError("Delivery slot not found.")
    now = utc_now_iso()
    await db.batch([
        ("DELETE FROM delivery_slots WHERE id = ?", (slot_id,)),
        audit_statement(
            action="delivery_slot.deleted",
            entity_type="delivery_slot",
            entity_id=slot_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"deleted": True},
        ),
    ])

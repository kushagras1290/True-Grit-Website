"""Inventory adjustments.

An adjustment is never a bare UPDATE: it updates the stock level, records an
immutable movement, and writes an audit row - all in one batch. Available stock
stays derived (on_hand minus reserved); we only ever move on_hand, and never
below what is already reserved.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

# Reason codes double as movement types (all are valid `inventory_movements` types).
VALID_REASONS = frozenset({"receipt", "manual_adjustment", "write_off", "correction"})
_MIN_NOTE_LENGTH = 5
_MAX_NOTE_LENGTH = 300


async def adjust_inventory(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    variant_id: str,
    quantity_delta: int,
    reason_code: str,
    note: str,
    location_id: str | None = None,
) -> dict[str, Any]:
    if reason_code not in VALID_REASONS:
        raise ValidationAppError("Unknown adjustment reason.")
    if quantity_delta == 0:
        raise ValidationAppError("Adjustment delta cannot be zero.")
    note = (note or "").strip()
    if len(note) < _MIN_NOTE_LENGTH:
        raise ValidationAppError("A note of at least 5 characters is required for the audit trail.")
    if len(note) > _MAX_NOTE_LENGTH:
        raise ValidationAppError("Note must be at most 300 characters.")

    level = await _resolve_level(db, variant_id, location_id, allow_create=True)
    new_on_hand = level["on_hand"] + quantity_delta
    if new_on_hand < 0:
        raise ValidationAppError("Adjustment would drive on-hand below zero.")
    if new_on_hand < level["reserved"]:
        raise ValidationAppError(f"On-hand cannot drop below reserved ({level['reserved']} units).")

    resolved_location = level["location_id"]
    now = utc_now_iso()
    level_statement = (
        (
            "INSERT INTO inventory_levels"
            " (variant_id, location_id, on_hand, reserved, reorder_threshold, version, updated_at)"
            " VALUES (?, ?, ?, 0, 0, 1, ?)",
            (variant_id, resolved_location, new_on_hand, now),
        )
        if level.get("new")
        else (
            "UPDATE inventory_levels SET on_hand = ?, version = version + 1, updated_at = ?"
            " WHERE variant_id = ? AND location_id = ?",
            (new_on_hand, now, variant_id, resolved_location),
        )
    )
    await db.batch(
        [
            level_statement,
            (
                "INSERT INTO inventory_movements"
                " (id, variant_id, location_id, movement_type, quantity_delta,"
                "  reason_code, note, actor_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    new_id("imv"),
                    variant_id,
                    resolved_location,
                    reason_code,
                    quantity_delta,
                    reason_code,
                    note,
                    actor.user_id,
                    now,
                ),
            ),
            audit_statement(
                action="inventory.adjusted",
                entity_type="inventory_level",
                entity_id=variant_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"on_hand": level["on_hand"]},
                after={"on_hand": new_on_hand, "delta": quantity_delta, "reason": reason_code},
            ),
        ]
    )
    return {
        "variantId": variant_id,
        "locationId": resolved_location,
        "onHand": new_on_hand,
        "reserved": level["reserved"],
        "available": new_on_hand - level["reserved"],
    }


async def clear_inventory_levels(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    variant_ids: list[str],
    note: str,
) -> dict[str, Any]:
    note = (note or "").strip()
    if len(note) < _MIN_NOTE_LENGTH:
        raise ValidationAppError("A note of at least 5 characters is required for the audit trail.")
    if len(note) > _MAX_NOTE_LENGTH:
        raise ValidationAppError("Note must be at most 300 characters.")

    unique_variant_ids = list(dict.fromkeys(variant_ids))
    if not unique_variant_ids:
        raise ValidationAppError("Select at least one inventory row.")

    now = utc_now_iso()
    statements: list[tuple[str, tuple[Any, ...]]] = []
    cleared: list[str] = []
    for variant_id in unique_variant_ids:
        level = await _resolve_level(db, variant_id, None)
        new_on_hand = level["reserved"]
        delta = new_on_hand - level["on_hand"]
        resolved_location = level["location_id"]
        statements.append(
            (
                "UPDATE inventory_levels SET on_hand = ?, version = version + 1, updated_at = ?"
                " WHERE variant_id = ? AND location_id = ?",
                (new_on_hand, now, variant_id, resolved_location),
            )
        )
        if delta != 0:
            statements.append(
                (
                    "INSERT INTO inventory_movements"
                    " (id, variant_id, location_id, movement_type, quantity_delta,"
                    "  reason_code, note, actor_id, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        new_id("imv"),
                        variant_id,
                        resolved_location,
                        "write_off",
                        delta,
                        "bulk_clear",
                        note,
                        actor.user_id,
                        now,
                    ),
                )
            )
        statements.append(
            audit_statement(
                action="inventory.cleared",
                entity_type="inventory_level",
                entity_id=variant_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"on_hand": level["on_hand"], "reserved": level["reserved"]},
                after={"on_hand": new_on_hand, "reserved": level["reserved"], "delta": delta},
            )
        )
        cleared.append(variant_id)

    await db.batch(statements)
    return {"clearedIds": cleared, "count": len(cleared)}


async def _resolve_level(
    db: Database, variant_id: str, location_id: str | None, *, allow_create: bool = False
) -> dict[str, Any]:
    if location_id:
        level = await db.fetch_one(
            "SELECT location_id, on_hand, reserved FROM inventory_levels"
            " WHERE variant_id = ? AND location_id = ?",
            (variant_id, location_id),
        )
        if level is None:
            raise NotFoundError("No stock level for that variant at that location.")
        return level

    levels = await db.fetch_all(
        "SELECT location_id, on_hand, reserved FROM inventory_levels WHERE variant_id = ?",
        (variant_id,),
    )
    if not levels:
        if allow_create:
            location = await db.fetch_one(
                "SELECT id FROM inventory_locations WHERE active = 1"
                " ORDER BY created_at, id LIMIT 1"
            )
            if location is None:
                raise NotFoundError("No active inventory location exists.")
            return {"location_id": location["id"], "on_hand": 0, "reserved": 0, "new": True}
        raise NotFoundError("No stock level exists for that variant.")
    if len(levels) > 1:
        raise ValidationAppError("This variant has multiple locations; specify one.")
    return levels[0]

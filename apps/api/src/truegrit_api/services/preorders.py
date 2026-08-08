"""Seasonal pre-orders and harvest calendar.

Customers reserve a not-yet-harvested product ahead of its expected harvest
window.  Charged at order time, fulfilled when the harvest actually comes in.
Pre-orders reserve against a *future* harvest, not current on_hand stock --
the normal inventory_levels reservation path is skipped.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso


def _validated_date(value: str, label: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValidationAppError(f"{label} must be a valid YYYY-MM-DD date.") from exc


def _window_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "productId": row["product_id"],
        "productName": row.get("product_name"),
        "title": row.get("title"),
        "expectedStart": row["expected_start"],
        "expectedEnd": row["expected_end"],
        "actualStart": row.get("actual_start"),
        "actualEnd": row.get("actual_end"),
        "maxPreorders": row.get("max_preorders"),
        "status": row["status"],
        "notes": row.get("notes"),
        "currentPreorders": row.get("current_preorders", 0),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _preorder_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "orderId": row["order_id"],
        "orderReference": row.get("public_reference"),
        "harvestWindowId": row["harvest_window_id"],
        "productId": row["product_id"],
        "productName": row.get("product_name"),
        "variantId": row["variant_id"],
        "quantity": row["quantity"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "fulfilledAt": row.get("fulfilled_at"),
    }


# ── Harvest Windows ────────────────────────────────────────────────────────


async def list_harvest_windows(
    db: Database,
    *,
    product_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conditions: list[str] = []
    params: list[Any] = []
    if product_id:
        conditions.append("hw.product_id = ?")
        params.append(product_id)
    if status:
        conditions.append("hw.status = ?")
        params.append(status)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    total_row = await db.fetch_one(
        f"SELECT COUNT(*) AS cnt FROM harvest_windows hw{where}",
        tuple(params),
    )
    rows = await db.fetch_all(
        f"""
        SELECT hw.*, p.name AS product_name,
               COALESCE((SELECT SUM(quantity) FROM preorders po
                         WHERE po.harvest_window_id = hw.id
                         AND po.status IN ('reserved', 'ready')), 0) AS current_preorders
        FROM harvest_windows hw
        JOIN products p ON p.id = hw.product_id
        {where}
        ORDER BY hw.expected_start ASC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return {
        "items": [_window_row(row) for row in rows],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


async def get_harvest_window(db: Database, window_id: str) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        SELECT hw.*, p.name AS product_name,
               COALESCE((SELECT SUM(quantity) FROM preorders po
                         WHERE po.harvest_window_id = hw.id
                         AND po.status IN ('reserved', 'ready')), 0) AS current_preorders
        FROM harvest_windows hw
        JOIN products p ON p.id = hw.product_id
        WHERE hw.id = ?
        """,
        (window_id,),
    )
    if row is None:
        raise NotFoundError("Harvest window not found.")
    return _window_row(row)


async def create_harvest_window(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    product_id: str,
    expected_start: str,
    expected_end: str,
    title: str | None = None,
    max_preorders: int | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    product = await db.fetch_one("SELECT id FROM products WHERE id = ?", (product_id,))
    if product is None:
        raise NotFoundError("Product not found.")
    expected_start = _validated_date(expected_start, "Expected start")
    expected_end = _validated_date(expected_end, "Expected end")
    if expected_start > expected_end:
        raise ValidationAppError("Expected start must be before expected end.")
    window_id = new_id("hw")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO harvest_windows"
                " (id, product_id, title, expected_start, expected_end,"
                "  max_preorders, notes, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'upcoming', ?, ?)",
                (
                    window_id,
                    product_id,
                    (title or "").strip() or None,
                    expected_start,
                    expected_end,
                    max_preorders,
                    (notes or "").strip() or None,
                    now,
                    now,
                ),
            ),
            audit_statement(
                action="harvest_window.created",
                entity_type="harvest_window",
                entity_id=window_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={
                    "productId": product_id,
                    "expectedStart": expected_start,
                    "expectedEnd": expected_end,
                },
            ),
        ]
    )
    return await get_harvest_window(db, window_id)


async def update_harvest_window(
    db: Database,
    actor: Principal,
    request_id: str,
    window_id: str,
    *,
    updates: dict[str, Any],
) -> dict[str, Any]:
    existing = await db.fetch_one(
        "SELECT * FROM harvest_windows WHERE id = ?",
        (window_id,),
    )
    if existing is None:
        raise NotFoundError("Harvest window not found.")

    expected_start = updates.get("expectedStart", existing["expected_start"])
    expected_end = updates.get("expectedEnd", existing["expected_end"])
    expected_start = _validated_date(expected_start, "Expected start")
    expected_end = _validated_date(expected_end, "Expected end")
    if expected_start > expected_end:
        raise ValidationAppError("Expected start must be before expected end.")

    actual_start = updates.get("actualStart", existing.get("actual_start"))
    actual_end = updates.get("actualEnd", existing.get("actual_end"))
    if actual_start:
        actual_start = _validated_date(actual_start, "Actual start")
    if actual_end:
        actual_end = _validated_date(actual_end, "Actual end")
    if actual_start and actual_end and actual_start > actual_end:
        raise ValidationAppError("Actual start must be before actual end.")

    sets: list[str] = []
    params: list[Any] = []
    changed: dict[str, Any] = {}

    for field, col in [
        ("title", "title"),
        ("expectedStart", "expected_start"),
        ("expectedEnd", "expected_end"),
        ("actualStart", "actual_start"),
        ("actualEnd", "actual_end"),
        ("notes", "notes"),
    ]:
        if field in updates:
            sets.append(f"{col} = ?")
            val = str(updates[field]).strip() if updates[field] else None
            params.append(val)
            changed[field] = val

    if "maxPreorders" in updates:
        next_capacity = updates["maxPreorders"]
        if next_capacity is not None:
            reserved = await db.fetch_one(
                "SELECT COALESCE(SUM(quantity), 0) AS total FROM preorders"
                " WHERE harvest_window_id = ? AND status IN ('reserved', 'ready')",
                (window_id,),
            )
            if reserved and int(reserved["total"]) > int(next_capacity):
                raise ConflictError(
                    "Pre-order capacity cannot be lower than the quantity already reserved."
                )
        sets.append("max_preorders = ?")
        params.append(next_capacity)
        changed["maxPreorders"] = next_capacity

    if "status" in updates:
        status = updates["status"]
        valid = ("upcoming", "active", "harvesting", "completed", "cancelled")
        if status not in valid:
            raise ValidationAppError(f"Status must be one of: {', '.join(valid)}")
        sets.append("status = ?")
        params.append(status)
        changed["status"] = status

    if not sets:
        return await get_harvest_window(db, window_id)

    now = utc_now_iso()
    sets.append("updated_at = ?")
    params.append(now)
    params.append(window_id)

    await db.batch(
        [
            (f"UPDATE harvest_windows SET {', '.join(sets)} WHERE id = ?", tuple(params)),
            audit_statement(
                action="harvest_window.updated",
                entity_type="harvest_window",
                entity_id=window_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after=changed,
            ),
        ]
    )
    return await get_harvest_window(db, window_id)


async def delete_harvest_window(
    db: Database,
    actor: Principal,
    request_id: str,
    window_id: str,
) -> None:
    existing = await db.fetch_one(
        "SELECT id FROM harvest_windows WHERE id = ?",
        (window_id,),
    )
    if existing is None:
        raise NotFoundError("Harvest window not found.")
    active_preorders = await db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM preorders"
        " WHERE harvest_window_id = ? AND status IN ('reserved', 'ready')",
        (window_id,),
    )
    if active_preorders and int(active_preorders["cnt"]) > 0:
        raise ConflictError("Cannot delete a harvest window with active pre-orders.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM harvest_windows WHERE id = ?", (window_id,)),
            audit_statement(
                action="harvest_window.deleted",
                entity_type="harvest_window",
                entity_id=window_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"deleted": True},
            ),
        ]
    )


# ── Pre-orders ─────────────────────────────────────────────────────────────


async def get_active_harvest_window_for_product(
    db: Database,
    product_id: str,
    *,
    quantity: int = 1,
) -> dict[str, Any] | None:
    """Return the currently active/upcoming harvest window for a product,
    if any.  Used at checkout to detect pre-order eligible products."""
    row = await db.fetch_one(
        """
        SELECT hw.*, p.name AS product_name,
               COALESCE((SELECT SUM(quantity) FROM preorders po
                         WHERE po.harvest_window_id = hw.id
                         AND po.status IN ('reserved', 'ready')), 0) AS current_preorders
        FROM harvest_windows hw
        JOIN products p ON p.id = hw.product_id
        WHERE hw.product_id = ? AND hw.status IN ('upcoming', 'active')
        ORDER BY hw.expected_start ASC
        LIMIT 1
        """,
        (product_id,),
    )
    if row is None:
        return None
    if row.get("max_preorders") is not None and (
        int(row["current_preorders"]) + quantity > int(row["max_preorders"])
    ):
        return None  # capacity full
    return _window_row(row)


async def create_preorder(
    db: Database,
    order_id: str,
    harvest_window_id: str,
    product_id: str,
    variant_id: str,
    quantity: int,
) -> str:
    preorder_id = new_id("po")
    now = utc_now_iso()
    await db.execute(
        "INSERT INTO preorders"
        " (id, order_id, harvest_window_id, product_id, variant_id,"
        "  quantity, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 'reserved', ?)",
        (preorder_id, order_id, harvest_window_id, product_id, variant_id, quantity, now),
    )
    return preorder_id


async def list_preorders(
    db: Database,
    *,
    status: str | None = None,
    harvest_window_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conditions: list[str] = []
    params: list[Any] = []
    if status:
        conditions.append("po.status = ?")
        params.append(status)
    if harvest_window_id:
        conditions.append("po.harvest_window_id = ?")
        params.append(harvest_window_id)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    total_row = await db.fetch_one(
        f"SELECT COUNT(*) AS cnt FROM preorders po{where}",
        tuple(params),
    )
    rows = await db.fetch_all(
        f"""
        SELECT po.*, o.public_reference, p.name AS product_name
        FROM preorders po
        JOIN orders o ON o.id = po.order_id
        JOIN products p ON p.id = po.product_id
        {where}
        ORDER BY po.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return {
        "items": [_preorder_row(row) for row in rows],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


async def fulfill_preorder(
    db: Database,
    actor: Principal,
    request_id: str,
    preorder_id: str,
) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM preorders WHERE id = ?", (preorder_id,))
    if row is None:
        raise NotFoundError("Pre-order not found.")
    if row["status"] not in ("reserved", "ready"):
        raise ConflictError(f"Pre-order is {row['status']}, cannot fulfill.")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE preorders SET status = 'fulfilled', fulfilled_at = ? WHERE id = ?",
                (now, preorder_id),
            ),
            audit_statement(
                action="preorder.fulfilled",
                entity_type="preorder",
                entity_id=preorder_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"status": "fulfilled"},
            ),
        ]
    )
    updated = await db.fetch_one(
        """
        SELECT po.*, o.public_reference, p.name AS product_name
        FROM preorders po
        JOIN orders o ON o.id = po.order_id
        JOIN products p ON p.id = po.product_id
        WHERE po.id = ?
        """,
        (preorder_id,),
    )
    return _preorder_row(updated)  # type: ignore[arg-type]


async def mark_preorders_ready(
    db: Database,
    actor: Principal,
    request_id: str,
    harvest_window_id: str,
) -> int:
    """Mark all reserved preorders for a harvest window as ready for fulfillment."""
    now = utc_now_iso()
    result = await db.execute(
        "UPDATE preorders SET status = 'ready' WHERE harvest_window_id = ? AND status = 'reserved'",
        (harvest_window_id,),
    )
    if result > 0:
        await db.execute(
            *audit_statement(
                action="preorder.batch_ready",
                entity_type="harvest_window",
                entity_id=harvest_window_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"count": result},
            ),
        )
    return result


async def get_public_seasonal_calendar(db: Database) -> list[dict[str, Any]]:
    """Upcoming and active harvest windows for the public seasonal page."""
    rows = await db.fetch_all(
        """
        SELECT hw.*, p.name AS product_name, p.slug AS product_slug,
               COALESCE((SELECT SUM(quantity) FROM preorders po
                         WHERE po.harvest_window_id = hw.id
                         AND po.status IN ('reserved', 'ready')), 0) AS current_preorders
        FROM harvest_windows hw
        JOIN products p ON p.id = hw.product_id
        WHERE hw.status IN ('upcoming', 'active') AND p.status = 'published'
        ORDER BY hw.expected_start ASC
        LIMIT 50
        """,
    )
    return [
        {
            **_window_row(row),
            "productSlug": row.get("product_slug"),
            "available": (
                row.get("max_preorders") is None
                or int(row["current_preorders"]) < int(row["max_preorders"])
            ),
        }
        for row in rows
    ]

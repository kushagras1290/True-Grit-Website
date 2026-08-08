"""B2B / bulk ordering (v1).

Business-customer accounts with quantity-based price breaks and optional
net-terms invoicing.  A B2B customer sees tier pricing on variants where
price breaks are configured, and can pay via invoice instead of immediate
payment at checkout.
"""

from __future__ import annotations

import secrets
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso


def _account_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "companyName": row["company_name"],
        "gstNumber": row.get("gst_number"),
        "contactName": row.get("contact_name"),
        "contactEmail": row.get("contact_email"),
        "contactPhone": row.get("contact_phone"),
        "creditLimitMinor": row["credit_limit_minor"],
        "paymentTermsDays": row["payment_terms_days"],
        "status": row["status"],
        "notes": row.get("notes"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _price_break_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "variantId": row["variant_id"],
        "variantName": row.get("variant_name"),
        "productName": row.get("product_name"),
        "minQuantity": row["min_quantity"],
        "priceMinor": row["price_minor"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _invoice_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "orderId": row["order_id"],
        "orderReference": row.get("public_reference"),
        "b2bAccountId": row["b2b_account_id"],
        "companyName": row.get("company_name"),
        "invoiceNumber": row["invoice_number"],
        "amountMinor": row["amount_minor"],
        "currencyCode": row["currency_code"],
        "dueDate": row["due_date"],
        "status": row["status"],
        "paymentReference": row.get("payment_reference"),
        "issuedAt": row["issued_at"],
        "paidAt": row.get("paid_at"),
        "notes": row.get("notes"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _generate_invoice_number() -> str:
    return "INV-" + "".join(secrets.choice("0123456789") for _ in range(8))


# ── B2B Accounts ───────────────────────────────────────────────────────────

async def list_b2b_accounts(
    db: Database, *, search: str | None = None, limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    clean_search = f"%{search.strip()}%" if search and search.strip() else None
    where = (
        " WHERE company_name LIKE ? OR contact_email LIKE ? OR gst_number LIKE ?"
        if clean_search
        else ""
    )
    params: tuple[Any, ...] = (clean_search, clean_search, clean_search) if clean_search else ()
    total_row = await db.fetch_one(
        f"SELECT COUNT(*) AS cnt FROM b2b_accounts{where}", params,
    )
    rows = await db.fetch_all(
        f"SELECT * FROM b2b_accounts{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    return {
        "items": [_account_row(row) for row in rows],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


async def get_b2b_account(db: Database, account_id: str) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM b2b_accounts WHERE id = ?", (account_id,))
    if row is None:
        raise NotFoundError("B2B account not found.")
    return _account_row(row)


async def create_b2b_account(
    db: Database, actor: Principal, request_id: str,
    *, company_name: str, gst_number: str | None = None,
    contact_name: str | None = None, contact_email: str | None = None,
    contact_phone: str | None = None,
    credit_limit_minor: int = 0, payment_terms_days: int = 30,
    notes: str | None = None,
) -> dict[str, Any]:
    clean_name = company_name.strip()
    if not clean_name:
        raise ValidationAppError("Company name is required.")
    account_id = new_id("b2b")
    now = utc_now_iso()
    await db.batch([
        (
            "INSERT INTO b2b_accounts"
            " (id, company_name, gst_number, contact_name, contact_email,"
            "  contact_phone, credit_limit_minor, payment_terms_days,"
            "  status, notes, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)",
            (
                account_id, clean_name,
                (gst_number or "").strip() or None,
                (contact_name or "").strip() or None,
                (contact_email or "").strip() or None,
                (contact_phone or "").strip() or None,
                credit_limit_minor, payment_terms_days,
                (notes or "").strip() or None,
                now, now,
            ),
        ),
        audit_statement(
            action="b2b_account.created",
            entity_type="b2b_account",
            entity_id=account_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"companyName": clean_name},
        ),
    ])
    return await get_b2b_account(db, account_id)


async def update_b2b_account(
    db: Database, actor: Principal, request_id: str,
    account_id: str, *, updates: dict[str, Any],
) -> dict[str, Any]:
    existing = await db.fetch_one(
        "SELECT * FROM b2b_accounts WHERE id = ?", (account_id,),
    )
    if existing is None:
        raise NotFoundError("B2B account not found.")

    sets: list[str] = []
    params: list[Any] = []
    changed: dict[str, Any] = {}

    field_map = {
        "companyName": "company_name", "gstNumber": "gst_number",
        "contactName": "contact_name", "contactEmail": "contact_email",
        "contactPhone": "contact_phone", "notes": "notes",
    }
    for camel, snake in field_map.items():
        if camel in updates:
            val = (str(updates[camel]).strip() if updates[camel] else None)
            sets.append(f"{snake} = ?")
            params.append(val)
            changed[camel] = val

    if "creditLimitMinor" in updates:
        sets.append("credit_limit_minor = ?")
        params.append(int(updates["creditLimitMinor"]))
        changed["creditLimitMinor"] = updates["creditLimitMinor"]

    if "paymentTermsDays" in updates:
        sets.append("payment_terms_days = ?")
        params.append(int(updates["paymentTermsDays"]))
        changed["paymentTermsDays"] = updates["paymentTermsDays"]

    if "status" in updates:
        status = updates["status"]
        if status not in ("pending", "active", "suspended"):
            raise ValidationAppError("Status must be 'pending', 'active', or 'suspended'.")
        sets.append("status = ?")
        params.append(status)
        changed["status"] = status

    if not sets:
        return await get_b2b_account(db, account_id)

    now = utc_now_iso()
    sets.append("updated_at = ?")
    params.append(now)
    params.append(account_id)

    await db.batch([
        (f"UPDATE b2b_accounts SET {', '.join(sets)} WHERE id = ?", tuple(params)),
        audit_statement(
            action="b2b_account.updated",
            entity_type="b2b_account",
            entity_id=account_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after=changed,
        ),
    ])
    return await get_b2b_account(db, account_id)


async def link_user_to_b2b(
    db: Database, actor: Principal, request_id: str,
    *, user_id: str, b2b_account_id: str,
) -> None:
    """Link a user to a B2B account."""
    account = await db.fetch_one(
        "SELECT id FROM b2b_accounts WHERE id = ?", (b2b_account_id,),
    )
    if account is None:
        raise NotFoundError("B2B account not found.")
    user = await db.fetch_one("SELECT id FROM users WHERE id = ?", (user_id,))
    if user is None:
        raise NotFoundError("Customer user not found.")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE users SET b2b_account_id = ? WHERE id = ?",
                (b2b_account_id, user_id),
            ),
            audit_statement(
                action="b2b_account.user_linked",
                entity_type="b2b_account",
                entity_id=b2b_account_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"userId": user_id},
            ),
        ]
    )


async def is_b2b_customer(db: Database, user_id: str) -> dict[str, Any] | None:
    """Check if a user is linked to a B2B account. Returns account or None."""
    row = await db.fetch_one(
        """
        SELECT b.* FROM b2b_accounts b
        JOIN users u ON u.b2b_account_id = b.id
        WHERE u.id = ? AND b.status = 'active'
        """,
        (user_id,),
    )
    return _account_row(row) if row else None


# ── Price Breaks ───────────────────────────────────────────────────────────

async def list_price_breaks(
    db: Database, *, variant_id: str | None = None, limit: int = 100, offset: int = 0,
) -> dict[str, Any]:
    where = " WHERE pb.variant_id = ?" if variant_id else ""
    params: tuple[Any, ...] = (variant_id,) if variant_id else ()
    total_row = await db.fetch_one(
        f"SELECT COUNT(*) AS cnt FROM b2b_price_breaks pb{where}", params,
    )
    rows = await db.fetch_all(
        f"""
        SELECT pb.*, v.name AS variant_name, p.name AS product_name
        FROM b2b_price_breaks pb
        JOIN product_variants v ON v.id = pb.variant_id
        JOIN products p ON p.id = v.product_id
        {where}
        ORDER BY pb.variant_id, pb.min_quantity ASC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return {
        "items": [_price_break_row(row) for row in rows],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


async def create_price_break(
    db: Database, actor: Principal, request_id: str,
    *, variant_id: str, min_quantity: int, price_minor: int,
) -> dict[str, Any]:
    if min_quantity < 1:
        raise ValidationAppError("Minimum quantity must be at least 1.")
    if price_minor < 0:
        raise ValidationAppError("Price must be non-negative.")
    variant = await db.fetch_one(
        "SELECT id FROM product_variants WHERE id = ?", (variant_id,),
    )
    if variant is None:
        raise NotFoundError("Variant not found.")
    existing = await db.fetch_one(
        "SELECT id FROM b2b_price_breaks WHERE variant_id = ? AND min_quantity = ?",
        (variant_id, min_quantity),
    )
    if existing:
        raise ConflictError("A price break for this quantity already exists.")
    break_id = new_id("bpb")
    now = utc_now_iso()
    await db.batch([
        (
            "INSERT INTO b2b_price_breaks"
            " (id, variant_id, min_quantity, price_minor, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (break_id, variant_id, min_quantity, price_minor, now, now),
        ),
        audit_statement(
            action="b2b_price_break.created",
            entity_type="b2b_price_break",
            entity_id=break_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"variantId": variant_id, "minQuantity": min_quantity,
                   "priceMinor": price_minor},
        ),
    ])
    row = await db.fetch_one(
        """
        SELECT pb.*, v.name AS variant_name, p.name AS product_name
        FROM b2b_price_breaks pb
        JOIN product_variants v ON v.id = pb.variant_id
        JOIN products p ON p.id = v.product_id
        WHERE pb.id = ?
        """,
        (break_id,),
    )
    return _price_break_row(row)  # type: ignore[arg-type]


async def delete_price_break(
    db: Database, actor: Principal, request_id: str, break_id: str,
) -> None:
    existing = await db.fetch_one(
        "SELECT id FROM b2b_price_breaks WHERE id = ?", (break_id,),
    )
    if existing is None:
        raise NotFoundError("Price break not found.")
    now = utc_now_iso()
    await db.batch([
        ("DELETE FROM b2b_price_breaks WHERE id = ?", (break_id,)),
        audit_statement(
            action="b2b_price_break.deleted",
            entity_type="b2b_price_break",
            entity_id=break_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"deleted": True},
        ),
    ])


async def resolve_b2b_price(
    db: Database, variant_id: str, quantity: int,
) -> int | None:
    """Resolve the B2B tier price for a variant at a given quantity.
    Returns the price_minor, or None if no matching price break."""
    row = await db.fetch_one(
        """
        SELECT price_minor FROM b2b_price_breaks
        WHERE variant_id = ? AND min_quantity <= ? AND status = 'active'
        ORDER BY min_quantity DESC
        LIMIT 1
        """,
        (variant_id, quantity),
    )
    return int(row["price_minor"]) if row else None


# ── Invoices ───────────────────────────────────────────────────────────────

async def list_invoices(
    db: Database, *, b2b_account_id: str | None = None,
    status: str | None = None, limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    conditions: list[str] = []
    params: list[Any] = []
    if b2b_account_id:
        conditions.append("bi.b2b_account_id = ?")
        params.append(b2b_account_id)
    if status:
        conditions.append("bi.status = ?")
        params.append(status)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    total_row = await db.fetch_one(
        f"SELECT COUNT(*) AS cnt FROM b2b_invoices bi{where}", tuple(params),
    )
    rows = await db.fetch_all(
        f"""
        SELECT bi.*, o.public_reference, ba.company_name
        FROM b2b_invoices bi
        JOIN orders o ON o.id = bi.order_id
        JOIN b2b_accounts ba ON ba.id = bi.b2b_account_id
        {where}
        ORDER BY bi.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return {
        "items": [_invoice_row(row) for row in rows],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


async def create_invoice(
    db: Database, order_id: str, b2b_account_id: str,
    amount_minor: int, payment_terms_days: int,
) -> dict[str, Any]:
    """Create an invoice for a B2B order.  Called at checkout."""
    import datetime
    invoice_id = new_id("inv")
    invoice_number = _generate_invoice_number()
    now = utc_now_iso()
    due_date = (
        datetime.datetime.fromisoformat(now.replace("Z", "+00:00"))
        + datetime.timedelta(days=payment_terms_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.execute(
        "INSERT INTO b2b_invoices"
        " (id, order_id, b2b_account_id, invoice_number, amount_minor,"
        "  currency_code, due_date, status, issued_at, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, 'INR', ?, 'issued', ?, ?, ?)",
        (invoice_id, order_id, b2b_account_id, invoice_number,
         amount_minor, due_date, now, now, now),
    )
    row = await db.fetch_one(
        """
        SELECT bi.*, o.public_reference, ba.company_name
        FROM b2b_invoices bi
        JOIN orders o ON o.id = bi.order_id
        JOIN b2b_accounts ba ON ba.id = bi.b2b_account_id
        WHERE bi.id = ?
        """,
        (invoice_id,),
    )
    return _invoice_row(row)  # type: ignore[arg-type]


async def mark_invoice_paid(
    db: Database, actor: Principal, request_id: str,
    invoice_id: str, *, payment_reference: str | None = None,
) -> dict[str, Any]:
    invoice = await db.fetch_one(
        "SELECT * FROM b2b_invoices WHERE id = ?", (invoice_id,),
    )
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    if invoice["status"] == "paid":
        raise ConflictError("Invoice is already paid.")
    if invoice["status"] == "cancelled":
        raise ConflictError("Cannot mark a cancelled invoice as paid.")
    now = utc_now_iso()
    await db.batch([
        (
            "UPDATE b2b_invoices SET status = 'paid', paid_at = ?,"
            " payment_reference = ?, updated_at = ? WHERE id = ?",
            (now, (payment_reference or "").strip() or None, now, invoice_id),
        ),
        (
            "UPDATE orders SET payment_status = 'paid' WHERE id = ?",
            (invoice["order_id"],),
        ),
        (
            "UPDATE payments SET status = 'paid' WHERE order_id = ? AND provider = 'invoice'",
            (invoice["order_id"],),
        ),
        audit_statement(
            action="b2b_invoice.paid",
            entity_type="b2b_invoice",
            entity_id=invoice_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"status": "paid", "paymentReference": payment_reference},
        ),
    ])
    row = await db.fetch_one(
        """
        SELECT bi.*, o.public_reference, ba.company_name
        FROM b2b_invoices bi
        JOIN orders o ON o.id = bi.order_id
        JOIN b2b_accounts ba ON ba.id = bi.b2b_account_id
        WHERE bi.id = ?
        """,
        (invoice_id,),
    )
    return _invoice_row(row)  # type: ignore[arg-type]


async def check_credit_limit(
    db: Database, b2b_account_id: str, new_amount_minor: int,
) -> bool:
    """Check if a B2B account has enough credit for a new order."""
    account = await db.fetch_one(
        "SELECT credit_limit_minor FROM b2b_accounts WHERE id = ?",
        (b2b_account_id,),
    )
    if account is None:
        return False
    if int(account["credit_limit_minor"]) == 0:
        return True  # 0 means unlimited
    outstanding = await db.fetch_one(
        "SELECT COALESCE(SUM(amount_minor), 0) AS total"
        " FROM b2b_invoices WHERE b2b_account_id = ? AND status IN ('issued', 'sent', 'overdue')",
        (b2b_account_id,),
    )
    outstanding_total = int(outstanding["total"]) if outstanding else 0
    return (outstanding_total + new_amount_minor) <= int(account["credit_limit_minor"])

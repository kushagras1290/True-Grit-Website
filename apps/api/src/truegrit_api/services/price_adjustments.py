"""Signed price adjustments -- a real markup or a real discount, scopable by
country, by a single product, by a whole category, or combined with country
(migration 0054).

`percent` is signed: positive raises the real price a customer pays, negative
genuinely reduces it. There is exactly one real price (a variant's stored
`list_amount_minor`); this module adjusts what a particular visitor actually
pays, and the storefront only ever shows a struck-through "original" price
alongside a genuine (negative) discount -- never to dress up a markup as if
something had been discounted from it. See `apply_percent` and
`resolve_adjustments`.

Resolution is most-specific-wins, not a merge, across three independent
targeting choices crossed with two scope choices: scope+product >
global+product > scope+category > global+category > scope-only >
global-only. A rule for one product in India does not blend with a global
category rule that also covers it; it replaces it for that one product, in
India. `product_id` and `category_id` are mutually exclusive per rule
(enforced by the table's CHECK) -- a rule targets one product, one category,
or every product, never a combination.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

GLOBAL_SCOPE: Final = "global"
MIN_PERCENT: Final = -90
MAX_PERCENT: Final = 500
# Country x product x category is a real matrix, not a handful of toggles --
# bounded generously so a catalogue-wide seasonal sale is never blocked, but
# still bounded, per the same reasoning as `MAX_COUNTRY_SCOPES` in appearance.py.
MAX_RULES: Final = 2000

_COUNTRY_CODE_PATTERN: Final = re.compile(r"^[A-Za-z]{2}$")
# "XX" (unknown) and "T1" (Tor) are Cloudflare sentinels, not real countries --
# see `resolveCountry()` in the storefront.
_NOT_REAL_COUNTRIES: Final = frozenset({"XX", "T1"})


def validate_scope(scope: str) -> str:
    """`'global'` or an ISO-3166 alpha-2 code, uppercase. Anything else is refused."""
    candidate = scope.strip()
    if candidate == GLOBAL_SCOPE:
        return GLOBAL_SCOPE
    code = candidate.upper()
    if not _COUNTRY_CODE_PATTERN.match(code) or code in _NOT_REAL_COUNTRIES:
        raise ValidationAppError(
            "A price adjustment scope must be 'global' or a real two-letter country code,"
            " such as IN."
        )
    return code


def apply_percent(list_minor: int, percent: int) -> int:
    """The real list price, adjusted by a signed percent, rounded half up.

    `percent` is bounded to [-90, 500] by the CHECK constraint, so `100 +
    percent` is always in [10, 600] -- strictly positive -- meaning a
    non-negative `list_minor` can never adjust to a negative amount.
    """
    if percent == 0:
        return list_minor
    return (list_minor * (100 + percent) + 50) // 100


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "scope": row["scope"],
        "productId": row["product_id"],
        "productName": row["product_name"],
        "productSlug": row["product_slug"],
        "categoryId": row["category_id"],
        "categoryName": row["category_name"],
        "categorySlug": row["category_slug"],
        "percent": int(row["percent"]),
        "active": bool(row["active"]),
        "updatedAt": row["updated_at"],
    }


async def list_rules(db: Database) -> list[dict[str, Any]]:
    """Every stored rule, for the admin console. Global-scope and
    all-products rules sort first, so the broadest rule an owner is about to
    override is the first thing they see."""
    rows = await db.fetch_all(
        """
        SELECT pa.id, pa.scope, pa.product_id, pa.category_id, pa.percent, pa.active,
               pa.updated_at, p.name AS product_name, p.slug AS product_slug,
               c.name AS category_name, c.slug AS category_slug
        FROM price_adjustments pa
        LEFT JOIN products p ON p.id = pa.product_id
        LEFT JOIN categories c ON c.id = pa.category_id
        ORDER BY (pa.scope != 'global'), pa.scope,
                 (pa.product_id IS NOT NULL), (pa.category_id IS NOT NULL),
                 p.name, c.name
        """
    )
    return [_row_to_dict(row) for row in rows]


async def resolve_adjustments(
    db: Database, product_ids: Sequence[str], country: str | None
) -> dict[str, int]:
    """`{product_id: percent}` for every product in `product_ids` that has an
    active, non-zero adjustment for this visitor. A product absent from the
    result has no adjustment -- its real list price is shown as-is.

    Two queries for the whole batch (never one query per product in a
    listing): each product's category memberships, then every rule that could
    possibly apply to this batch. Resolution then runs in Python against the
    priority order this module's docstring describes. When a product belongs
    to more than one category that each carry a rule at the same tier, the
    most recently saved rule wins -- the same "last edit wins" an owner would
    expect from any other overlapping setting.
    """
    unique_ids = list(dict.fromkeys(product_ids))
    if not unique_ids:
        return {}
    code = country.strip().upper() if country else None
    if not (code and _COUNTRY_CODE_PATTERN.match(code)):
        code = None
    scopes = [GLOBAL_SCOPE] + ([code] if code else [])

    product_placeholders = ", ".join("?" for _ in unique_ids)
    category_rows = await db.fetch_all(
        f"SELECT product_id, category_id FROM product_categories"
        f" WHERE product_id IN ({product_placeholders})",
        unique_ids,
    )
    categories_by_product: dict[str, list[str]] = {}
    all_category_ids: set[str] = set()
    for row in category_rows:
        categories_by_product.setdefault(row["product_id"], []).append(row["category_id"])
        all_category_ids.add(row["category_id"])

    scope_placeholders = ", ".join("?" for _ in scopes)
    category_placeholders = ", ".join("?" for _ in all_category_ids) if all_category_ids else ""
    category_clause = f" OR category_id IN ({category_placeholders})" if all_category_ids else ""
    rows = await db.fetch_all(
        f"""
        SELECT scope, product_id, category_id, percent, updated_at
        FROM price_adjustments
        WHERE active = 1
          AND scope IN ({scope_placeholders})
          AND (
            (product_id IS NULL AND category_id IS NULL)
            OR product_id IN ({product_placeholders})
            {category_clause}
          )
        """,
        (*scopes, *unique_ids, *all_category_ids),
    )

    by_product: dict[tuple[str, str], int] = {}
    by_category: dict[tuple[str, str], tuple[int, str]] = {}
    blanket: dict[str, int] = {}
    for row in rows:
        scope, product_id, category_id = row["scope"], row["product_id"], row["category_id"]
        percent = int(row["percent"])
        if product_id is not None:
            by_product[(scope, product_id)] = percent
        elif category_id is not None:
            candidate = (percent, row["updated_at"])
            key = (scope, category_id)
            current = by_category.get(key)
            if current is None or candidate[1] >= current[1]:
                by_category[key] = candidate
        else:
            blanket[scope] = percent

    def best_category_percent(scope: str, category_ids: list[str]) -> int | None:
        best: tuple[int, str] | None = None
        for category_id in category_ids:
            candidate = by_category.get((scope, category_id))
            if candidate is not None and (best is None or candidate[1] >= best[1]):
                best = candidate
        return best[0] if best else None

    result: dict[str, int] = {}
    for product_id in unique_ids:
        product_categories = categories_by_product.get(product_id, [])
        percent = None
        if code is not None:
            percent = by_product.get((code, product_id))
        if percent is None:
            percent = by_product.get((GLOBAL_SCOPE, product_id))
        if percent is None and code is not None:
            percent = best_category_percent(code, product_categories)
        if percent is None:
            percent = best_category_percent(GLOBAL_SCOPE, product_categories)
        if percent is None and code is not None:
            percent = blanket.get(code)
        if percent is None:
            percent = blanket.get(GLOBAL_SCOPE)
        if percent:
            result[product_id] = percent
    return result


async def save_rule(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    scope: str,
    product_id: str | None,
    category_id: str | None,
    percent: int,
    active: bool,
) -> None:
    resolved_scope = validate_scope(scope)
    if not MIN_PERCENT <= percent <= MAX_PERCENT:
        raise ValidationAppError(
            f"A price adjustment must be between {MIN_PERCENT}% and {MAX_PERCENT}%."
        )
    resolved_product_id = product_id.strip() if product_id and product_id.strip() else None
    resolved_category_id = category_id.strip() if category_id and category_id.strip() else None
    if resolved_product_id is not None and resolved_category_id is not None:
        raise ValidationAppError(
            "A price adjustment can target one product or one category, not both."
        )
    if resolved_product_id is not None:
        product = await db.fetch_one(
            "SELECT 1 AS ok FROM products WHERE id = ?", (resolved_product_id,)
        )
        if product is None:
            raise NotFoundError("That product could not be found.")
    if resolved_category_id is not None:
        category = await db.fetch_one(
            "SELECT 1 AS ok FROM categories WHERE id = ?", (resolved_category_id,)
        )
        if category is None:
            raise NotFoundError("That category could not be found.")

    existing = await db.fetch_one(
        "SELECT id FROM price_adjustments"
        " WHERE scope = ? AND COALESCE(product_id, '') = COALESCE(?, '')"
        " AND COALESCE(category_id, '') = COALESCE(?, '')",
        (resolved_scope, resolved_product_id, resolved_category_id),
    )
    now = utc_now_iso()
    audit_after = {
        "scope": resolved_scope,
        "productId": resolved_product_id,
        "categoryId": resolved_category_id,
        "percent": percent,
        "active": active,
    }

    if existing is not None:
        statements: list[tuple[str, Sequence[Any]]] = [
            (
                "UPDATE price_adjustments"
                " SET percent = ?, active = ?, updated_at = ?, updated_by = ?"
                " WHERE id = ?",
                (percent, int(active), now, actor.user_id, existing["id"]),
            ),
            audit_statement(
                action="settings.price_adjustment_updated",
                entity_type="price_adjustment",
                entity_id=existing["id"],
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after=audit_after,
            ),
        ]
        await db.batch(statements)
        return

    count = await db.fetch_one("SELECT COUNT(*) AS total FROM price_adjustments")
    if count and int(count["total"]) >= MAX_RULES:
        raise ValidationAppError(f"At most {MAX_RULES} price adjustment rules are allowed.")

    new_rule_id = new_id("padj")
    await db.batch(
        [
            (
                "INSERT INTO price_adjustments"
                " (id, scope, product_id, category_id, percent, active,"
                "  created_at, created_by, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    new_rule_id,
                    resolved_scope,
                    resolved_product_id,
                    resolved_category_id,
                    percent,
                    int(active),
                    now,
                    actor.user_id,
                    now,
                    actor.user_id,
                ),
            ),
            audit_statement(
                action="settings.price_adjustment_created",
                entity_type="price_adjustment",
                entity_id=new_rule_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after=audit_after,
            ),
        ]
    )


async def delete_rule(db: Database, actor: Principal, request_id: str, *, rule_id: str) -> None:
    existing = await db.fetch_one(
        "SELECT scope, product_id, category_id FROM price_adjustments WHERE id = ?", (rule_id,)
    )
    if existing is None:
        raise NotFoundError("That price adjustment rule could not be found.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM price_adjustments WHERE id = ?", (rule_id,)),
            audit_statement(
                action="settings.price_adjustment_deleted",
                entity_type="price_adjustment",
                entity_id=rule_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={
                    "scope": existing["scope"],
                    "productId": existing["product_id"],
                    "categoryId": existing["category_id"],
                },
            ),
        ]
    )

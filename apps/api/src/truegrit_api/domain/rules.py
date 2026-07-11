"""Category product-rule engine.

Editors store a validated JSON rule tree; it compiles only to allowlisted,
parameterized SQL fragments. Unknown fields and operators are rejected, values
are always bound as parameters, and the compiler can never emit an untrusted
column name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from truegrit_api.errors import ValidationAppError

MAX_CONDITIONS = 20
MAX_LIMIT = 200
MAX_VALUE_LENGTH = 96

# field key -> (SQL fragment builder id, allowed operators, value type)
_FIELDS: dict[str, tuple[str, frozenset[str], type]] = {
    "product.status": ("p.status", frozenset({"equals", "in"}), str),
    "product.type": ("p.product_type", frozenset({"equals", "in"}), str),
    "category.slug": ("__category_slug__", frozenset({"equals", "in"}), str),
    "farm.slug": ("__farm_slug__", frozenset({"equals", "in"}), str),
    "tag.key": ("__tag_key__", frozenset({"equals", "in"}), str),
    "inventory.available": ("__inventory_available__", frozenset({"greater_than"}), int),
}

_SORTS: dict[str, str] = {
    "name": "p.name",
    "updated_at": "p.updated_at",
    # merchandising_score is not materialized yet; deterministic fallback.
    "merchandising_score": "p.updated_at",
}


@dataclass(frozen=True)
class CompiledRule:
    where_sql: str
    params: tuple[Any, ...]
    order_sql: str
    limit: int


def _validate_value(field: str, operator: str, value: Any, value_type: type) -> list[Any]:
    if operator == "in":
        if not isinstance(value, list) or not value or len(value) > MAX_CONDITIONS:
            raise ValidationAppError(f"'{field}' with 'in' needs a non-empty list.")
        items = value
    else:
        items = [value]
    checked: list[Any] = []
    for item in items:
        if isinstance(item, bool) or not isinstance(item, value_type):
            raise ValidationAppError(f"Invalid value type for '{field}'.")
        if isinstance(item, str) and len(item) > MAX_VALUE_LENGTH:
            raise ValidationAppError(f"Value too long for '{field}'.")
        if isinstance(item, int) and not 0 <= item <= 1_000_000:
            raise ValidationAppError(f"Value out of range for '{field}'.")
        checked.append(item)
    return checked


def _fragment(column_id: str, operator: str, values: list[Any]) -> tuple[str, list[Any]]:
    placeholders = ", ".join("?" for _ in values)
    if column_id == "__category_slug__":
        return (
            "p.id IN (SELECT pc.product_id FROM product_categories pc"
            " JOIN categories c ON c.id = pc.category_id"
            f" WHERE c.slug IN ({placeholders}))",
            values,
        )
    if column_id == "__farm_slug__":
        return (f"p.farm_id IN (SELECT f.id FROM farms f WHERE f.slug IN ({placeholders}))", values)
    if column_id == "__tag_key__":
        return (
            "p.id IN (SELECT pt.product_id FROM product_tags pt"
            f" JOIN tags t ON t.id = pt.tag_id WHERE t.key IN ({placeholders}))",
            values,
        )
    if column_id == "__inventory_available__":
        return (
            "p.id IN (SELECT v.product_id FROM product_variants v"
            " JOIN inventory_levels il ON il.variant_id = v.id"
            " GROUP BY v.product_id HAVING SUM(il.on_hand - il.reserved) > ?)",
            values,
        )
    if operator == "in":
        return (f"{column_id} IN ({placeholders})", values)
    return (f"{column_id} = ?", values)


def compile_rule(rule: dict[str, Any]) -> CompiledRule:
    """Validate a rule tree and compile it to parameterized SQL fragments."""
    if not isinstance(rule, dict):
        raise ValidationAppError("Rule must be an object.")
    if rule.get("version") != 1:
        raise ValidationAppError("Unsupported rule version.")
    operator = rule.get("operator", "and")
    if operator not in {"and", "or"}:
        raise ValidationAppError("Rule operator must be 'and' or 'or'.")

    conditions = rule.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValidationAppError("Rule needs at least one condition.")
    if len(conditions) > MAX_CONDITIONS:
        raise ValidationAppError(f"Rule supports at most {MAX_CONDITIONS} conditions.")

    fragments: list[str] = []
    params: list[Any] = []
    for condition in conditions:
        if not isinstance(condition, dict):
            raise ValidationAppError("Each condition must be an object.")
        field = condition.get("field")
        cond_op = condition.get("operator")
        if field not in _FIELDS:
            raise ValidationAppError(f"Unknown rule field '{field}'.")
        column_id, allowed_ops, value_type = _FIELDS[field]
        if cond_op not in allowed_ops:
            raise ValidationAppError(f"Operator '{cond_op}' is not allowed for '{field}'.")
        values = _validate_value(str(field), str(cond_op), condition.get("value"), value_type)
        sql, bound = _fragment(column_id, str(cond_op), values)
        fragments.append(sql)
        params.extend(bound)

    joiner = " AND " if operator == "and" else " OR "
    where_sql = "(" + joiner.join(fragments) + ")"

    order_parts: list[str] = []
    for sort in rule.get("sort", [{"field": "name", "direction": "asc"}]):
        if not isinstance(sort, dict):
            raise ValidationAppError("Sort entries must be objects.")
        sort_field = sort.get("field")
        direction = sort.get("direction", "asc")
        if sort_field not in _SORTS:
            raise ValidationAppError(f"Unknown sort field '{sort_field}'.")
        if direction not in {"asc", "desc"}:
            raise ValidationAppError("Sort direction must be 'asc' or 'desc'.")
        order_parts.append(f"{_SORTS[str(sort_field)]} {direction.upper()}")
    order_sql = ", ".join(order_parts) if order_parts else "p.name ASC"

    limit = rule.get("limit", 96)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
        raise ValidationAppError(f"Rule limit must be between 1 and {MAX_LIMIT}.")

    return CompiledRule(where_sql=where_sql, params=tuple(params), order_sql=order_sql, limit=limit)

import pytest

from truegrit_api.domain.rules import MAX_CONDITIONS, compile_rule
from truegrit_api.errors import ValidationAppError

VALID_RULE = {
    "version": 1,
    "operator": "and",
    "conditions": [
        {"field": "product.status", "operator": "equals", "value": "published"},
        {"field": "category.slug", "operator": "in", "value": ["fruits"]},
        {"field": "inventory.available", "operator": "greater_than", "value": 0},
    ],
    "sort": [
        {"field": "merchandising_score", "direction": "desc"},
        {"field": "name", "direction": "asc"},
    ],
    "limit": 96,
}


def test_compiles_valid_rule_with_bound_params():
    compiled = compile_rule(VALID_RULE)
    assert compiled.params == ("published", "fruits", 0)
    assert compiled.limit == 96
    assert "p.status = ?" in compiled.where_sql
    assert "c.slug IN (?)" in compiled.where_sql
    # Every value is a placeholder; no literal leaks into SQL.
    assert "published" not in compiled.where_sql
    assert "fruits" not in compiled.where_sql


def test_rejects_unknown_field():
    rule = {
        "version": 1,
        "conditions": [{"field": "product.price; DROP TABLE", "operator": "equals", "value": "x"}],
    }
    with pytest.raises(ValidationAppError):
        compile_rule(rule)


def test_rejects_unknown_operator():
    rule = {
        "version": 1,
        "conditions": [{"field": "product.status", "operator": "like", "value": "pub%"}],
    }
    with pytest.raises(ValidationAppError):
        compile_rule(rule)


def test_rejects_wrong_value_type():
    rule = {
        "version": 1,
        "conditions": [{"field": "inventory.available", "operator": "greater_than", "value": "0"}],
    }
    with pytest.raises(ValidationAppError):
        compile_rule(rule)


def test_rejects_untrusted_sort_field():
    rule = {
        "version": 1,
        "conditions": [{"field": "product.status", "operator": "equals", "value": "published"}],
        "sort": [{"field": "p.name; --", "direction": "asc"}],
    }
    with pytest.raises(ValidationAppError):
        compile_rule(rule)


def test_enforces_condition_and_limit_bounds():
    too_many = {
        "version": 1,
        "conditions": [
            {"field": "product.status", "operator": "equals", "value": "published"}
            for _ in range(MAX_CONDITIONS + 1)
        ],
    }
    with pytest.raises(ValidationAppError):
        compile_rule(too_many)
    with pytest.raises(ValidationAppError):
        compile_rule({**VALID_RULE, "limit": 5000})
    with pytest.raises(ValidationAppError):
        compile_rule({**VALID_RULE, "version": 2})

from __future__ import annotations

import asyncio

import pytest

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import build_local_database
from truegrit_api.services import price_adjustments, price_tiers


def principal() -> Principal:
    # "usr_admin" is the seeded super-admin (database/seeds/development.sql) --
    # price_tier_brackets.updated_by and audit_logs.actor_user_id both FK to
    # users, so any test that persists a write needs a real seeded user.
    return Principal(
        user_id="usr_admin", display_name="Owner", email="owner@truegrit.test", user_type="staff"
    )


def test_seed_migration_ships_three_brackets_with_no_countries() -> None:
    async def scenario() -> None:
        db = build_local_database()
        brackets = await price_tiers.list_brackets(db)
        assert [(b["id"], b["percent"]) for b in brackets] == [
            ("ptier_1", 100),
            ("ptier_2", 75),
            ("ptier_3", 50),
        ]
        assert all(bracket["countries"] == [] for bracket in brackets)

    asyncio.run(scenario())


def test_create_bracket_appends_to_sort_order() -> None:
    async def scenario() -> None:
        db = build_local_database()
        created = await price_tiers.create_bracket(
            db, principal(), "req_1", label="Tier 4", percent=25
        )
        assert created["percent"] == 25
        brackets = await price_tiers.list_brackets(db)
        assert brackets[-1]["id"] == created["id"]
        assert brackets[-1]["sortOrder"] == 3

    asyncio.run(scenario())


def test_create_bracket_rejects_blank_label() -> None:
    async def scenario() -> None:
        db = build_local_database()
        with pytest.raises(ValidationAppError):
            await price_tiers.create_bracket(db, principal(), "req_1", label="  ", percent=10)

    asyncio.run(scenario())


def test_create_bracket_rejects_out_of_range_percent() -> None:
    async def scenario() -> None:
        db = build_local_database()
        with pytest.raises(ValidationAppError):
            await price_tiers.create_bracket(db, principal(), "req_1", label="Tier X", percent=600)

    asyncio.run(scenario())


def test_assign_country_writes_a_bracket_tagged_price_adjustment() -> None:
    async def scenario() -> None:
        db = build_local_database()
        await price_tiers.assign_country(
            db, principal(), "req_1", country_code="us", bracket_id="ptier_1"
        )
        brackets = await price_tiers.list_brackets(db)
        tier_1 = next(b for b in brackets if b["id"] == "ptier_1")
        assert tier_1["countries"] == ["US"]

        rule = await db.fetch_one(
            "SELECT scope, percent, bracket_id, product_id, category_id"
            " FROM price_adjustments WHERE bracket_id = 'ptier_1'"
        )
        assert rule is not None
        assert rule["scope"] == "US"
        assert rule["percent"] == 100
        assert rule["product_id"] is None
        assert rule["category_id"] is None

    asyncio.run(scenario())


def test_reassigning_a_country_moves_it_between_brackets() -> None:
    async def scenario() -> None:
        db = build_local_database()
        await price_tiers.assign_country(
            db, principal(), "req_1", country_code="US", bracket_id="ptier_1"
        )
        await price_tiers.assign_country(
            db, principal(), "req_2", country_code="US", bracket_id="ptier_2"
        )
        brackets = await price_tiers.list_brackets(db)
        by_id = {b["id"]: b for b in brackets}
        assert by_id["ptier_1"]["countries"] == []
        assert by_id["ptier_2"]["countries"] == ["US"]

        rules = await db.fetch_all(
            "SELECT scope, bracket_id FROM price_adjustments WHERE scope = 'US'"
        )
        assert len(rules) == 1
        assert rules[0]["bracket_id"] == "ptier_2"

    asyncio.run(scenario())


def test_assign_country_conflicts_with_an_existing_manual_rule() -> None:
    async def scenario() -> None:
        db = build_local_database()
        await price_adjustments.save_rule(
            db,
            principal(),
            "req_manual",
            scope="US",
            product_id=None,
            category_id=None,
            percent=15,
            active=True,
        )
        with pytest.raises(ConflictError):
            await price_tiers.assign_country(
                db, principal(), "req_1", country_code="US", bracket_id="ptier_1"
            )

    asyncio.run(scenario())


def test_assign_country_rejects_unknown_bracket() -> None:
    async def scenario() -> None:
        db = build_local_database()
        with pytest.raises(NotFoundError):
            await price_tiers.assign_country(
                db, principal(), "req_1", country_code="US", bracket_id="ptier_missing"
            )

    asyncio.run(scenario())


def test_assign_country_rejects_invalid_country_code() -> None:
    async def scenario() -> None:
        db = build_local_database()
        with pytest.raises(ValidationAppError):
            await price_tiers.assign_country(
                db, principal(), "req_1", country_code="USA", bracket_id="ptier_1"
            )
        with pytest.raises(ValidationAppError):
            await price_tiers.assign_country(
                db, principal(), "req_1", country_code="XX", bracket_id="ptier_1"
            )

    asyncio.run(scenario())


def test_unassign_country_removes_both_rows() -> None:
    async def scenario() -> None:
        db = build_local_database()
        await price_tiers.assign_country(
            db, principal(), "req_1", country_code="US", bracket_id="ptier_1"
        )
        await price_tiers.unassign_country(db, principal(), "req_2", country_code="US")
        brackets = await price_tiers.list_brackets(db)
        assert all(bracket["countries"] == [] for bracket in brackets)
        rule = await db.fetch_one("SELECT id FROM price_adjustments WHERE scope = 'US'")
        assert rule is None

    asyncio.run(scenario())


def test_unassign_country_rejects_unknown_country() -> None:
    async def scenario() -> None:
        db = build_local_database()
        with pytest.raises(NotFoundError):
            await price_tiers.unassign_country(db, principal(), "req_1", country_code="US")

    asyncio.run(scenario())


def test_updating_bracket_percent_cascades_to_every_assigned_country() -> None:
    async def scenario() -> None:
        db = build_local_database()
        await price_tiers.assign_country(
            db, principal(), "req_1", country_code="US", bracket_id="ptier_1"
        )
        await price_tiers.assign_country(
            db, principal(), "req_2", country_code="GB", bracket_id="ptier_1"
        )
        await price_tiers.update_bracket(
            db, principal(), "req_3", "ptier_1", label="Tier 1", percent=125
        )
        rules = await db.fetch_all(
            "SELECT scope, percent FROM price_adjustments WHERE bracket_id = 'ptier_1'"
            " ORDER BY scope"
        )
        assert [(row["scope"], row["percent"]) for row in rules] == [("GB", 125), ("US", 125)]

    asyncio.run(scenario())


def test_deleting_a_bracket_cascades_countries_and_price_rules() -> None:
    async def scenario() -> None:
        db = build_local_database()
        await price_tiers.assign_country(
            db, principal(), "req_1", country_code="US", bracket_id="ptier_1"
        )
        await price_tiers.delete_bracket(db, principal(), "req_2", "ptier_1")

        brackets = await price_tiers.list_brackets(db)
        assert {b["id"] for b in brackets} == {"ptier_2", "ptier_3"}
        assert (
            await db.fetch_one(
                "SELECT country_code FROM price_tier_countries WHERE country_code = 'US'"
            )
        ) is None
        assert (await db.fetch_one("SELECT id FROM price_adjustments WHERE scope = 'US'")) is None

    asyncio.run(scenario())


def test_delete_bracket_rejects_unknown_id() -> None:
    async def scenario() -> None:
        db = build_local_database()
        with pytest.raises(NotFoundError):
            await price_tiers.delete_bracket(db, principal(), "req_1", "ptier_missing")

    asyncio.run(scenario())

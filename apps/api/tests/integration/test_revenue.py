"""Farm revenue console and payouts, end to end against the real schema.

The properties worth protecting here are the ones that cost real money when
they break: a line can never be paid twice, unpaid orders never count as
earnings, refunds come off before the split, and a rate change never restates
a payout that has already been made.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

# Seeded facts this module builds on: ord_1001 is paid (₹899 of prd_alphonso,
# which belongs to farm_devika); ord_1002 is pending_payment and must never
# show up as revenue. Default commission is 15% (migration 0042).
PAID_LINE_MINOR = 89_900
DEFAULT_BPS = 1500


def as_owner(client: TestClient, db: SQLiteDatabase) -> TestClient:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    return client


def devika(payload: dict) -> dict:
    return next(farm for farm in payload["farms"] if farm["farmId"] == "farm_devika")


def add_paid_order(
    db: SQLiteDatabase,
    order_id: str,
    *,
    items: list[tuple[str, str, int]],
    refund_minor: int = 0,
    payment_status: str = "paid",
    order_status: str = "confirmed",
) -> None:
    """Insert a paid order carrying `(item_id, product_id, line_total)` lines."""
    total = sum(line_total for _, _, line_total in items)
    db._conn.execute(  # test-only direct access, mirroring conftest
        "INSERT INTO orders (id, public_reference, customer_user_id, customer_email,"
        " currency_code, subtotal_minor, discount_minor, delivery_minor, tax_minor,"
        " total_minor, order_status, payment_status, fulfilment_status, delivery_status,"
        " placed_at, created_at, updated_at)"
        " VALUES (?, ?, 'usr_cust_riya', 'riya@example.test', 'INR', ?, 0, 0, 0, ?,"
        " ?, ?, 'unfulfilled', 'not_ready',"
        " '2026-07-20T09:00:00Z', '2026-07-20T09:00:00Z', '2026-07-20T09:00:00Z')",
        (order_id, order_id.upper(), total, total, order_status, payment_status),
    )
    for item_id, product_id, line_total in items:
        db._conn.execute(
            "INSERT INTO order_items (id, order_id, product_id, variant_id, product_name,"
            " variant_name, sku, quantity, unit_list_amount_minor,"
            " unit_effective_amount_minor, discount_minor, tax_minor, line_total_minor)"
            " VALUES (?, ?, ?, NULL, 'Test item', 'unit', 'SKU', 1, ?, ?, 0, 0, ?)",
            (item_id, order_id, product_id, line_total, line_total, line_total),
        )
    if refund_minor:
        db._conn.execute(
            "INSERT INTO order_adjustments (id, order_id, adjustment_type, label,"
            " amount_minor, created_at, created_by)"
            " VALUES (?, ?, 'refund', 'Test refund', ?, '2026-07-21T09:00:00Z', 'usr_admin')",
            (f"adj_{order_id}", order_id, -refund_minor),
        )
    db._conn.commit()


def add_product(db: SQLiteDatabase, product_id: str, farm_id: str) -> None:
    db._conn.execute(
        "INSERT INTO products (id, internal_name, name, slug, product_type, farm_id, status,"
        " created_at, created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, 'simple', ?, 'published',"
        " '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin')",
        (product_id, product_id, product_id, product_id.replace("_", "-"), farm_id),
    )
    db._conn.commit()


class TestSummary:
    def test_reports_seeded_revenue_at_the_default_rate(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        body = as_owner(client, db).get("/v1/admin/revenue").json()
        assert body["defaultCommissionBps"] == DEFAULT_BPS
        assert body["defaultCommissionPercent"] == 15

        farm = devika(body)
        assert farm["grossMinor"] == PAID_LINE_MINOR
        assert farm["commissionSource"] == "default"
        # 15% of ₹899 = ₹134.85; the farm keeps the rest.
        assert farm["commissionMinor"] == 13_485
        assert farm["farmEarningsMinor"] == 76_415
        assert farm["outstandingPayoutMinor"] == 76_415

    def test_unpaid_orders_are_not_revenue(self, client: TestClient, db: SQLiteDatabase) -> None:
        """ord_1002 is `pending_payment`. Counting an abandoned checkout as a
        farm's earnings would have the platform pay out money it never took."""
        farm = devika(as_owner(client, db).get("/v1/admin/revenue").json())
        assert farm["grossMinor"] == PAID_LINE_MINOR  # not 89_900 + 149_900

    def test_cancelled_orders_are_not_revenue(self, client: TestClient, db: SQLiteDatabase) -> None:
        add_paid_order(
            db,
            "ord_cancelled",
            items=[("oit_cancelled", "prd_alphonso", 50_000)],
            order_status="cancelled",
        )
        farm = devika(as_owner(client, db).get("/v1/admin/revenue").json())
        assert farm["grossMinor"] == PAID_LINE_MINOR

    def test_refunds_come_off_before_the_split(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        add_paid_order(
            db,
            "ord_refunded",
            items=[("oit_refunded", "prd_alphonso", 100_000)],
            refund_minor=40_000,
        )
        farm = devika(as_owner(client, db).get("/v1/admin/revenue").json())
        assert farm["grossMinor"] == PAID_LINE_MINOR + 100_000
        assert farm["refundedMinor"] == 40_000
        assert farm["netRevenueMinor"] == PAID_LINE_MINOR + 60_000

    def test_refund_on_a_two_farm_order_splits_by_value(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        """`order_adjustments` records refunds against the order, not the line.
        On a mixed order the only attribution the data supports is each farm's
        share of the goods value."""
        add_product(db, "prd_anand_test", "farm_anandvan")
        add_paid_order(
            db,
            "ord_mixed",
            items=[
                ("oit_mixed_a", "prd_alphonso", 40_000),
                ("oit_mixed_b", "prd_anand_test", 60_000),
            ],
            refund_minor=10_000,
        )
        body = as_owner(client, db).get("/v1/admin/revenue").json()
        alphonso = devika(body)
        anandvan = next(f for f in body["farms"] if f["farmId"] == "farm_anandvan")
        # ₹100 refund on a ₹1000 order: 40% to one farm, 60% to the other.
        assert alphonso["refundedMinor"] == 4_000
        assert anandvan["refundedMinor"] == 6_000


class TestCommissionRates:
    def test_owner_can_change_the_default_rate(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        owner = as_owner(client, db)
        assert owner.patch("/v1/admin/revenue/commission", json={"percent": 20}).status_code == 200
        farm = devika(owner.get("/v1/admin/revenue").json())
        assert farm["commissionBps"] == 2000
        assert farm["commissionMinor"] == 17_980  # 20% of ₹899

    def test_a_farm_override_beats_the_default(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        owner = as_owner(client, db)
        response = owner.patch(
            "/v1/admin/revenue/farms/farm_devika/commission", json={"percent": 10}
        )
        assert response.status_code == 200
        assert response.json()["commissionSource"] == "farm"

        farm = devika(owner.get("/v1/admin/revenue").json())
        assert farm["commissionBps"] == 1000
        assert farm["commissionMinor"] == 8_990

    def test_clearing_an_override_returns_the_farm_to_the_default(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        """`null` means "follow the default"; 0 means "charge this farm
        nothing". Collapsing the two would make the first unexpressable."""
        owner = as_owner(client, db)
        owner.patch("/v1/admin/revenue/farms/farm_devika/commission", json={"percent": 10})
        cleared = owner.patch(
            "/v1/admin/revenue/farms/farm_devika/commission", json={"percent": None}
        )
        assert cleared.json()["commissionSource"] == "default"
        assert devika(owner.get("/v1/admin/revenue").json())["commissionBps"] == DEFAULT_BPS

    def test_zero_percent_is_a_real_rate_not_a_cleared_one(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        owner = as_owner(client, db)
        response = owner.patch(
            "/v1/admin/revenue/farms/farm_devika/commission", json={"percent": 0}
        )
        assert response.json() == {
            "farmId": "farm_devika",
            "commissionBps": 0,
            "commissionPercent": 0,
            "commissionSource": "farm",
        }
        farm = devika(owner.get("/v1/admin/revenue").json())
        assert farm["commissionMinor"] == 0
        assert farm["farmEarningsMinor"] == PAID_LINE_MINOR

    @pytest.mark.parametrize("percent", [-1, 101, 12.345])
    def test_rejects_impossible_rates(
        self, client: TestClient, db: SQLiteDatabase, percent: float
    ) -> None:
        response = as_owner(client, db).patch(
            "/v1/admin/revenue/commission", json={"percent": percent}
        )
        assert response.status_code in (400, 422)


class TestPayouts:
    def test_issuing_a_payout_settles_the_outstanding_balance(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        owner = as_owner(client, db)
        before = devika(owner.get("/v1/admin/revenue").json())
        assert before["outstandingPayoutMinor"] == 76_415

        response = owner.post(
            "/v1/admin/revenue/farms/farm_devika/payouts",
            json={"reference": "UTR-123", "note": "July", "expectedPayoutMinor": 76_415},
        )
        assert response.status_code == 200, response.text
        payout = response.json()
        assert payout["payoutMinor"] == 76_415
        assert payout["commissionMinor"] == 13_485
        assert payout["itemCount"] == 1

        after = devika(owner.get("/v1/admin/revenue").json())
        assert after["outstandingPayoutMinor"] == 0
        assert after["paidOutMinor"] == 76_415
        assert after["payoutCount"] == 1

    def test_the_same_revenue_cannot_be_paid_twice(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        """The property the whole ledger exists for."""
        owner = as_owner(client, db)
        first = owner.post(
            "/v1/admin/revenue/farms/farm_devika/payouts",
            json={"expectedPayoutMinor": 76_415},
        )
        assert first.status_code == 200

        second = owner.post("/v1/admin/revenue/farms/farm_devika/payouts", json={})
        assert second.status_code == 409
        assert devika(owner.get("/v1/admin/revenue").json())["paidOutMinor"] == 76_415

    def test_a_stale_expected_amount_is_refused(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        """If the balance moved between the page loading and the click, the
        operator would be approving one number and paying another."""
        response = as_owner(client, db).post(
            "/v1/admin/revenue/farms/farm_devika/payouts",
            json={"expectedPayoutMinor": 999_999},
        )
        assert response.status_code == 409

    def test_new_revenue_after_a_payout_becomes_outstanding_again(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        owner = as_owner(client, db)
        owner.post("/v1/admin/revenue/farms/farm_devika/payouts", json={})

        add_paid_order(db, "ord_later", items=[("oit_later", "prd_alphonso", 100_000)])
        farm = devika(owner.get("/v1/admin/revenue").json())
        assert farm["outstandingPayoutMinor"] == 85_000  # ₹1000 less 15%
        assert farm["paidOutMinor"] == 76_415

    def test_a_rate_change_does_not_restate_a_completed_payout(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        """The payout snapshots the rate it used. Recomputing history from
        today's rate would silently change what a farm was already paid."""
        owner = as_owner(client, db)
        owner.post("/v1/admin/revenue/farms/farm_devika/payouts", json={})
        owner.patch("/v1/admin/revenue/farms/farm_devika/commission", json={"percent": 50})

        payouts = owner.get("/v1/admin/revenue/payouts").json()["items"]
        assert payouts[0]["commissionBps"] == DEFAULT_BPS
        assert payouts[0]["payoutMinor"] == 76_415

    def test_paying_a_farm_with_nothing_outstanding_is_a_conflict(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        owner = as_owner(client, db)
        owner.post("/v1/admin/revenue/farms/farm_devika/payouts", json={})
        assert owner.post("/v1/admin/revenue/farms/farm_devika/payouts", json={}).status_code == 409

    def test_payout_is_recorded_in_the_audit_trail(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        owner = as_owner(client, db)
        owner.post(
            "/v1/admin/revenue/farms/farm_devika/payouts",
            json={"reference": "UTR-9"},
        )
        row = db._conn.execute(
            "SELECT actor_user_id, entity_id FROM audit_logs WHERE action = 'revenue.payout_issued'"
        ).fetchone()
        assert row is not None
        assert row["actor_user_id"] == "usr_admin"
        assert row["entity_id"] == "farm_devika"

    def test_unknown_farm_is_not_found(self, client: TestClient, db: SQLiteDatabase) -> None:
        response = as_owner(client, db).post("/v1/admin/revenue/farms/farm_nope/payouts", json={})
        assert response.status_code == 404


class TestDetail:
    def test_lists_the_order_lines_behind_the_total(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        body = as_owner(client, db).get("/v1/admin/revenue/farms/farm_devika").json()
        assert body["summary"]["farmId"] == "farm_devika"
        references = [line["orderReference"] for line in body["lines"]]
        assert references == ["TG-1001"]  # the paid order only
        assert body["lines"][0]["settled"] is False

    def test_lines_are_marked_settled_after_a_payout(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        owner = as_owner(client, db)
        owner.post("/v1/admin/revenue/farms/farm_devika/payouts", json={})
        body = owner.get("/v1/admin/revenue/farms/farm_devika").json()
        assert body["lines"][0]["settled"] is True
        assert body["lines"][0]["payoutId"] is not None
        assert len(body["payouts"]) == 1

    def test_unknown_farm_is_not_found(self, client: TestClient, db: SQLiteDatabase) -> None:
        assert as_owner(client, db).get("/v1/admin/revenue/farms/farm_nope").status_code == 404


class TestPermissions:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("get", "/v1/admin/revenue"),
            ("get", "/v1/admin/revenue/payouts"),
            ("get", "/v1/admin/revenue/farms/farm_devika"),
            ("patch", "/v1/admin/revenue/commission"),
            ("patch", "/v1/admin/revenue/farms/farm_devika/commission"),
            ("post", "/v1/admin/revenue/farms/farm_devika/payouts"),
        ],
    )
    def test_requires_authentication(self, client: TestClient, method: str, path: str) -> None:
        response = client.request(method.upper(), path, json={})
        assert response.status_code == 401

    def test_a_role_without_revenue_view_is_refused(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        """Hiding the nav entry is a courtesy; the API is the gate."""
        client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
        assert client.get("/v1/admin/revenue").status_code == 403

    def test_reading_revenue_does_not_grant_paying_it_out(
        self, client: TestClient, db: SQLiteDatabase
    ) -> None:
        """`rol_manager` gets revenue.view but not revenue.manage — oversight
        without the ability to move money."""
        db._conn.execute(
            "INSERT INTO users (id, email, display_name, user_type, status,"
            " created_at, updated_at)"
            " VALUES ('usr_viewer', 'viewer@truegrit.test', 'Viewer', 'staff', 'active',"
            " '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')"
        )
        db._conn.execute(
            "INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by)"
            " VALUES ('usr_viewer', 'rol_manager', '2026-07-01T00:00:00Z', 'usr_admin')"
        )
        db._conn.commit()
        client.cookies.set(SESSION_COOKIE, create_session(db, "usr_viewer"))

        assert client.get("/v1/admin/revenue").status_code == 200
        assert (
            client.post("/v1/admin/revenue/farms/farm_devika/payouts", json={}).status_code == 403
        )

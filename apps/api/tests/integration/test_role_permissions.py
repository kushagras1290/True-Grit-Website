"""Every seeded role holds the permissions its job needs.

Grants accumulated one feature at a time across migrations 0013-0034, and the
result had holes that only showed up as a blank page in the console: Publisher
could approve articles it had no permission to list, Accounts owned refunds but
could not open the refunds page, Administrator held almost nothing at all.
0041_role_permission_baseline.sql closed those, and the dev seed restates them
because migrations run before the seed and so cannot see the roles it creates.

These assertions are the contract between those two files. A permission added to
one and forgotten in the other fails here.
"""

from __future__ import annotations

import pytest

from truegrit_api.platform.database import SQLiteDatabase

# The console page each permission unlocks, so a failure says what broke rather
# than just naming a key. See NAV_GROUPS in apps/admin/src/components/layout.tsx.
REQUIRED_GRANTS: dict[str, set[str]] = {
    # Owner and Administrator run everything.
    "super_admin": set(),  # checked separately: must hold every permission
    "admin": set(),
    "manager": {
        "products.view",
        "categories.view",
        "orders.view",
        "inventory.view",
        "returns.view",
        "articles.view",
        "recipes.view",
        "media.view",
        "users.view",  # Farms + Contact Attempts nav
        "audit.view",
        "submissions.view",
        "submissions.review",
        "discussions.view",
        "discussions.moderate",
        # Farm requests: deciding who supplies the market is a commercial call,
        # so it sits with Manager and above and never with the content roles.
        "farm_requests.view",
        "farm_requests.review",
        "reviews.view",
        "reviews.moderate",
    },
    # Approving content it cannot list is not a job.
    "publisher": {
        "pages.view",
        "pages.approve",
        "pages.publish",
        "articles.view",
        "articles.approve",
        "recipes.view",
        "recipes.approve",
        "media.view",
    },
    "content_editor": {
        "pages.view",
        "pages.edit",
        "articles.view",
        "articles.edit",
        "recipes.view",
        "media.view",
        "media.edit",
    },
    "product_manager": {
        "products.view",
        "products.create",
        "products.edit",
        "products.publish",
        "products.archive",
        "categories.view",
        "categories.edit",
        "inventory.view",
    },
    "inventory_manager": {"inventory.view", "inventory.adjust", "products.view", "orders.view"},
    "order_manager": {
        "orders.view",
        "orders.cancel",
        "returns.view",
        "returns.manage",
        "products.view",
        "inventory.view",
        "reviews.view",
        "reviews.moderate",
    },
    # The "Payments & Refunds" console is gated on audit.view; without it the
    # role built for refunds could not reach the page it exists to use.
    "accounts": {"orders.view", "orders.refund", "returns.view", "audit.view"},
    "blogger": {
        "articles.view",
        "articles.create",
        "articles.edit",
        "submissions.view",
        "submissions.review",
        "discussions.view",
        "media.upload",
    },
    "chef": {
        "recipes.view",
        "recipes.create",
        "recipes.edit",
        "submissions.view",
        "submissions.review",
        "discussions.view",
        "media.upload",
    },
    "farm_owner": {
        "products.view",
        "products.edit",
        "inventory.view",
        "inventory.adjust",
        "orders.view",
        "media.upload",
    },
}

# Permissions a role must NOT hold. A role whose whole point is a narrow scope
# stops being useful the moment it quietly acquires a wide one.
FORBIDDEN_GRANTS: dict[str, set[str]] = {
    "accounts": {"products.edit", "categories.edit", "users.invite", "settings.edit"},
    "blogger": {"recipes.publish", "articles.publish", "orders.view", "users.view"},
    "chef": {"articles.publish", "recipes.publish", "orders.view", "users.view"},
    "content_editor": {"pages.publish", "articles.publish", "recipes.publish"},
    "inventory": {"users.view", "settings.edit", "orders.refund"},
    # Site Control now also holds the sign-in and payment kill-switches, so it
    # stays with the owner rather than with everyone who can edit a product.
    "manager": {"settings.edit", "settings.view", "users.invite", "users.manage_roles"},
    "farm_owner": {"users.view", "settings.edit", "orders.refund", "audit.view"},
}


def permissions_for(db: SQLiteDatabase, role_key: str) -> set[str]:
    rows = db._conn.execute(  # test-only direct access
        """
        SELECT p.key
        FROM roles r
        JOIN role_permissions rp ON rp.role_id = r.id
        JOIN permissions p ON p.id = rp.permission_id
        WHERE r.key = ?
        """,
        (role_key,),
    ).fetchall()
    return {row[0] for row in rows}


@pytest.mark.parametrize("role_key", sorted(REQUIRED_GRANTS))
def test_role_holds_the_permissions_its_job_needs(db: SQLiteDatabase, role_key: str):
    granted = permissions_for(db, role_key)
    missing = REQUIRED_GRANTS[role_key] - granted
    assert not missing, f"role '{role_key}' is missing: {sorted(missing)}"


@pytest.mark.parametrize("role_key", sorted(FORBIDDEN_GRANTS))
def test_role_does_not_hold_permissions_outside_its_scope(db: SQLiteDatabase, role_key: str):
    granted = permissions_for(db, role_key)
    overreach = FORBIDDEN_GRANTS[role_key] & granted
    assert not overreach, f"role '{role_key}' should not hold: {sorted(overreach)}"


def test_super_admin_and_admin_hold_every_permission(db: SQLiteDatabase):
    """Both are whole-console roles. The super-admin-only diagnostics pages are
    gated on the `super_admin` role itself, not on a permission row, so this
    does not blur the two."""
    everything = {
        row[0]
        for row in db._conn.execute("SELECT key FROM permissions").fetchall()  # test-only
    }
    assert everything, "no permissions seeded at all"
    assert permissions_for(db, "super_admin") == everything
    assert permissions_for(db, "admin") == everything


def test_every_seeded_role_has_at_least_one_permission(db: SQLiteDatabase):
    """A role with no grants signs in to an empty console — which is exactly the
    state Administrator was in before 0041."""
    empty = db._conn.execute(  # test-only direct access
        """
        SELECT r.key
        FROM roles r
        LEFT JOIN role_permissions rp ON rp.role_id = r.id
        GROUP BY r.key
        HAVING count(rp.permission_id) = 0
        """
    ).fetchall()
    assert not empty, f"roles with no permissions: {[row[0] for row in empty]}"

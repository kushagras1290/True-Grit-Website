"""Reads over `farm_partnership_requests` (migration 0044).

Kept out of `repositories.content` because an application to supply the
marketplace is commercial pipeline, not publishable content, and the two have
no shared query shape. Writes live in `services.farm_partnerships`, matching
the repository/service split used everywhere else: repositories read, services
decide and audit.
"""

from __future__ import annotations

from typing import Any, Final

from truegrit_api.platform.database import Database

# Bounds applied here as well as in the route's Query() validators, so a
# programmatic caller cannot ask for an unbounded page by bypassing FastAPI.
_MAX_LIMIT: Final = 100

# What the admin queue counts as "needs a human". Mirrors the open statuses in
# `services.farm_partnerships`; 'contacted' is included because an application
# somebody rang but never decided is still outstanding work.
OPEN_STATUSES: Final = ("submitted", "under_review", "contacted")


class FarmPartnershipRequestRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_admin(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """The review queue, newest first.

        `status=None` means every status. Search covers the four fields staff
        actually have to hand when someone rings back -- farm, person, email,
        phone.
        """
        search_clause = ""
        params: list[Any] = [status, status]
        if search:
            search_clause = (
                "AND (r.farm_name LIKE ? OR r.contact_name LIKE ?"
                " OR r.contact_email LIKE ? OR r.contact_phone LIKE ?)"
            )
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern, pattern])
        params.extend([min(max(limit, 1), _MAX_LIMIT), max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT r.id, r.status, r.farm_name, r.region, r.state, r.city,
                   r.contact_name, r.contact_email, r.contact_phone,
                   r.created_at, r.reviewed_at, r.linked_farm_id
            FROM farm_partnership_requests r
            WHERE (? IS NULL OR r.status = ?)
            {search_clause}
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def count(self, *, status: str | None = None, search: str | None = None) -> int:
        search_clause = ""
        params: list[Any] = [status, status]
        if search:
            search_clause = (
                "AND (r.farm_name LIKE ? OR r.contact_name LIKE ?"
                " OR r.contact_email LIKE ? OR r.contact_phone LIKE ?)"
            )
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern, pattern])
        row = await self._db.fetch_one(
            f"""
            SELECT COUNT(*) AS total
            FROM farm_partnership_requests r
            WHERE (? IS NULL OR r.status = ?)
            {search_clause}
            """,
            tuple(params),
        )
        return int(row["total"]) if row else 0

    async def count_open(self) -> int:
        """Drives the sidebar badge and the dashboard notification."""
        placeholders = ", ".join("?" for _ in OPEN_STATUSES)
        row = await self._db.fetch_one(
            f"SELECT COUNT(*) AS total FROM farm_partnership_requests"
            f" WHERE status IN ({placeholders})",
            OPEN_STATUSES,
        )
        return int(row["total"]) if row else 0

    async def get(self, entry_id: str) -> dict[str, Any] | None:
        """Full detail, with the reviewer's and linked farm's display names
        resolved -- LEFT JOINs because both are nullable and an application with
        no decision yet must still be readable."""
        return await self._db.fetch_one(
            """
            SELECT r.*,
                   reviewer.display_name AS reviewer_name,
                   submitter.display_name AS submitter_name,
                   f.name AS linked_farm_name
            FROM farm_partnership_requests r
            LEFT JOIN users reviewer ON reviewer.id = r.reviewed_by
            LEFT JOIN users submitter ON submitter.id = r.submitter_user_id
            LEFT JOIN farms f ON f.id = r.linked_farm_id
            WHERE r.id = ?
            """,
            (entry_id,),
        )

    async def count_recent_from_contact(self, *, email: str, phone: str, since_iso: str) -> int:
        """How many applications this person has already filed since
        `since_iso`. The route uses it to refuse a duplicate flood from one
        grower without penalising a shared office IP, which is the failure mode
        of IP-only limiting in rural India where NAT is the norm."""
        row = await self._db.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM farm_partnership_requests
            WHERE created_at >= ? AND (contact_email = ? OR contact_phone = ?)
            """,
            (since_iso, email, phone),
        )
        return int(row["total"]) if row else 0

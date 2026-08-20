"""Operator surface for the SEO agent: read the audit, apply its proposals.

The crawler itself is a separate TypeScript Worker (`apps/seo`) that writes to
the same D1. This module never crawls; it reads what the agent found and, on an
explicit click from a staff member, writes the agent's proposed values into the
CMS rows they belong to.

**Applying a proposal is the sharpest edge in this codebase.** It is a direct
UPDATE against a live catalogue, so four things are enforced here rather than
trusted from upstream:

1. **The target table and column come from an allowlist, never from the row.**
   SQL identifiers cannot be parameterised, so `entity_type` and `field` are
   mapped through `_APPLY_TARGETS` and `_ALLOWED_FIELDS` and anything else is
   refused. The database has CHECK constraints on both columns too; this is the
   second lock, not the only one.
2. **The previous value is read at apply time, not taken from the proposal.**
   The proposal recorded what the field held when the crawl ran, which may be
   hours old. A revert has to restore what was actually there a moment before,
   or it silently discards an edit somebody made in between.
3. **Every apply and revert is audited**, with before and after, like every
   other sensitive write in this codebase.
4. **A bulk apply is not a transaction.** Each proposal succeeds or fails on
   its own and the caller is told the counts, because one deleted product must
   not roll back forty good changes.

Nothing here generates copy. The values were produced by the agent from the
entity's own text and are applied verbatim.
"""

from __future__ import annotations

from typing import Any, Literal

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.logging import log_event
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

FindingStatus = Literal["open", "fixed", "ignored"]
ProposalStatus = Literal["pending", "applied", "rejected", "superseded", "reverted"]

# entity_type -> (table, key column). The only tables this module may write.
_APPLY_TARGETS: dict[str, tuple[str, str]] = {
    "product": ("products", "id"),
    "article": ("articles", "id"),
    "recipe": ("recipes", "id"),
    "category": ("categories", "id"),
    "page": ("pages", "id"),
    "route": ("route_seo_overrides", "path"),
}

# The only columns this module may write, and which tables actually have them.
# `products` and `categories` have no `seo_keywords` column; a proposal naming
# it for one of those is a bug in the agent and is refused here rather than
# turned into a SQL error.
_ALLOWED_FIELDS: dict[str, frozenset[str]] = {
    "product": frozenset({"seo_title", "seo_description", "indexing_policy"}),
    "category": frozenset({"seo_title", "seo_description", "indexing_policy"}),
    "article": frozenset({"seo_title", "seo_description", "seo_keywords", "indexing_policy"}),
    "recipe": frozenset({"seo_title", "seo_description", "seo_keywords", "indexing_policy"}),
    "page": frozenset({"seo_title", "seo_description", "seo_keywords", "indexing_policy"}),
    "route": frozenset({"seo_title", "seo_description", "seo_keywords", "indexing_policy"}),
}

_INDEXING_VALUES = frozenset({"index", "noindex"})
_MAX_PAGE_SIZE = 200
_SEVERITY_ORDER = (
    "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END"
)
# 0 = manual only. The Worker's daily cron tick checks this against the last
# cron-queued run before deciding to actually queue one -- see apps/seo/worker.
_ALLOWED_SCHEDULE_DAYS = frozenset({0, 1, 3, 7})


# --- Settings ---------------------------------------------------------------


async def is_enabled(db: Database) -> bool:
    row = await db.fetch_one("SELECT value FROM app_settings WHERE key = 'seo.enabled'")
    return row is not None and row["value"] == "true"


async def get_settings(db: Database) -> dict[str, Any]:
    rows = await db.fetch_all(
        "SELECT key, value FROM app_settings WHERE key LIKE 'seo.%'",
    )
    values = {str(row["key"]): str(row["value"] or "") for row in rows}
    try:
        schedule_days = int(values.get("seo.schedule_days") or 1)
    except ValueError:
        schedule_days = 1
    if schedule_days not in _ALLOWED_SCHEDULE_DAYS:
        schedule_days = 1
    return {
        "enabled": values.get("seo.enabled") == "true",
        "maxPages": int(values.get("seo.max_pages") or 500),
        "competitorMaxPages": int(values.get("seo.competitor_max_pages") or 30),
        "scheduleDays": schedule_days,
    }


async def update_settings(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    enabled: bool | None = None,
    schedule_days: int | None = None,
) -> dict[str, Any]:
    """Partial update: only the fields actually sent are written, the same
    discipline `update_storefront_settings` uses -- flipping the schedule
    must never silently reset the enabled switch to whatever the client last
    rendered, or the other way round."""
    if schedule_days is not None and schedule_days not in _ALLOWED_SCHEDULE_DAYS:
        raise ValidationAppError("Schedule must be 0 (manual), 1, 3, or 7 days.")

    now = utc_now_iso()
    statements: list[tuple[str, Any]] = []
    changed: dict[str, Any] = {}

    if enabled is not None:
        statements.append(
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by)"
                " VALUES ('seo.enabled', ?, ?, ?) ON CONFLICT(key) DO UPDATE SET"
                " value = excluded.value, updated_at = excluded.updated_at,"
                " updated_by = excluded.updated_by",
                ("true" if enabled else "false", now, actor.user_id),
            )
        )
        changed["enabled"] = enabled

    if schedule_days is not None:
        statements.append(
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by)"
                " VALUES ('seo.schedule_days', ?, ?, ?) ON CONFLICT(key) DO UPDATE SET"
                " value = excluded.value, updated_at = excluded.updated_at,"
                " updated_by = excluded.updated_by",
                (str(schedule_days), now, actor.user_id),
            )
        )
        changed["scheduleDays"] = schedule_days

    if not statements:
        return await get_settings(db)

    statements.append(
        audit_statement(
            action="seo.settings_changed",
            entity_type="app_setting",
            entity_id="seo",
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after=changed,
        )
    )
    await db.batch(statements)
    return await get_settings(db)


# --- Runs -------------------------------------------------------------------


async def list_runs(db: Database, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        "SELECT id, status, trigger, base_url, queued_at, started_at, finished_at,"
        " pages_discovered, pages_crawled, pages_failed, findings_opened, findings_closed, error"
        " FROM seo_crawl_runs ORDER BY queued_at DESC LIMIT ?",
        (max(1, min(_MAX_PAGE_SIZE, limit)),),
    )
    return [
        {
            "id": row["id"],
            "status": row["status"],
            "trigger": row["trigger"],
            "baseUrl": row["base_url"],
            "queuedAt": row["queued_at"],
            "startedAt": row["started_at"],
            "finishedAt": row["finished_at"],
            "pagesDiscovered": row["pages_discovered"],
            "pagesCrawled": row["pages_crawled"],
            "pagesFailed": row["pages_failed"],
            "findingsOpened": row["findings_opened"],
            "findingsClosed": row["findings_closed"],
            "error": row["error"],
        }
        for row in rows
    ]


async def queue_run(db: Database, actor: Principal, request_id: str) -> dict[str, Any]:
    """Ask for a crawl. The Worker's own cron picks this up within a few
    minutes; the API deliberately has no producer binding for the crawler, so
    a queued row is the entire handoff."""
    if not await is_enabled(db):
        raise ValidationAppError(
            "The SEO agent is switched off. Turn it on before starting a crawl."
        )
    existing = await db.fetch_one(
        "SELECT id FROM seo_crawl_runs WHERE status IN ('queued', 'running') LIMIT 1"
    )
    if existing is not None:
        raise ConflictError("A crawl is already queued or running.")

    run_id = new_id("seorun")
    now = utc_now_iso()
    base = await db.fetch_one("SELECT value FROM app_settings WHERE key = 'seo.base_url'")
    await db.batch(
        [
            (
                "INSERT INTO seo_crawl_runs (id, status, trigger, requested_by, base_url,"
                " queued_at) VALUES (?, 'queued', 'manual', ?, ?, ?)",
                (run_id, actor.user_id, str(base["value"]) if base else "", now),
            ),
            audit_statement(
                action="seo.run_queued",
                entity_type="seo_crawl_run",
                entity_id=run_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )
    return {"id": run_id, "status": "queued"}


# --- Findings ---------------------------------------------------------------


async def list_findings(
    db: Database,
    *,
    status: FindingStatus | None = "open",
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    conditions: list[str] = []
    params: list[Any] = []
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if category is not None:
        conditions.append("category = ?")
        params.append(category)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

    total = await db.fetch_one(f"SELECT COUNT(*) AS total FROM seo_findings{where}", tuple(params))
    rows = await db.fetch_all(
        f"""
        SELECT id, rule, category, severity, path, page_type, summary, detail, fix_hint,
               evidence_json, status, first_seen_at, last_seen_at
        FROM seo_findings{where}
        ORDER BY {_SEVERITY_ORDER}, first_seen_at
        LIMIT ? OFFSET ?
        """,
        (*params, max(1, min(_MAX_PAGE_SIZE, limit)), max(0, offset)),
    )
    return {
        "total": int(total["total"]) if total else 0,
        "items": [
            {
                "id": row["id"],
                "rule": row["rule"],
                "category": row["category"],
                "severity": row["severity"],
                "path": row["path"],
                "pageType": row["page_type"],
                "summary": row["summary"],
                "detail": row["detail"],
                "fixHint": row["fix_hint"],
                "status": row["status"],
                "firstSeenAt": row["first_seen_at"],
                "lastSeenAt": row["last_seen_at"],
            }
            for row in rows
        ],
    }


async def summarise(db: Database) -> dict[str, Any]:
    """Counts for the dashboard header."""
    severities = await db.fetch_all(
        "SELECT severity, COUNT(*) AS count FROM seo_findings WHERE status = 'open'"
        " GROUP BY severity"
    )
    categories = await db.fetch_all(
        "SELECT category, COUNT(*) AS count FROM seo_findings WHERE status = 'open'"
        " GROUP BY category"
    )
    pending = await db.fetch_one(
        "SELECT COUNT(*) AS count FROM seo_proposals WHERE status = 'pending'"
    )
    applied = await db.fetch_one(
        "SELECT COUNT(*) AS count FROM seo_proposals WHERE status = 'applied'"
    )
    return {
        "openBySeverity": {str(row["severity"]): int(row["count"]) for row in severities},
        "openByCategory": {str(row["category"]): int(row["count"]) for row in categories},
        "pendingProposals": int(pending["count"]) if pending else 0,
        "appliedProposals": int(applied["count"]) if applied else 0,
    }


async def set_finding_status(
    db: Database, actor: Principal, request_id: str, finding_id: str, status: FindingStatus
) -> dict[str, Any]:
    existing = await db.fetch_one("SELECT id, status FROM seo_findings WHERE id = ?", (finding_id,))
    if existing is None:
        raise NotFoundError("Finding not found.")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE seo_findings SET status = ?, resolved_at = ?, resolved_by = ? WHERE id = ?",
                (
                    status,
                    now if status != "open" else None,
                    actor.user_id if status != "open" else None,
                    finding_id,
                ),
            ),
            audit_statement(
                action="seo.finding_status_changed",
                entity_type="seo_finding",
                entity_id=finding_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": existing["status"]},
                after={"status": status},
            ),
        ]
    )
    return {"id": finding_id, "status": status}


# --- Keywords and content gaps ----------------------------------------------


async def list_keywords(db: Database, *, limit: int = 100) -> list[dict[str, Any]]:
    """Terms competitors invest in more than we do, best gap first.

    These describe what rivals *target*, not what they rank for: the crawl can
    see a phrase in fifteen of their titles, and cannot see a single search
    impression. The API says `gapScore` rather than anything about ranking so
    the dashboard has no vocabulary to overclaim with.
    """
    latest = await db.fetch_one(
        "SELECT id FROM seo_crawl_runs WHERE status = 'completed' ORDER BY finished_at DESC LIMIT 1"
    )
    if latest is None:
        return []
    rows = await db.fetch_all(
        "SELECT term, term_words, own_pages, own_title_hits, competitor_pages,"
        " competitor_title_hits, competitor_count, gap_score FROM seo_keywords"
        " WHERE run_id = ? ORDER BY gap_score DESC LIMIT ?",
        (latest["id"], max(1, min(_MAX_PAGE_SIZE, limit))),
    )
    return [
        {
            "term": row["term"],
            "termWords": row["term_words"],
            "ownPages": row["own_pages"],
            "ownTitleHits": row["own_title_hits"],
            "competitorPages": row["competitor_pages"],
            "competitorTitleHits": row["competitor_title_hits"],
            "competitorCount": row["competitor_count"],
            "gapScore": row["gap_score"],
        }
        for row in rows
    ]


async def list_content_gaps(db: Database, *, limit: int = 60) -> list[dict[str, Any]]:
    """Page sections competitors publish that we do not have anywhere.

    A left join against our own headings for the same page type is what turns
    a list of their sections into a list of *our* omissions.
    """
    latest = await db.fetch_one(
        "SELECT id FROM seo_crawl_runs WHERE status = 'completed' ORDER BY finished_at DESC LIMIT 1"
    )
    if latest is None:
        return []
    rows = await db.fetch_all(
        """
        SELECT c.page_type, c.heading_key, MIN(c.heading) AS heading,
               COUNT(DISTINCT c.competitor_id) AS competitor_count,
               SUM(c.occurrences) AS occurrences
        FROM seo_content_chunks c
        WHERE c.run_id = ? AND c.source = 'competitor'
          AND NOT EXISTS (
            SELECT 1 FROM seo_content_chunks own
            WHERE own.run_id = c.run_id AND own.source = 'own'
              AND own.page_type = c.page_type AND own.heading_key = c.heading_key
          )
        GROUP BY c.page_type, c.heading_key
        ORDER BY competitor_count DESC, occurrences DESC
        LIMIT ?
        """,
        (latest["id"], max(1, min(_MAX_PAGE_SIZE, limit))),
    )
    return [
        {
            "pageType": row["page_type"],
            "heading": row["heading"],
            "headingKey": row["heading_key"],
            "competitorCount": int(row["competitor_count"]),
            "occurrences": int(row["occurrences"]),
        }
        for row in rows
    ]


# --- Competitors ------------------------------------------------------------


async def list_competitors(db: Database) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        "SELECT id, label, origin, status, robots_blocked, last_crawled_at, last_error, notes"
        " FROM seo_competitors ORDER BY label"
    )
    return [
        {
            "id": row["id"],
            "label": row["label"],
            "origin": row["origin"],
            "status": row["status"],
            "robotsBlocked": bool(row["robots_blocked"]),
            "lastCrawledAt": row["last_crawled_at"],
            "lastError": row["last_error"],
            "notes": row["notes"],
        }
        for row in rows
    ]


async def add_competitor(
    db: Database, actor: Principal, request_id: str, *, label: str, origin: str
) -> dict[str, Any]:
    clean_label = label.strip()
    clean_origin = origin.strip().rstrip("/")
    if not clean_label:
        raise ValidationAppError("Give the competitor a name.")
    if not clean_origin.startswith(("http://", "https://")):
        raise ValidationAppError("The site must start with http:// or https://.")
    # Only the origin is stored, so a pasted deep link cannot turn into a crawl
    # rooted halfway down someone's site.
    parts = clean_origin.split("/")
    if len(parts) > 3:
        clean_origin = "/".join(parts[:3])

    existing = await db.fetch_one(
        "SELECT id FROM seo_competitors WHERE origin = ? COLLATE NOCASE", (clean_origin,)
    )
    if existing is not None:
        raise ConflictError("That site is already on the list.")

    competitor_id = new_id("seocmp")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO seo_competitors (id, label, origin, status, added_at, added_by)"
                " VALUES (?, ?, ?, 'active', ?, ?)",
                (competitor_id, clean_label, clean_origin, now, actor.user_id),
            ),
            audit_statement(
                action="seo.competitor_added",
                entity_type="seo_competitor",
                entity_id=competitor_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"label": clean_label, "origin": clean_origin},
            ),
        ]
    )
    return {"id": competitor_id, "label": clean_label, "origin": clean_origin, "status": "active"}


async def remove_competitor(
    db: Database, actor: Principal, request_id: str, competitor_id: str
) -> None:
    existing = await db.fetch_one(
        "SELECT id, label FROM seo_competitors WHERE id = ?", (competitor_id,)
    )
    if existing is None:
        raise NotFoundError("Competitor not found.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM seo_competitors WHERE id = ?", (competitor_id,)),
            audit_statement(
                action="seo.competitor_removed",
                entity_type="seo_competitor",
                entity_id=competitor_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"label": existing["label"]},
            ),
        ]
    )


# --- Proposals --------------------------------------------------------------


def _proposal_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "entityType": row["entity_type"],
        "entityId": row["entity_id"],
        "entityLabel": row["entity_label"],
        "path": row["path"],
        "field": row["field"],
        "currentValue": row["current_value"] or "",
        "proposedValue": row["proposed_value"],
        "rationale": row["rationale"],
        "source": row["source"],
        "sourceRef": row["source_ref"],
        "confidence": row["confidence"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "appliedAt": row["applied_at"],
    }


async def list_proposals(
    db: Database, *, status: ProposalStatus = "pending", limit: int = 200
) -> dict[str, Any]:
    total = await db.fetch_one(
        "SELECT COUNT(*) AS total FROM seo_proposals WHERE status = ?", (status,)
    )
    rows = await db.fetch_all(
        "SELECT id, entity_type, entity_id, entity_label, path, field, current_value,"
        " proposed_value, rationale, source, source_ref, confidence, status, created_at,"
        " applied_at FROM seo_proposals WHERE status = ?"
        " ORDER BY confidence DESC, entity_label, field LIMIT ?",
        (status, max(1, min(_MAX_PAGE_SIZE, limit))),
    )
    return {
        "total": int(total["total"]) if total else 0,
        "items": [_proposal_row(row) for row in rows],
    }


def _target_for(entity_type: str, field: str) -> tuple[str, str]:
    """Resolve a proposal to a real table and column, or refuse.

    This is the function that stops a row in the database from choosing which
    SQL identifier gets interpolated. Both values are validated against the
    allowlists above before either reaches a query string.
    """
    target = _APPLY_TARGETS.get(entity_type)
    if target is None:
        raise ValidationAppError(f"Unknown entity type: {entity_type}")
    allowed = _ALLOWED_FIELDS.get(entity_type, frozenset())
    if field not in allowed:
        raise ValidationAppError(
            f"{entity_type} rows have no {field} field, so this change cannot be applied."
        )
    return target


async def apply_proposal(
    db: Database, actor: Principal, request_id: str, proposal_id: str
) -> dict[str, Any]:
    """Write one proposed value into its CMS row."""
    proposal = await db.fetch_one(
        "SELECT id, entity_type, entity_id, field, proposed_value, status, path, entity_label"
        " FROM seo_proposals WHERE id = ?",
        (proposal_id,),
    )
    if proposal is None:
        raise NotFoundError("Proposal not found.")
    if proposal["status"] != "pending":
        raise ConflictError(f"That change is already {proposal['status']}.")

    entity_type = str(proposal["entity_type"])
    field = str(proposal["field"])
    table, key_column = _target_for(entity_type, field)
    value = str(proposal["proposed_value"])

    if field == "indexing_policy" and value not in _INDEXING_VALUES:
        raise ValidationAppError("Indexing policy must be 'index' or 'noindex'.")

    # Identifiers are allowlisted constants by this point; the values stay
    # parameterised.
    current = await db.fetch_one(
        f"SELECT {field} AS value FROM {table} WHERE {key_column} = ?",
        (proposal["entity_id"],),
    )
    if current is None:
        raise NotFoundError(
            f"The {entity_type} this change targets no longer exists. It was probably deleted"
            " after the crawl ran."
        )
    previous = str(current["value"] or "")
    now = utc_now_iso()

    await db.batch(
        [
            (
                f"UPDATE {table} SET {field} = ? WHERE {key_column} = ?",
                (value, proposal["entity_id"]),
            ),
            (
                "UPDATE seo_proposals SET status = 'applied', previous_value = ?,"
                " applied_at = ?, applied_by = ? WHERE id = ?",
                (previous, now, actor.user_id, proposal_id),
            ),
            audit_statement(
                action="seo.proposal_applied",
                entity_type=entity_type,
                entity_id=str(proposal["entity_id"]),
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={field: previous},
                after={field: value},
            ),
        ]
    )
    log_event(
        "info",
        "seo.proposal_applied",
        proposal_id=proposal_id,
        entity_type=entity_type,
        field=field,
        path=proposal["path"],
    )
    return {"id": proposal_id, "status": "applied", "previousValue": previous}


async def apply_all(
    db: Database, actor: Principal, request_id: str, *, proposal_ids: list[str] | None = None
) -> dict[str, Any]:
    """Apply every pending proposal, or a named subset.

    Not a transaction on purpose. One product deleted since the crawl must not
    roll back the other forty changes, so each is attempted independently and
    the failures are reported rather than raised.
    """
    if proposal_ids:
        placeholders = ", ".join("?" for _ in proposal_ids)
        rows = await db.fetch_all(
            f"SELECT id FROM seo_proposals WHERE status = 'pending' AND id IN ({placeholders})",
            tuple(proposal_ids),
        )
    else:
        rows = await db.fetch_all("SELECT id FROM seo_proposals WHERE status = 'pending'")

    applied = 0
    failures: list[dict[str, str]] = []
    for row in rows:
        try:
            await apply_proposal(db, actor, request_id, str(row["id"]))
            applied += 1
        except (ValidationAppError, NotFoundError, ConflictError) as exc:
            failures.append({"id": str(row["id"]), "reason": str(exc)})

    log_event(
        "info",
        "seo.bulk_apply",
        request_id=request_id,
        attempted=len(rows),
        applied=applied,
        failed=len(failures),
    )
    return {"attempted": len(rows), "applied": applied, "failed": failures}


async def reject_proposal(
    db: Database, actor: Principal, request_id: str, proposal_id: str
) -> dict[str, Any]:
    existing = await db.fetch_one(
        "SELECT id, status FROM seo_proposals WHERE id = ?", (proposal_id,)
    )
    if existing is None:
        raise NotFoundError("Proposal not found.")
    if existing["status"] != "pending":
        raise ConflictError(f"That change is already {existing['status']}.")
    now = utc_now_iso()
    await db.batch(
        [
            ("UPDATE seo_proposals SET status = 'rejected' WHERE id = ?", (proposal_id,)),
            audit_statement(
                action="seo.proposal_rejected",
                entity_type="seo_proposal",
                entity_id=proposal_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )
    return {"id": proposal_id, "status": "rejected"}


async def revert_proposal(
    db: Database, actor: Principal, request_id: str, proposal_id: str
) -> dict[str, Any]:
    """Put back exactly what the field held before this proposal was applied."""
    proposal = await db.fetch_one(
        "SELECT id, entity_type, entity_id, field, previous_value, status"
        " FROM seo_proposals WHERE id = ?",
        (proposal_id,),
    )
    if proposal is None:
        raise NotFoundError("Proposal not found.")
    if proposal["status"] != "applied":
        raise ConflictError("Only an applied change can be reverted.")

    entity_type = str(proposal["entity_type"])
    field = str(proposal["field"])
    table, key_column = _target_for(entity_type, field)
    previous = str(proposal["previous_value"] or "")
    now = utc_now_iso()

    await db.batch(
        [
            (
                f"UPDATE {table} SET {field} = ? WHERE {key_column} = ?",
                (previous, proposal["entity_id"]),
            ),
            (
                "UPDATE seo_proposals SET status = 'reverted', reverted_at = ? WHERE id = ?",
                (now, proposal_id),
            ),
            audit_statement(
                action="seo.proposal_reverted",
                entity_type=entity_type,
                entity_id=str(proposal["entity_id"]),
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={field: previous},
            ),
        ]
    )
    return {"id": proposal_id, "status": "reverted"}

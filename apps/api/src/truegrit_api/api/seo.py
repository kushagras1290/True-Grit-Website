"""SEO agent dashboard API, consumed by `apps/seo`'s SPA at seo.truegritin.com.

Every route is gated on `seo.manage` (migration 0110). The dashboard is a
separate Worker serving static assets, exactly like `apps/process`; it holds no
credentials of its own and authenticates against the same staff session cookie
this API already issues, so "password protected" here means a real staff
account rather than a shared secret.

The crawler Worker does not talk to this API at all. It writes to the same D1
directly, and the only handoff in the other direction is a queued row in
`seo_crawl_runs` that its cron picks up.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database, require_permission
from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.services import seo

router = APIRouter(tags=["seo-agent"])

_Actor = Annotated[Principal, Depends(require_permission("seo.manage"))]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class EnabledRequest(_CamelModel):
    enabled: bool


class CompetitorRequest(_CamelModel):
    label: str = Field(min_length=1, max_length=120)
    origin: str = Field(min_length=4, max_length=200)


class FindingStatusRequest(_CamelModel):
    status: Literal["open", "fixed", "ignored"]


class ApplyAllRequest(_CamelModel):
    """Omit `proposalIds` to apply everything currently pending.

    The explicit list exists so the dashboard can offer "apply the ones I have
    ticked" without a different endpoint, and so a client that has just
    rendered a page of proposals applies exactly those rather than whatever
    became pending in the meantime.
    """

    proposal_ids: list[str] | None = Field(default=None, max_length=500)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


# --- Overview ---------------------------------------------------------------


@router.get("/seo/summary")
async def summary(db: Annotated[Database, Depends(get_database)], actor: _Actor) -> dict[str, Any]:
    return {
        "settings": await seo.get_settings(db),
        "counts": await seo.summarise(db),
        "runs": await seo.list_runs(db, limit=5),
    }


@router.patch("/seo/settings")
async def set_enabled(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    request: Request,
    body: EnabledRequest,
) -> dict[str, Any]:
    return await seo.set_enabled(db, actor, _request_id(request), body.enabled)


# --- Runs -------------------------------------------------------------------


@router.get("/seo/runs")
async def list_runs(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict[str, Any]]:
    return await seo.list_runs(db, limit=limit)


@router.post("/seo/runs")
async def queue_run(
    db: Annotated[Database, Depends(get_database)], actor: _Actor, request: Request
) -> dict[str, Any]:
    """Queue a crawl. The agent's cron starts it within a few minutes."""
    return await seo.queue_run(db, actor, _request_id(request))


# --- Findings ---------------------------------------------------------------


@router.get("/seo/findings")
async def list_findings(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    status: Annotated[Literal["open", "fixed", "ignored"] | None, Query()] = "open",
    category: Annotated[
        Literal["schema", "eeat", "links", "indexing", "content"] | None, Query()
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return await seo.list_findings(db, status=status, category=category, limit=limit, offset=offset)


@router.patch("/seo/findings/{finding_id}")
async def set_finding_status(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    request: Request,
    finding_id: str,
    body: FindingStatusRequest,
) -> dict[str, Any]:
    return await seo.set_finding_status(db, actor, _request_id(request), finding_id, body.status)


# --- Research ---------------------------------------------------------------


@router.get("/seo/keywords")
async def list_keywords(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[dict[str, Any]]:
    """Phrases competitors target more heavily than we do.

    `gapScore` measures their editorial investment against ours. It is not a
    ranking or a search volume, and the dashboard labels it accordingly.
    """
    return await seo.list_keywords(db, limit=limit)


@router.get("/seo/content-gaps")
async def list_content_gaps(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
) -> list[dict[str, Any]]:
    return await seo.list_content_gaps(db, limit=limit)


# --- Competitors ------------------------------------------------------------


@router.get("/seo/competitors")
async def list_competitors(
    db: Annotated[Database, Depends(get_database)], actor: _Actor
) -> list[dict[str, Any]]:
    return await seo.list_competitors(db)


@router.post("/seo/competitors")
async def add_competitor(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    request: Request,
    body: CompetitorRequest,
) -> dict[str, Any]:
    return await seo.add_competitor(
        db, actor, _request_id(request), label=body.label, origin=body.origin
    )


@router.delete("/seo/competitors/{competitor_id}")
async def remove_competitor(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    request: Request,
    competitor_id: str,
) -> dict[str, str]:
    await seo.remove_competitor(db, actor, _request_id(request), competitor_id)
    return {"id": competitor_id}


# --- Proposals --------------------------------------------------------------


@router.get("/seo/proposals")
async def list_proposals(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    status: Annotated[
        Literal["pending", "applied", "rejected", "superseded", "reverted"], Query()
    ] = "pending",
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> dict[str, Any]:
    return await seo.list_proposals(db, status=status, limit=limit)


@router.post("/seo/proposals/apply")
async def apply_all(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    request: Request,
    body: ApplyAllRequest,
) -> dict[str, Any]:
    """The one-click button. Writes every pending change into its CMS row.

    Reports per-item failures rather than failing the batch: a product deleted
    since the crawl should not stop the rest from being applied.
    """
    return await seo.apply_all(db, actor, _request_id(request), proposal_ids=body.proposal_ids)


@router.post("/seo/proposals/{proposal_id}/apply")
async def apply_one(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    request: Request,
    proposal_id: str,
) -> dict[str, Any]:
    return await seo.apply_proposal(db, actor, _request_id(request), proposal_id)


@router.post("/seo/proposals/{proposal_id}/reject")
async def reject_one(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    request: Request,
    proposal_id: str,
) -> dict[str, Any]:
    return await seo.reject_proposal(db, actor, _request_id(request), proposal_id)


@router.post("/seo/proposals/{proposal_id}/revert")
async def revert_one(
    db: Annotated[Database, Depends(get_database)],
    actor: _Actor,
    request: Request,
    proposal_id: str,
) -> dict[str, Any]:
    """Undo an applied change, restoring the value the field held before."""
    return await seo.revert_proposal(db, actor, _request_id(request), proposal_id)

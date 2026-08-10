"""Dedicated language and translation operations API."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database, get_translator, require_permission
from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.platform.translation import Translator
from truegrit_api.services import translation_batches, translation_hub

admin_router = APIRouter(tags=["translation-hub"])
public_router = APIRouter(tags=["storefront-translations"])

_TranslationActor = Annotated[Principal, Depends(require_permission("translations.manage"))]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ResourceSaveRequest(_CamelModel):
    translations: dict[str, str] = Field(max_length=translation_hub.MAX_FIELDS_PER_RESOURCE)


class InterfaceEntry(_CamelModel):
    source: str = Field(min_length=1, max_length=translation_hub.MAX_TEXT_LENGTH)
    translation: str = Field(default="", max_length=translation_hub.MAX_TEXT_LENGTH)


class InterfaceSaveRequest(_CamelModel):
    entries: dict[str, InterfaceEntry] = Field(max_length=100)


class LocaleSaveRequest(_CamelModel):
    code: str = Field(min_length=2, max_length=35)
    native_name: str = Field(min_length=1, max_length=120)
    english_name: str = Field(min_length=1, max_length=120)
    direction: Literal["ltr", "rtl"] = "ltr"
    group_name: Literal["indian", "world"] = "world"
    active: bool = True


class ContentBatchResource(_CamelModel):
    resource_id: str = Field(min_length=1, max_length=120)
    field_keys: list[str] = Field(
        default_factory=list, max_length=translation_hub.MAX_FIELDS_PER_RESOURCE
    )


class ContentBatchRequest(_CamelModel):
    resource_type: str = Field(min_length=1, max_length=40)
    resources: list[ContentBatchResource] = Field(
        min_length=1, max_length=translation_batches.MAX_CONTENT_RESOURCES
    )
    locales: list[str] = Field(min_length=1, max_length=translation_batches.MAX_LANGUAGES)
    overwrite_existing: bool = False


class InterfaceBatchRequest(_CamelModel):
    target: Literal["storefront", "admin"] = "storefront"
    entries: dict[str, InterfaceEntry] = Field(
        min_length=1, max_length=translation_batches.MAX_INTERFACE_ENTRIES
    )
    locales: list[str] = Field(min_length=1, max_length=translation_batches.MAX_LANGUAGES)
    overwrite_existing: bool = False


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@public_router.get("/locales/custom")
async def public_custom_locales(
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return {"items": await translation_hub.list_custom_locales(db, active_only=True)}


@public_router.get("/translations/interface")
async def public_interface_translations(
    db: Annotated[Database, Depends(get_database)],
    locale: Annotated[str, Query(min_length=2, max_length=35)],
    target: Annotated[Literal["storefront", "admin"], Query()] = "storefront",
) -> Any:
    return {
        "locale": locale,
        "target": target,
        "messages": await translation_hub.interface_overrides(db, locale, target=target),
    }


@admin_router.get("/translation-hub/resources")
async def list_translation_resources(
    db: Annotated[Database, Depends(get_database)],
    _actor: _TranslationActor,
    resource_type: Annotated[str, Query(alias="type", min_length=1, max_length=40)],
    locale: Annotated[str, Query(min_length=2, max_length=35)],
    search: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    return await translation_hub.list_resources(
        db,
        resource_type,
        locale,
        search=search,
        limit=limit,
        offset=offset,
    )


@admin_router.get("/translation-hub/resources/{resource_type}/{resource_id}")
async def translation_resource_detail(
    resource_type: str,
    resource_id: str,
    db: Annotated[Database, Depends(get_database)],
    _actor: _TranslationActor,
    locale: Annotated[str, Query(min_length=2, max_length=35)],
) -> Any:
    return await translation_hub.resource_detail(db, resource_type, resource_id, locale)


@admin_router.put("/translation-hub/resources/{resource_type}/{resource_id}")
async def save_translation_resource(
    resource_type: str,
    resource_id: str,
    payload: ResourceSaveRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: _TranslationActor,
    locale: Annotated[str, Query(min_length=2, max_length=35)],
) -> Any:
    return await translation_hub.save_resource(
        db,
        actor,
        _request_id(request),
        resource_type,
        resource_id,
        locale,
        payload.translations,
    )


@admin_router.post("/translation-hub/resources/{resource_type}/{resource_id}/auto-translate")
async def auto_translate_resource(
    resource_type: str,
    resource_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: _TranslationActor,
    translator: Annotated[Translator, Depends(get_translator)],
    locale: Annotated[str, Query(min_length=2, max_length=35)],
) -> Any:
    return await translation_hub.auto_translate_resource(
        db,
        actor,
        _request_id(request),
        translator,
        resource_type,
        resource_id,
        locale,
    )


@admin_router.delete("/translation-hub/resources/{resource_type}/{resource_id}")
async def delete_translation_resource(
    resource_type: str,
    resource_id: str,
    db: Annotated[Database, Depends(get_database)],
    _actor: _TranslationActor,
    locale: Annotated[str, Query(min_length=2, max_length=35)],
) -> Any:
    await translation_hub.delete_resource_locale(db, resource_type, resource_id, locale)
    return {"deleted": True}


@admin_router.get("/translation-hub/interface")
async def admin_interface_translations(
    db: Annotated[Database, Depends(get_database)],
    _actor: _TranslationActor,
    locale: Annotated[str, Query(min_length=2, max_length=35)],
    target: Annotated[Literal["storefront", "admin"], Query()] = "storefront",
) -> Any:
    return {
        "locale": locale,
        "target": target,
        "messages": await translation_hub.interface_overrides(db, locale, target=target),
    }


@admin_router.put("/translation-hub/interface")
async def save_interface_translations(
    payload: InterfaceSaveRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: _TranslationActor,
    locale: Annotated[str, Query(min_length=2, max_length=35)],
    target: Annotated[Literal["storefront", "admin"], Query()] = "storefront",
) -> Any:
    messages = await translation_hub.save_interface_entries(
        db,
        actor,
        _request_id(request),
        None,
        locale,
        {key: value.model_dump() for key, value in payload.entries.items()},
        auto_translate=False,
        target=target,
    )
    return {"locale": locale, "messages": messages}


@admin_router.post("/translation-hub/interface/auto-translate")
async def auto_translate_interface(
    payload: InterfaceSaveRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: _TranslationActor,
    translator: Annotated[Translator, Depends(get_translator)],
    locale: Annotated[str, Query(min_length=2, max_length=35)],
    target: Annotated[Literal["storefront", "admin"], Query()] = "storefront",
) -> Any:
    messages = await translation_hub.save_interface_entries(
        db,
        actor,
        _request_id(request),
        translator,
        locale,
        {key: value.model_dump() for key, value in payload.entries.items()},
        auto_translate=True,
        target=target,
    )
    return {"locale": locale, "messages": messages}


@admin_router.post("/translation-hub/batches/content", status_code=202)
async def create_content_translation_batch(
    payload: ContentBatchRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: _TranslationActor,
) -> Any:
    return await translation_batches.create_content_batch(
        db,
        actor,
        _request_id(request),
        resource_type=payload.resource_type,
        resources=[item.model_dump(by_alias=True) for item in payload.resources],
        locales=payload.locales,
        overwrite_existing=payload.overwrite_existing,
    )


@admin_router.post("/translation-hub/batches/interface", status_code=202)
async def create_interface_translation_batch(
    payload: InterfaceBatchRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: _TranslationActor,
) -> Any:
    return await translation_batches.create_interface_batch(
        db,
        actor,
        _request_id(request),
        target=payload.target,
        entries={key: item.model_dump() for key, item in payload.entries.items()},
        locales=payload.locales,
        overwrite_existing=payload.overwrite_existing,
    )


@admin_router.get("/translation-hub/batches/{batch_id}")
async def translation_batch_detail(
    batch_id: str,
    db: Annotated[Database, Depends(get_database)],
    _actor: _TranslationActor,
) -> Any:
    return await translation_batches.batch_detail(db, batch_id)


@admin_router.get("/translation-hub/locales")
async def admin_custom_locales(
    db: Annotated[Database, Depends(get_database)], _actor: _TranslationActor
) -> Any:
    return {"items": await translation_hub.list_custom_locales(db, active_only=False)}


@admin_router.put("/translation-hub/locales/{code}")
async def save_custom_locale(
    code: str,
    payload: LocaleSaveRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: _TranslationActor,
) -> Any:
    # The path is the stable identity. Reject a mismatched body instead of
    # silently creating a different language than the URL says.
    if code.lower() != payload.code.lower():
        from truegrit_api.errors import ValidationAppError

        raise ValidationAppError("Language code in the URL and form must match.")
    return await translation_hub.save_custom_locale(
        db,
        actor,
        _request_id(request),
        code=payload.code,
        native_name=payload.native_name,
        english_name=payload.english_name,
        direction=payload.direction,
        group_name=payload.group_name,
        active=payload.active,
    )


@admin_router.delete("/translation-hub/locales/{code}")
async def delete_custom_locale(
    code: str,
    db: Annotated[Database, Depends(get_database)],
    _actor: _TranslationActor,
) -> Any:
    await translation_hub.delete_custom_locale(db, code)
    return {"deleted": True}

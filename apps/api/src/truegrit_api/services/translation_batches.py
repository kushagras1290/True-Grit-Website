"""Durable, observable fan-out for bulk machine translation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.platform.translation import Translator
from truegrit_api.services import translation_hub
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

TRANSLATION_TASK_EVENT: Final = "translation.batch-task.v1"
MAX_LANGUAGES: Final = 150
MAX_CONTENT_RESOURCES: Final = 25
MAX_INTERFACE_ENTRIES: Final = 2_000
MAX_CONTENT_TASKS: Final = 2_500
MAX_BATCH_TASKS: Final = 25_000
_FIELDS_PER_TASK: Final = 10
_ROWS_PER_INSERT: Final = 10  # 10 columns x 10 rows = D1's 100-bind maximum.


def _validated_locales(locales: Sequence[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for raw in locales:
        locale = translation_hub.validate_locale(raw)
        marker = locale.lower()
        if marker not in seen:
            seen.add(marker)
            unique.append(locale)
    if not unique:
        raise ValidationAppError("Select at least one target language.")
    if len(unique) > MAX_LANGUAGES:
        raise ValidationAppError(f"Select at most {MAX_LANGUAGES} languages in one batch.")
    return unique


def _chunks(values: Sequence[str], size: int = _FIELDS_PER_TASK) -> list[list[str]]:
    return [list(values[index : index + size]) for index in range(0, len(values), size)]


def _task_insert_statement(rows: Sequence[tuple[Any, ...]]) -> tuple[str, Sequence[Any]]:
    if len(rows) > _ROWS_PER_INSERT:
        raise ValueError("A translation task insert would exceed D1's bind limit.")
    placeholders = ",".join("(?,?,?,?,?,?,?,?,?,?)" for _ in rows)
    params: list[Any] = []
    for row in rows:
        params.extend(row)
    return (
        "INSERT INTO translation_batch_tasks"
        " (id, batch_id, locale, resource_type, resource_id, payload_json, status,"
        " translated_count, created_at, updated_at) VALUES " + placeholders,
        params,
    )


async def create_content_batch(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    resource_type: str,
    resources: Sequence[dict[str, Any]],
    locales: Sequence[str],
    overwrite_existing: bool,
) -> dict[str, Any]:
    target_locales = _validated_locales(locales)
    if not resources or len(resources) > MAX_CONTENT_RESOURCES:
        raise ValidationAppError(
            f"Select between 1 and {MAX_CONTENT_RESOURCES} content items per batch."
        )

    normalized: list[tuple[str, list[str]]] = []
    seen_ids: set[str] = set()
    for item in resources:
        resource_id = str(item.get("resourceId") or "").strip()
        if not resource_id or resource_id in seen_ids:
            raise ValidationAppError("Each selected content item must have a unique id.")
        seen_ids.add(resource_id)
        sources, _ = await translation_hub.get_source_fields(db, resource_type, resource_id)
        requested = [str(key) for key in item.get("fieldKeys") or []]
        field_keys = requested or list(sources)
        if unknown := set(field_keys) - set(sources):
            raise ValidationAppError(
                f"The source changed for {resource_id}; reload before translating "
                f"{next(iter(unknown))}."
            )
        normalized.append((resource_id, field_keys))

    task_count = sum(len(_chunks(keys)) for _, keys in normalized) * len(target_locales)
    if task_count > MAX_CONTENT_TASKS:
        raise ValidationAppError(
            "That selection is too large for one safe run. Select fewer content items or fields."
        )

    batch_id = new_id("trb")
    now = utc_now_iso()
    task_rows: list[tuple[Any, ...]] = []
    for locale in target_locales:
        for resource_id, field_keys in normalized:
            for field_chunk in _chunks(field_keys):
                task_rows.append(
                    (
                        new_id("trt"),
                        batch_id,
                        locale,
                        resource_type,
                        resource_id,
                        json.dumps({"fieldKeys": field_chunk}, separators=(",", ":")),
                        "pending",
                        0,
                        now,
                        now,
                    )
                )

    statements: list[tuple[str, Sequence[Any]]] = [
        (
            "INSERT INTO translation_batches"
            " (id, mode, resource_type, target, payload_json, overwrite_existing, total_tasks,"
            " status, created_by, created_at, updated_at)"
            " VALUES (?, 'content', ?, NULL, '{}', ?, ?, 'queued', ?, ?, ?)",
            (
                batch_id,
                resource_type,
                int(overwrite_existing),
                len(task_rows),
                actor.user_id,
                now,
                now,
            ),
        )
    ]
    statements.extend(_task_insert_statement(chunk) for chunk in _row_chunks(task_rows))
    statements.append(
        audit_statement(
            action="translation_hub.batch_created",
            entity_type="translation_batch",
            entity_id=batch_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={
                "mode": "content",
                "resourceType": resource_type,
                "resources": len(normalized),
                "languages": len(target_locales),
                "tasks": len(task_rows),
                "overwriteExisting": overwrite_existing,
            },
        )
    )
    await db.batch(statements)
    return await batch_detail(db, batch_id)


async def create_interface_batch(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    target: str,
    entries: dict[str, dict[str, str]],
    locales: Sequence[str],
    overwrite_existing: bool,
) -> dict[str, Any]:
    target_locales = _validated_locales(locales)
    if target not in {"storefront", "admin"}:
        raise ValidationAppError("Unsupported interface translation target.")
    if not entries or len(entries) > MAX_INTERFACE_ENTRIES:
        raise ValidationAppError(
            f"Select between 1 and {MAX_INTERFACE_ENTRIES} interface strings per batch."
        )
    normalized: dict[str, dict[str, str]] = {}
    for key, item in entries.items():
        source = str(item.get("source") or "").strip()
        if not source or len(source) > translation_hub.MAX_TEXT_LENGTH or len(key) > 160:
            raise ValidationAppError("Invalid interface translation entry.")
        normalized[str(key)] = {"source": source, "translation": ""}

    key_chunks = _chunks(list(normalized))
    task_count = len(key_chunks) * len(target_locales)
    if task_count > MAX_BATCH_TASKS:
        raise ValidationAppError("That selection is too large for one safe translation run.")

    batch_id = new_id("trb")
    now = utc_now_iso()
    statements: list[tuple[str, Sequence[Any]]] = [
        (
            "INSERT INTO translation_batches"
            " (id, mode, resource_type, target, payload_json, overwrite_existing, total_tasks,"
            " status, created_by, created_at, updated_at, generation_cursor,"
            " generation_complete)"
            " VALUES (?, 'interface', 'interface', ?, ?, ?, ?, 'queued', ?, ?, ?, 0, 0)",
            (
                batch_id,
                target,
                json.dumps(
                    {"entries": normalized, "locales": target_locales}, separators=(",", ":")
                ),
                int(overwrite_existing),
                task_count,
                actor.user_id,
                now,
                now,
            ),
        )
    ]
    statements.append(
        audit_statement(
            action="translation_hub.batch_created",
            entity_type="translation_batch",
            entity_id=batch_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={
                "mode": "interface",
                "target": target,
                "strings": len(normalized),
                "languages": len(target_locales),
                "tasks": task_count,
                "overwriteExisting": overwrite_existing,
            },
        )
    )
    await db.batch(statements)
    return await batch_detail(db, batch_id)


def _row_chunks(rows: Sequence[tuple[Any, ...]]) -> list[Sequence[tuple[Any, ...]]]:
    return [
        rows[index : index + _ROWS_PER_INSERT] for index in range(0, len(rows), _ROWS_PER_INSERT)
    ]


def _generated_task_id(batch_id: str, cursor: int) -> str:
    digest = hashlib.sha256(f"{batch_id}:{cursor}".encode()).hexdigest()[:32]
    return f"trt_{digest}"


def _outbox_insert(task_id: str, batch_id: str, now: str) -> tuple[str, Sequence[Any]]:
    digest = hashlib.sha256(f"translation:{task_id}".encode()).hexdigest()[:32]
    return (
        "INSERT OR IGNORE INTO outbox_events"
        " (id, event_type, event_version, aggregate_type, aggregate_id, payload_json,"
        " status, available_at, created_at)"
        " VALUES (?, ?, 1, 'translation_batch', ?, ?, 'pending', ?, ?)",
        (
            f"evt_{digest}",
            TRANSLATION_TASK_EVENT,
            batch_id,
            json.dumps({"taskId": task_id}, separators=(",", ":")),
            now,
            now,
        ),
    )


async def enqueue_pending_tasks(db: Database, *, limit: int = 50) -> int:
    # Forty tasks keeps this D1 transaction below 100 prepared statements even
    # when every task must be materialized and paired with an outbox event.
    bounded_limit = max(1, min(limit, 40))
    rows = await db.fetch_all(
        "SELECT t.id, t.batch_id FROM translation_batch_tasks t"
        " JOIN translation_batches b ON b.id = t.batch_id"
        " WHERE t.status = 'pending' AND b.status IN ('queued', 'running')"
        " ORDER BY t.created_at, t.id LIMIT ?",
        (bounded_limit,),
    )
    now = utc_now_iso()
    statements: list[tuple[str, Sequence[Any]]] = []
    for row in rows:
        task_id = str(row["id"])
        statements.extend(
            [
                _outbox_insert(task_id, str(row["batch_id"]), now),
                (
                    "UPDATE translation_batch_tasks SET status = 'queued', updated_at = ?"
                    " WHERE id = ? AND status = 'pending'",
                    (now, task_id),
                ),
            ]
        )
    queued_count = len(rows)

    remaining = bounded_limit - queued_count
    if remaining:
        batches = await db.fetch_all(
            "SELECT id, target, payload_json, generation_cursor, total_tasks, created_at"
            " FROM translation_batches"
            " WHERE generation_complete = 0 AND mode = 'interface'"
            " AND status IN ('queued', 'running')"
            " ORDER BY created_at, id LIMIT 10"
        )
        for batch in batches:
            if remaining <= 0:
                break
            payload = json.loads(batch["payload_json"] or "{}")
            entries = payload.get("entries") or {}
            locales = [str(locale) for locale in payload.get("locales") or []]
            key_chunks = _chunks(list(entries))
            chunks_per_locale = len(key_chunks)
            cursor = int(batch["generation_cursor"] or 0)
            total_tasks = int(batch["total_tasks"])
            expected_tasks = len(locales) * chunks_per_locale
            if expected_tasks != total_tasks:
                statements.append(
                    (
                        "UPDATE translation_batches SET status = 'failed',"
                        " generation_complete = 1, updated_at = ? WHERE id = ?",
                        (now, batch["id"]),
                    )
                )
                continue
            if not locales or not key_chunks or cursor >= total_tasks:
                statements.append(
                    (
                        "UPDATE translation_batches SET generation_complete = 1, updated_at = ?"
                        " WHERE id = ? AND generation_cursor = ?",
                        (now, batch["id"], cursor),
                    )
                )
                continue

            generate_count = min(remaining, total_tasks - cursor)
            batch_id = str(batch["id"])
            for task_cursor in range(cursor, cursor + generate_count):
                locale_index, chunk_index = divmod(task_cursor, chunks_per_locale)
                task_id = _generated_task_id(batch_id, task_cursor)
                statements.extend(
                    [
                        (
                            "INSERT OR IGNORE INTO translation_batch_tasks"
                            " (id, batch_id, locale, resource_type, resource_id, payload_json,"
                            " status, translated_count, created_at, updated_at)"
                            " VALUES (?, ?, ?, 'interface', ?, ?, 'queued', 0, ?, ?)",
                            (
                                task_id,
                                batch_id,
                                locales[locale_index],
                                batch["target"],
                                json.dumps(
                                    {"fieldKeys": key_chunks[chunk_index]},
                                    separators=(",", ":"),
                                ),
                                now,
                                now,
                            ),
                        ),
                        _outbox_insert(task_id, batch_id, now),
                    ]
                )
            next_cursor = cursor + generate_count
            statements.append(
                (
                    "UPDATE translation_batches SET generation_cursor = ?,"
                    " generation_complete = ?, updated_at = ?"
                    " WHERE id = ? AND generation_cursor = ?",
                    (next_cursor, int(next_cursor >= total_tasks), now, batch_id, cursor),
                )
            )
            queued_count += generate_count
            remaining -= generate_count

    if not statements:
        return 0
    await db.batch(statements)
    return queued_count


async def batch_detail(db: Database, batch_id: str) -> dict[str, Any]:
    row = await db.fetch_one(
        "SELECT id, mode, resource_type, target, overwrite_existing, total_tasks, status,"
        " created_at, updated_at FROM translation_batches WHERE id = ?",
        (batch_id,),
    )
    if row is None:
        raise NotFoundError("Translation batch not found.")
    counts = await db.fetch_one(
        "SELECT"
        " SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_tasks,"
        " SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_tasks,"
        " SUM(translated_count) AS translated_strings"
        " FROM translation_batch_tasks WHERE batch_id = ?",
        (batch_id,),
    )
    failures = await db.fetch_all(
        "SELECT locale, error_summary FROM translation_batch_tasks"
        " WHERE batch_id = ? AND status = 'failed' ORDER BY updated_at DESC LIMIT 12",
        (batch_id,),
    )
    completed = int((counts or {}).get("completed_tasks") or 0)
    failed = int((counts or {}).get("failed_tasks") or 0)
    total = int(row["total_tasks"])
    return {
        "id": row["id"],
        "mode": row["mode"],
        "resourceType": row["resource_type"],
        "target": row["target"],
        "overwriteExisting": bool(row["overwrite_existing"]),
        "status": row["status"],
        "totalTasks": total,
        "completedTasks": completed,
        "failedTasks": failed,
        "pendingTasks": max(0, total - completed - failed),
        "translatedStrings": int((counts or {}).get("translated_strings") or 0),
        "failures": [
            {"locale": item["locale"], "message": item["error_summary"] or "Translation failed."}
            for item in failures
        ],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


async def _refresh_batch_status(db: Database, batch_id: str) -> None:
    batch = await db.fetch_one(
        "SELECT total_tasks FROM translation_batches WHERE id = ?", (batch_id,)
    )
    if batch is None:
        raise NotFoundError("Translation batch not found.")
    counts = await db.fetch_one(
        "SELECT SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,"
        " SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed"
        " FROM translation_batch_tasks WHERE batch_id = ?",
        (batch_id,),
    )
    total = int(batch["total_tasks"])
    completed = int((counts or {}).get("completed") or 0)
    failed = int((counts or {}).get("failed") or 0)
    if completed + failed < total:
        status = "running"
    elif failed == total:
        status = "failed"
    elif failed:
        status = "partial"
    else:
        status = "completed"
    await db.execute(
        "UPDATE translation_batches SET status = ?, updated_at = ? WHERE id = ?",
        (status, utc_now_iso(), batch_id),
    )


async def process_task(db: Database, translator: Translator, task_id: str) -> None:
    task = await db.fetch_one(
        "SELECT t.*, b.mode, b.target, b.payload_json AS batch_payload_json,"
        " b.overwrite_existing, b.created_by"
        " FROM translation_batch_tasks t JOIN translation_batches b ON b.id = t.batch_id"
        " WHERE t.id = ?",
        (task_id,),
    )
    if task is None:
        raise NotFoundError("Translation task not found.")
    if task["status"] == "completed":
        return
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE translation_batch_tasks SET status = 'running', error_summary = NULL,"
                " updated_at = ? WHERE id = ?",
                (now, task_id),
            ),
            (
                "UPDATE translation_batches SET status = 'running', updated_at = ?"
                " WHERE id = ? AND status = 'queued'",
                (now, task["batch_id"]),
            ),
        ]
    )
    user = await db.fetch_one(
        "SELECT display_name, email FROM users WHERE id = ?", (task["created_by"],)
    )
    actor = Principal(
        user_id=str(task["created_by"]),
        display_name=str((user or {}).get("display_name") or "Translation batch"),
        email=str((user or {}).get("email") or "translation@internal.invalid"),
        user_type="staff",
    )
    translated_count = 0
    try:
        payload = json.loads(task["payload_json"] or "{}")
        field_keys = [str(key) for key in payload.get("fieldKeys") or []]
        locale = str(task["locale"])
        overwrite = bool(task["overwrite_existing"])
        if task["mode"] == "content":
            resource_type = str(task["resource_type"])
            resource_id = str(task["resource_id"])
            sources, _ = await translation_hub.get_source_fields(db, resource_type, resource_id)
            saved = await translation_hub.get_saved_entries(db, resource_type, resource_id, locale)
            translations: dict[str, str] = {}
            for key in field_keys:
                source = sources.get(key)
                if source is None:
                    continue
                entry = saved.get(key)
                current = bool(entry and str(entry["translated_text"]).strip())
                fresh = bool(entry and entry["source_hash"] == translation_hub.source_hash(source))
                if not overwrite and current and fresh:
                    continue
                translations[key] = await translator.translate(source, target_lang=locale)
            if translations:
                await translation_hub.save_resource(
                    db,
                    actor,
                    f"batch:{task['batch_id']}",
                    resource_type,
                    resource_id,
                    locale,
                    translations,
                    status="machine",
                )
            translated_count = len(translations)
        else:
            batch_payload = json.loads(task["batch_payload_json"] or "{}")
            all_entries = batch_payload.get("entries") or {}
            entries = {key: all_entries[key] for key in field_keys if key in all_entries}
            existing_rows = (
                await db.fetch_all(
                    "SELECT field_key, source_hash, translated_text FROM translation_entries"
                    " WHERE resource_type = 'interface' AND resource_id = ? AND locale = ?"
                    f" AND field_key IN ({','.join('?' for _ in entries)})",
                    (task["target"], locale, *entries),
                )
                if entries
                else []
            )
            existing = {str(row["field_key"]): row for row in existing_rows}
            selected: dict[str, dict[str, str]] = {}
            for key, item in entries.items():
                source = str(item["source"])
                row = existing.get(key)
                current = bool(row and str(row["translated_text"]).strip())
                fresh = bool(row and row["source_hash"] == translation_hub.source_hash(source))
                if not overwrite and current and fresh:
                    continue
                selected[key] = item
            if selected:
                await translation_hub.save_interface_entries(
                    db,
                    actor,
                    f"batch:{task['batch_id']}",
                    translator,
                    locale,
                    selected,
                    auto_translate=True,
                    target=str(task["target"]),
                )
            translated_count = len(selected)
    except ValidationAppError as exc:
        await db.execute(
            "UPDATE translation_batch_tasks SET status = 'failed', error_summary = ?,"
            " updated_at = ? WHERE id = ?",
            (str(exc)[:500], utc_now_iso(), task_id),
        )
        await _refresh_batch_status(db, str(task["batch_id"]))
        return

    await db.execute(
        "UPDATE translation_batch_tasks SET status = 'completed', translated_count = ?,"
        " error_summary = NULL, updated_at = ? WHERE id = ?",
        (translated_count, utc_now_iso(), task_id),
    )
    await _refresh_batch_status(db, str(task["batch_id"]))

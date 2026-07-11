"""Slug rules: lowercase, hyphenated, unique per entity, stable once published."""

from __future__ import annotations

import re
import unicodedata

from truegrit_api.errors import ValidationAppError

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG_LENGTH = 96


def validate_slug(slug: str) -> str:
    if not isinstance(slug, str) or not slug:
        raise ValidationAppError("Slug is required.")
    if len(slug) > MAX_SLUG_LENGTH:
        raise ValidationAppError(f"Slug must be at most {MAX_SLUG_LENGTH} characters.")
    if not _SLUG_RE.fullmatch(slug):
        raise ValidationAppError(
            "Slug must be lowercase letters, numbers, and single hyphens.",
            details={"slug": slug},
        )
    return slug


def slugify(name: str) -> str:
    """Derive a valid slug from a display name."""
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    lowered = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    collapsed = re.sub(r"-{2,}", "-", lowered)[:MAX_SLUG_LENGTH].strip("-")
    if not collapsed:
        raise ValidationAppError("Could not derive a slug from that name.")
    return collapsed

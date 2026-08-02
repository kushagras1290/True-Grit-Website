"""Auto-translate adapter (migration 0067) — used only inside the Workers
runtime, mirroring `platform.d1`'s "kept import-safe outside Workers: nothing
here imports `js` at module load" discipline.

Wraps Cloudflare Workers AI's `@cf/meta/m2m100-1.2b` (a many-to-many
multilingual translation model) via the Worker's own `env.AI` binding — no
external API key, no separate billing account, and the daily free-neuron
allowance comfortably covers "translate a page once, store the result"
(this is never called per-visitor-per-request; see services.translation).

m2m100 is a real but imperfect translator, and (being a research model) does
not cover every one of the storefront's fifty-plus locales -- an
unsupported target language surfaces as `TranslationUnavailableError` rather
than a raw provider error, so the admin editor can say plainly "not
available for this language yet, edit it by hand" instead of showing a
stack trace.
"""

from __future__ import annotations

from typing import Any, Protocol

from truegrit_api.errors import ValidationAppError

_MODEL = "@cf/meta/m2m100-1.2b"


class TranslationUnavailableError(ValidationAppError):
    """Auto-translate could not run — not deployed to Workers, or the
    provider rejected this language pair. Either way there is nothing an
    editor can do but write the translation by hand."""


class Translator(Protocol):
    async def translate(self, text: str, *, target_lang: str, source_lang: str = "en") -> str: ...


class UnavailableTranslator:
    """Local dev / test fallback. Workers AI has no local emulator (unlike
    D1, which `build_local_database` reproduces exactly against real SQLite),
    so auto-translate simply explains itself here rather than crashing --
    the same reasoning `services.payments.PaymentError` gives a customer
    when a gateway is not configured."""

    async def translate(self, text: str, *, target_lang: str, source_lang: str = "en") -> str:
        raise TranslationUnavailableError(
            "Auto-translate runs on the deployed Worker's AI binding and is not"
            " available in local development. Edit this locale by hand, or test"
            " on a deployed environment."
        )


class WorkersAITranslator:
    """Wraps the Worker `env.AI` binding."""

    def __init__(self, binding: Any):
        self._ai = binding

    async def translate(self, text: str, *, target_lang: str, source_lang: str = "en") -> str:
        try:
            result = await self._ai.run(
                _MODEL, {"text": text, "source_lang": source_lang, "target_lang": target_lang}
            )
        except Exception as exc:
            raise TranslationUnavailableError(
                f"Could not translate into '{target_lang}' — the built-in translator may not"
                " support this language yet. Edit it by hand instead."
            ) from exc
        translated = getattr(result, "translated_text", None)
        if translated is None and isinstance(result, dict):
            translated = result.get("translated_text")
        if not translated:
            raise TranslationUnavailableError(
                f"The translator returned no result for '{target_lang}'."
            )
        return str(translated)

"""Chat-completion adapter — used only inside the Workers runtime, mirroring
`platform.translation`'s "kept import-safe outside Workers: nothing here
imports `js` at module load" discipline.

Wraps Cloudflare Workers AI's `env.AI` binding for the admin and storefront
support bots (`services.support_bot` / a future storefront equivalent) — the
same binding `platform.translation` already uses for auto-translate, so this
needs no separate API key or billing account.

This module only covers plain chat completion (system prompt + turn history in,
assistant text out). Function/tool-calling for the bots' live-data lookups is
layered on top of `ChatModel` in the service layer once each bot's tool set is
built — the Workers AI tool-calling request/response shape is still evolving
quickly enough that it is deliberately not baked into this adapter's interface
ahead of that work; confirm the current shape against Cloudflare's docs when
that lands rather than assuming this scaffold already matches it.
"""

from __future__ import annotations

from typing import Any, Protocol

from truegrit_api.errors import ValidationAppError

# A small, broadly-available instruct model — adequate for short support-bot
# answers grounded in a curated knowledge snippet. Reassess when tool-calling
# is added: not every Workers AI chat model supports function calling, so the
# model used for that may need to differ from this plain-completion default.
_DEFAULT_MODEL = "@cf/meta/llama-3.1-8b-instruct"


class ChatUnavailableError(ValidationAppError):
    """The support bot could not respond — not deployed to Workers, or the
    provider rejected the request. Either way there is nothing the caller can
    do but show a plain "try again" message."""


class ChatModel(Protocol):
    async def complete(self, *, system_prompt: str, messages: list[dict[str, str]]) -> str: ...


class UnavailableChat:
    """Local dev / test fallback. Like Workers AI translation, there is no
    local emulator for Workers AI chat models, so the support bot simply
    explains itself here rather than crashing."""

    async def complete(self, *, system_prompt: str, messages: list[dict[str, str]]) -> str:
        raise ChatUnavailableError(
            "The support bot runs on the deployed Worker's AI binding and is not"
            " available in local development. Test it on a deployed environment."
        )


class WorkersAIChat:
    """Wraps the Worker `env.AI` binding for chat completion."""

    def __init__(self, binding: Any, *, model: str = _DEFAULT_MODEL):
        self._ai = binding
        self._model = model

    async def complete(self, *, system_prompt: str, messages: list[dict[str, str]]) -> str:
        try:
            result = await self._ai.run(
                self._model,
                {"messages": [{"role": "system", "content": system_prompt}, *messages]},
            )
        except Exception as exc:
            raise ChatUnavailableError(
                "The support bot is temporarily unavailable. Try again shortly."
            ) from exc
        response = getattr(result, "response", None)
        if response is None and isinstance(result, dict):
            response = result.get("response")
        if not response:
            raise ChatUnavailableError("The support bot returned no answer.")
        return str(response)

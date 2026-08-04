"""Chat-completion adapter — used only inside the Workers runtime, mirroring
`platform.translation`'s "kept import-safe outside Workers: nothing here
imports `js` at module load" discipline.

Wraps Cloudflare Workers AI's `env.AI` binding for the admin and storefront
support bots (`services.support_bot` / a future storefront equivalent) — the
same binding `platform.translation` already uses for auto-translate, so this
needs no separate API key or billing account.

Covers both plain chat completion and function/tool calling: the bots mix a
curated knowledge snippet with live-data lookups, and Workers AI's
`@cf/meta/llama-3.3-70b-instruct-fp8-fast` supports the latter natively
(https://developers.cloudflare.com/workers-ai/function-calling/) via an
OpenAI-style `tools` array and a `tool_calls[]` field on the response. The
provider-specific wire shape is isolated inside `WorkersAIChat` — callers
(`services.support_bot`) only see the plain `ToolDefinition`/`ToolCall`/
`ChatCompletion` types below, so a future model/provider swap does not ripple
into the tool-calling loop itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from truegrit_api.errors import ValidationAppError

# Chosen specifically for documented function-calling support -- not every
# Workers AI chat model has it (the plain-completion default used to be the
# smaller llama-3.1-8b-instruct, which does not). One model covers both bots'
# needs since both mix knowledge-snippet answers with tool calls.
_DEFAULT_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"


class ChatUnavailableError(ValidationAppError):
    """The support bot could not respond — not deployed to Workers, or the
    provider rejected the request. Either way there is nothing the caller can
    do but show a plain "try again" message."""


@dataclass(frozen=True)
class ToolDefinition:
    """One callable the model may invoke. `parameters` is a JSON Schema
    object describing the arguments, e.g.
    `{"type": "object", "properties": {"order_id": {"type": "string"}},
    "required": ["order_id"]}`."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatCompletion:
    """Either `text` is set (the model answered directly) or `tool_calls` is
    non-empty (the model wants those run before it will answer) — the loop in
    `services.support_bot` executes any tool calls, appends their results as
    `role: "tool"` messages, and calls `complete` again until `text` comes
    back."""

    text: str | None
    tool_calls: list[ToolCall]


class ChatModel(Protocol):
    async def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition] | None = None,
    ) -> ChatCompletion: ...


class UnavailableChat:
    """Local dev / test fallback. Like Workers AI translation, there is no
    local emulator for Workers AI chat models, so the support bot simply
    explains itself here rather than crashing."""

    async def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition] | None = None,
    ) -> ChatCompletion:
        raise ChatUnavailableError(
            "The support bot runs on the deployed Worker's AI binding and is not"
            " available in local development. Test it on a deployed environment."
        )


def _tool_to_wire(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


class WorkersAIChat:
    """Wraps the Worker `env.AI` binding for chat completion and tool calling."""

    def __init__(self, binding: Any, *, model: str = _DEFAULT_MODEL):
        self._ai = binding
        self._model = model

    async def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition] | None = None,
    ) -> ChatCompletion:
        payload: dict[str, Any] = {
            "messages": [{"role": "system", "content": system_prompt}, *messages]
        }
        if tools:
            payload["tools"] = [_tool_to_wire(tool) for tool in tools]
        try:
            result = await self._ai.run(self._model, payload)
        except Exception as exc:  # TEMPORARY: debug print, remove once root-caused
            import traceback

            print(f"ai_chat.run_failed: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            raise ChatUnavailableError(
                "The support bot is temporarily unavailable. Try again shortly."
            ) from exc
        return _parse_completion(result)


def _get(result: Any, key: str) -> Any:
    value = getattr(result, key, None)
    if value is None and isinstance(result, dict):
        value = result.get(key)
    return value


def _parse_completion(result: Any) -> ChatCompletion:
    raw_tool_calls = _get(result, "tool_calls") or []
    tool_calls: list[ToolCall] = []
    for index, raw_call in enumerate(raw_tool_calls):
        name = _get(raw_call, "name")
        arguments = _get(raw_call, "arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        if not name:
            continue
        call_id = _get(raw_call, "id") or f"call_{index}"
        tool_calls.append(ToolCall(id=str(call_id), name=str(name), arguments=arguments))

    if tool_calls:
        return ChatCompletion(text=None, tool_calls=tool_calls)

    response = _get(result, "response")
    if not response:
        raise ChatUnavailableError("The support bot returned no answer.")
    return ChatCompletion(text=str(response), tool_calls=[])

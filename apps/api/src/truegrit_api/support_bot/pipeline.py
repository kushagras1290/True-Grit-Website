"""The four stages, wired together.

    message -> classify -> gate -> resolve -> render -> reply

`ask` is the only entry point. It is a plain async function over the `Database`
protocol with no model, no network call and no binding, which is what lets the
whole bot run in the test suite and in local development. The Workers AI path
it replaced could only ever be exercised on a deployed Worker.

Ordering matters and is not the order the stages are named in. The gate runs
*before* the resolver, not after: a message the bot is not confident about must
not cause a database read, and an escalation must not be able to leak a row the
bot was never going to be allowed to talk about.

The only way out of this function is a string from `templates.TEMPLATES` or a
handover. There is no branch that composes a sentence.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ValidationAppError
from truegrit_api.logging import log_event
from truegrit_api.platform.database import Database
from truegrit_api.services import support_bot_settings
from truegrit_api.support_bot import gate, intents, resolvers, templates
from truegrit_api.support_bot.classifier import Classification, classify
from truegrit_api.support_bot.intents import Handling, IntentSpec, Severity

# How many alternatives a clarification offers. Two is a question; four is a
# menu the customer has to read, which is worse than handing over.
_CLARIFY_OPTIONS = 2
# Only alternatives that are themselves plausible are worth offering.
_CLARIFY_MIN_SCORE = 0.45


class SupportBotUnavailableError(ValidationAppError):
    """The storefront bot is switched off in Site Settings.

    Kept as its own type, and as a 422 like the model-backed bot's
    `ChatUnavailableError` before it, so the widget's existing error handling
    keeps working unchanged.
    """


def _clarify_options(classification: Classification) -> str:
    """Runner-up intents as a short list a customer can choose from.

    Uses each intent's *first* canonical phrasing as its label. That phrasing
    is already written the way a customer would say it, so the shortlist reads
    as a question rather than as internal taxonomy leaking into the chat.
    """
    labels: list[str] = []
    for candidate in classification.alternatives:
        if candidate.score < _CLARIFY_MIN_SCORE:
            continue
        spec = intents.REGISTRY.get(candidate.intent)
        if spec is None:
            continue
        questions = spec.canonical_questions
        if not questions:
            continue
        labels.append(f"- {questions[0]}?")
        if len(labels) >= _CLARIFY_OPTIONS:
            break
    return "\n".join(labels)


async def _resolve(
    db: Database,
    spec: IntentSpec,
    classification: Classification,
    customer: Principal | None,
    country: str | None,
    locale: str | None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Run the intent's resolver. Returns (status, template data, context)."""
    if spec.resolver is None:
        return resolvers.Status.OK.value, {}, {}
    resolver = resolvers.RESOLVERS.get(spec.resolver)
    if resolver is None:
        # The registry names a resolver that does not exist. Caught by the
        # wiring test; at runtime it must degrade to a handover, not a 500.
        log_event("error", "support_bot.missing_resolver", intent=spec.key, resolver=spec.resolver)
        return "", {}, {}
    resolution = await resolver(
        resolvers.ResolveContext(
            db=db,
            customer=customer,
            slots=classification.slots,
            country=country,
            locale=locale,
        )
    )
    return resolution.status.value, resolution.data, resolution.context


async def ask(
    db: Database,
    customer: Principal | None,
    *,
    message: str,
    history: list[dict[str, str]],
    request_id: str,
    country: str | None = None,
    locale: str | None = None,
) -> dict[str, Any]:
    """One turn. Returns the widget's `{"reply": ...}` plus routing metadata.

    The extra fields are additive; `support-bot-widget.tsx` reads only `reply`,
    and the rest exists so the admin queue and the tests can assert on what the
    pipeline decided rather than on the wording it happened to choose.
    """
    if not await support_bot_settings.is_enabled(db, "storefront"):
        raise SupportBotUnavailableError(
            "The help assistant is currently unavailable. Please use the contact form instead."
        )

    # Stage 1.
    classification = classify(message)
    spec = intents.spec_for(classification.intent)

    # Stage 4 runs here, ahead of any database read: a message the bot is not
    # confident about must not touch a customer's rows on the way to being
    # handed over.
    repeated = gate.is_repeat(history, message, classification.intent)
    verdict = gate.decide(classification, spec, repeated=repeated)

    facts = await gate.load_policy_facts(db)
    data: dict[str, Any] = {"contact_line": gate.contact_line(facts)}

    if verdict.action is gate.Action.CLARIFY:
        options = _clarify_options(classification)
        if options:
            reply = templates.render("clarify", data={**data, "options": options}, facts=facts)
            if reply is not None:
                return _result(reply, classification, verdict.reason, escalated=False)
        # Nothing worth offering, so this is really a handover.
        verdict = gate.Verdict(action=gate.Action.HAND_OVER, reason=verdict.reason)

    if verdict.action is gate.Action.HAND_OVER:
        return await _hand_over(
            db,
            request_id=request_id,
            customer=customer,
            message=message,
            classification=classification,
            spec=intents.spec_for(intents.UNKNOWN),
            reason=verdict.reason,
            severity=Severity.NORMAL,
            data=data,
            facts=facts,
        )

    # A question about the customer's own records, asked by nobody. Signing in
    # solves it in one click, so this is not a handover.
    if spec.requires_auth and customer is None:
        reply = templates.render("sign_in", data=data, facts=facts)
        if reply is not None:
            return _result(reply, classification, "sign_in_required", escalated=False)

    # Stages 2 and 3.
    status, resolved, context = await _resolve(db, spec, classification, customer, country, locale)
    if not status:
        return await _hand_over(
            db,
            request_id=request_id,
            customer=customer,
            message=message,
            classification=classification,
            spec=spec,
            reason="unconfigured",
            severity=spec.severity,
            data=data,
            facts=facts,
        )

    reply = templates.render(spec.template, status=status, data={**data, **resolved}, facts=facts)
    if reply is None:
        # The template needed a policy fact nobody has configured, or a field
        # the resolver did not return. Either way the bot has nothing true to
        # say, so a person says it.
        return await _hand_over(
            db,
            request_id=request_id,
            customer=customer,
            message=message,
            classification=classification,
            spec=spec,
            reason="unconfigured",
            severity=spec.severity,
            data=data,
            facts=facts,
        )

    # An ESCALATE intent still shows its own template; the customer is told a
    # person is picking it up, and the row carries whatever was resolved so
    # that person is not starting cold.
    needs_human = spec.handling is Handling.ESCALATE or (
        spec.handling is Handling.GUARD and spec.escalate_after_guard
    )
    if needs_human:
        escalation_id = await gate.record_escalation(
            db,
            request_id=request_id,
            customer=customer,
            message=message,
            classification=classification,
            spec=spec,
            reason="policy",
            severity=spec.severity,
            context=context,
        )
        return _result(reply, classification, "policy", escalated=True, escalation_id=escalation_id)

    return _result(reply, classification, verdict.reason, escalated=False)


async def _hand_over(
    db: Database,
    *,
    request_id: str,
    customer: Principal | None,
    message: str,
    classification: Classification,
    spec: IntentSpec,
    reason: str,
    severity: Severity,
    data: dict[str, Any],
    facts: dict[str, str],
) -> dict[str, Any]:
    """Record the escalation and tell the customer, using `spec`'s own copy."""
    escalation_id = await gate.record_escalation(
        db,
        request_id=request_id,
        customer=customer,
        message=message,
        classification=classification,
        spec=spec,
        reason=reason,
        severity=severity,
    )
    reply = templates.render(spec.template, data=data, facts=facts)
    if reply is None:
        # `unknown` takes no resolver fields and only the always-present
        # contact line, so this is the one template that cannot fail. Falling
        # back to it keeps the customer from ever seeing an empty bubble.
        reply = templates.render("unknown", data=data, facts=facts) or (
            "I have passed this to the team and a person will reply."
        )
    return _result(reply, classification, reason, escalated=True, escalation_id=escalation_id)


def _result(
    reply: str,
    classification: Classification,
    reason: str,
    *,
    escalated: bool,
    escalation_id: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "reply": reply,
        "intent": classification.intent,
        "confidence": round(classification.confidence, 4),
        "tier": classification.tier,
        "reason": reason,
        "escalated": escalated,
    }
    if escalation_id is not None:
        result["escalationId"] = escalation_id
    return result

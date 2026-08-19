"""Stage 4: decide whether the bot is allowed to answer, and hand over if not.

The classifier always returns *something*; this is what decides whether that
something is trustworthy enough to say out loud. Three outcomes:

* ``PROCEED``  -- answer it.
* ``CLARIFY``  -- the bot has a shortlist but not a winner, so it asks which
                  one rather than picking. Still no human involved.
* ``HAND_OVER`` -- a person takes it, with everything the bot worked out
                  attached.

**Why two thresholds and not one.** A single accept threshold turns every
near-miss into a handover, and most near-misses are a customer whose phrasing
sits between two intents. Asking "did you mean your refund or your return?"
resolves those in one turn and costs nobody anything. Below the lower band
there is nothing useful to offer, and guessing there is how a deterministic bot
starts behaving like the model it replaced.

**Why margin gates alongside score.** 0.78 against `return_status` with 0.77
against `refund_status` clears any sensible threshold and is still a coin toss
between two different answers. `Classification.margin` is what catches it.

**Why repeats escalate.** A customer who rephrases the same question after a
clarification has already told the bot it failed. Asking again is the single
most irritating thing a support bot does, so the second attempt goes to a
person instead.

Every handover is written to `support_bot_escalations`. That table is both the
work queue and the only feedback signal this design has: the messages it could
not place are exactly the phrasings `phrasebook.py` is missing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.logging import log_event
from truegrit_api.platform.database import Database
from truegrit_api.support_bot.classifier import Classification
from truegrit_api.support_bot.intents import Handling, IntentSpec, Severity
from truegrit_api.support_bot.normalize import prepare
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

# At or above this, a match is treated as settled.
#
# Set by measurement, not by preference. `tests/unit/test_support_bot_routing.py`
# holds ninety-odd phrasings that appear nowhere in the phrasebook; sweeping the
# threshold across them gives:
#
#     threshold   answered   wrong   precision   coverage
#       0.55          74        1       0.986      0.777
#       0.60          71        1       0.986      0.745
#       0.62          66        0       1.000      0.702
#       0.65          65        0       1.000      0.691
#       0.75          52        0       1.000      0.553
#
# Precision is perfect anywhere from 0.62 up, so everything above that trades
# answered questions away for nothing. 0.65 sits clear of the 0.60 error onset
# by a margin rather than hugging it, and answers 69% of held-out traffic
# against 55% at 0.75.
#
# The original design note specified 0.75. That number came from cosine
# similarity over sentence-transformer embeddings, which is a different
# quantity on a different scale; this scorer is IDF-weighted lexical overlap
# and had to be calibrated on its own evidence.
ACCEPT_THRESHOLD = 0.65
# Below this there is no shortlist worth offering, only a handover. A
# clarification asserts nothing, so this band is allowed to be generous.
CLARIFY_THRESHOLD = 0.45
# How far clear of the runner-up intent the winner has to be. Two intents
# inside this band are a tie, however high they both scored.
AMBIGUITY_MARGIN = 0.06
# Token-set overlap at which a new message counts as the same question again.
# Held high on purpose: "where is my order" and "where is my refund" overlap
# 0.6, and treating those as the same question would escalate a customer who
# simply moved on to their next one. The intent comparison in `is_repeat` is
# what catches the rewordings this misses.
REPEAT_SIMILARITY = 0.8
# How many of the customer's own earlier turns to compare against.
_REPEAT_LOOKBACK = 4

# Escalation payload caps. An escalation is a work item, not an archive: a
# pasted wall of text is truncated so one message cannot bloat the table.
_MAX_STORED_MESSAGE = 4000
_MAX_STORED_JSON = 2000


class Action(StrEnum):
    PROCEED = "proceed"
    CLARIFY = "clarify"
    HAND_OVER = "hand_over"


@dataclass(frozen=True)
class Verdict:
    action: Action
    # Matches the `reason` column on support_bot_escalations.
    reason: str


def is_repeat(history: list[dict[str, str]], message: str, intent: str) -> bool:
    """Has the customer already asked this in the same conversation?

    Two signals, because neither is sufficient alone:

    * **Same classified intent as an earlier turn.** This is the reliable one.
      A customer who rewords "wheres my parcel gone" as "where has my parcel
      got to" has asked the same question, and token overlap between those two
      is only 0.67 -- below any threshold that does not also fire on "where is
      my order" versus "where is my refund", which differ by the one word that
      matters.
    * **Near-identical wording.** Catches a repeat whose intent the classifier
      places differently each time, which is exactly the situation where the
      customer is getting nowhere and should stop being asked to clarify.

    Only the last few turns are examined. Classifying is cheap but not free,
    and a question asked ten turns ago is not the one being repeated.
    """
    current = prepare(message).token_set
    if not current:
        return False
    recent = [turn for turn in history if turn.get("role") == "user"][-_REPEAT_LOOKBACK:]
    for turn in recent:
        content = turn.get("content", "")
        previous = prepare(content).token_set
        if not previous:
            continue
        if len(current & previous) / len(current | previous) >= REPEAT_SIMILARITY:
            return True
        # Imported here rather than at module scope: `classifier` imports
        # nothing from this module, and keeping it that way avoids a cycle.
        from truegrit_api.support_bot.classifier import classify

        if classify(content).intent == intent:
            return True
    return False


def decide(
    classification: Classification,
    spec: IntentSpec,
    *,
    repeated: bool = False,
) -> Verdict:
    """Whether this classification may be acted on."""
    # Safety, fraud, abuse and an explicit request for a person.
    #
    # Preemption is deliberately conditional on *how* the intent was reached. A
    # rule firing is an assertion and settles it. A weak lexical match is not,
    # and letting it preempt was a live bug: "I am a reporter and need a
    # comment" scored 0.38 against "I need a member of staff", and because
    # `human_handoff` is preemptive it was acted on at that score. Lexical
    # matches on a preemptive intent still have to clear the normal bar.
    if spec.preemptive and (
        classification.tier == "rule" or classification.confidence >= ACCEPT_THRESHOLD
    ):
        return Verdict(action=Action.PROCEED, reason="policy")

    # Greetings and acknowledgements carry no risk of being wrong in a way that
    # costs anything, so they clear on the lower band alone.
    if spec.handling is Handling.SOCIAL and classification.confidence >= CLARIFY_THRESHOLD:
        return Verdict(action=Action.PROCEED, reason="social")

    if classification.confidence >= ACCEPT_THRESHOLD:
        if classification.margin >= AMBIGUITY_MARGIN:
            return Verdict(action=Action.PROCEED, reason="confident")
        # Scored well, but a different intent scored almost as well.
        return Verdict(action=Action.HAND_OVER if repeated else Action.CLARIFY, reason="ambiguous")

    if classification.confidence >= CLARIFY_THRESHOLD:
        return Verdict(
            action=Action.HAND_OVER if repeated else Action.CLARIFY, reason="low_confidence"
        )

    return Verdict(action=Action.HAND_OVER, reason="low_confidence")


# --- Policy facts -----------------------------------------------------------


async def load_policy_facts(db: Database) -> dict[str, str]:
    """Every configured fact, blanks included.

    Blanks are returned rather than filtered out so `templates.render` can tell
    "not configured" from "key does not exist"; both skip a variant, but only
    the second is a bug.
    """
    rows = await db.fetch_all("SELECT key, value FROM support_bot_policy_facts")
    return {str(row["key"]): str(row["value"] or "") for row in rows}


def contact_line(facts: dict[str, str]) -> str:
    """The "and here is how else to reach us" clause every handover ends with.

    Always returns something usable. `/contact` exists regardless of what an
    operator has configured, so a handover never reads as a dead end.
    """
    email = facts.get("support_email", "").strip()
    hours = facts.get("support_hours", "").strip()
    phone = facts.get("support_phone", "").strip()

    if email and phone:
        reach = f" You can also reach the team at {email} or {phone}"
    elif email:
        reach = f" You can also reach the team at {email}"
    elif phone:
        reach = f" You can also reach the team on {phone}"
    else:
        return " You can also reach the team through /contact."
    return f"{reach} ({hours})." if hours else f"{reach}."


# --- Escalation records -----------------------------------------------------


def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _json_or_none(payload: Any) -> str | None:
    if not payload:
        return None
    return _clip(json.dumps(payload, default=str), _MAX_STORED_JSON)


async def record_escalation(
    db: Database,
    *,
    request_id: str,
    customer: Principal | None,
    message: str,
    classification: Classification,
    spec: IntentSpec,
    reason: str,
    severity: Severity,
    context: dict[str, Any] | None = None,
) -> str:
    """Persist one handover and return its id.

    Writes the runner-up intents alongside the message on purpose: an operator
    reviewing the queue needs to see what the bot nearly matched, because that
    is what tells them which phrasing to add. Counting unrecognised messages
    would tell them a number and nothing they could act on.
    """
    escalation_id = new_id("sbe")
    await db.execute(
        """
        INSERT INTO support_bot_escalations (
            id, created_at, customer_user_id, request_id, message, intent, confidence,
            tier, reason, severity, alternatives_json, slots_json, context_json, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
        """,
        (
            escalation_id,
            utc_now_iso(),
            customer.user_id if customer is not None else None,
            request_id,
            _clip(message, _MAX_STORED_MESSAGE),
            classification.intent,
            round(classification.confidence, 4),
            classification.tier,
            reason,
            severity.value,
            _json_or_none(
                [
                    {"intent": item.intent, "score": round(item.score, 4)}
                    for item in classification.alternatives
                ]
            ),
            _json_or_none(classification.slots),
            _json_or_none(context),
        ),
    )
    # Structured log as well as the row: the row is the work queue, the log is
    # what an alert on a spike in CRITICAL escalations would read.
    log_event(
        "info",
        "support_bot.escalated",
        escalation_id=escalation_id,
        request_id=request_id,
        intent=classification.intent,
        confidence=round(classification.confidence, 4),
        tier=classification.tier,
        reason=reason,
        severity=severity.value,
        signed_in=customer is not None,
    )
    return escalation_id

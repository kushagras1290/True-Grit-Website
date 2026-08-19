"""Stage 5: customer email for AUTO_APPROVE/AUTO_DENY outcomes only --
escalation changes nothing customer-visible yet (the return simply moves to
`under_review`, where staff already look), so it sends nothing.

Goes through the existing durable outbox (`services.jobs.enqueue_email`),
the same path every other transactional email in this codebase uses:
retried on provider failure, rate-limited, and independently toggleable from
the admin email console via its own category.
"""

from __future__ import annotations

from truegrit_api.platform.database import Database
from truegrit_api.services.contact import contactable_email
from truegrit_api.services.email_templates import render_refund_approved, render_refund_denied
from truegrit_api.services.jobs import enqueue_email
from truegrit_api.services.refund_orchestrator.decision import Decision, DecisionOutcome
from truegrit_api.services.refund_orchestrator.reader import RefundContext

CATEGORY: str = "refund_orchestrator"


def _format_minor(amount_minor: int, currency_code: str) -> str:
    major = amount_minor / 100
    symbol = "₹" if currency_code == "INR" else f"{currency_code} "
    return f"{symbol}{major:,.2f}"


async def notify_customer(
    db: Database,
    *,
    ctx: RefundContext,
    outcome: DecisionOutcome,
    refunded_amount_minor: int | None,
) -> None:
    if outcome.decision not in (Decision.AUTO_APPROVE, Decision.AUTO_DENY):
        return
    if not ctx.customer_user_id:
        return

    customer = await db.fetch_one(
        "SELECT display_name, email FROM users WHERE id = ?", (ctx.customer_user_id,)
    )
    if customer is None:
        return
    to = contactable_email(customer["email"])
    if not to:
        return

    order = await db.fetch_one(
        "SELECT public_reference, currency_code FROM orders WHERE id = ?", (ctx.order_id,)
    )
    reference = order["public_reference"] if order else ctx.order_id
    currency_code = order["currency_code"] if order else "INR"
    display_name = customer["display_name"]

    if outcome.decision == Decision.AUTO_APPROVE:
        amount_display = _format_minor(refunded_amount_minor or 0, currency_code)
        subject = f"Your refund for order {reference} has been processed"
        body = (
            f"Hi {display_name},\n\n"
            f"Your return for order {reference} has been approved and {amount_display} has"
            " been refunded to your original payment method.\n\n"
            "The True Grit Team"
        )
        html_body = render_refund_approved(display_name, reference, amount_display)
        dedupe_suffix = "refund-approved"
    else:
        subject = f"About your return for order {reference}"
        body = (
            f"Hi {display_name},\n\n"
            f"After review, we're not able to refund your return for order {reference}."
            f" {outcome.rationale}\n\n"
            "If you think this is a mistake, reply to this email and our team will take"
            " another look.\n\n"
            "The True Grit Team"
        )
        html_body = render_refund_denied(display_name, reference, outcome.rationale)
        dedupe_suffix = "refund-denied"

    await enqueue_email(
        db,
        dedupe_key=f"return:{ctx.return_request_id}:{dedupe_suffix}",
        to=to,
        subject=subject,
        body=body,
        html_body=html_body,
        aggregate_type="return_request",
        aggregate_id=ctx.return_request_id,
        category=CATEGORY,
    )

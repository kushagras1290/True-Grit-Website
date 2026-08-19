"""The intent taxonomy: what the bot recognises and how each one is handled.

Every message ends up as exactly one `IntentSpec` (or the built-in `UNKNOWN`),
and the spec alone decides the rest of the pipeline -- whether a D1 resolver
runs, which template renders, whether a signed-in customer is required, and
whether the answer is allowed to be given by a machine at all.

The five handling classes are the whole design:

* ``DATA``     -- the answer is a row in D1. A resolver fetches it, a template
                  states it. If the resolver finds nothing, the template says
                  so; it never fills the gap with prose.
* ``STATIC``   -- the answer is a standing fact about the shop (a policy
                  window, a page to visit). Rendered from `support_bot_policy_facts`
                  plus a fixed link, so changing the policy is a database edit.
* ``SOCIAL``   -- greetings and acknowledgements. No data, no escalation; the
                  bot would look broken handing "thanks" to a human.
* ``ESCALATE`` -- a person must handle this. Money that has gone missing, a
                  damaged delivery, anything mutating an existing order. The
                  bot's job is to collect context and hand over cleanly.
* ``GUARD``    -- the message is trying to do something the bot must refuse:
                  prompt injection, harvesting other customers' data, health
                  claims. A fixed refusal, and for the dangerous subset an
                  escalation as well.

Why so much lands in ``ESCALATE`` on purpose: a deterministic bot's value is
that it is never wrong, and the fastest way to lose that is to let it improvise
on the cases where being wrong is expensive. "Money was debited but no order
appeared" is answerable in principle -- and catastrophic to answer incorrectly,
so it goes to a human every time with the order context already attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from truegrit_api.support_bot.phrasebook import PHRASEBOOK


class Handling(StrEnum):
    DATA = "data"
    STATIC = "static"
    SOCIAL = "social"
    ESCALATE = "escalate"
    GUARD = "guard"


class Severity(StrEnum):
    """How urgently a human needs to see an escalation.

    `CRITICAL` exists for the food-safety and fraud cases: those must be
    visible ahead of a queue of delivery questions, and `services.support_bot`
    admin tooling sorts on it.
    """

    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class IntentSpec:
    key: str
    handling: Handling
    # Template id in `templates.TEMPLATES`. Every intent has one, including
    # escalations -- the customer is always told what is happening next.
    template: str
    # Resolver id in `resolvers.RESOLVERS`, for DATA intents only.
    resolver: str | None = None
    # DATA intents that read a customer's own records. When no one is signed
    # in these answer with `templates` "sign in first" copy rather than
    # escalating -- the customer can self-serve in one click.
    requires_auth: bool = False
    # ESCALATE/GUARD only: what the human is being handed, and how loudly.
    severity: Severity = Severity.NORMAL
    # GUARD only: refuse, and additionally raise it with a human.
    escalate_after_guard: bool = False
    # Matching this intent at all is enough -- skip the confidence gate. Set
    # only for the safety cases, where a mid-confidence match on "I got sick"
    # must still reach a person rather than fall through to a clarification.
    preemptive: bool = False

    @property
    def canonical_questions(self) -> tuple[str, ...]:
        return PHRASEBOOK.get(self.key, ())


# Intent keys the classifier can produce without a phrasebook entry.
UNKNOWN = "unknown"
EMPTY_INPUT = "empty_input"
NON_LATIN = "non_latin"
ABUSE = "abuse"
PROMPT_INJECTION = "prompt_injection"


def _spec(
    key: str,
    handling: Handling,
    template: str,
    *,
    resolver: str | None = None,
    requires_auth: bool = False,
    severity: Severity = Severity.NORMAL,
    escalate_after_guard: bool = False,
    preemptive: bool = False,
) -> tuple[str, IntentSpec]:
    return key, IntentSpec(
        key=key,
        handling=handling,
        template=template,
        resolver=resolver,
        requires_auth=requires_auth,
        severity=severity,
        escalate_after_guard=escalate_after_guard,
        preemptive=preemptive,
    )


REGISTRY: dict[str, IntentSpec] = dict(
    (
        # ------------------------------------------------------------ orders
        _spec(
            "order_status",
            Handling.DATA,
            "order_status",
            resolver="order_status",
            requires_auth=True,
        ),
        _spec("order_list", Handling.DATA, "order_list", resolver="order_list", requires_auth=True),
        _spec(
            "order_items", Handling.DATA, "order_items", resolver="order_items", requires_auth=True
        ),
        # Cancellation is time-limited and mutating: the bot explains the rule
        # and hands over rather than promising an outcome it cannot deliver.
        _spec("order_cancel", Handling.ESCALATE, "order_cancel", severity=Severity.HIGH),
        _spec(
            "order_invoice",
            Handling.DATA,
            "order_invoice",
            resolver="order_invoice",
            requires_auth=True,
        ),
        _spec(
            "order_change_address",
            Handling.ESCALATE,
            "order_change_address",
            severity=Severity.HIGH,
        ),
        _spec("order_missing_item", Handling.ESCALATE, "order_problem", severity=Severity.HIGH),
        _spec("order_damaged_item", Handling.ESCALATE, "order_problem", severity=Severity.HIGH),
        _spec("order_wrong_item", Handling.ESCALATE, "order_problem", severity=Severity.HIGH),
        _spec("order_not_arrived", Handling.ESCALATE, "order_problem", severity=Severity.HIGH),
        _spec("order_delayed", Handling.ESCALATE, "order_problem"),
        # ----------------------------------------------------------- returns
        _spec("return_policy", Handling.STATIC, "return_policy"),
        _spec("return_start", Handling.STATIC, "return_start"),
        _spec(
            "return_status",
            Handling.DATA,
            "return_status",
            resolver="return_status",
            requires_auth=True,
        ),
        _spec(
            "refund_status",
            Handling.DATA,
            "refund_status",
            resolver="refund_status",
            requires_auth=True,
        ),
        _spec("refund_timing", Handling.STATIC, "refund_timing"),
        _spec("exchange_request", Handling.STATIC, "exchange_request"),
        # ---------------------------------------------------------- payments
        _spec("payment_methods", Handling.STATIC, "payment_methods"),
        _spec("payment_failed", Handling.STATIC, "payment_failed"),
        # Money that left an account and produced no order. Never templated.
        _spec(
            "payment_debited_no_order",
            Handling.ESCALATE,
            "payment_dispute",
            severity=Severity.CRITICAL,
            preemptive=True,
        ),
        _spec("cod_availability", Handling.STATIC, "cod_availability"),
        # --------------------------------------------------------- catalogue
        _spec(
            "product_availability",
            Handling.DATA,
            "product_availability",
            resolver="product_availability",
        ),
        _spec("product_price", Handling.DATA, "product_price", resolver="product_price"),
        _spec("product_restock", Handling.DATA, "product_restock", resolver="product_availability"),
        _spec("product_storage", Handling.DATA, "product_storage", resolver="product_storage"),
        _spec("product_sourcing", Handling.DATA, "product_sourcing", resolver="product_sourcing"),
        _spec(
            "product_certification",
            Handling.DATA,
            "product_certification",
            resolver="product_certification",
        ),
        _spec("category_browse", Handling.DATA, "category_browse", resolver="categories"),
        _spec("bundle_info", Handling.DATA, "bundle_info", resolver="bundles"),
        # ---------------------------------------------------------- delivery
        _spec("delivery_areas", Handling.DATA, "delivery_areas", resolver="delivery_areas"),
        _spec("delivery_charges", Handling.STATIC, "delivery_charges"),
        _spec("delivery_time", Handling.STATIC, "delivery_time"),
        _spec("delivery_slots", Handling.STATIC, "delivery_slots"),
        _spec("pickup_points", Handling.DATA, "pickup_points", resolver="pickup_points"),
        _spec("international_shipping", Handling.STATIC, "international_shipping"),
        # ----------------------------------------------------------- account
        _spec("account_signin_problem", Handling.STATIC, "account_signin_problem"),
        _spec("account_password_reset", Handling.STATIC, "account_password_reset"),
        _spec("account_otp_not_received", Handling.STATIC, "account_otp_not_received"),
        # Erasure is a rights request with a legal clock on it, not a setting.
        _spec("account_delete", Handling.ESCALATE, "account_delete", severity=Severity.HIGH),
        _spec("account_change_contact", Handling.STATIC, "account_change_contact"),
        _spec("account_addresses", Handling.STATIC, "account_addresses"),
        _spec("account_unsubscribe", Handling.STATIC, "account_unsubscribe"),
        _spec("account_register", Handling.STATIC, "account_register"),
        # ---------------------------------------------------------- programs
        _spec(
            "loyalty_points",
            Handling.DATA,
            "loyalty_points",
            resolver="loyalty",
            requires_auth=True,
        ),
        _spec(
            "referral_program",
            Handling.DATA,
            "referral_program",
            resolver="referral",
            requires_auth=True,
        ),
        # Balance is read against a code the customer supplies, and the code is
        # the bearer instrument itself -- so this needs a signed-in account as
        # well, which also gives the rate limiter someone to count against.
        _spec(
            "giftcard_balance",
            Handling.DATA,
            "giftcard_balance",
            resolver="giftcard_balance",
            requires_auth=True,
        ),
        _spec("giftcard_buy", Handling.STATIC, "giftcard_buy"),
        _spec("discount_available", Handling.DATA, "discount_available", resolver="promotions"),
        _spec("discount_not_working", Handling.STATIC, "discount_not_working"),
        _spec(
            "subscription_status",
            Handling.DATA,
            "subscription_status",
            resolver="subscriptions",
            requires_auth=True,
        ),
        _spec("subscription_manage", Handling.STATIC, "subscription_manage"),
        _spec("preorder_harvest", Handling.DATA, "preorder_harvest", resolver="harvest"),
        _spec("bulk_b2b", Handling.STATIC, "bulk_b2b"),
        # ----------------------------------------------------------- content
        _spec("recipe_lookup", Handling.DATA, "recipe_lookup", resolver="recipes"),
        _spec("article_lookup", Handling.DATA, "article_lookup", resolver="articles"),
        _spec("review_how_to", Handling.STATIC, "review_how_to"),
        _spec("wishlist_how_to", Handling.STATIC, "wishlist_how_to"),
        _spec(
            "community_discussions", Handling.DATA, "community_discussions", resolver="discussions"
        ),
        # ----------------------------------------------------------- company
        _spec("about_company", Handling.STATIC, "about_company"),
        _spec("farm_partnership", Handling.STATIC, "farm_partnership"),
        _spec("careers", Handling.STATIC, "careers"),
        _spec("press_media", Handling.ESCALATE, "press_media"),
        _spec("contact_details", Handling.STATIC, "contact_details"),
        _spec("privacy_policy", Handling.STATIC, "privacy_policy"),
        _spec("terms_conditions", Handling.STATIC, "terms_conditions"),
        _spec("sourcing_standards", Handling.STATIC, "sourcing_standards"),
        # ------------------------------------------------------------ social
        _spec("greeting", Handling.SOCIAL, "greeting"),
        _spec("farewell", Handling.SOCIAL, "farewell"),
        _spec("thanks", Handling.SOCIAL, "thanks"),
        _spec("affirm", Handling.SOCIAL, "affirm"),
        _spec("deny", Handling.SOCIAL, "deny"),
        _spec("bot_identity", Handling.SOCIAL, "bot_identity"),
        _spec("capabilities", Handling.SOCIAL, "capabilities"),
        # -------------------------------------------------- humans and guard
        _spec("human_handoff", Handling.ESCALATE, "human_handoff", preemptive=True),
        _spec("complaint", Handling.ESCALATE, "complaint", severity=Severity.HIGH, preemptive=True),
        _spec(
            "legal_threat",
            Handling.ESCALATE,
            "legal_threat",
            severity=Severity.CRITICAL,
            preemptive=True,
        ),
        # Illness, contamination, allergic reaction. Highest priority there is:
        # this must outrank every commercial intent the message also matches.
        _spec(
            "safety_food",
            Handling.ESCALATE,
            "safety_food",
            severity=Severity.CRITICAL,
            preemptive=True,
        ),
        # Health claims about food are regulated and the bot has no basis for
        # one; it declines and points at the ingredient information instead.
        _spec("medical_advice", Handling.GUARD, "medical_advice"),
        _spec(
            "pii_request",
            Handling.GUARD,
            "pii_request",
            severity=Severity.HIGH,
            escalate_after_guard=True,
            preemptive=True,
        ),
        _spec(
            "fraud_scam",
            Handling.GUARD,
            "fraud_scam",
            severity=Severity.CRITICAL,
            escalate_after_guard=True,
            preemptive=True,
        ),
        _spec("off_topic", Handling.GUARD, "off_topic"),
        # ---------------------------------------- produced without phrasebook
        _spec(ABUSE, Handling.GUARD, "abuse", severity=Severity.HIGH, preemptive=True),
        _spec(PROMPT_INJECTION, Handling.GUARD, "prompt_injection", preemptive=True),
        _spec(EMPTY_INPUT, Handling.GUARD, "empty_input"),
        _spec(NON_LATIN, Handling.ESCALATE, "non_latin"),
        _spec(UNKNOWN, Handling.ESCALATE, "unknown"),
    )
)


def spec_for(key: str) -> IntentSpec:
    """Look up an intent, falling back to `UNKNOWN` rather than raising.

    A key that is not in the registry means the phrasebook and the taxonomy
    have drifted apart -- a bug, but one that must degrade to "a human will
    pick this up" rather than a 500 in a customer's chat window. The drift
    itself is caught in tests, not at runtime.
    """
    return REGISTRY.get(key, REGISTRY[UNKNOWN])


# Phrasebook entries with no matching spec would be silently unroutable, and
# specs with no phrasings are only reachable by regex. Both are legitimate in
# one direction only, so the check that matters runs in the test suite.
MATCHABLE_INTENTS: tuple[str, ...] = tuple(key for key in PHRASEBOOK if key in REGISTRY)

"""Tier A: rule matching and slot extraction.

Two jobs, both deterministic and both ahead of any similarity scoring.

**Rules.** A rule fires on a regular expression and asserts an intent outright.
This tier exists for the cases where one phrase settles the question no matter
what the rest of the sentence says -- an order reference, "speak to a human",
"I got sick after eating this". Similarity scoring cannot be trusted with
those: a long, rambling message about a delayed delivery that happens to
mention illness would score highest on `order_delayed`, and the illness would
be answered with a tracking link.

Rules therefore carry a `priority`, and the highest-priority match wins
regardless of how well anything else scores. The safety, fraud and abuse rules
sit at the top of that ordering on purpose.

**Surfaces.** Each rule declares whether it matches the plain normalised text
or the synonym-folded token stream from `normalize.tokenise`. Intent rules use
tokens, so "wheres my parcel" and "where is my order" are one pattern rather
than two. Guard rules use the normalised text, because folding "shipped" onto
"delivery" is helpful for routing and actively harmful when you are trying to
match a specific offensive word or an injection attempt verbatim.

**Slots.** Extraction runs over the raw message, not either normalised form,
because the things worth extracting -- `TG-12345678`, a gift-card code, a six
digit PIN code -- are exactly the tokens normalisation would flatten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any

from truegrit_api.support_bot import intents
from truegrit_api.support_bot.normalize import Prepared

# Production references are `TG-` plus eight digits (services.checkout), but the
# separator is whatever the customer's keyboard produced and the body is matched
# loosely so a mistyped reference still resolves to "no such order on your
# account" rather than being missed entirely.
ORDER_REFERENCE = re.compile(r"\bTG[\s\-_]?([A-Za-z0-9]{1,12})\b", re.IGNORECASE)
# Gift card codes are 6-24 alphanumerics (services.gift_cards). Requiring both a
# letter and a digit keeps ordinary words and bare numbers out.
GIFT_CARD_CODE = re.compile(r"\b(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)([A-Z0-9]{6,24})\b")
INDIA_PIN_CODE = re.compile(r"\b([1-9]\d{5})\b")
EMAIL_ADDRESS = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


class Surface(StrEnum):
    NORMALISED = "normalised"
    TOKENS = "tokens"


class Priority(IntEnum):
    """Rule precedence. Ordering, not scoring -- a `SAFETY` rule beats a
    `DECISIVE` rule even though both are certain about their own match."""

    SAFETY = 100
    HANDOFF = 80
    DECISIVE = 60
    STRONG = 40


@dataclass(frozen=True)
class Rule:
    intent: str
    pattern: re.Pattern[str]
    priority: Priority
    surface: Surface = Surface.TOKENS
    # Tier A is rule-based, so a match is an assertion rather than an estimate.
    # The few rules below 1.0 are the ones that are merely strong evidence.
    confidence: float = 1.0


def _rule(
    intent: str,
    expression: str,
    priority: Priority,
    *,
    surface: Surface = Surface.TOKENS,
    confidence: float = 1.0,
) -> Rule:
    return Rule(
        intent=intent,
        pattern=re.compile(expression, re.IGNORECASE),
        priority=priority,
        surface=surface,
        confidence=confidence,
    )


# --- Safety, abuse and manipulation ----------------------------------------
# Everything in this block outranks every commercial intent. A message that is
# both a complaint about a late delivery and a report of illness is the second
# thing, and treating it as the first is the worst outcome this bot can produce.

_SAFETY_RULES: tuple[Rule, ...] = (
    # Illness following consumption. Deliberately broad: a false positive costs
    # one unnecessary human review, a false negative is a customer told to
    # check their tracking link after reporting food poisoning.
    _rule(
        "safety_food",
        r"\b(sick|ill|unwell|vomit\w*|nausea\w*|diarrh\w*|poison\w*|hospital\w*|"
        r"food\s*poisoning|stomach\s*(ache|upset|pain)|throwing\s*up)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "safety_food",
        r"\b(allerg\w*|anaphyla\w*|rash|hives|swell\w*|breathing|reaction)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    # Contamination and spoilage found in the product itself.
    _rule(
        "safety_food",
        r"\b(mould|mold|mouldy|moldy|fungus|fungal|rotten|rotting|spoil\w*|stale|"
        r"maggot\w*|larva\w*|worm\w*|insect\w*|weevil\w*|cockroach\w*|"
        r"foreign\s*(object|body|matter)|glass|metal\s*piece|stone\w*|hair)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    # Money left the account and produced nothing. Always a person.
    _rule(
        "payment_debited_no_order",
        r"\b(debit\w*|deduct\w*|charg\w*|cut)\b.{0,40}\b(no|not|without|never)\b.{0,20}\border\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "payment_debited_no_order",
        r"\b(twice|double|duplicate|two\s*times)\b.{0,30}\b(charg\w*|debit\w*|deduct\w*|paid|pay)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "payment_debited_no_order",
        r"\b(charg\w*|debit\w*|deduct\w*)\b.{0,30}\b(twice|double|duplicate|two\s*times)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    # Someone steering the conversation toward a payout or a credential.
    _rule(
        "fraud_scam",
        r"\b(share|send|give|tell|forward)\b.{0,25}\b(otp|password|pin|cvv|"
        r"one\s*time\s*password)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "fraud_scam",
        r"\b(refund|money|amount|payment)\b.{0,30}\b(to\s*(this|my|another|different)|"
        r"upi|wallet|paytm|gpay|phonepe)\b.{0,20}\b(id|account|number)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "fraud_scam",
        r"\bi\s*am\s*(from|with)\b.{0,20}\b(bank|rbi|paytm|support\s*team|security\s*team)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    # Legal escalation. Answering these with a policy summary reads as a brush
    # off and is the wrong move commercially as well as legally.
    _rule(
        "legal_threat",
        r"\b(sue|suing|lawsuit|lawyer|advocate|solicitor|legal\s*(action|notice)|"
        r"consumer\s*(court|forum)|file\s*(a\s*)?(case|complaint\s*with)|fir|police|"
        r"litigation|defamation)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    # Harvesting other people's data.
    _rule(
        intents.PROMPT_INJECTION,
        r"\b(ignore|disregard|forget|override)\b.{0,30}\b(previous|prior|above|earlier|all)\b"
        r".{0,20}\b(instruction\w*|prompt\w*|rule\w*|direction\w*)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    _rule(
        intents.PROMPT_INJECTION,
        r"\b(system\s*prompt|your\s*(instruction\w*|prompt|rules|guidelines)|"
        r"jailbreak|dan\s*mode|developer\s*mode|pretend\s*(you|to\s*be)|"
        r"act\s*as\s*(a|an|if)|you\s*are\s*now|roleplay\s*as|repeat\s*(the\s*)?"
        r"(text|words)\s*above)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "pii_request",
        r"\b(phone|mobile|email|address|detail\w*|name\w*|data|record\w*|list)\b"
        r".{0,30}\b(another|other|someone\s*else|different)\s*(customer|user|buyer|person)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "pii_request",
        r"\b(customer|user|client)\s*(list|database|records|data|emails|details)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "pii_request",
        r"\b(home\s*address|personal\s*(number|phone|address))\b.{0,30}\b(owner|founder|ceo|staff)\b",
        Priority.SAFETY,
        surface=Surface.NORMALISED,
    ),
)

# Abuse is matched on the raw normalised surface and kept as its own block so
# the list is easy to review and extend without touching routing logic. The
# response is a firm, non-escalating boundary the first time (`templates.abuse`);
# the widget's own repetition guard in `gate.py` is what handles persistence.
_ABUSE_TERMS = (
    r"fuck\w*|f\*+k|shit\w*|bullshit|bastard\w*|bitch\w*|asshole\w*|arsehole\w*|"
    r"dickhead\w*|idiot\w*|moron\w*|stupid\s*(bot|people|company)|scum\w*|"
    r"retard\w*|wanker\w*|prick\w*|cunt\w*|"
    r"chutiy\w*|madarchod\w*|behenchod\w*|bhenchod\w*|randi|gandu|harami|kutt[aei]|"
    r"kill\s*(you|yourself)|i\s*will\s*(find|hurt|kill|beat)\s*you"
)
_ABUSE_RULES: tuple[Rule, ...] = (
    _rule(intents.ABUSE, rf"\b({_ABUSE_TERMS})\b", Priority.SAFETY, surface=Surface.NORMALISED),
)

# --- Handing over to a person ----------------------------------------------

_HANDOFF_RULES: tuple[Rule, ...] = (
    _rule(
        "human_handoff",
        r"\b(talk|speak|connect|transfer|chat|put\s*me\s*through|get\s*me)\b.{0,25}"
        r"\b(human|person|agent|representative|executive|advisor|someone\s*real|"
        r"real\s*(person|human)|customer\s*(care|service|support))\b",
        Priority.HANDOFF,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "human_handoff",
        r"\b(real\s*(person|human)|human\s*(agent|being)|not\s*a\s*bot|"
        r"stop\s*(the\s*)?bot|useless\s*bot)\b",
        Priority.HANDOFF,
        surface=Surface.NORMALISED,
    ),
)

# --- Decisive commercial rules ---------------------------------------------
# These run against the synonym-folded token stream, so each pattern covers the
# whole family of phrasings `normalize.SYNONYMS` maps together.

_DECISIVE_RULES: tuple[Rule, ...] = (
    # A verb next to an order reference settles which order intent it is; the
    # bare reference alone (handled in `match` below) means "status".
    _rule("order_cancel", r"\bcancel\b.{0,30}\border\b", Priority.DECISIVE),
    _rule("order_cancel", r"\border\b.{0,30}\bcancel\b", Priority.DECISIVE),
    # Duration and limit words turn any return phrasing into a policy question,
    # and must beat the `return_start` rules below on the phrasings that match
    # both ("how many days do I have to return this"). Higher confidence is how
    # that tie is broken; see `match_rules`.
    _rule(
        "return_policy",
        r"\b(how long|how many|what.{0,10}window|deadline|time limit|cut ?off|"
        r"days?\b.{0,15}\bto)\b.{0,30}\b(return|send.{0,20}back|give.{0,20}back)\b",
        Priority.DECISIVE,
        surface=Surface.NORMALISED,
        confidence=0.95,
    ),
    # Deliberately narrow. An earlier, looser version of this
    # (`how|where|want|need|start...` within 30 characters of "return") also
    # swallowed "how many days do I have to return an item", which is a policy
    # question with a completely different answer. Only phrasings that state an
    # intention to act belong here.
    _rule(
        "return_start",
        r"\b(want|need|like|wish)\b.{0,15}\breturn\b",
        Priority.DECISIVE,
        confidence=0.9,
    ),
    _rule(
        "return_start",
        r"\b(start|raise|initiate|begin|make|create|process)\b.{0,15}\breturn\b",
        Priority.DECISIVE,
        confidence=0.9,
    ),
    _rule(
        "return_start",
        r"\bhow\b.{0,10}\b(do|can)\b.{0,10}\b(i|we)\b.{0,10}\breturn\b",
        Priority.DECISIVE,
        confidence=0.9,
    ),
    _rule("refund_status", r"\b(where|status|update|not)\b.{0,25}\brefund\b", Priority.DECISIVE),
    _rule("track", r"\btrack\b.{0,20}\border\b", Priority.DECISIVE),
    _rule("order_status", r"\border\b.{0,20}\btrack\b", Priority.DECISIVE),
    _rule("order_invoice", r"\binvoice\b", Priority.DECISIVE, confidence=0.9),
    _rule("giftcard_balance", r"\bgiftcard\b.{0,25}\bbalance\b", Priority.DECISIVE),
    _rule("giftcard_balance", r"\bbalance\b.{0,25}\bgiftcard\b", Priority.DECISIVE),
    _rule(
        "loyalty_points",
        r"\b(my|how\s*many)\b.{0,15}\bpoints?\b",
        Priority.DECISIVE,
        confidence=0.9,
    ),
    _rule(
        "account_password_reset", r"\b(forgot|reset|change)\b.{0,15}\bpassword\b", Priority.DECISIVE
    ),
    _rule(
        "account_otp_not_received", r"\botp\b.{0,25}\b(not|never|resend|again)\b", Priority.DECISIVE
    ),
    _rule("account_otp_not_received", r"\b(not|never|resend)\b.{0,25}\botp\b", Priority.DECISIVE),
    _rule("account_delete", r"\bdelete\b.{0,20}\baccount\b", Priority.DECISIVE),
    _rule(
        "account_unsubscribe",
        r"\b(unsubscribe|opt\s*out|stop)\b.{0,25}\bemail\b",
        Priority.DECISIVE,
    ),
    # "in stock" carries no other meaning in this domain, and leaving it to
    # similarity scoring was actively wrong: "do you have black mustard oil in
    # stock" shares "do you have" with "do you have a blog", and because the
    # blog phrasing is four tokens long the coverage term scored it higher than
    # any product phrasing. One rule removes the whole class of that mistake.
    _rule(
        "product_restock",
        r"\b(back in stock|restock\w*|available again|"
        r"in stock again|when.{0,20}back)\b",
        Priority.DECISIVE,
        surface=Surface.NORMALISED,
        confidence=0.97,
    ),
    _rule(
        "product_availability",
        r"\b(in stock|out of stock|in-stock|stock level)\b",
        Priority.DECISIVE,
        surface=Surface.NORMALISED,
        confidence=0.95,
    ),
    # Spelled out, "cash on delivery" never reaches the `cod` synonym fold.
    _rule(
        "cod_availability",
        r"\b(cash on delivery|pay (on|at|upon) delivery|"
        r"cash when it arrives)\b",
        Priority.DECISIVE,
        surface=Surface.NORMALISED,
        confidence=0.96,
    ),
    _rule("bulk_b2b", r"\bbulk\b", Priority.DECISIVE, confidence=0.85),
    _rule("cod_availability", r"\bcashondelivery\b", Priority.DECISIVE),
    _rule(
        "international_shipping",
        r"\b(international|abroad|overseas|outside\s*india)\b",
        Priority.DECISIVE,
        surface=Surface.NORMALISED,
        confidence=0.9,
    ),
    _rule(
        "farm_partnership",
        r"\b(become|join|partner|supply)\b.{0,25}\bfarm\b",
        Priority.DECISIVE,
        confidence=0.9,
    ),
    _rule(
        "careers",
        r"\b(hiring|job\s*opening|vacanc\w*|career|resume|cv|recruit\w*)\b",
        Priority.DECISIVE,
        surface=Surface.NORMALISED,
        confidence=0.9,
    ),
)

# --- Short social utterances ------------------------------------------------
# Anchored end to end: "hi" is a greeting, "hi, where is my order" is not.

_SOCIAL_RULES: tuple[Rule, ...] = (
    _rule(
        "greeting",
        r"^(hi|hii+|hey+|hello+|helo|yo|namaste|namaskara|good\s*(morning|afternoon|"
        r"evening|day))[\s!.]*$",
        Priority.STRONG,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "farewell",
        r"^(bye+|goodbye|good\s*night|see\s*(you|ya)|cya|later|that\s*is\s*all|"
        r"nothing\s*else)[\s!.]*$",
        Priority.STRONG,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "thanks",
        r"^(thanks?|thank\s*you|thx|ty|cheers|great|perfect|awesome|nice|"
        r"got\s*it|ok\s*thanks?)[\s!.]*$",
        Priority.STRONG,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "affirm",
        r"^(yes|yep|yeah|yup|ya|sure|ok|okay|k|correct|right|fine|"
        r"please\s*do)[\s!.]*$",
        Priority.STRONG,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "deny",
        r"^(no|nope|nah|not\s*really|no\s*thanks?|never\s*mind)[\s!.]*$",
        Priority.STRONG,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "capabilities",
        r"^(help|what\s*can\s*you\s*do|options|menu)[\s!?.]*$",
        Priority.STRONG,
        surface=Surface.NORMALISED,
    ),
    _rule(
        "bot_identity",
        r"\b(are\s*you\s*(a\s*)?(bot|robot|human|real|ai|person)|"
        r"am\s*i\s*(talking|chatting)\s*to\s*a\s*(bot|human|person)|"
        r"who\s*are\s*you)\b",
        Priority.STRONG,
        surface=Surface.NORMALISED,
    ),
)

RULES: tuple[Rule, ...] = (
    *_SAFETY_RULES,
    *_ABUSE_RULES,
    *_HANDOFF_RULES,
    *_DECISIVE_RULES,
    *_SOCIAL_RULES,
)


@dataclass(frozen=True)
class RuleMatch:
    intent: str
    confidence: float
    priority: int
    pattern: str


def match_rules(prepared: Prepared) -> RuleMatch | None:
    """The highest-priority rule that fires, or None.

    Ties inside a priority band are broken by confidence and then by the order
    the rules are declared in, so the result is stable for a given message --
    an operator debugging a misroute gets the same answer every time they
    replay it.
    """
    token_text = " ".join(prepared.tokens)
    best: RuleMatch | None = None
    for rule in RULES:
        haystack = token_text if rule.surface is Surface.TOKENS else prepared.normalised
        if not rule.pattern.search(haystack):
            continue
        # `track` is a synonym-fold artefact rather than a real intent: the
        # token stream turns "tracking" into "track", which is only ever a
        # request for order status.
        intent = "order_status" if rule.intent == "track" else rule.intent
        candidate = RuleMatch(
            intent=intent,
            confidence=rule.confidence,
            priority=int(rule.priority),
            pattern=rule.pattern.pattern,
        )
        if best is None or (candidate.priority, candidate.confidence) > (
            best.priority,
            best.confidence,
        ):
            best = candidate
    return best


# --- Slot extraction --------------------------------------------------------

# Words that describe the question rather than the thing being asked about.
# Stripped from the token stream to leave a usable catalogue search term, so
# "do you have any organic turmeric in stock" searches for "organic turmeric".
_QUERY_NOISE: frozenset[str] = frozenset(
    {
        "do",
        "you",
        "have",
        "be",
        "there",
        "any",
        "is",
        "it",
        "this",
        "that",
        "i",
        "me",
        "my",
        "we",
        "can",
        "could",
        "will",
        "would",
        "should",
        "want",
        "need",
        "get",
        "buy",
        "order",
        "sell",
        "stock",
        "available",
        "left",
        "still",
        "right",
        "now",
        "currently",
        "today",
        "what",
        "when",
        "where",
        "which",
        "how",
        "why",
        "who",
        "much",
        "many",
        "price",
        "cost",
        "tell",
        "know",
        "look",
        "for",
        "about",
        "some",
        "more",
        "your",
        "yours",
        "product",
        "in",
        "on",
        "at",
        "to",
        "from",
        "with",
        "and",
        "or",
        "but",
        "not",
        "no",
        "yes",
        "storage",
        "store",
        "keep",
        "fresh",
        "long",
        "does",
        "did",
        "was",
        "are",
        "am",
        "back",
        "again",
        "restock",
        "come",
        "coming",
        "sourcing",
        "source",
        "grow",
        "grown",
        "farm",
        "certification",
        "organic",
        "certified",
        "recipe",
        "article",
        "delivery",
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank",
        "sir",
        "madam",
        "team",
        "help",
        "hii",
    }
)


def _product_query(prepared: Prepared) -> str:
    """Whatever the customer is asking *about*, once the asking is removed.

    Falls back to the empty string rather than guessing when nothing
    distinctive is left -- `resolvers` turns that into "which product did you
    mean?", which is a better outcome than searching the catalogue for "any".
    """
    remaining = [token for token in prepared.tokens if token not in _QUERY_NOISE]
    return " ".join(remaining[:6])


def extract_slots(raw: str, prepared: Prepared) -> dict[str, Any]:
    """Structured values pulled from the raw message.

    Runs on `raw` because normalisation strips exactly the punctuation these
    identifiers are made of -- `TG-12345678` survives here and nowhere else.
    """
    slots: dict[str, Any] = {}

    reference = ORDER_REFERENCE.search(raw)
    if reference is not None:
        slots["order_reference"] = f"TG-{reference.group(1).upper()}"

    gift_card = GIFT_CARD_CODE.search(raw.upper())
    if gift_card is not None:
        candidate = gift_card.group(1)
        # An order reference also satisfies the gift-card shape; the more
        # specific match wins so "TG12345678" is never read as a voucher.
        if slots.get("order_reference", "").replace("-", "") != candidate:
            slots["gift_card_code"] = candidate

    pin_code = INDIA_PIN_CODE.search(raw)
    if pin_code is not None:
        slots["postal_code"] = pin_code.group(1)

    if EMAIL_ADDRESS.search(raw) is not None:
        # The value itself is deliberately not kept -- nothing downstream needs
        # it, and an escalation record should not carry an address the customer
        # typed in passing. Only the fact that one was present is useful, as a
        # hint for the human picking the conversation up.
        slots["contains_email"] = True

    query = _product_query(prepared)
    if query:
        slots["query"] = query

    return slots

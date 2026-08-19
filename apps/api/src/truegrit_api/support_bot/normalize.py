"""Text normalisation shared by both classifier tiers.

Everything the deterministic bot does downstream keys off the token tuple this
module produces, so the rules here are deliberately explicit and inspectable
rather than clever: an operator looking at a misrouted question must be able to
read exactly why "wheres my parcel" became `("where", "be", "my", "order")`
and fix it by editing a table, not by retraining anything.

Three decisions worth stating, because each is the opposite of what a general
NLP pipeline would do:

* **No general stemmer.** Porter-style suffix stripping collapses
  "package"/"packages" to different roots ("package" vs "packag") unless the
  singular is stemmed too, and mangles domain words a support bot cares about
  ("status" -> "statu"). Only plural -> singular is applied, guarded against
  the `-ss`/`-us`/`-is` endings that are not plurals at all, and every verb or
  variant form that matters is listed in `SYNONYMS` where it can be seen.
* **Almost no stopwords.** Question words carry the intent here -- dropping
  "where"/"when"/"how" would make "where is my order", "when will my order
  arrive" and "how do I cancel my order" the same token set. Only words that
  are genuinely empty in every phrasing are removed.
* **Synonyms map onto the phrasebook's vocabulary, not onto English.**
  "parcel", "package", "shipment" and "consignment" all become "order" because
  this store's canonical questions say "order"; the map exists to close the gap
  between how customers write and how the phrasebook is written.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Runs of anything that is not a letter, digit or internal apostrophe become a
# single space. Keeping digits matters: order references (`TG-12345678`) and
# quantities survive normalisation and are still available to the regex tier.
_NON_WORD = re.compile(r"[^a-z0-9]+")

# Expanded before anything else, so the singulariser never sees "wheres" and
# the synonym map never has to carry both "dont" and "do not".
CONTRACTIONS: dict[str, tuple[str, ...]] = {
    "im": ("i", "be"),
    "ive": ("i", "have"),
    "id": ("i", "would"),
    "ill": ("i", "will"),
    "youre": ("you", "be"),
    "youve": ("you", "have"),
    "its": ("it", "be"),
    "thats": ("that", "be"),
    "whats": ("what", "be"),
    "wheres": ("where", "be"),
    "whens": ("when", "be"),
    "hows": ("how", "be"),
    "whos": ("who", "be"),
    "whys": ("why", "be"),
    "theres": ("there", "be"),
    "heres": ("here", "be"),
    "dont": ("do", "not"),
    "doesnt": ("do", "not"),
    "didnt": ("do", "not"),
    "cant": ("can", "not"),
    "cannot": ("can", "not"),
    "couldnt": ("can", "not"),
    "wont": ("will", "not"),
    "wouldnt": ("would", "not"),
    "shouldnt": ("should", "not"),
    "isnt": ("be", "not"),
    "arent": ("be", "not"),
    "wasnt": ("be", "not"),
    "werent": ("be", "not"),
    "havent": ("have", "not"),
    "hasnt": ("have", "not"),
    "hadnt": ("have", "not"),
    "lets": ("let", "us"),
    "gimme": ("give", "me"),
    "wanna": ("want", "to"),
    "gonna": ("go", "to"),
    "plz": ("please",),
    "pls": ("please",),
    "u": ("you",),
    "ur": ("your",),
    "r": ("be",),
    "n": ("and",),
    "thx": ("thanks",),
    "ty": ("thanks",),
    "asap": ("urgent",),
}

# Domain vocabulary folded onto the words the phrasebook actually uses. Read
# this as "customers say X, the canonical questions say Y".
SYNONYMS: dict[str, str] = {
    # --- copulas and modals, so tense never splits a match ------------------
    "is": "be",
    "are": "be",
    "am": "be",
    "was": "be",
    "were": "be",
    "been": "be",
    "has": "have",
    "had": "have",
    "does": "do",
    "did": "do",
    "could": "can",
    "shall": "will",
    "gonna": "will",
    # --- the order object ---------------------------------------------------
    "parcel": "order",
    "package": "order",
    "packet": "order",
    "shipment": "order",
    "consignment": "order",
    "purchase": "order",
    "buy": "order",
    "bought": "order",
    "ordered": "order",
    "ordering": "order",
    "booking": "order",
    "booked": "order",
    # --- delivery -----------------------------------------------------------
    "shipping": "delivery",
    "shipped": "delivery",
    "ship": "delivery",
    "dispatch": "delivery",
    "dispatched": "delivery",
    "despatch": "delivery",
    "courier": "delivery",
    "delivered": "delivery",
    "deliver": "delivery",
    "delivering": "delivery",
    "arrive": "delivery",
    "arrived": "delivery",
    "arriving": "delivery",
    "arrival": "delivery",
    "reach": "delivery",
    "reached": "delivery",
    "eta": "delivery",
    "tracking": "track",
    "trace": "track",
    "traced": "track",
    "whereabouts": "track",
    # --- money --------------------------------------------------------------
    "cost": "price",
    "costs": "price",
    "rate": "price",
    "rates": "price",
    "pricing": "price",
    "charge": "price",
    "charges": "price",
    "fee": "price",
    "fees": "price",
    "amount": "price",
    "rupees": "price",
    "rs": "price",
    "inr": "price",
    "money": "payment",
    "paid": "payment",
    "pay": "payment",
    "paying": "payment",
    "payments": "payment",
    "debited": "debit",
    "deducted": "debit",
    "cod": "cashondelivery",
    "upi": "payment",
    "netbanking": "payment",
    "card": "payment",
    # --- returns ------------------------------------------------------------
    "returns": "return",
    "returned": "return",
    "returning": "return",
    "refunded": "refund",
    "refunds": "refund",
    "reimburse": "refund",
    "reimbursement": "refund",
    "replace": "exchange",
    "replacement": "exchange",
    "swap": "exchange",
    # --- catalogue ----------------------------------------------------------
    "item": "product",
    "items": "product",
    "goods": "product",
    "produce": "product",
    "stuff": "product",
    "sku": "product",
    "variant": "product",
    "instock": "stock",
    "availability": "available",
    "restock": "stock",
    "restocked": "stock",
    "stocked": "stock",
    "inventory": "stock",
    "sold": "stock",
    "soldout": "stock",
    # --- account ------------------------------------------------------------
    "login": "signin",
    "log": "signin",
    "signin": "signin",
    "signup": "register",
    "registration": "register",
    "registered": "register",
    "passwd": "password",
    "pwd": "password",
    "otp": "otp",
    "verification": "verify",
    "verified": "verify",
    "mobile": "phone",
    "number": "phone",
    "mail": "email",
    "emails": "email",
    "newsletter": "email",
    "profile": "account",
    "accounts": "account",
    # --- people / escalation ------------------------------------------------
    "human": "agent",
    "person": "agent",
    "someone": "agent",
    "somebody": "agent",
    "representative": "agent",
    "rep": "agent",
    "executive": "agent",
    "manager": "agent",
    "staff": "agent",
    "support": "agent",
    "helpline": "agent",
    "customercare": "agent",
    "complaint": "complain",
    "complaining": "complain",
    "grievance": "complain",
    # --- content ------------------------------------------------------------
    "recipes": "recipe",
    "cook": "recipe",
    "cooking": "recipe",
    "blog": "article",
    "articles": "article",
    "post": "article",
    "posts": "article",
    # --- misc ---------------------------------------------------------------
    "cancelled": "cancel",
    "canceled": "cancel",
    "cancelling": "cancel",
    "cancellation": "cancel",
    "bill": "invoice",
    "billing": "invoice",
    "receipt": "invoice",
    "gst": "invoice",
    "coupon": "discount",
    "promo": "discount",
    "voucher": "discount",
    "offer": "discount",
    "deal": "discount",
    "sale": "discount",
    "subscribe": "subscription",
    "subscriptions": "subscription",
    "recurring": "subscription",
    "giftcard": "giftcard",
    "loyalty": "points",
    "reward": "points",
    "rewards": "points",
    "referral": "refer",
    "wholesale": "bulk",
    "b2b": "bulk",
    "quantity": "bulk",
    "organic": "organic",
    "certified": "certification",
    "certificate": "certification",
    "farmer": "farm",
    "farms": "farm",
    "grower": "farm",
    "store": "storage",
    "storing": "storage",
    "preserve": "storage",
    "urgently": "urgent",
    "immediately": "urgent",
}

# Only words that add nothing in every phrasing this bot sees. Pronouns and
# question words stay -- "my order" versus "an order" is the difference between
# an account lookup and a policy answer.
STOPWORDS: frozenset[str] = frozenset({"a", "an", "the", "of", "please", "kindly"})

# Endings that look plural but are not. `-os` is excluded from the simple
# `-s` rule instead ("kilos" -> "kilo" is wanted, "chaos" is not a word here).
_NOT_PLURAL_ENDINGS = ("ss", "us", "is", "as")
_ES_PLURAL_ENDINGS = ("ches", "shes", "sses", "xes", "zes")


def _singularise(token: str) -> str:
    """Plural -> singular only. Anything containing a digit is left alone so
    order references and quantities survive intact."""
    if any(character.isdigit() for character in token):
        return token
    if len(token) < 4 or not token.endswith("s"):
        return token
    if token.endswith("ies") and len(token) >= 5:
        return token[:-3] + "y"
    if token.endswith(_ES_PLURAL_ENDINGS) and len(token) >= 6:
        return token[:-2]
    if token.endswith(_NOT_PLURAL_ENDINGS):
        return token
    return token[:-1]


def normalise(raw: str) -> str:
    """Lowercase, strip accents, reduce every other character to a space.

    Accent folding is what lets "café" and "cafe" match; it is applied by
    decomposing to NFKD and dropping the combining marks, which leaves
    non-Latin scripts (Hindi, Kannada) intact rather than mangled -- those
    reach the classifier as-is and are detected as non-Latin upstream.
    """
    decomposed = unicodedata.normalize("NFKD", raw.lower())
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _NON_WORD.sub(" ", without_marks).strip()


def tokenise(raw: str) -> tuple[str, ...]:
    """Normalised text -> the canonical token tuple used for matching."""
    tokens: list[str] = []
    for word in normalise(raw).split():
        for expanded in CONTRACTIONS.get(word, (word,)):
            singular = _singularise(expanded)
            canonical = SYNONYMS.get(singular, SYNONYMS.get(expanded, singular))
            if canonical and canonical not in STOPWORDS:
                tokens.append(canonical)
    return tuple(tokens)


def char_bigrams(raw: str) -> frozenset[str]:
    """Character bigrams over the normalised string, for typo tolerance.

    Token matching alone cannot see that "recieve" and "receive" are the same
    word; a shared-bigram ratio can, which is why the classifier blends the
    two rather than relying on either.
    """
    text = f" {normalise(raw)} "
    return frozenset(text[index : index + 2] for index in range(len(text) - 1))


@dataclass(frozen=True)
class Prepared:
    """One piece of text, ready to be scored.

    Built once per message and once per phrasebook entry at import time, so
    neither tokenisation nor bigram extraction ever repeats inside the
    matching loop.
    """

    raw: str
    normalised: str
    tokens: tuple[str, ...]
    token_set: frozenset[str]
    bigrams: frozenset[str]

    @property
    def is_empty(self) -> bool:
        return not self.token_set


def prepare(raw: str) -> Prepared:
    normalised = normalise(raw)
    tokens = tokenise(raw)
    return Prepared(
        raw=raw,
        normalised=normalised,
        tokens=tokens,
        token_set=frozenset(tokens),
        bigrams=char_bigrams(raw),
    )

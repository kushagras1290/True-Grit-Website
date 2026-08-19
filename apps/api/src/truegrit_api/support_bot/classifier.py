"""Stage 1: message -> intent, with a number attached that means something.

Two tiers, in order.

**Tier A (`patterns.match_rules`)** is rule based. When a rule fires the answer
is asserted, not estimated, and the highest-priority rule wins outright. This
is what keeps a food-safety report out of the delivery-tracking path.

**Tier B (here)** is lexical similarity against `phrasebook.PHRASEBOOK`. No
model, no network call, no embedding: the message is scored against every
canonical phrasing and the best-matching intent wins. That choice is forced by
the runtime -- this API is Cloudflare Python Workers on Pyodide, where
`sentence-transformers` cannot be installed -- but it is also the better fit,
because it runs in the test suite and in local development, which the Workers
AI path never has.

Scoring blends two views of the same pair:

* **IDF-weighted cosine over tokens** carries the meaning. Weighting by inverse
  document frequency *across the phrasebook* is what stops "order" -- which
  appears in dozens of canonical questions -- from dominating "cancel", which
  appears in a handful and is the word that actually decides the intent.
* **Character-bigram Jaccard** carries the spelling. It is the reason
  "recieve", "recive" and "receive" land in the same place without any of them
  being listed.

The blend is weighted toward tokens; bigrams are a tie-breaker and a typo
absorber, and letting them weigh more starts matching unrelated questions that
happen to share common letter pairs.

**Margin matters as much as score.** A message scoring 0.78 against
`return_status` and 0.77 against `refund_status` is not a confident match, it
is a coin toss between two intents whose answers are different. `Classification`
reports the gap so `gate.py` can send that to a clarification instead of
guessing; the raw top score alone would have cleared the threshold.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from truegrit_api.support_bot import intents, patterns
from truegrit_api.support_bot.normalize import Prepared, prepare
from truegrit_api.support_bot.phrasebook import PHRASEBOOK

# Token similarity carries meaning, bigram similarity carries spelling.
_TOKEN_WEIGHT = 0.8
_BIGRAM_WEIGHT = 0.2
# Exponent applied to raw IDF before it is used as a term weight. 1.0 is
# textbook IDF; see `_Bank.__init__` for why that is the wrong choice on a
# phrasebook this small.
_IDF_DAMPING = 0.5
# Split between symmetric similarity (cosine) and "how much of the canonical
# question did the message account for" (coverage).
_COVERAGE_SHARE = 0.5


def _containment(left: frozenset[str], right: frozenset[str]) -> float:
    """Shared fraction of the smaller set (Szymkiewicz-Simpson overlap).

    Used for bigrams rather than Jaccard because the two sides are routinely
    very different lengths: a customer's sentence against a four-word canonical
    question. Jaccard would score that pair low on length alone even when every
    bigram of the shorter one is present.
    """
    smaller = min(len(left), len(right))
    return len(left & right) / smaller if smaller else 0.0


# A message where most letters are outside the Latin script is not something a
# phrasebook written in English can classify. It is routed to a human rather
# than scored, because a low score would be indistinguishable from gibberish.
_NON_LATIN_RATIO = 0.4
_MIN_LETTERS_FOR_SCRIPT_CHECK = 4


@dataclass(frozen=True)
class Candidate:
    intent: str
    score: float
    matched_question: str


@dataclass(frozen=True)
class Classification:
    intent: str
    confidence: float
    # "rule" (Tier A), "lexical" (Tier B), or "guard" for the structural
    # short-circuits (empty input, non-Latin script) that precede both.
    tier: str
    slots: dict[str, Any] = field(default_factory=dict)
    # Runner-up intents, best first, for the clarification template and for the
    # escalation record -- a human picking up a handed-over conversation can
    # see what the bot thought it might have been.
    alternatives: tuple[Candidate, ...] = ()
    # Gap between the winning score and the best score belonging to a different
    # intent. 1.0 when there is no competing intent at all.
    margin: float = 1.0
    # Why a rule fired, kept for operator debugging of a misroute.
    matched_on: str = ""


class _Bank:
    """The scored phrasebook, built once at import.

    Everything here is derived from static data, so it is computed at module
    load rather than per request: the token/bigram sets, the IDF table, and the
    inverted index. On Workers that cost lands in the isolate's cold start, and
    every subsequent message reuses it.
    """

    def __init__(self, phrasebook: dict[str, tuple[str, ...]]) -> None:
        self.intents: list[str] = []
        self.questions: list[str] = []
        self.prepared: list[Prepared] = []
        for intent_key, questions in phrasebook.items():
            for question in questions:
                self.intents.append(intent_key)
                self.questions.append(question)
                self.prepared.append(prepare(question))

        total = len(self.prepared) or 1
        document_frequency: dict[str, int] = {}
        for entry in self.prepared:
            for token in entry.token_set:
                document_frequency[token] = document_frequency.get(token, 0) + 1
        # Smoothed IDF, floored at 1.0 so a token shared by every question
        # still contributes a little rather than dropping out entirely, then
        # damped by `_IDF_DAMPING`.
        #
        # The damping matters more than it looks. Raw IDF spans roughly 1 to 7
        # across this phrasebook, and cosine squares those weights, so a single
        # rare word present on one side and absent on the other can swamp four
        # words the two share. That produced a scale where correct and
        # incorrect matches overlapped almost completely. The square root
        # compresses the range without losing the ordering, which is the part
        # that actually does the work.
        self.idf: dict[str, float] = {
            token: (math.log((total + 1) / (count + 1)) + 1.0) ** _IDF_DAMPING
            for token, count in document_frequency.items()
        }
        # An unseen token is maximally informative: a query full of vocabulary
        # the phrasebook has never seen should score low against all of it,
        # which is what pushes genuinely novel questions toward a human.
        self.unseen_idf: float = (math.log(total + 1) + 1.0) ** _IDF_DAMPING

        self.norms: list[float] = [self._norm(entry.token_set) for entry in self.prepared]
        # token -> indices of the questions containing it, so a message is only
        # scored against phrasings it shares at least one word with.
        self.index: dict[str, list[int]] = {}
        for position, entry in enumerate(self.prepared):
            for token in entry.token_set:
                self.index.setdefault(token, []).append(position)

    def weight(self, token: str) -> float:
        return self.idf.get(token, self.unseen_idf)

    def _norm(self, tokens: frozenset[str]) -> float:
        return math.sqrt(sum(self.weight(token) ** 2 for token in tokens)) or 1.0

    def candidates(self, tokens: frozenset[str]) -> list[int]:
        seen: set[int] = set()
        for token in tokens:
            seen.update(self.index.get(token, ()))
        return sorted(seen)

    def score(self, query: Prepared, query_norm: float, position: int) -> float:
        entry = self.prepared[position]
        shared = query.token_set & entry.token_set
        if not shared:
            return _BIGRAM_WEIGHT * _containment(query.bigrams, entry.bigrams)

        overlap = sum(self.weight(token) ** 2 for token in shared)
        cosine = overlap / (query_norm * self.norms[position])
        # How much of the *canonical question* the message accounts for.
        # Cosine alone punishes a message for carrying words the phrasebook has
        # never seen, which is precisely what a product name is: "do you have
        # organic turmeric in stock" is a perfect match for "is this product in
        # stock" plus two words no canonical question could ever contain.
        # Coverage ignores the extra words; cosine still stops a message from
        # matching on one shared word alone.
        coverage = overlap / (self.norms[position] ** 2)
        # A one-word canonical question ("help", "hi") has nothing to cover, so
        # coverage would read 1.0 for any message containing that word. Those
        # fall back to cosine, and are rule-anchored in `patterns.py` anyway.
        token_score = (
            (1.0 - _COVERAGE_SHARE) * cosine + _COVERAGE_SHARE * coverage
            if len(entry.token_set) >= 2
            else cosine
        )
        # Containment rather than Jaccard: a long message and a short canonical
        # question share few bigrams *proportionally* however well they match,
        # and penalising that is the same length bias coverage just removed.
        return _TOKEN_WEIGHT * min(token_score, 1.0) + _BIGRAM_WEIGHT * _containment(
            query.bigrams, entry.bigrams
        )


BANK = _Bank(PHRASEBOOK)


def _non_latin_ratio(text: str) -> float:
    letters = [character for character in text if character.isalpha()]
    if len(letters) < _MIN_LETTERS_FOR_SCRIPT_CHECK:
        return 0.0
    non_latin = sum(1 for character in letters if "LATIN" not in unicodedata.name(character, ""))
    return non_latin / len(letters)


def rank(prepared: Prepared, *, limit: int = 4) -> tuple[Candidate, ...]:
    """Best candidate per intent, highest first.

    Scores every phrasing that shares a token with the message, then keeps only
    each intent's best -- an intent with fifteen phrasings must not outrank one
    with five just by appearing more often in the results.
    """
    if prepared.is_empty:
        return ()
    query_norm = BANK._norm(prepared.token_set)
    positions = BANK.candidates(prepared.token_set)
    if not positions:
        # No shared vocabulary at all. Scoring the whole bank on bigrams alone
        # is the last chance to recover a badly misspelt but real question.
        positions = list(range(len(BANK.prepared)))

    best_per_intent: dict[str, Candidate] = {}
    for position in positions:
        score = BANK.score(prepared, query_norm, position)
        intent_key = BANK.intents[position]
        current = best_per_intent.get(intent_key)
        if current is None or score > current.score:
            best_per_intent[intent_key] = Candidate(
                intent=intent_key, score=score, matched_question=BANK.questions[position]
            )
    ordered = sorted(best_per_intent.values(), key=lambda item: (-item.score, item.intent))
    return tuple(ordered[:limit])


def classify(raw: str) -> Classification:
    """Message -> intent, confidence, and the slots the resolvers will need."""
    prepared = prepare(raw)

    # Script check first, and the order is load-bearing. `normalise` reduces
    # everything outside `[a-z0-9]` to spaces, so a message written entirely in
    # Devanagari or Kannada tokenises to nothing and is indistinguishable from
    # an empty one by the time `is_empty` sees it. Checked the other way round,
    # a Hindi-speaking customer was told "I did not catch that" instead of
    # being passed to someone who can read it.
    if _non_latin_ratio(raw) >= _NON_LATIN_RATIO:
        return Classification(intent=intents.NON_LATIN, confidence=1.0, tier="guard")

    if prepared.is_empty:
        return Classification(intent=intents.EMPTY_INPUT, confidence=1.0, tier="guard")

    slots = patterns.extract_slots(raw, prepared)
    rule = patterns.match_rules(prepared)
    ranked = rank(prepared)

    # A rule at or above the handoff band is an assertion about safety or
    # intent to leave the bot. Nothing Tier B computes may override it.
    if rule is not None and rule.priority >= int(patterns.Priority.HANDOFF):
        return Classification(
            intent=rule.intent,
            confidence=rule.confidence,
            tier="rule",
            slots=slots,
            alternatives=ranked,
            matched_on=rule.pattern,
        )

    if rule is not None:
        # A lower-band rule still wins the routing, but if Tier B independently
        # agrees the match is stronger than either signal alone.
        agreeing = next((item for item in ranked if item.intent == rule.intent), None)
        confidence = max(rule.confidence, agreeing.score) if agreeing else rule.confidence
        competing = next((item for item in ranked if item.intent != rule.intent), None)
        return Classification(
            intent=rule.intent,
            confidence=min(confidence, 1.0),
            tier="rule",
            slots=slots,
            alternatives=ranked,
            margin=confidence - competing.score if competing else 1.0,
            matched_on=rule.pattern,
        )

    # An order reference and no rule saying what to do with it. Quoting a
    # reference is only ever a question about that order, and the alternative
    # is scoring "can you check TG-40028122 for me" against a phrasebook that
    # has never seen a reference number and cannot say anything useful about
    # one. No rule fired above, so nothing more specific is being overridden.
    if "order_reference" in slots:
        return Classification(
            intent="order_status",
            confidence=1.0,
            tier="rule",
            slots=slots,
            alternatives=ranked,
            matched_on="order_reference_present",
        )

    if not ranked:
        return Classification(intent=intents.UNKNOWN, confidence=0.0, tier="lexical", slots=slots)

    top = ranked[0]
    runner_up = next((item for item in ranked[1:] if item.intent != top.intent), None)
    return Classification(
        intent=top.intent,
        confidence=top.score,
        tier="lexical",
        slots=slots,
        alternatives=ranked,
        margin=top.score - runner_up.score if runner_up else 1.0,
        matched_on=top.matched_question,
    )

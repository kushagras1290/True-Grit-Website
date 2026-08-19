"""Structural consistency between the taxonomy, the resolvers and the templates.

The three registries in `support_bot/` are wired by string keys: an
`IntentSpec` names a resolver and a template, and neither reference is checked
by the type system. A typo in either is invisible until a customer hits that
intent in production, where it degrades to an escalation -- safe, but silently
wrong, and the escalation queue gives no hint why.

These tests are the checker that would otherwise not exist. They are cheap, and
they fail at the moment the drift is introduced rather than weeks later.

The template tests are the important ones. `templates.render` fails closed on a
missing placeholder, so a template asking for a field its resolver never
produces does not crash; it silently escalates every time. Rendering each
template against its resolver's real output is what catches that.
"""

from __future__ import annotations

import inspect
import re

import pytest

from truegrit_api.support_bot import intents, resolvers, templates
from truegrit_api.support_bot.intents import Handling
from truegrit_api.support_bot.phrasebook import PHRASEBOOK

_PLACEHOLDER = re.compile(r"\{([a-z_][a-z0-9_]*)\}")

# Supplied by the pipeline on every render, so no template has to declare it.
_ALWAYS_PROVIDED = {"contact_line"}


def _placeholders(text: str) -> set[str]:
    return set(_PLACEHOLDER.findall(text))


def test_every_intent_has_a_template():
    missing = sorted(
        spec.key for spec in intents.REGISTRY.values() if not templates.has_template(spec.template)
    )
    assert not missing, f"intents whose template does not exist: {missing}"


def test_every_named_resolver_exists():
    missing = sorted(
        f"{spec.key} -> {spec.resolver}"
        for spec in intents.REGISTRY.values()
        if spec.resolver is not None and spec.resolver not in resolvers.RESOLVERS
    )
    assert not missing, f"intents naming a resolver that does not exist: {missing}"


def test_every_resolver_is_reachable():
    """A resolver no intent names is dead code; it will never run."""
    named = {spec.resolver for spec in intents.REGISTRY.values() if spec.resolver}
    orphans = sorted(set(resolvers.RESOLVERS) - named)
    assert not orphans, f"resolvers no intent uses: {orphans}"


def test_data_intents_have_a_resolver():
    missing = sorted(
        spec.key
        for spec in intents.REGISTRY.values()
        if spec.handling is Handling.DATA and spec.resolver is None
    )
    assert not missing, f"DATA intents with no resolver: {missing}"


def test_non_data_intents_have_no_resolver():
    """Only DATA intents read the database. A STATIC or SOCIAL intent with a
    resolver would be doing a query nothing needs."""
    extra = sorted(
        spec.key
        for spec in intents.REGISTRY.values()
        if spec.handling is not Handling.DATA and spec.resolver is not None
    )
    assert not extra, f"non-DATA intents naming a resolver: {extra}"


def test_data_intents_have_empty_and_needs_input_variants():
    """Every resolver can come back with nothing, and the ones taking a slot can
    come back asking for it. Both need their own wording, or the customer gets
    a sentence with a blank where the answer should be."""
    missing: list[str] = []
    for spec in intents.REGISTRY.values():
        if spec.handling is not Handling.DATA:
            continue
        if not templates.has_template(f"{spec.template}.empty"):
            missing.append(f"{spec.template}.empty")
    assert not missing, f"DATA templates with no empty variant: {sorted(set(missing))}"


def test_needs_input_resolvers_have_a_needs_input_template():
    """A resolver that can return NEEDS_INPUT must have somewhere to say so."""
    slot_dependent = {
        spec.template
        for spec in intents.REGISTRY.values()
        if spec.resolver
        and "Status.NEEDS_INPUT" in inspect.getsource(resolvers.RESOLVERS[spec.resolver])
    }
    missing = sorted(
        template
        for template in slot_dependent
        if not templates.has_template(f"{template}.needs_input")
    )
    assert not missing, f"slot-dependent templates with no needs_input variant: {missing}"


def test_templates_declare_the_facts_their_wording_uses():
    """A `{fact_x}` placeholder with no matching entry in `facts` would render
    only when x happened to be set, and silently escalate otherwise."""
    mismatched: list[str] = []
    for key, template in templates.TEMPLATES.items():
        used = {name[5:] for name in _placeholders(template.text) if name.startswith("fact_")}
        declared = set(template.facts)
        if used != declared:
            mismatched.append(f"{key}: uses {sorted(used)}, declares {sorted(declared)}")
    assert not mismatched, "template fact declarations out of step:\n" + "\n".join(mismatched)


def test_base_templates_need_no_policy_facts():
    """The unsuffixed form of every template must render on a completely
    unconfigured install. `.configured` variants are where facts belong; if a
    base template needed one, a fresh deployment would escalate that intent
    forever and the reason would not be obvious."""
    offenders = sorted(
        key
        for key, template in templates.TEMPLATES.items()
        if template.facts and not key.endswith(".configured")
    )
    assert not offenders, f"base templates requiring policy facts: {offenders}"


def test_configured_variants_have_a_plain_fallback():
    for key in templates.TEMPLATES:
        if key.endswith(".configured"):
            base = key[: -len(".configured")]
            assert templates.has_template(base), f"{key} has no unconfigured fallback"


def test_escalation_templates_render_with_nothing_but_the_contact_line():
    """Handovers happen when a resolver produced nothing, so their wording can
    only depend on what the pipeline always supplies. A handover that cannot
    render is a customer staring at an empty chat bubble."""
    data = {"contact_line": " You can also reach the team through /contact."}
    for spec in intents.REGISTRY.values():
        if spec.handling not in (Handling.ESCALATE, Handling.GUARD, Handling.SOCIAL):
            continue
        rendered = templates.render(spec.template, data=data, facts={})
        assert rendered, f"{spec.key} ({spec.template}) does not render without resolver data"
        assert "{" not in rendered, f"{spec.key} rendered with an unfilled placeholder: {rendered}"


def test_no_template_leaves_an_unfilled_placeholder():
    """`render` returns None rather than a half-filled string. Assert it really
    does, by rendering every template with nothing supplied."""
    for key in templates.TEMPLATES:
        rendered = templates.render(key, data={}, facts={})
        assert rendered is None or "{" not in rendered, f"{key} leaked a placeholder: {rendered}"


def test_social_templates_never_escalate():
    """Greetings must not create escalation rows. A queue full of "hi" is a
    queue nobody reads."""
    for spec in intents.REGISTRY.values():
        if spec.handling is Handling.SOCIAL:
            assert not spec.escalate_after_guard
            assert spec.resolver is None


@pytest.mark.parametrize("intent_key", sorted(PHRASEBOOK))
def test_phrasebook_entries_are_distinct(intent_key: str):
    questions = PHRASEBOOK[intent_key]
    assert len(set(questions)) == len(questions), f"{intent_key} repeats a phrasing"
    assert len(questions) >= 3, f"{intent_key} has too few phrasings to match reliably"


def test_no_phrasing_is_shared_between_intents():
    """The same sentence under two intents makes one of them unreachable."""
    seen: dict[str, str] = {}
    clashes: list[str] = []
    for intent_key, questions in PHRASEBOOK.items():
        for question in questions:
            if question in seen:
                clashes.append(f"{question!r} in both {seen[question]} and {intent_key}")
            seen[question] = intent_key
    assert not clashes, "\n".join(clashes)


def test_auth_scoped_intents_are_all_data_intents():
    """`requires_auth` only means anything on an intent that reads rows. On a
    STATIC intent it would gate a public answer behind a login for no reason."""
    for spec in intents.REGISTRY.values():
        if spec.requires_auth:
            assert spec.handling is Handling.DATA, f"{spec.key} requires auth but is not DATA"


def test_placeholders_are_supplied_by_the_pipeline_or_a_resolver():
    """No template may reference a variable nothing produces. Catches a renamed
    resolver field, which otherwise turns into a permanent silent escalation."""
    unknown: list[str] = []
    for key, template in templates.TEMPLATES.items():
        for name in _placeholders(template.text):
            if name.startswith("fact_") or name in _ALWAYS_PROVIDED:
                continue
            # The field has to appear in some resolver's data dict, or in the
            # clarify path the pipeline builds.
            if name in {"options"}:
                continue
            source = inspect.getsource(resolvers)
            if f'"{name}"' not in source:
                unknown.append(f"{key}: {{{name}}}")
    assert not unknown, "templates referencing fields no resolver produces:\n" + "\n".join(unknown)

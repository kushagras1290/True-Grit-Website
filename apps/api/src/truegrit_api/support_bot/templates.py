"""Stage 3: fixed templates, filled from resolver output.

Nothing is generated here. `render` performs string substitution over a fixed
sentence and returns `None` if it cannot fill every slot, which is the
mechanism that makes hallucination structurally impossible rather than merely
unlikely: there is no code path from a message to a reply that does not pass
through a literal string in this file.

**Variants.** A template key may have suffixed forms that `render` prefers when
they apply:

* ``{key}.empty`` -- the resolver ran and found nothing.
* ``{key}.needs_input`` -- the resolver was not given enough to look anything up.
* ``{key}.configured`` -- a richer sentence that needs a policy fact. Used only
  when every fact it names has a non-blank value in `support_bot_policy_facts`.

That last one is the whole reason policy facts seed blank. Out of the box the
bot says "the return window is shown on your order page, full policy at
/returns", which is true of any configuration. Once an owner sets
`return_window_days` it says the number instead. It never says a number nobody
entered.

**Failure is silent and safe.** A missing placeholder raises `KeyError` inside
`format_map`, `render` catches it and returns `None`, and `pipeline.py` turns
that into an escalation. A reply containing a literal `{reference}` can
therefore never reach a customer.

Wording follows the storefront's own voice: plain sentences, no dashes standing
in for connectives, and a path the customer can click on every answer that has
one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Template:
    text: str
    # Policy-fact keys this wording depends on. Every one must resolve to a
    # non-blank value or the template is skipped.
    facts: tuple[str, ...] = ()


def _t(text: str, *facts: str) -> Template:
    return Template(text=text, facts=facts)


TEMPLATES: dict[str, Template] = {
    # ------------------------------------------------------------------ orders
    "order_status": _t(
        "Order {reference} is {order_status} and the delivery is"
        " {delivery_status}.{tracking} You can see the full detail at {path}."
    ),
    "order_status.empty": _t(
        "I could not find that order on your account. Check the reference on your"
        " confirmation email, or see everything you have ordered at /account."
    ),
    "order_list": _t(
        "Here are your {count} most recent orders:\n{orders}\n\nFull history: /account."
    ),
    "order_list.empty": _t(
        "There are no orders on your account yet. Once you place one it will show up at /account."
    ),
    "order_items": _t("Order {reference} contains:\n{items}\n\nFull detail: {path}."),
    "order_items.empty": _t(
        "I could not find the items for that order. You can see all your orders at /account."
    ),
    "order_invoice": _t("The receipt for order {reference} is at {path}."),
    "order_invoice.empty": _t(
        "I could not find an order to invoice on your account. Your orders are at /account."
    ),
    "order_cancel": _t(
        "Whether an order can still be cancelled depends on how far along it is, so I am"
        " passing this to the team to check and action for you.{contact_line}"
    ),
    "order_change_address": _t(
        "Changing a delivery address after an order is placed has to be done by a person,"
        " so I have passed this to the team.{contact_line}"
    ),
    "order_problem": _t(
        "I am sorry about that. Something went wrong with the order itself, so I have"
        " passed this to the team with what you have told me and they will sort it"
        " out.{contact_line}"
    ),
    # ----------------------------------------------------------------- returns
    "return_policy": _t(
        "Returns are accepted within the window shown on your order page, and the full"
        " policy including what can and cannot be returned is at /returns."
    ),
    "return_policy.configured": _t(
        "Returns are accepted within {fact_return_window_days} days of delivery. The full"
        " policy including what can and cannot be returned is at /returns.",
        "return_window_days",
    ),
    "return_start": _t(
        "Open the order at /account, then use the return option on the order detail page."
        " The team reviews the request and tells you what to do next."
    ),
    "return_status": _t("Here is where your returns stand:\n{returns}\n\nFull detail: /account."),
    "return_status.empty": _t(
        "There are no return requests on your account. You can start one from the order"
        " detail page at /account."
    ),
    "refund_status": _t("Here is what I can see on your refunds:\n{refunds}"),
    "refund_status.empty": _t(
        "I cannot see an approved refund on your account yet. If you have raised a return,"
        " its status is on the order page at /account."
    ),
    "refund_timing": _t(
        "Once a return is approved the refund goes back to your original payment method."
        " The exact timing is on the returns policy at /returns."
    ),
    "refund_timing.configured": _t(
        "Once a return is approved the refund goes back to your original payment method,"
        " usually within {fact_refund_processing_days} working days. Full policy: /returns.",
        "refund_processing_days",
    ),
    "exchange_request": _t(
        "Exchanges are handled as part of a return. Start one from the order detail page at"
        " /account and say what you would like instead, and the team will take it from there."
    ),
    # ---------------------------------------------------------------- payments
    "payment_methods": _t(
        "The payment methods available to you are shown at checkout and depend on your"
        " order and location. Cards, UPI and net banking are supported where enabled."
    ),
    "payment_failed": _t(
        "A failed payment usually means the bank declined it, and no money leaves your"
        " account when that happens. Try again at /cart, or use a different method at"
        " checkout. If money did leave your account, tell me and I will get a person onto it."
    ),
    "payment_dispute": _t(
        "That is a money problem and I am not going to guess at it. I have passed this"
        " straight to the team as a priority with the detail you gave me.{contact_line}"
    ),
    "cod_availability": _t(
        "Whether cash on delivery is available depends on your order and address, and the"
        " options you have are shown at checkout before you pay."
    ),
    "cod_availability.configured": _t(
        "Cash on delivery: {fact_cod_available}. The exact options for your order are"
        " shown at checkout before you pay.",
        "cod_available",
    ),
    # --------------------------------------------------------------- catalogue
    "product_availability": _t("{name} is {stock_state}.{price_sentence} See it at {path}."),
    "product_availability.empty": _t(
        'I could not find anything matching "{query}" in the catalogue. Try browsing'
        " /shop, or search from the top of any page."
    ),
    "product_availability.needs_input": _t(
        "Which product did you mean? Tell me the name and I will check it."
    ),
    "product_price": _t("{name}:\n{prices}\n\nFull detail: {path}."),
    "product_price.empty": _t(
        'I could not find a current price for "{query}". The product page has the live'
        " figure: {path}."
    ),
    "product_price.needs_input": _t(
        "Which product would you like the price for? Give me the name and I will look it up."
    ),
    "product_restock": _t(
        "{name} is {stock_state}.{price_sentence} The product page at {path} always shows"
        " the live position, and it is the fastest way to catch a restock."
    ),
    "product_restock.empty": _t(
        'I could not find "{query}" in the catalogue to check. Browse what is available'
        " now at /shop."
    ),
    "product_restock.needs_input": _t(
        "Which product are you waiting on? Tell me the name and I will check where it stands."
    ),
    "product_storage": _t("{name}: {guidance}\n\nMore about it at {path}."),
    "product_storage.empty": _t(
        'I do not have storage guidance recorded for "{query}". The product page may have'
        " more: {path}."
    ),
    "product_storage.needs_input": _t(
        "Which product are you storing? Tell me the name and I will check what we recommend."
    ),
    "product_sourcing": _t(
        "{name} comes from {farm}{region}.{method} You can read about the farm at {path}."
    ),
    "product_sourcing.empty": _t(
        'I do not have a farm recorded against "{query}". The product page may say more: {path}.'
    ),
    "product_sourcing.needs_input": _t(
        "Which product would you like the origin of? Give me the name and I will look it up."
    ),
    "product_certification": _t(
        "{name} carries:\n{certifications}\n\nDetail on the product page: {path}."
    ),
    "product_certification.empty": _t(
        'I do not have approved certifications recorded for "{query}". Our sourcing'
        " standards are at /standards, and the product page is {path}."
    ),
    "product_certification.needs_input": _t("Which product did you want the certifications for?"),
    "category_browse": _t("Here is what we sell:\n{categories}\n\nEverything is at /shop."),
    "category_browse.empty": _t("Browse the full catalogue at /shop."),
    "bundle_info": _t("Current bundles:\n{bundles}\n\nAll of them: /bundles."),
    "bundle_info.empty": _t(
        "There are no bundles running at the moment. The catalogue is at /shop."
    ),
    # ---------------------------------------------------------------- delivery
    "delivery_areas": _t("Yes, {postal_code} is in our {zone} delivery zone.{lead_sentence}"),
    "delivery_areas.empty": _t(
        "{postal_code} is not in a delivery zone I can see. Checkout is the authority on"
        " this, so it is worth trying your address there, and the delivery page is /delivery."
    ),
    "delivery_areas.needs_input": _t(
        "Tell me your PIN code and I will check whether we deliver there."
    ),
    "delivery_charges": _t(
        "Any delivery fee for your order is calculated from your address and shown at"
        " checkout before you pay. The delivery page has the detail: /delivery."
    ),
    "delivery_charges.configured": _t(
        "Delivery is {fact_delivery_fee}, and free above {fact_free_delivery_threshold}."
        " Your exact figure is shown at checkout. Full detail: /delivery.",
        "delivery_fee",
        "free_delivery_threshold",
    ),
    "delivery_time": _t(
        "Delivery timing depends on your address and what you ordered, and the estimate for"
        " your basket is shown at checkout. The delivery page has the detail: /delivery."
    ),
    "delivery_time.configured": _t(
        "Orders usually arrive within {fact_standard_delivery_days} days, and the estimate"
        " for your basket is shown at checkout. Full detail: /delivery.",
        "standard_delivery_days",
    ),
    "delivery_slots": _t(
        "Where slot booking is available for your address you can choose one at checkout."
        " The delivery page explains how it works: /delivery."
    ),
    "pickup_points": _t("You can collect from:\n{points}\n\nPick one at checkout."),
    "pickup_points.empty": _t(
        "There are no collection points available at the moment, so orders come to your"
        " address. Detail: /delivery."
    ),
    "international_shipping": _t(
        "Where we can deliver is decided by your address at checkout, and the delivery page"
        " has the detail: /delivery."
    ),
    "international_shipping.configured": _t(
        "International delivery: {fact_international_shipping}. Full detail: /delivery.",
        "international_shipping",
    ),
    # ----------------------------------------------------------------- account
    "account_signin_problem": _t(
        "Try resetting your password at /reset-password, which fixes most sign-in problems."
        " If you signed up with Google or with your mobile number, use that same method"
        " again rather than a password."
    ),
    "account_password_reset": _t("Reset it at /reset-password and the link comes to your email."),
    "account_otp_not_received": _t(
        "Codes can take a minute. Check the number is right, look in your spam folder if it"
        " was emailed, then request a new one. If it still does not arrive, tell me and I"
        " will get a person to help."
    ),
    "account_delete": _t(
        "Account deletion is handled by a person so it is done properly and completely."
        " I have passed your request to the team.{contact_line}"
    ),
    "account_change_contact": _t("You can update your email and mobile number at /account."),
    "account_addresses": _t("Your saved delivery addresses are at /account."),
    "account_unsubscribe": _t(
        "Every marketing email has an unsubscribe link at the bottom, and using it stops"
        " them immediately. Order and delivery emails are separate and keep coming so you"
        " still hear about your purchases."
    ),
    "account_register": _t(
        "You can create an account from the sign-in page with an email address, a Google"
        " account, or a verified mobile number. An account keeps your orders and addresses"
        " in one place at /account."
    ),
    # ---------------------------------------------------------------- programs
    "loyalty_points": _t("You have {points} points. You can put them toward an order at checkout."),
    "loyalty_points.empty": _t(
        "I cannot see a loyalty account for you yet. Your account page is /account."
    ),
    "referral_program": _t(
        "Your referral code is {code}. Share it and your friend gets a discount on their"
        " first order. Detail is on your account page at /account."
    ),
    "referral_program.empty": _t(
        "I cannot see a referral code on your account yet. Check /account for the current"
        " programme."
    ),
    "giftcard_balance": _t("Gift card {code} has {balance} left.{expiry_sentence}"),
    "giftcard_balance.empty": _t(
        "I could not find an active gift card with the code {code}. Check the code and try"
        " again, and if it should be working tell me and I will get a person to look."
    ),
    "giftcard_balance.needs_input": _t(
        "Tell me the gift card code and I will check the balance on it."
    ),
    "giftcard_buy": _t(
        "Gift cards are redeemed by entering the code at checkout, where the balance comes"
        " off your total. Browse what you can spend one on at /shop."
    ),
    "discount_available": _t(
        "Running at the moment:\n{promotions}\n\nAll of it applies at checkout."
    ),
    "discount_available.empty": _t(
        "There are no promotions running right now. Seasonal picks are at /seasonal."
    ),
    "discount_not_working": _t(
        "A code usually fails because it has expired, because the basket does not meet its"
        " conditions, or because another discount is already applied. Check those at /cart."
        " If it still will not go through, tell me and I will get a person to look at it."
    ),
    "subscription_status": _t("Your subscriptions:\n{subscriptions}\n\nManage them at /account."),
    "subscription_status.empty": _t(
        "You have no active subscriptions. Look for Subscribe and Save on a product page to"
        " set one up."
    ),
    "subscription_manage": _t(
        "Pause, skip, change the frequency, or cancel a subscription from /account. Changes"
        " apply from the next delivery onward."
    ),
    "preorder_harvest": _t("Coming up:\n{harvests}\n\nPreorder from the product page."),
    "preorder_harvest.empty": _t(
        "There are no harvest windows open for preorder right now. What is available today"
        " is at /shop."
    ),
    "bulk_b2b": _t(
        "We do supply businesses and bulk orders. Send the quantities and how often you"
        " need them through /contact and the team will come back with pricing."
    ),
    # ----------------------------------------------------------------- content
    "recipe_lookup": _t("Recipes you might like:\n{recipes}\n\nAll of them: /recipes."),
    "recipe_lookup.empty": _t("I could not find a recipe for that. Browse them all at /recipes."),
    "article_lookup": _t("From the blog:\n{articles}\n\nEverything: /blog."),
    "article_lookup.empty": _t("I could not find a post on that. The full blog is at /blog."),
    "review_how_to": _t(
        "You can review anything you have bought from the order detail page at /account."
        " Reviews are checked before they appear, so there is a short delay. Published"
        " reviews are at /reviews."
    ),
    "wishlist_how_to": _t(
        "Use the save option on any product page and it goes to your wishlist, which lives"
        " on your account page at /account."
    ),
    "community_discussions": _t("From the community:\n{discussions}\n\nAll threads: /community."),
    "community_discussions.empty": _t(
        "I could not find a thread on that. The community is at /community and you can start"
        " one yourself."
    ),
    # ----------------------------------------------------------------- company
    "about_company": _t(
        "True Grit sells produce direct from the farms that grow it. The story is at /about,"
        " and how we choose and check those farms is at /standards."
    ),
    "farm_partnership": _t(
        "We do take on new partner farms. Apply at /farms/partner and the team reviews every"
        " application."
    ),
    "careers": _t(
        "Send what you are looking for and your CV through /contact and it reaches the right"
        " people."
    ),
    "press_media": _t(
        "I have passed your enquiry to the team so the right person comes back to"
        " you.{contact_line}"
    ),
    "contact_details": _t("You can reach the team through /contact.{contact_line}"),
    "privacy_policy": _t("The privacy policy, including what we keep and why, is at /privacy."),
    "terms_conditions": _t("The terms and conditions are at /terms."),
    "sourcing_standards": _t(
        "How farms are chosen, what is checked, and what we require of them is at /standards."
    ),
    # ------------------------------------------------------------------ social
    "greeting": _t(
        "Hello. I can help with orders, delivery, returns, and anything in the catalogue."
        " What do you need?"
    ),
    "farewell": _t("Thanks for stopping by. Come back any time."),
    "thanks": _t("Glad that helped. Anything else?"),
    "affirm": _t("Tell me a bit more and I will pick it up from there."),
    "deny": _t("No problem. Ask me anything else whenever you need to."),
    "bot_identity": _t(
        "I am an automated assistant. I answer from what is actually recorded against your"
        " account and the catalogue, and anything I cannot answer that way goes to a person."
    ),
    "capabilities": _t(
        "I can check an order, delivery, and returns, look up products, prices, stock and"
        " where they came from, and explain how returns, delivery and payment work."
        " Anything I am not sure about I hand to a person rather than guess."
    ),
    # ------------------------------------------------------- handoff and guard
    "human_handoff": _t(
        "Of course. I have passed this conversation to the team so a person can pick it"
        " up.{contact_line}"
    ),
    "complaint": _t(
        "I am sorry, that is not the experience you should have had. I have passed this to"
        " the team so a person deals with it properly.{contact_line}"
    ),
    "legal_threat": _t(
        "I have passed this to the team so the right person responds to you directly.{contact_line}"
    ),
    "safety_food": _t(
        "I am sorry, and thank you for telling us. Please stop eating the product and keep"
        " it along with its packaging if you can. I have flagged this to the team as urgent"
        " so a person contacts you.{contact_line} If you feel unwell, please speak to a"
        " doctor."
    ),
    "medical_advice": _t(
        "I am not able to give health or dietary advice, and I would not want to get that"
        " wrong. What each product is and where it came from is on its page, and a doctor"
        " or dietitian is the right person for the rest."
    ),
    "pii_request": _t(
        "I can only help with your own account and with public information about the shop,"
        " so I cannot share anyone else's details."
    ),
    "fraud_scam": _t(
        "I cannot act on that. Refunds only ever go back to the original payment method, and"
        " nobody from True Grit will ask you for a code, a password, or a payment to a"
        " personal account. I have flagged this conversation to the team."
    ),
    "off_topic": _t(
        "That one is outside what I can help with. I can answer questions about orders,"
        " delivery, returns, and anything in the catalogue."
    ),
    "abuse": _t(
        "I want to help, but I am not going to continue like this. Tell me what has gone"
        " wrong and I will do what I can, or I can pass you to a person."
    ),
    "prompt_injection": _t(
        "I only answer questions about True Grit orders, delivery, returns, and the"
        " catalogue. What can I help you with?"
    ),
    "empty_input": _t("I did not catch that. What can I help you with?"),
    "non_latin": _t(
        "I can only read English at the moment, so I have passed this to the team and a"
        " person will reply.{contact_line} You can also switch the site language from the"
        " footer."
    ),
    "unknown": _t(
        "I do not want to guess at that one. I have passed it to the team so a person can"
        " answer properly.{contact_line}"
    ),
    # Shown instead of an answer when a customer-scoped question arrives with no
    # session. Not an escalation: signing in is one click and solves it.
    "sign_in": _t(
        "That is on your account, so sign in first and then ask me again and I will look it"
        " up. Sign in at /account."
    ),
    # The mid-confidence band. Offering the two things it might have been is
    # more useful than either guessing or handing straight to a person.
    "clarify": _t("I am not sure which you mean. Did you want:\n{options}\n\nTell me which one."),
}


class _StrictDict(dict):
    """`format_map` backing store that refuses to invent a value.

    `str.format` on a plain dict raises KeyError for a missing key, which is
    what we want, but a `defaultdict` or a `.get`-based mapping would silently
    produce an empty string. Being explicit here keeps the fail-closed
    behaviour from depending on which mapping type a caller passed in.
    """

    def __missing__(self, key: str) -> str:
        raise KeyError(key)


def render(
    key: str,
    *,
    status: str = "ok",
    data: dict[str, Any],
    facts: dict[str, str],
) -> str | None:
    """Fill the best available variant of `key`, or None if it cannot be filled.

    None is not an error condition to paper over: `pipeline.py` treats it as
    "this cannot be answered from a template" and escalates, which is the
    correct outcome for an unconfigured policy or a resolver that returned
    fields the template did not expect.
    """
    candidates: list[str] = []
    if status and status != "ok":
        candidates.append(f"{key}.{status}")
        candidates.append(f"{key}.configured" if status == "ok" else f"{key}.{status}.configured")
    else:
        candidates.append(f"{key}.configured")
    candidates.append(key)

    values = _StrictDict(data)
    values.update({f"fact_{name}": value for name, value in facts.items() if value})

    for candidate in candidates:
        template = TEMPLATES.get(candidate)
        if template is None:
            continue
        if any(not facts.get(name, "").strip() for name in template.facts):
            continue
        try:
            return template.text.format_map(values).strip()
        except (KeyError, IndexError, ValueError):
            # This variant wanted a field the resolver did not produce. Fall
            # through to the plainer one rather than emitting a broken string.
            continue
    return None


def has_template(key: str) -> bool:
    return key in TEMPLATES

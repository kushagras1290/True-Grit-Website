"""Deterministic storefront support bot.

A four-stage pipeline with no language model anywhere in it:

    classify (rules, then lexical similarity)
      -> gate (confident enough? ambiguous? hand over?)
      -> resolve (read the answer out of D1)
      -> render (fill a fixed template)

It replaced a Workers AI tool-calling bot on the storefront. The admin panel's
bot (`services.support_bot`) is a different job -- explaining admin screens to
staff -- and still runs on the model.

Three properties follow from the structure rather than from care:

* **It cannot state something no row contained.** Every reply is a literal
  string in `templates.py` with values substituted from a resolver. A template
  that cannot be filled returns None and the turn is handed to a person.
* **It cannot see another customer's data.** Customer-scoped resolvers put
  `customer_user_id` in the WHERE clause, and the gate runs before any query,
  so a message the bot is unsure about never reaches the database at all.
* **It runs offline.** No binding, no network call, so the whole thing is
  exercised in pytest against the real migrated schema.

`ask` is the entry point. `api/support_bot_public.py` is its only caller.
"""

from __future__ import annotations

from truegrit_api.support_bot.pipeline import SupportBotUnavailableError, ask

__all__ = ["SupportBotUnavailableError", "ask"]

# Inventory intelligence and recommendations

## Overview

Migration `0111_inventory_intelligence_recommendations.sql` adds two classical,
explainable data products over the existing D1 commerce source of truth:

- SKU demand forecasts for inventory planning.
- Product recommendations from market baskets, item similarity and cold-start
  popularity.

No LLM, vector database, Prophet or native ML dependency is required. This is
intentional: the current data volume and the Cloudflare Python Worker runtime
are better served by deterministic SQL and standard-library Python.

## Demand forecasting

`services/demand_forecasting.py` reads non-cancelled order lines for the last
180 days. For every active variant of a published product it computes:

- 7-day and 30-day average units/day.
- A 65/35 short/long moving-average blend once 30 data days exist; younger SKUs
  use the 7-day average.
- Weekday multipliers over the last 84 days, shrunk toward 1.0 and clamped to
  0.5-2.0 so sparse launches cannot create extreme seasonality.
- A 30-day daily forecast with a 95% residual interval.
- Days/projected date until available stock is consumed.
- A reorder flag when stockout falls inside lead time or the configured stock
  threshold is breached.
- A recommended order quantity covering lead time plus safety-stock days.

Lead time defaults to 7 days and safety stock to 2 days per SKU. Operators can
edit both from **Admin > Inventory Intelligence**. The existing inventory table
remains the stock source of truth; forecasts never mutate stock.

The weekly trigger is `30 2 * * 1` (Monday 02:30 UTC). A store-wide operator can
also run it from the admin page or `POST /v1/admin/inventory-intelligence/recompute`.

## Recommendations

`services/recommendations.py` recomputes a 365-day rollup nightly:

1. Unique product baskets are built per non-cancelled order.
2. Each source/target pair receives co-purchase count, confidence, lift and
   cosine similarity over order-incidence vectors.
3. Category match, 30-day popularity and exponentially decayed recency are
   blended with the basket signals.
4. Up to 50 ranked candidates are stored per source product.
5. A separate popularity table supplies cold-start candidates. Shared-category
   products rank ahead of global trends when the source has no basket history.

The public endpoint is
`GET /v1/public/products/{product-id-or-slug}/recommendations`. It returns the
product card data plus run id, score, confidence, lift, cosine similarity and a
reason. Unpublished, geo-hidden, unorderable and out-of-stock products are
removed before response. If no completed run exists yet, the endpoint falls
back to live bestsellers rather than rendering an empty module.

The nightly trigger is `15 2 * * *` (02:15 UTC). An analytics operator can also
run `POST /v1/admin/recommendations/recompute`.

## Attribution and metrics

Recommendation widgets record best-effort impressions, clicks and add-to-cart
events with a per-tab random session id. No email, customer name, address or
raw auth/session token is stored.

The recommendation source, completed run and placement travel through the
product URL and persisted cart. Checkout treats this metadata as untrusted:
source/target/run associations are validated before a
`recommendation_attributions` row is written in the same atomic batch as the
order and order item. Attributed revenue is line revenue after a proportional
allocation of order-level discounts.

The existing Admin Analytics date range now reports:

- impressions and clicks;
- click-through rate;
- add-to-cart events;
- attributed orders and units;
- attributed revenue.

Raw engagement events are retained for 400 days. Order attribution follows the
order lifecycle. Eight completed model runs are retained for rollback/comparison;
failed run diagnostics are kept for 90 days.

## Failure and rollback behavior

Both refresh jobs are run-scoped and immutable. A run starts as `running`,
writes its rows in bounded D1 batches, and becomes visible only after it is
marked `completed`. If a later run fails, storefront/admin readers continue to
use the previous completed run. The failure is logged and stored on the run;
the Cron Trigger invocation also fails so Cloudflare Past Events exposes it.

Rolling back application code does not require rolling back the additive
migration. Older code ignores the new tables and cron expressions can be
removed independently. D1 backups remain the database recovery mechanism.

## Deployment and verification

No new environment variables or secrets are required.

```powershell
python scripts/validate_migrations.py
uv run --project apps/api python -m pytest tests/unit/test_inventory_intelligence.py
corepack pnpm --filter @truegrit/contracts typecheck
corepack pnpm --filter @truegrit/storefront typecheck
corepack pnpm --filter @truegrit/admin typecheck
```

After deploying migration `0111` and the API Worker:

1. Open **Inventory Intelligence** and run the baseline once.
2. Open **Analytics** and rebuild recommendations once, or wait for the nightly
   trigger.
3. Verify a product page recommendation click carries `recPlacement`,
   `recSource` and (when precomputed) `recRun` query parameters.
4. Add that product, check out in a non-production test environment, and verify
   one `recommendation_attributions` row points at the order item.
5. Use Cloudflare Cron Past Events/logs to verify the next scheduled invocations.

Cron expressions are exact UTC strings. When testing locally with Wrangler,
invoke `/cdn-cgi/handler/scheduled?cron=15+2+*+*+*` or the weekly equivalent.

## Known limits and upgrade path

- Forecast intervals are operational uncertainty bands, not calibrated
  probabilistic guarantees.
- Promotions, holidays and stockout-censored demand are not yet modeled.
- Recommendations are item-to-item, not per-user collaborative filtering; this
  avoids sparse personal histories and keeps behavior explainable.
- Move to ARIMA/Prophet only after at least three months of clean demand per
  relevant SKU and measured baseline error justify the added runtime.
- Move to a global gradient-boosted model only when SKU scale and offline
  backtesting demonstrate a material gain.

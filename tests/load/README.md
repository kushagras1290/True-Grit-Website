# Capacity tests

Run these only against the isolated staging resources. The public scenario ramps anonymous browse
traffic and records latency, error rate, and `CF-Cache-Status`. The checkout race is intentionally
mutating and requires two pre-created customer sessions plus a variant seeded with exactly one unit.

```bash
k6 run -e BASE_URL=https://truegrit-api-staging.example.com \
  -e PRODUCT_SLUG=example -e CATEGORY_SLUG=example tests/load/public-browse.js

k6 run -e BASE_URL=https://truegrit-api-staging.example.com -e ENABLE_MUTATIONS=true \
  -e VARIANT_ID=var_example -e CUSTOMER_SESSION_A=... -e CUSTOMER_SESSION_B=... \
  -e CSRF_TOKEN_A=... -e CSRF_TOKEN_B=... tests/load/checkout-race.js
```

Store the JSON output with the commit SHA and workload variables. Stop a run when p95 latency,
unexpected errors, D1 overloads, Worker CPU, queue age, or provider safety limits cross the approved
staging objective. Never provide real payment, email, or SMS credentials to a load-test deployment.

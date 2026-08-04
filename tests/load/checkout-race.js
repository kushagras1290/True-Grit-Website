import http from "k6/http";
import { check, fail } from "k6";

const baseUrl = (__ENV.BASE_URL || "").replace(/\/$/, "");

export const options = {
  scenarios: {
    final_unit_race: {
      executor: "shared-iterations",
      vus: 2,
      iterations: 2,
      maxDuration: "30s",
    },
  },
  thresholds: { checks: ["rate==1"] },
};

export function setup() {
  const required = [
    "BASE_URL",
    "VARIANT_ID",
    "CUSTOMER_SESSION_A",
    "CUSTOMER_SESSION_B",
    "CSRF_TOKEN_A",
    "CSRF_TOKEN_B",
  ];
  for (const key of required) {
    if (!__ENV[key]) fail(`${key} is required.`);
  }
  if (__ENV.ENABLE_MUTATIONS !== "true") {
    fail("Set ENABLE_MUTATIONS=true after seeding exactly one unit in isolated staging.");
  }
  if (/truegrit-api-prod|api\.truegrit/i.test(baseUrl)) {
    fail("The destructive checkout race is staging-only.");
  }
  return { runId: `${Date.now()}` };
}

export default function (data) {
  const index = __VU === 1 ? "A" : "B";
  const payload = JSON.stringify({
    items: [{ variantId: __ENV.VARIANT_ID, quantity: 1 }],
    paymentMethod: "cod",
    idempotencyKey: `k6-final-unit-${data.runId}-${index}`,
    deliveryAddress: {
      recipientName: "Capacity Test",
      line1: "1 Test Lane",
      city: "Bengaluru",
      state: "Karnataka",
      postalCode: "560001",
      countryCode: "IN",
      phone: "+919999999999",
    },
  });
  const response = http.post(`${baseUrl}/v1/public/checkout`, payload, {
    headers: {
      "Content-Type": "application/json",
      Cookie: `tg_session=${__ENV[`CUSTOMER_SESSION_${index}`]}`,
      "X-CSRF-Token": __ENV[`CSRF_TOKEN_${index}`],
    },
    tags: { route_family: "checkout-race" },
  });
  check(response, {
    "exactly one accepted or rejected outcome": (value) => [200, 409, 422].includes(value.status),
  });
}

export function handleSummary(data) {
  const statuses = data.metrics.http_reqs?.values?.count || 0;
  return {
    stdout: `Checkout race completed with ${statuses} requests. Verify one order and zero negative inventory rows.\n`,
  };
}

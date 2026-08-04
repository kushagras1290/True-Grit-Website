import http from "k6/http";
import { check, fail, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const baseUrl = (__ENV.BASE_URL || "").replace(/\/$/, "");
const productSlug = __ENV.PRODUCT_SLUG || "";
const categorySlug = __ENV.CATEGORY_SLUG || "";
const articleSlug = __ENV.ARTICLE_SLUG || "";
const recipeSlug = __ENV.RECIPE_SLUG || "";

const cacheHitRate = new Rate("edge_cache_hit");
const browseLatency = new Trend("browse_latency", true);

export const options = {
  scenarios: {
    anonymous_browse: {
      executor: "ramping-arrival-rate",
      startRate: Number(__ENV.START_RPS || 5),
      timeUnit: "1s",
      preAllocatedVUs: Number(__ENV.PREALLOCATED_VUS || 25),
      maxVUs: Number(__ENV.MAX_VUS || 250),
      stages: [
        { target: Number(__ENV.TARGET_RPS || 25), duration: __ENV.RAMP_DURATION || "1m" },
        { target: Number(__ENV.TARGET_RPS || 25), duration: __ENV.HOLD_DURATION || "3m" },
        { target: 0, duration: "30s" },
      ],
      gracefulStop: "30s",
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
    http_req_failed: ["rate<0.001"],
    http_req_duration: ["p(95)<750", "p(99)<1500"],
    browse_latency: ["p(95)<750"],
  },
};

function requiredConfiguration() {
  if (!baseUrl) {
    fail("BASE_URL is required.");
  }
  const isProduction = /truegrit-api-prod|api\.truegrit/i.test(baseUrl);
  if (isProduction && __ENV.ALLOW_PRODUCTION !== "true") {
    fail("Refusing to load test production. Set ALLOW_PRODUCTION=true only for an approved test.");
  }
}

export function setup() {
  requiredConfiguration();
  return { baseUrl };
}

function routes() {
  const values = ["/v1/public/bootstrap", "/v1/public/home", "/v1/public/products"];
  if (categorySlug) values.push(`/v1/public/categories/${categorySlug}`);
  if (productSlug) values.push(`/v1/public/products/${productSlug}`);
  if (articleSlug) values.push(`/v1/public/articles/${articleSlug}`);
  if (recipeSlug) values.push(`/v1/public/recipes/${recipeSlug}`);
  return values;
}

export default function (data) {
  const availableRoutes = routes();
  const path = availableRoutes[Math.floor(Math.random() * availableRoutes.length)];
  const separator = path.includes("?") ? "&" : "?";
  const response = http.get(`${data.baseUrl}${path}${separator}country=IN&locale=en-IN`, {
    headers: { Accept: "application/json" },
    tags: { route_family: "public-browse" },
  });

  browseLatency.add(response.timings.duration);
  cacheHitRate.add((response.headers["Cf-Cache-Status"] || "").toUpperCase() === "HIT");
  check(response, {
    "public response is successful": (value) => value.status === 200,
    "shared cache policy is present": (value) =>
      (value.headers["Cache-Control"] || "").includes("s-maxage="),
    "response has request correlation": (value) => Boolean(value.headers["X-Request-Id"]),
  });
  sleep(Math.random() * 0.5);
}

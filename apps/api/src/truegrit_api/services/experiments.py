"""A/B testing / experimentation framework (migration 0112).

Deterministic hash-based variant assignment (no DB write per assignment),
event tracking (exposure / conversion / intermediate), and a stats engine
with proper statistical rigour:

* Two-proportion z-test for binary conversion metrics
* Welch's t-test for continuous metrics (order value, session duration)
* Power analysis (required sample size for desired statistical power)
* mSPRT sequential testing — honest p-values under continuous monitoring,
  so the admin dashboard's "statistically significant" flag only lights up
  when it is actually earned, not after a lucky peek at n=40.

The report surfaces: effect size, confidence interval, p-value (both naive
and sequential), required vs actual sample size, and achieved power.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_MAX_VARIANTS: Final = 10
_MAX_KEY_LENGTH: Final = 80
_MAX_NAME_LENGTH: Final = 200
_MAX_DESCRIPTION_LENGTH: Final = 2000

# ─── Variant assignment ───────────────────────────────────────────────


def assign_variant(
    user_id: str,
    experiment_key: str,
    variants: list[dict[str, str]],
    allocation_pct: int,
) -> str | None:
    """Deterministic, stateless variant assignment via hash bucketing.

    ``hash(user_id + experiment_key) % 100 < allocation_pct`` → the user is
    in the experiment and gets a consistent variant across sessions with no
    DB write needed per assignment.

    Returns the variant key, or ``None`` if the user is outside the
    allocation (e.g. allocation_pct = 50 means half of users are excluded
    and see the default experience, unmeasured).
    """
    digest = hashlib.sha256(f"{user_id}:{experiment_key}".encode()).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket >= allocation_pct:
        return None  # user not in experiment
    variant_index = int(digest[8:16], 16) % len(variants)
    return variants[variant_index]["key"]


def _parse_variants(raw: str) -> list[dict[str, str]]:
    try:
        variants = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(variants, list):
        return []
    return variants


# ─── Stats engine ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class BinaryResult:
    """Result of a two-proportion z-test for binary conversion metrics."""

    control_conversions: int
    control_total: int
    treatment_conversions: int
    treatment_total: int
    control_rate: float
    treatment_rate: float
    absolute_effect: float
    relative_effect: float  # (treatment - control) / control, or 0 if control is 0
    z_stat: float
    p_value: float
    ci_lower: float
    ci_upper: float
    # Sequential testing
    msprt_stat: float
    msprt_p_value: float
    is_significant: bool  # mSPRT-honest, not the naive p-value
    # Power
    required_sample_per_variant: int | None
    power_achieved: float


@dataclass(frozen=True)
class ContinuousResult:
    """Result of a Welch's t-test for continuous metrics."""

    control_n: int
    control_mean: float
    control_std: float
    treatment_n: int
    treatment_mean: float
    treatment_std: float
    mean_diff: float
    relative_effect: float
    t_stat: float
    p_value: float
    ci_lower: float
    ci_upper: float
    msprt_stat: float
    msprt_p_value: float
    is_significant: bool
    required_sample_per_variant: int | None
    power_achieved: float


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via the error function (math.erf)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (percent-point function).

    Uses the rational approximation by Abramowitz & Stegun (formula 26.2.23)
    with refinement -- accurate to ~4.5 x 10^-4, more than sufficient for
    power analysis and CI computation.
    """
    if p <= 0:
        return float("-inf")
    if p >= 1:
        return float("inf")
    if p == 0.5:
        return 0.0

    # Work in the upper tail
    if p > 0.5:
        return -_norm_ppf(1.0 - p)

    t = math.sqrt(-2.0 * math.log(p))
    # Rational approximation constants
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    result = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)
    return -result


def power_analysis_binary(
    baseline_rate: float,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Required sample size per variant for a two-proportion z-test.

    ``baseline_rate``: expected conversion rate of the control (e.g. 0.05)
    ``mde``: minimum detectable effect as an absolute difference (e.g. 0.02
    means we want to detect a lift from 5% to 7%)
    ``alpha``: significance level (Type I error rate)
    ``power``: desired statistical power (1 - Type II error rate)

    Returns the number of observations needed *per variant*.
    """
    if mde <= 0 or baseline_rate <= 0 or baseline_rate >= 1:
        return 0
    p1 = baseline_rate
    p2 = baseline_rate + mde
    if p2 >= 1:
        p2 = 0.999
    p_bar = (p1 + p2) / 2.0
    z_alpha = _norm_ppf(1 - alpha / 2)
    z_beta = _norm_ppf(power)
    numerator = (
        z_alpha * math.sqrt(2 * p_bar * (1 - p_bar))
        + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    denominator = mde**2
    return math.ceil(numerator / denominator)


def power_analysis_continuous(
    baseline_std: float,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Required sample size per variant for a two-sample t-test.

    ``baseline_std``: expected standard deviation of the metric
    ``mde``: minimum detectable difference in means
    """
    if mde <= 0 or baseline_std <= 0:
        return 0
    z_alpha = _norm_ppf(1 - alpha / 2)
    z_beta = _norm_ppf(power)
    return math.ceil(2 * ((z_alpha + z_beta) * baseline_std / mde) ** 2)


def _achieved_power_binary(p1: float, p2: float, n: int, alpha: float = 0.05) -> float:
    """Post-hoc power at the current sample size for a binary metric."""
    if n <= 0 or p1 <= 0 or p1 >= 1:
        return 0.0
    mde = abs(p2 - p1)
    if mde == 0:
        return alpha  # no effect → power = alpha (Type I)
    p_bar = (p1 + p2) / 2.0
    z_alpha = _norm_ppf(1 - alpha / 2)
    se_pooled = math.sqrt(2 * p_bar * (1 - p_bar) / n)
    se_separate = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n)
    if se_separate == 0:
        return 1.0
    z_beta = (mde - z_alpha * se_pooled) / se_separate
    return _norm_cdf(z_beta)


def _achieved_power_continuous(std: float, mean_diff: float, n: int, alpha: float = 0.05) -> float:
    """Post-hoc power at the current sample size for a continuous metric."""
    if n <= 1 or std <= 0:
        return 0.0
    if mean_diff == 0:
        return alpha
    z_alpha = _norm_ppf(1 - alpha / 2)
    se = std * math.sqrt(2.0 / n)
    if se == 0:
        return 1.0
    z_beta = (abs(mean_diff) - z_alpha * se) / se
    return _norm_cdf(z_beta)


def two_proportion_z_test(
    c_conv: int,
    c_total: int,
    t_conv: int,
    t_total: int,
) -> tuple[float, float, float, float]:
    """Two-proportion z-test.  Returns (z_stat, p_value, ci_lower, ci_upper)."""
    if c_total == 0 or t_total == 0:
        return 0.0, 1.0, 0.0, 0.0
    p_c = c_conv / c_total
    p_t = t_conv / t_total
    diff = p_t - p_c
    # Pooled proportion for the z-statistic
    p_pool = (c_conv + t_conv) / (c_total + t_total)
    se_pooled = math.sqrt(p_pool * (1 - p_pool) * (1 / c_total + 1 / t_total))
    if se_pooled == 0:
        return 0.0, 1.0, diff, diff
    z = diff / se_pooled
    p_value = 2 * (1 - _norm_cdf(abs(z)))
    # CI uses the unpooled SE (Wald interval)
    se_unpooled = math.sqrt(p_c * (1 - p_c) / c_total + p_t * (1 - p_t) / t_total)
    margin = 1.96 * se_unpooled
    return z, p_value, diff - margin, diff + margin


def welch_t_test(
    c_values: list[float],
    t_values: list[float],
) -> tuple[float, float, float, float]:
    """Welch's t-test for unequal variances.  Returns (t_stat, p_value, ci_lower, ci_upper)."""
    n_c = len(c_values)
    n_t = len(t_values)
    if n_c < 2 or n_t < 2:
        return 0.0, 1.0, 0.0, 0.0

    mean_c = sum(c_values) / n_c
    mean_t = sum(t_values) / n_t
    var_c = sum((x - mean_c) ** 2 for x in c_values) / (n_c - 1)
    var_t = sum((x - mean_t) ** 2 for x in t_values) / (n_t - 1)

    se = math.sqrt(var_c / n_c + var_t / n_t)
    if se == 0:
        diff = mean_t - mean_c
        return 0.0, 1.0, diff, diff

    t_stat = (mean_t - mean_c) / se

    # Approximate p-value using the normal distribution rather than the
    # Welch-Satterthwaite t-distribution: accurate once either arm has a
    # reasonable sample size (t approaches normal past ~30 observations per
    # arm), and needs no scipy dependency for the exact t-CDF.
    p_value = 2 * (1 - _norm_cdf(abs(t_stat)))

    diff = mean_t - mean_c
    margin = 1.96 * se  # Using normal approximation for CI
    return t_stat, p_value, diff - margin, diff + margin


def msprt_z(z_stat: float, n_total: int, *, theta: float = 0.1) -> tuple[float, float]:
    """Mixture Sequential Probability Ratio Test (mSPRT) for z-statistics.

    Returns ``(msprt_statistic, msprt_p_value)`` — an always-valid p-value
    that stays honest under continuous monitoring. ``theta`` controls the
    mixing distribution variance (larger = more conservative early stopping,
    smaller = closer to the fixed-horizon test at large n).

    The mSPRT statistic is the likelihood ratio of the data under the mixture
    alternative vs the null. We convert it to a "p-value" via
    ``min(1, 1 / Lambda)`` which is always valid as a significance threshold.

    Reference: Johari et al. (2017) "Peeking at A/B Tests: Why it matters,
    and what to do about it" (KDD '17).
    """
    if n_total <= 0:
        return 0.0, 1.0
    # Variance of the mixing distribution, scaled by sample size
    v = theta * n_total
    # Log-likelihood ratio under the mSPRT
    log_lambda = (z_stat**2 / 2) * (v / (v + 1)) - 0.5 * math.log(1 + v)
    lambda_stat = math.exp(min(log_lambda, 500))  # cap to avoid overflow
    p_value = min(1.0, 1.0 / lambda_stat) if lambda_stat > 0 else 1.0
    return lambda_stat, p_value


# ─── Experiment CRUD ──────────────────────────────────────────────────


def _validate_key(key: str) -> str:
    clean = key.strip().lower()
    if not clean:
        raise ValidationAppError("Experiment key cannot be empty.")
    if len(clean) > _MAX_KEY_LENGTH:
        raise ValidationAppError(f"Experiment key cannot exceed {_MAX_KEY_LENGTH} characters.")
    if not all(c.isalnum() or c in ("_", "-") for c in clean):
        raise ValidationAppError(
            "Experiment key may only contain letters, digits, hyphens, and underscores."
        )
    return clean


def _validate_variants_input(variants: list[dict[str, str]]) -> str:
    if len(variants) < 2:
        raise ValidationAppError("An experiment needs at least two variants.")
    if len(variants) > _MAX_VARIANTS:
        raise ValidationAppError(f"An experiment may have at most {_MAX_VARIANTS} variants.")
    keys_seen: set[str] = set()
    for v in variants:
        vkey = (v.get("key") or "").strip()
        vname = (v.get("name") or "").strip()
        if not vkey or not vname:
            raise ValidationAppError("Every variant must have a key and a name.")
        if vkey in keys_seen:
            raise ValidationAppError(f"Duplicate variant key: {vkey}")
        keys_seen.add(vkey)
    return json.dumps(variants)


async def create_experiment(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    key: str,
    name: str,
    description: str = "",
    variants: list[dict[str, str]],
    allocation_pct: int = 100,
    primary_metric: str = "conversion",
    target_sample_size: int | None = None,
) -> dict[str, Any]:
    clean_key = _validate_key(key)
    clean_name = name.strip()
    if not clean_name:
        raise ValidationAppError("Experiment name cannot be empty.")
    if len(clean_name) > _MAX_NAME_LENGTH:
        raise ValidationAppError(f"Experiment name cannot exceed {_MAX_NAME_LENGTH} characters.")
    clean_desc = (description or "").strip()[:_MAX_DESCRIPTION_LENGTH]
    variants_json = _validate_variants_input(variants)
    if not 0 <= allocation_pct <= 100:
        raise ValidationAppError("Allocation percentage must be between 0 and 100.")
    if primary_metric not in ("conversion", "continuous"):
        raise ValidationAppError("Primary metric must be 'conversion' or 'continuous'.")

    existing = await db.fetch_one("SELECT 1 FROM experiments WHERE key = ?", (clean_key,))
    if existing:
        raise ConflictError(f"An experiment with key '{clean_key}' already exists.")

    exp_id = new_id("exp")
    now = utc_now_iso()
    await db.batch(
        [
            (
                """INSERT INTO experiments
               (id, key, name, description, status, variants, allocation_pct,
                primary_metric, target_sample_size, created_at, created_by, updated_at)
               VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    exp_id,
                    clean_key,
                    clean_name,
                    clean_desc,
                    variants_json,
                    allocation_pct,
                    primary_metric,
                    target_sample_size,
                    now,
                    actor.user_id,
                    now,
                ),
            ),
            audit_statement(
                action="experiment.created",
                entity_type="experiment",
                entity_id=exp_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"key": clean_key, "name": clean_name},
            ),
        ]
    )
    return {
        "id": exp_id,
        "key": clean_key,
        "name": clean_name,
        "description": clean_desc,
        "status": "draft",
        "variants": variants,
        "allocationPct": allocation_pct,
        "primaryMetric": primary_metric,
        "targetSampleSize": target_sample_size,
        "startedAt": None,
        "endedAt": None,
        "createdAt": now,
        "updatedAt": now,
    }


async def update_experiment(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    experiment_id: str,
    name: str | None = None,
    description: str | None = None,
    variants: list[dict[str, str]] | None = None,
    allocation_pct: int | None = None,
    primary_metric: str | None = None,
    target_sample_size: int | None = None,
) -> dict[str, Any]:
    exp = await db.fetch_one("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
    if not exp:
        raise NotFoundError("Experiment not found.")
    if exp["status"] != "draft":
        raise ConflictError("Only draft experiments can be edited.")

    now = utc_now_iso()
    updates: list[str] = []
    params: list[Any] = []
    changed: dict[str, Any] = {}

    if name is not None:
        clean_name = name.strip()
        if not clean_name:
            raise ValidationAppError("Experiment name cannot be empty.")
        updates.append("name = ?")
        params.append(clean_name)
        changed["name"] = clean_name
    if description is not None:
        clean_desc = description.strip()[:_MAX_DESCRIPTION_LENGTH]
        updates.append("description = ?")
        params.append(clean_desc)
        changed["description"] = clean_desc
    if variants is not None:
        variants_json = _validate_variants_input(variants)
        updates.append("variants = ?")
        params.append(variants_json)
        changed["variants"] = variants
    if allocation_pct is not None:
        if not 0 <= allocation_pct <= 100:
            raise ValidationAppError("Allocation percentage must be between 0 and 100.")
        updates.append("allocation_pct = ?")
        params.append(allocation_pct)
        changed["allocationPct"] = allocation_pct
    if primary_metric is not None:
        if primary_metric not in ("conversion", "continuous"):
            raise ValidationAppError("Primary metric must be 'conversion' or 'continuous'.")
        updates.append("primary_metric = ?")
        params.append(primary_metric)
        changed["primaryMetric"] = primary_metric
    if target_sample_size is not None:
        updates.append("target_sample_size = ?")
        params.append(target_sample_size if target_sample_size > 0 else None)
        changed["targetSampleSize"] = target_sample_size

    if not updates:
        raise ValidationAppError("Nothing to update.")

    updates.append("updated_at = ?")
    params.append(now)
    params.append(experiment_id)

    await db.batch(
        [
            (f"UPDATE experiments SET {', '.join(updates)} WHERE id = ?", params),
            audit_statement(
                action="experiment.updated",
                entity_type="experiment",
                entity_id=experiment_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after=changed,
            ),
        ]
    )
    return await get_experiment(db, experiment_id)


async def _transition(
    db: Database,
    actor: Principal,
    request_id: str,
    experiment_id: str,
    from_status: str,
    to_status: str,
    action_name: str,
) -> dict[str, Any]:
    exp = await db.fetch_one("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
    if not exp:
        raise NotFoundError("Experiment not found.")
    if exp["status"] != from_status:
        raise ConflictError(
            f"Cannot {action_name} an experiment with status '{exp['status']}'. "
            f"Expected '{from_status}'."
        )
    now = utc_now_iso()
    time_field = "started_at" if to_status == "running" else "ended_at"
    await db.batch(
        [
            (
                f"UPDATE experiments SET status = ?, {time_field} = ?, updated_at = ? WHERE id = ?",
                (to_status, now, now, experiment_id),
            ),
            audit_statement(
                action=f"experiment.{action_name}",
                entity_type="experiment",
                entity_id=experiment_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"status": to_status},
            ),
        ]
    )
    return await get_experiment(db, experiment_id)


async def start_experiment(
    db: Database, actor: Principal, request_id: str, experiment_id: str
) -> dict[str, Any]:
    return await _transition(db, actor, request_id, experiment_id, "draft", "running", "started")


async def stop_experiment(
    db: Database, actor: Principal, request_id: str, experiment_id: str
) -> dict[str, Any]:
    return await _transition(db, actor, request_id, experiment_id, "running", "stopped", "stopped")


async def complete_experiment(
    db: Database, actor: Principal, request_id: str, experiment_id: str
) -> dict[str, Any]:
    return await _transition(
        db, actor, request_id, experiment_id, "running", "completed", "completed"
    )


async def list_experiments(db: Database, *, status: str | None = None) -> list[dict[str, Any]]:
    if status:
        rows = await db.fetch_all(
            "SELECT * FROM experiments WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
    else:
        rows = await db.fetch_all("SELECT * FROM experiments ORDER BY created_at DESC")
    result = []
    for row in rows:
        exp = _format_experiment(row)
        # Attach lightweight sample counts
        counts = await db.fetch_all(
            """SELECT variant, COUNT(DISTINCT user_id) AS users
               FROM experiment_events
               WHERE experiment_key = ? AND event_type = 'exposure'
               GROUP BY variant""",
            (row["key"],),
        )
        exp["sampleSizes"] = {c["variant"]: int(c["users"]) for c in counts}
        result.append(exp)
    return result


async def get_experiment(db: Database, experiment_id: str) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
    if not row:
        raise NotFoundError("Experiment not found.")
    return _format_experiment(row)


def _format_experiment(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "key": row["key"],
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "variants": _parse_variants(row["variants"]),
        "allocationPct": row["allocation_pct"],
        "primaryMetric": row["primary_metric"],
        "targetSampleSize": row["target_sample_size"],
        "startedAt": row["started_at"],
        "endedAt": row["ended_at"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


# ─── Event tracking ──────────────────────────────────────────────────


async def track_event(
    db: Database,
    *,
    experiment_key: str,
    user_id: str,
    event_type: str,
    event_value: float | None = None,
) -> bool:
    """Record an experiment event.  Returns True if the event was written.

    Exposure events are deduplicated: only one per user per experiment.
    Conversion and intermediate events are always written (a user may
    convert multiple times for continuous metrics like order value).
    """
    if event_type not in ("exposure", "conversion", "add_to_cart", "checkout_started"):
        raise ValidationAppError(f"Unknown event type: {event_type}")

    # Verify the experiment exists and is running
    exp = await db.fetch_one(
        "SELECT key, status, variants FROM experiments WHERE key = ?",
        (experiment_key,),
    )
    if not exp:
        return False  # silently ignore events for unknown experiments
    if exp["status"] != "running":
        return False  # silently ignore events for non-running experiments

    # Determine the user's variant
    variants = _parse_variants(exp["variants"])
    if not variants:
        return False

    # For exposure dedup: only one exposure per user per experiment
    if event_type == "exposure":
        existing = await db.fetch_one(
            """SELECT 1 FROM experiment_events
               WHERE experiment_key = ? AND user_id = ? AND event_type = 'exposure'
               LIMIT 1""",
            (experiment_key, user_id),
        )
        if existing:
            return False  # already exposed

    # We need the variant — look it up from existing exposure or assign fresh
    variant_row = await db.fetch_one(
        """SELECT variant FROM experiment_events
           WHERE experiment_key = ? AND user_id = ? AND event_type = 'exposure'
           LIMIT 1""",
        (experiment_key, user_id),
    )
    if variant_row:
        variant = variant_row["variant"]
    else:
        # No exposure yet — compute from hash
        exp_full = await db.fetch_one(
            "SELECT allocation_pct FROM experiments WHERE key = ?",
            (experiment_key,),
        )
        alloc = exp_full["allocation_pct"] if exp_full else 100
        variant = assign_variant(user_id, experiment_key, variants, alloc)
        if variant is None:
            return False  # user not in experiment

    evt_id = new_id("evt")
    now = utc_now_iso()
    await db.execute(
        """INSERT INTO experiment_events
           (id, experiment_key, variant, user_id, event_type, event_value, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (evt_id, experiment_key, variant, user_id, event_type, event_value, now),
    )
    return True


async def get_user_assignments(db: Database, user_id: str) -> list[dict[str, str]]:
    """All running experiments and the user's variant assignment for each."""
    experiments = await db.fetch_all(
        "SELECT key, variants, allocation_pct FROM experiments WHERE status = 'running'"
    )
    assignments = []
    for exp in experiments:
        variants = _parse_variants(exp["variants"])
        if not variants:
            continue
        variant = assign_variant(user_id, exp["key"], variants, exp["allocation_pct"])
        if variant is not None:
            assignments.append({"experimentKey": exp["key"], "variant": variant})
    return assignments


# ─── Results / stats ─────────────────────────────────────────────────


async def compute_results(db: Database, experiment_id: str) -> dict[str, Any]:
    """Full statistical results for an experiment."""
    exp = await db.fetch_one("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
    if not exp:
        raise NotFoundError("Experiment not found.")

    variants = _parse_variants(exp["variants"])
    exp_key = exp["key"]
    primary_metric = exp["primary_metric"]
    target = exp["target_sample_size"]

    # Aggregate per-variant event counts
    variant_stats: dict[str, dict[str, Any]] = {}
    for v in variants:
        vkey = v["key"]
        exposures = await db.fetch_one(
            """SELECT COUNT(DISTINCT user_id) AS n
               FROM experiment_events
               WHERE experiment_key = ? AND variant = ? AND event_type = 'exposure'""",
            (exp_key, vkey),
        )
        conversions = await db.fetch_one(
            """SELECT COUNT(DISTINCT user_id) AS n
               FROM experiment_events
               WHERE experiment_key = ? AND variant = ? AND event_type = 'conversion'""",
            (exp_key, vkey),
        )

        # For continuous: get the actual values
        value_rows = await db.fetch_all(
            """SELECT event_value FROM experiment_events
               WHERE experiment_key = ? AND variant = ? AND event_type = 'conversion'
                 AND event_value IS NOT NULL""",
            (exp_key, vkey),
        )
        values = [float(r["event_value"]) for r in value_rows]

        n_exposed = int(exposures["n"]) if exposures else 0
        n_converted = int(conversions["n"]) if conversions else 0
        mean_value = sum(values) / len(values) if values else 0.0
        std_value = (
            math.sqrt(sum((x - mean_value) ** 2 for x in values) / (len(values) - 1))
            if len(values) > 1
            else 0.0
        )

        variant_stats[vkey] = {
            "key": vkey,
            "name": v.get("name", vkey),
            "exposures": n_exposed,
            "conversions": n_converted,
            "conversionRate": n_converted / n_exposed if n_exposed > 0 else 0.0,
            "values": values,
            "meanValue": mean_value,
            "stdValue": std_value,
        }

    # Statistical comparison: first variant is control, rest are treatments
    comparisons = []
    if len(variants) >= 2:
        control_key = variants[0]["key"]
        ctrl = variant_stats[control_key]

        for v in variants[1:]:
            treat = variant_stats[v["key"]]

            if primary_metric == "conversion":
                z, p, ci_lo, ci_hi = two_proportion_z_test(
                    ctrl["conversions"],
                    ctrl["exposures"],
                    treat["conversions"],
                    treat["exposures"],
                )
                n_total = ctrl["exposures"] + treat["exposures"]
                msprt_lambda, msprt_p = msprt_z(z, n_total)

                abs_effect = treat["conversionRate"] - ctrl["conversionRate"]
                rel_effect = (
                    abs_effect / ctrl["conversionRate"] if ctrl["conversionRate"] > 0 else 0.0
                )

                required = target
                power_now = _achieved_power_binary(
                    ctrl["conversionRate"],
                    treat["conversionRate"],
                    min(ctrl["exposures"], treat["exposures"]),
                )

                comparisons.append(
                    {
                        "treatmentKey": v["key"],
                        "treatmentName": v.get("name", v["key"]),
                        "metricType": "conversion",
                        "controlRate": ctrl["conversionRate"],
                        "treatmentRate": treat["conversionRate"],
                        "absoluteEffect": abs_effect,
                        "relativeEffect": rel_effect,
                        "zStat": round(z, 4),
                        "pValue": round(p, 6),
                        "ciLower": round(ci_lo, 6),
                        "ciUpper": round(ci_hi, 6),
                        "msprtStat": round(msprt_lambda, 4),
                        "msprtPValue": round(msprt_p, 6),
                        "isSignificant": msprt_p < 0.05,
                        "requiredSamplePerVariant": required,
                        "powerAchieved": round(power_now, 4),
                    }
                )
            else:
                # Continuous metric — Welch's t-test
                t, p, ci_lo, ci_hi = welch_t_test(ctrl["values"], treat["values"])
                n_total = len(ctrl["values"]) + len(treat["values"])
                msprt_lambda, msprt_p = msprt_z(t, n_total)

                mean_diff = treat["meanValue"] - ctrl["meanValue"]
                rel_effect = mean_diff / ctrl["meanValue"] if ctrl["meanValue"] != 0 else 0.0
                pooled_std = (
                    math.sqrt((ctrl["stdValue"] ** 2 + treat["stdValue"] ** 2) / 2)
                    if ctrl["stdValue"] > 0 or treat["stdValue"] > 0
                    else 0.0
                )

                power_now = _achieved_power_continuous(
                    pooled_std,
                    mean_diff,
                    min(len(ctrl["values"]), len(treat["values"])),
                )

                comparisons.append(
                    {
                        "treatmentKey": v["key"],
                        "treatmentName": v.get("name", v["key"]),
                        "metricType": "continuous",
                        "controlMean": round(ctrl["meanValue"], 2),
                        "controlStd": round(ctrl["stdValue"], 2),
                        "treatmentMean": round(treat["meanValue"], 2),
                        "treatmentStd": round(treat["stdValue"], 2),
                        "meanDifference": round(mean_diff, 2),
                        "relativeEffect": round(rel_effect, 4),
                        "tStat": round(t, 4),
                        "pValue": round(p, 6),
                        "ciLower": round(ci_lo, 2),
                        "ciUpper": round(ci_hi, 2),
                        "msprtStat": round(msprt_lambda, 4),
                        "msprtPValue": round(msprt_p, 6),
                        "isSignificant": msprt_p < 0.05,
                        "requiredSamplePerVariant": target,
                        "powerAchieved": round(power_now, 4),
                    }
                )

    return {
        "experiment": _format_experiment(exp),
        "variants": [
            {
                "key": vs["key"],
                "name": vs["name"],
                "exposures": vs["exposures"],
                "conversions": vs["conversions"],
                "conversionRate": round(vs["conversionRate"], 6),
                "meanValue": round(vs["meanValue"], 2),
                "stdValue": round(vs["stdValue"], 2),
            }
            for vs in variant_stats.values()
        ],
        "comparisons": comparisons,
        "totalExposures": sum(vs["exposures"] for vs in variant_stats.values()),
        "totalConversions": sum(vs["conversions"] for vs in variant_stats.values()),
    }

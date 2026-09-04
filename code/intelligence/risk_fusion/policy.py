"""Fixed, auditable Day-7 review-priority policy v0.1."""

from __future__ import annotations


POLICY_VERSION = "REVIEW_PRIORITY_POLICY_V0_1"

ANOMALY = "ANOMALY"
PEER_DEVIATION = "PEER_DEVIATION"
DUPLICATE_REVIEW = "DUPLICATE_REVIEW"
PAYMENT_EXECUTION = "PAYMENT_EXECUTION"
OBSERVED_CONDITIONS = "OBSERVED_CONDITIONS"
COMPLIANCE = "COMPLIANCE"
COST_OVERRUN_PREDICTION = "COST_OVERRUN_PREDICTION"
OPERATIONAL_TREND_CONTEXT = "OPERATIONAL_TREND_CONTEXT"

FAMILY_ORDER = (
    ANOMALY,
    PEER_DEVIATION,
    DUPLICATE_REVIEW,
    PAYMENT_EXECUTION,
    OBSERVED_CONDITIONS,
    COMPLIANCE,
    COST_OVERRUN_PREDICTION,
    OPERATIONAL_TREND_CONTEXT,
)

LIFECYCLE_WEIGHTS: dict[str, dict[str, int]] = {
    "PRE_SANCTION": {
        ANOMALY: 30,
        PEER_DEVIATION: 25,
        DUPLICATE_REVIEW: 25,
        OPERATIONAL_TREND_CONTEXT: 20,
    },
    "EXECUTION": {
        ANOMALY: 10,
        PEER_DEVIATION: 10,
        DUPLICATE_REVIEW: 15,
        PAYMENT_EXECUTION: 25,
        OBSERVED_CONDITIONS: 20,
        COMPLIANCE: 10,
        COST_OVERRUN_PREDICTION: 5,
        OPERATIONAL_TREND_CONTEXT: 5,
    },
    "COMPLETION": {
        ANOMALY: 8,
        PEER_DEVIATION: 7,
        DUPLICATE_REVIEW: 15,
        PAYMENT_EXECUTION: 20,
        COMPLIANCE: 40,
        OPERATIONAL_TREND_CONTEXT: 10,
    },
}

SOURCE_ARTIFACTS = {
    ANOMALY: "data/processed/anomaly_scores.csv",
    PEER_DEVIATION: "data/processed/peer_benchmark_summary.csv",
    DUPLICATE_REVIEW: "data/processed/duplicate_summary.csv",
    PAYMENT_EXECUTION: (
        "data/processed/payment_irregularities.csv;"
        "data/processed/fund_progress_evidence.csv"
    ),
    OBSERVED_CONDITIONS: (
        "data/processed/project_features.csv;data/processed/predictive_scores.csv"
    ),
    COMPLIANCE: "data/processed/compliance_evidence.csv",
    COST_OVERRUN_PREDICTION: "data/processed/predictive_scores.csv",
    OPERATIONAL_TREND_CONTEXT: "data/processed/work_trend_context.csv",
}

BANDS = (
    {"name": "LOW", "minimum_inclusive": 0.0, "maximum_exclusive": 25.0},
    {"name": "MEDIUM", "minimum_inclusive": 25.0, "maximum_exclusive": 50.0},
    {"name": "HIGH", "minimum_inclusive": 50.0, "maximum_exclusive": 75.0},
    {"name": "CRITICAL", "minimum_inclusive": 75.0, "maximum_inclusive": 100.0},
)


def validate_policy() -> None:
    if set(LIFECYCLE_WEIGHTS) != {"PRE_SANCTION", "EXECUTION", "COMPLETION"}:
        raise ValueError("Unexpected lifecycle policy")
    for lifecycle, weights in LIFECYCLE_WEIGHTS.items():
        if sum(weights.values()) != 100:
            raise ValueError(f"{lifecycle} weights do not sum to 100")
        if not set(weights).issubset(FAMILY_ORDER):
            raise ValueError(f"{lifecycle} contains an unknown evidence family")
    if "DELAY_PREDICTION" in FAMILY_ORDER:
        raise ValueError("Unavailable delay model must not enter policy v0.1")


def priority_band(score: float) -> str:
    if not 0 <= score <= 100:
        raise ValueError(f"Review-priority score outside 0-100: {score}")
    if score < 25:
        return "LOW"
    if score < 50:
        return "MEDIUM"
    if score < 75:
        return "HIGH"
    return "CRITICAL"


def policy_document() -> dict[str, object]:
    validate_policy()
    return {
        "policy_version": POLICY_VERSION,
        "policy_role": "deterministic human-review prioritization; not a probability, finding, or verdict",
        "family_definitions": {
            ANOMALY: "Day-3 within-lifecycle unusualness percentile; not probability.",
            PEER_DEVIATION: "Lifecycle-local percentile of strongest valid robust peer deviation, only where peer-outlier evidence exists.",
            DUPLICATE_REVIEW: "Day-4.1 corroborated review candidate and best review similarity only.",
            PAYMENT_EXECUTION: "One capped family combining non-over-sanction payment severity and positive fund-progress context.",
            OBSERVED_CONDITIONS: "Already-observed overdue and over-sanction facts; not predictions.",
            COMPLIANCE: "Strongest actionable deterministic Day-5 rule result; not summed rule counts.",
            COST_OVERRUN_PREDICTION: "Weak secondary raw-XGBoost serving percentile; maximum five execution points.",
            OPERATIONAL_TREND_CONTEXT: "Independent supported operational-event trend context; detector hotspots excluded.",
        },
        "normalization_rules": {
            ANOMALY: "use within_stage_anomaly_percentile_0_100 directly",
            PEER_DEVIATION: "lifecycle-local 0-100 percentile of max absolute valid deviation for works with peer-outlier evidence",
            DUPLICATE_REVIEW: "0 unless review_candidate=true; then best_review_similarity_score_0_100",
            PAYMENT_EXECUTION: "max(non-over-sanction payment severity, positive-gap percentile plus at most 10 persistence points), capped at 100",
            OBSERVED_CONDITIONS: "overdue=50+0.5*percentile; over-sanction=75+0.25*percentile; take maximum",
            COMPLIANCE: "NON_COMPLIANT=100; REVIEW INFO/WARNING/STRONG_WARNING=30/60/80; otherwise 0",
            COST_OVERRUN_PREDICTION: "cost_overrun_serving_percentile_0_100 only",
            OPERATIONAL_TREND_CONTEXT: "latest-complete-month supported operational trend-deviation strength percentile",
        },
        "lifecycle_weight_maps_pct": LIFECYCLE_WEIGHTS,
        "review_priority_bands": list(BANDS),
        "source_artifacts": SOURCE_ARTIFACTS,
        "exclusion_rules": [
            "evaluation ground truth and helper labels are prohibited",
            "historical duplicate candidate_flag is prohibited; only review_candidate is used",
            "RELEASED_TOTAL_EXCEEDS_SANCTION is excluded from PAYMENT_EXECUTION and assigned to OBSERVED_CONDITIONS",
            "detector hotspot prevalence never enters an individual score",
            "unavailable delay prediction contributes no signal and has no policy weight",
            "missing family evidence does not cause weight renormalization",
        ],
        "predictive_serving_restrictions": {
            "required_calibration_status": "UNSTABLE_RANK_REVERSAL",
            "required_calibration_serving_eligible": False,
            "required_model_quality_status": "PROTOTYPE_WEAK_DISCRIMINATION",
            "allowed_field": "cost_overrun_serving_percentile_0_100",
            "calibrated_probability_role": "diagnostic only; never fused",
            "maximum_execution_contribution_points": 5,
        },
        "no_ground_truth_statement": (
            "No ground-truth label, injected anomaly field, expected-risk field, or "
            "duplicate helper was used to define, tune, or calculate this policy."
        ),
        "coverage_rule": (
            "Sum declared lifecycle weights whose required evidence was evaluable. "
            "Coverage is reported separately and never multiplies the priority score."
        ),
    }

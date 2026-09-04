"""Day-7 fixed policy, serving safety, and no-double-counting tests."""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from intelligence.risk_fusion import fusion, signals
from intelligence.risk_fusion.policy import (
    COST_OVERRUN_PREDICTION,
    LIFECYCLE_WEIGHTS,
    PAYMENT_EXECUTION,
    POLICY_VERSION,
    priority_band,
)


@pytest.fixture(scope="module")
def day7_outputs(project_paths):
    processed = project_paths.processed_data_dir
    return {
        "scores": pd.read_csv(processed / "review_priority_scores.csv", low_memory=False),
        "evidence": pd.read_csv(processed / "review_priority_evidence.csv", low_memory=False),
        "predictive": pd.read_csv(processed / "predictive_scores.csv", low_memory=False),
        "duplicates": pd.read_csv(processed / "duplicate_summary.csv", low_memory=False),
        "policy": __import__("json").loads((processed / "risk_fusion_policy.json").read_text()),
    }


def test_policy_version_and_lifecycle_weights_are_exact():
    assert POLICY_VERSION == "REVIEW_PRIORITY_POLICY_V0_1"
    assert LIFECYCLE_WEIGHTS == {
        "PRE_SANCTION": {
            "ANOMALY": 30,
            "PEER_DEVIATION": 25,
            "DUPLICATE_REVIEW": 25,
            "OPERATIONAL_TREND_CONTEXT": 20,
        },
        "EXECUTION": {
            "ANOMALY": 10,
            "PEER_DEVIATION": 10,
            "DUPLICATE_REVIEW": 15,
            "PAYMENT_EXECUTION": 25,
            "OBSERVED_CONDITIONS": 20,
            "COMPLIANCE": 10,
            "COST_OVERRUN_PREDICTION": 5,
            "OPERATIONAL_TREND_CONTEXT": 5,
        },
        "COMPLETION": {
            "ANOMALY": 8,
            "PEER_DEVIATION": 7,
            "DUPLICATE_REVIEW": 15,
            "PAYMENT_EXECUTION": 20,
            "COMPLIANCE": 40,
            "OPERATIONAL_TREND_CONTEXT": 10,
        },
    }
    assert all(sum(weights.values()) == 100 for weights in LIFECYCLE_WEIGHTS.values())
    assert all("DELAY" not in family for weights in LIFECYCLE_WEIGHTS.values() for family in weights)


def test_each_lifecycle_uses_only_declared_families(day7_outputs):
    evidence = day7_outputs["evidence"]
    for lifecycle, expected in LIFECYCLE_WEIGHTS.items():
        actual = set(evidence.loc[evidence["lifecycle_stage"].eq(lifecycle), "family"])
        assert actual == set(expected)
        per_work = evidence.loc[evidence["lifecycle_stage"].eq(lifecycle)].groupby("work_id")["family"].nunique()
        assert per_work.eq(len(expected)).all()


def test_raw_cost_serving_percentile_is_used_and_contribution_is_capped(day7_outputs):
    evidence = day7_outputs["evidence"]
    predictive = day7_outputs["predictive"]
    cost = evidence.loc[evidence["family"].eq(COST_OVERRUN_PREDICTION)].merge(
        predictive[["work_id", "cost_overrun_serving_percentile_0_100"]],
        on="work_id",
        validate="one_to_one",
    )
    np.testing.assert_allclose(
        cost["family_score_0_100"], cost["cost_overrun_serving_percentile_0_100"]
    )
    assert cost["contribution_points"].le(5).all()
    source = inspect.getsource(signals.cost_prediction_signal)
    assert "cost_overrun_serving_percentile_0_100" in source
    assert "cost_overrun_probability_calibrated" not in source


def test_only_review_candidate_enters_duplicate_family(day7_outputs):
    duplicates = day7_outputs["duplicates"]
    evidence = day7_outputs["evidence"]
    duplicate_family = evidence.loc[evidence["family"].eq("DUPLICATE_REVIEW")]
    aligned = duplicate_family.merge(
        duplicates[["work_id", "review_candidate", "best_review_similarity_score_0_100"]],
        on="work_id",
        validate="one_to_one",
    )
    review = signals.as_bool(aligned["review_candidate"])
    assert aligned.loc[~review, "family_score_0_100"].eq(0).all()
    np.testing.assert_allclose(
        aligned.loc[review, "family_score_0_100"],
        aligned.loc[review, "best_review_similarity_score_0_100"],
    )
    assert "candidate_flag" not in inspect.getsource(signals.duplicate_signal)


def test_over_sanction_is_not_double_counted_in_payment_family(day7_outputs):
    payment = day7_outputs["evidence"].loc[
        day7_outputs["evidence"]["family"].eq(PAYMENT_EXECUTION)
    ]
    assert not payment["evidence_code"].eq("RELEASED_TOTAL_EXCEEDS_SANCTION").any()
    assert "RELEASED_TOTAL_EXCEEDS_SANCTION" in inspect.getsource(signals.payment_execution_signal)


def test_final_score_is_exact_sum_and_coverage_is_separate(day7_outputs):
    scores = day7_outputs["scores"]
    evidence = day7_outputs["evidence"]
    sums = evidence.groupby("work_id")["contribution_points"].sum().round(6)
    aligned = scores.set_index("work_id")
    np.testing.assert_allclose(
        aligned.loc[sums.index, "review_priority_score_0_100"], sums, rtol=0, atol=1e-6
    )
    assert scores["review_priority_score_0_100"].between(0, 100).all()
    assert scores["fusion_evidence_coverage_pct"].between(0, 100).all()
    source = inspect.getsource(fusion.build_review_priority_scores)
    assert '* scores["fusion_evidence_coverage_pct"]' not in source


@pytest.mark.parametrize(
    ("score", "band"),
    [(0, "LOW"), (24.999, "LOW"), (25, "MEDIUM"), (49.999, "MEDIUM"), (50, "HIGH"), (74.999, "HIGH"), (75, "CRITICAL"), (100, "CRITICAL")],
)
def test_exact_fixed_bands(score, band):
    assert priority_band(score) == band


def test_no_hotspot_feedback_delay_signal_or_fraud_fields(day7_outputs):
    fusion_source = inspect.getsource(fusion).casefold()
    signal_source = inspect.getsource(signals).casefold()
    assert "detector_hotspot" not in fusion_source + signal_source
    assert "delay_prediction" not in set(day7_outputs["evidence"]["family"])
    columns = " ".join(day7_outputs["scores"].columns).casefold()
    assert "fraud" not in columns
    assert "verdict" not in columns
    assert day7_outputs["policy"]["predictive_serving_restrictions"]["calibrated_probability_role"].startswith("diagnostic")

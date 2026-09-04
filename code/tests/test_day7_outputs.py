"""Day-7 output contracts, provenance, language, and frozen-input integrity."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd

from intelligence.risk_fusion import alerts, fusion, policy, runner, signals
from intelligence.trends import context, hotspots, monthly, robust


FROZEN_DAY7_INPUT_HASHES = {
    "data/processed/project_features.csv": "760D1D1366316C54CF928C5CCE03AD3A10F2793C0F986782477F03F6D9A77148",
    "data/processed/anomaly_scores.csv": "F65777B89067A8335AA953255C448774D7E52F08728B7455A4C9FBA7DF91D4CC",
    "data/processed/peer_benchmark_summary.csv": "EBD4DB143972483B95219F81FE0F55DEF0ABB0EC279C53016858E20E3E9F5F63",
    "data/processed/peer_benchmark_evidence.csv": "9C22930D7B821CE1ACCC10EF7B41E93F8CE3ACEA03DC83D67E1D3243FB88E3D5",
    "data/processed/duplicate_summary.csv": "60950E8A0CC4250F43D70418281ACA8AFA9177E67C57434E551536C42224C3AA",
    "data/processed/duplicate_candidates.csv": "150EA1548FBC31C4B4FD67BF921BE8F5E95C720C5B269899032778F6F9203246",
    "data/processed/payment_irregularity_summary.csv": "7F3DEDFFD64C63E047113A5F616D2FA0016A16C7C72BE6081679C5DEB4BCDF7D",
    "data/processed/payment_irregularities.csv": "C7BCCF4DD02D6A6CDBF322E4B19AE393212B59898434B714C7D6868C2302BBE0",
    "data/processed/fund_progress_evidence.csv": "812D9295E38285CBAE784D2F6F3EBD606F7BED5981DD3279CF61975A3CFD206C",
    "data/processed/compliance_summary.csv": "E3D5C37ABA64F494BBA4C93564FAD2A978241BA917530E5315851F28E237F69F",
    "data/processed/compliance_evidence.csv": "9ED912957A1260355DF50403950E0631C6896DF54A122E7749926FD443801C3D",
    "data/processed/predictive_scores.csv": "0AD74532D0ABEB2330B241ABC02EB968E9A66B31D7527E179D37DB8283B2D2F4",
    "data/processed/predictive_explanations.csv": "10FD8A1757B5022F2C28604DB5CD8A68C308719D7B4059BAB55003985236D610",
    "data/processed/day6_predictive_summary.json": "714645D81CA217623E489DF5BD5ABDA9DDB0E75E5791B31F12E4D2BB5ABFA9BA",
    "code/models/predictive/predictive_model_metadata.json": "47034A5193EE7FA88C3236D3E36BF81B1738F867F4F6E13DDDBB96EE72895234",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def test_score_queue_evidence_and_alert_referential_integrity(project_paths):
    processed = project_paths.processed_data_dir
    scores = pd.read_csv(processed / "review_priority_scores.csv", low_memory=False)
    queue = pd.read_csv(processed / "review_priority_queue.csv", low_memory=False)
    evidence = pd.read_csv(processed / "review_priority_evidence.csv", low_memory=False)
    review_alerts = pd.read_csv(processed / "review_alerts.csv", low_memory=False)
    assert len(scores) == scores["work_id"].nunique() == 3_000
    work_ids = set(scores["work_id"])
    assert set(queue["work_id"]).issubset(work_ids)
    assert set(evidence["work_id"]) == work_ids
    assert set(review_alerts["work_id"]).issubset(work_ids)
    assert queue["review_priority_band"].isin(["HIGH", "CRITICAL"]).all()
    for source in review_alerts["source_artifact"].unique():
        assert (project_paths.project_root / source).is_file(), source


def test_top_contributors_and_ranks_are_deterministic(project_paths):
    processed = project_paths.processed_data_dir
    scores = pd.read_csv(processed / "review_priority_scores.csv", low_memory=False)
    evidence = pd.read_csv(processed / "review_priority_evidence.csv", low_memory=False)
    family_order = {family: index for index, family in enumerate(policy.FAMILY_ORDER)}
    evidence["_order"] = evidence["family"].map(family_order)
    expected_top = evidence.sort_values(
        ["work_id", "contribution_points", "_order"],
        ascending=[True, False, True],
        kind="stable",
    ).groupby("work_id").head(3)
    expected_top["position"] = expected_top.groupby("work_id").cumcount() + 1
    for position in (1, 2, 3):
        expected = expected_top.loc[expected_top["position"].eq(position)].set_index("work_id")
        aligned = scores.set_index("work_id")
        assert aligned[f"top_contributor_{position}_family"].equals(expected["family"].reindex(aligned.index))
        np.testing.assert_allclose(
            aligned[f"top_contributor_{position}_points"],
            expected["contribution_points"].reindex(aligned.index),
        )

    overall = scores.sort_values(
        ["review_priority_score_0_100", "work_id"], ascending=[False, True], kind="stable"
    )
    assert overall["review_priority_rank_overall"].tolist() == list(range(1, 3_001))
    for _, group in scores.groupby("lifecycle_stage"):
        ranked = group.sort_values(
            ["review_priority_score_0_100", "work_id"], ascending=[False, True], kind="stable"
        )
        assert ranked["review_priority_rank_within_lifecycle"].tolist() == list(
            range(1, len(ranked) + 1)
        )


def test_hotspot_denominators_and_no_opaque_score(project_paths):
    frame = pd.read_csv(project_paths.processed_data_dir / "detector_hotspots.csv")
    assert frame["work_count"].ge(20).all()
    assert not any("score" in column.casefold() for column in frame.columns)
    share_columns = [column for column in frame if column.endswith("_share")]
    assert frame[share_columns].apply(lambda column: column.between(0, 1).all()).all()


def test_alert_counts_preserve_strong_evidence(project_paths):
    review_alerts = pd.read_csv(project_paths.processed_data_dir / "review_alerts.csv")
    counts = review_alerts["alert_type"].value_counts()
    assert counts["DETERMINISTIC_NON_COMPLIANCE"] == 1
    assert counts["DUPLICATE_REVIEW_CANDIDATE"] == 24
    assert counts["OBSERVED_OVERDUE"] == 272
    assert counts["OBSERVED_OVER_SANCTION"] == 20
    assert counts["COST_OVERRUN_EARLY_WARNING"] == 78
    assert not review_alerts["alert_type"].str.contains("FRAUD", case=False).any()


def test_production_source_firewall_and_language(project_paths):
    modules = (monthly, robust, context, hotspots, policy, signals, fusion, alerts, runner)
    source = "\n".join(inspect.getsource(module) for module in modules).casefold()
    for forbidden in (
        "07_anomaly_ground_truth",
        "injected_anomaly",
        "expected_risk",
        "duplicate_group_reference",
    ):
        assert forbidden not in source

    output_files = [
        "risk_fusion_policy.json",
        "day7_intelligence_summary.json",
        "review_priority_scores.csv",
        "review_priority_evidence.csv",
        "review_alerts.csv",
    ]
    text = "\n".join(
        (project_paths.processed_data_dir / filename).read_text(encoding="utf-8")
        for filename in output_files
    ).casefold()
    for phrase in ("fraud confirmed", "fraud detected", "guilty", "corrupt", "criminal project"):
        assert phrase not in text


def test_summary_and_policy_governance_contract(project_paths):
    summary = json.loads(
        (project_paths.processed_data_dir / "day7_intelligence_summary.json").read_text()
    )
    fusion_policy = json.loads(
        (project_paths.processed_data_dir / "risk_fusion_policy.json").read_text()
    )
    assert summary["latest_complete_trend_month"] == "2026-08"
    assert summary["trend_metric_count"] == 7
    assert summary["risk_fusion_policy_version"] == "REVIEW_PRIORITY_POLICY_V0_1"
    assert summary["predictive_governance"]["calibrated_cost_probability_fused"] is False
    assert summary["predictive_governance"]["delay_model_signal_contribution"] == 0
    assert summary["detector_hotspot_feedback_used"] is False
    assert summary["ground_truth_used"] is False
    assert fusion_policy["predictive_serving_restrictions"]["maximum_execution_contribution_points"] == 5


def test_all_day7_frozen_inputs_remain_byte_identical(project_paths):
    for relative, expected in FROZEN_DAY7_INPUT_HASHES.items():
        assert _sha256(project_paths.project_root / relative) == expected

"""Day-5 deterministic rule, guideline, and frozen-artifact guardrails."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
import pytest

from intelligence.compliance.engine import (
    build_compliance_evidence,
    build_compliance_summary,
)
from intelligence.compliance.guideline import (
    EXPECTED_PAGE_COUNT,
    GUIDELINE_FILENAME,
    extract_guideline_chunks,
    get_guideline_chunk,
    get_guideline_clause,
    sha256_file,
)
from intelligence.compliance.models import ComplianceResult
from intelligence.compliance.rule_registry import build_rule_registry
from intelligence.compliance.rules import IMPLEMENTED_RULES, IMPLEMENTED_RULE_BY_ID


AS_OF_DATE = date(2026, 9, 1)
ASSET_COLUMNS = [
    "work_id",
    "completion_date",
    "public_use_date",
    "completion_photo_reference",
    "handover_date",
    "asset_register_entry",
    "utilization_certificate_status",
    "utilization_certificate_date",
]
_DEFAULT_ASSETS = object()

PRIOR_DAY_HASHES = {
    "data/processed/project_features.csv": "760D1D1366316C54CF928C5CCE03AD3A10F2793C0F986782477F03F6D9A77148",
    "data/processed/anomaly_scores.csv": "F65777B89067A8335AA953255C448774D7E52F08728B7455A4C9FBA7DF91D4CC",
    "data/processed/peer_benchmark_summary.csv": "EBD4DB143972483B95219F81FE0F55DEF0ABB0EC279C53016858E20E3E9F5F63",
    "data/processed/duplicate_candidates.csv": "150EA1548FBC31C4B4FD67BF921BE8F5E95C720C5B269899032778F6F9203246",
    "data/processed/duplicate_summary.csv": "60950E8A0CC4250F43D70418281ACA8AFA9177E67C57434E551536C42224C3AA",
    "data/processed/duplicate_work_embeddings.npy": "C946D5A99D1D82230BD677CF1D6875F367770E37454091EDD6C48CC5D260C8BF",
    "data/processed/duplicate_work_embeddings_metadata.json": "15EBB520DAE1081F62AFE90D1F38A581C14BF4A9A852594EFF1CDE40BD9074F6",
    "data/processed/payment_irregularities.csv": "C7BCCF4DD02D6A6CDBF322E4B19AE393212B59898434B714C7D6868C2302BBE0",
    "data/processed/payment_irregularity_summary.csv": "7F3DEDFFD64C63E047113A5F616D2FA0016A16C7C72BE6081679C5DEB4BCDF7D",
    "data/processed/fund_progress_evidence.csv": "812D9295E38285CBAE784D2F6F3EBD606F7BED5981DD3279CF61975A3CFD206C",
    "data/processed/day4_detector_summary.json": "7ADABE3D1CEEBC8E2A022D1511E5A3C418B85A4B5FFCC63C7C9D64FA88884005",
    "code/models/anomaly/isolation_forest_pre_sanction.joblib": "A87EBECFA83E1DF9A52614FDCEAA038D7E7D87DEAEAF1231864CE3D1C6F54529",
    "code/models/anomaly/isolation_forest_execution.joblib": "C7267BD53FB0EEC426CE572FDBC6D17FBC9925A21485962FA20EFC3E47DEFFCD",
    "code/models/anomaly/isolation_forest_completion.joblib": "48C9C6AF5384C2C9CC19B55FD012A56CC73357F49611101FFF5A81250C78C86B",
    "code/models/anomaly/anomaly_model_metadata.json": "FA07C130E2BB37CA354922DE72F5872FA5DBE5F50FFF012A7919601E19349B1F",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _work(**updates) -> dict[str, object]:
    row: dict[str, object] = {
        "work_id": "TEST-WORK",
        "lifecycle_stage": "COMPLETION",
        "recommendation_date": pd.Timestamp("2026-01-01"),
        "sanction_date_as_of": pd.Timestamp("2026-02-01"),
        "sanctioned_amount_inr": 300_000,
        "expected_completion_date": pd.Timestamp("2026-12-31"),
    }
    row.update(updates)
    return row


def _asset(**updates) -> dict[str, object]:
    row: dict[str, object] = {
        "work_id": "TEST-WORK",
        "completion_date": pd.Timestamp("2026-08-31"),
        "public_use_date": pd.Timestamp("2026-09-01"),
        "completion_photo_reference": "PHOTO-001",
        "handover_date": pd.Timestamp("2026-09-01"),
        "asset_register_entry": "Yes",
        "utilization_certificate_status": "Submitted",
        "utilization_certificate_date": pd.Timestamp("2026-09-01"),
    }
    row.update(updates)
    return row


def _run_rule(
    rule_id: str,
    *,
    work_updates: dict[str, object] | None = None,
    asset_rows: object = _DEFAULT_ASSETS,
) -> str:
    work = _work(**(work_updates or {}))
    if asset_rows is _DEFAULT_ASSETS:
        rows = [_asset()]
    else:
        rows = asset_rows
    assets = pd.DataFrame(rows, columns=ASSET_COLUMNS)
    evidence = build_compliance_evidence(
        pd.DataFrame([work]),
        assets,
        AS_OF_DATE,
        rules=(IMPLEMENTED_RULE_BY_ID[rule_id],),
    )
    return str(evidence.loc[0, "result"])


def test_rule_sanction_response_all_results():
    rule_id = "MPLADS-3.2.4-SANCTION-45D"
    assert _run_rule(rule_id) == "PASS"
    assert _run_rule(
        rule_id, work_updates={"sanction_date_as_of": pd.Timestamp("2026-03-01")}
    ) == "REVIEW"
    assert _run_rule(
        rule_id, work_updates={"lifecycle_stage": "PRE_SANCTION"}
    ) == "NOT_APPLICABLE"
    assert _run_rule(
        rule_id, work_updates={"sanction_date_as_of": pd.NaT}
    ) == "INSUFFICIENT_DATA"


def test_rule_minimum_sanction_all_results():
    rule_id = "MPLADS-3.2.9-MIN-SANCTION"
    assert _run_rule(rule_id) == "PASS"
    assert _run_rule(
        rule_id, work_updates={"sanctioned_amount_inr": 249_999}
    ) == "REVIEW"
    assert _run_rule(
        rule_id, work_updates={"lifecycle_stage": "PRE_SANCTION"}
    ) == "NOT_APPLICABLE"
    assert _run_rule(
        rule_id, work_updates={"sanctioned_amount_inr": pd.NA}
    ) == "INSUFFICIENT_DATA"


def test_rule_completion_limit_all_results():
    rule_id = "MPLADS-3.2.12-COMPLETION-LIMIT"
    assert _run_rule(rule_id) == "PASS"
    assert _run_rule(
        rule_id,
        work_updates={"expected_completion_date": pd.Timestamp("2027-03-01")},
    ) == "REVIEW"
    assert _run_rule(
        rule_id, work_updates={"lifecycle_stage": "PRE_SANCTION"}
    ) == "NOT_APPLICABLE"
    assert _run_rule(
        rule_id, work_updates={"expected_completion_date": pd.NaT}
    ) == "INSUFFICIENT_DATA"


def test_rule_public_use_all_results():
    rule_id = "MPLADS-3.2.17-PUBLIC-USE"
    assert _run_rule(rule_id) == "PASS"
    assert _run_rule(
        rule_id, asset_rows=[_asset(public_use_date=pd.Timestamp("2026-09-02"))]
    ) == "REVIEW"
    assert _run_rule(
        rule_id, work_updates={"lifecycle_stage": "EXECUTION"}
    ) == "NOT_APPLICABLE"
    assert _run_rule(rule_id, asset_rows=[]) == "INSUFFICIENT_DATA"


def test_rule_completion_photo_all_results():
    rule_id = "MPLADS-4.5.3-COMPLETION-PHOTO"
    assert _run_rule(rule_id) == "PASS"
    assert _run_rule(
        rule_id, asset_rows=[_asset(completion_photo_reference="")]
    ) == "NON_COMPLIANT"
    assert _run_rule(
        rule_id, work_updates={"lifecycle_stage": "EXECUTION"}
    ) == "NOT_APPLICABLE"
    assert _run_rule(rule_id, asset_rows=[]) == "INSUFFICIENT_DATA"


def test_rule_asset_handover_all_results():
    rule_id = "MPLADS-11.3-ASSET-HANDOVER"
    assert _run_rule(rule_id) == "PASS"
    assert _run_rule(
        rule_id, asset_rows=[_asset(handover_date=pd.Timestamp("2026-09-02"))]
    ) == "REVIEW"
    assert _run_rule(
        rule_id, work_updates={"lifecycle_stage": "EXECUTION"}
    ) == "NOT_APPLICABLE"
    assert _run_rule(rule_id, asset_rows=[]) == "INSUFFICIENT_DATA"


def test_rule_asset_register_all_results():
    rule_id = "MPLADS-4.5.8-ASSET-REGISTER"
    assert _run_rule(rule_id) == "PASS"
    assert _run_rule(
        rule_id, asset_rows=[_asset(asset_register_entry="No")]
    ) == "NON_COMPLIANT"
    assert _run_rule(
        rule_id, asset_rows=[_asset(asset_register_entry="Pending")]
    ) == "REVIEW"
    assert _run_rule(
        rule_id, asset_rows=[_asset(handover_date=pd.Timestamp("2026-09-02"))]
    ) == "NOT_APPLICABLE"
    assert _run_rule(
        rule_id, asset_rows=[_asset(asset_register_entry=None)]
    ) == "INSUFFICIENT_DATA"


def test_rule_completion_uc_all_results():
    rule_id = "MPLADS-11.2-COMPLETION-UC"
    assert _run_rule(rule_id) == "PASS"
    assert _run_rule(
        rule_id,
        asset_rows=[
            _asset(
                utilization_certificate_status="Pending",
                utilization_certificate_date=pd.NaT,
            )
        ],
    ) == "REVIEW"
    assert _run_rule(
        rule_id, work_updates={"lifecycle_stage": "EXECUTION"}
    ) == "NOT_APPLICABLE"
    assert _run_rule(
        rule_id,
        asset_rows=[_asset(utilization_certificate_status=None)],
    ) == "INSUFFICIENT_DATA"


@pytest.fixture(scope="module")
def guideline_extract(project_paths):
    path = project_paths.guidelines_dir / GUIDELINE_FILENAME
    chunks, diagnostics = extract_guideline_chunks(path)
    return path, chunks, diagnostics


def test_guideline_extraction_hash_pages_and_clause_lookup(guideline_extract):
    path, chunks, diagnostics = guideline_extract
    assert diagnostics["page_count"] == EXPECTED_PAGE_COUNT == 70
    assert diagnostics["extractable_page_count"] == 64
    assert len(chunks) == diagnostics["chunk_count"] == 61
    assert all(chunk["source_file_sha256"] == sha256_file(path) for chunk in chunks)
    assert get_guideline_chunk("MPLADS-2023-P020", chunks)["page_start"] == 20
    assert get_guideline_clause("3.2.12", chunks)[0]["page_start"] == 20
    assert get_guideline_clause("11.3", chunks)[0]["page_start"] == 51


def test_registry_covers_rules_and_every_reference_resolves(guideline_extract):
    _, chunks, _ = guideline_extract
    registry = build_rule_registry()
    implemented = [
        item for item in registry["rules"] if item["implemented_status"] == "IMPLEMENTED"
    ]
    assert registry["implemented_rule_count"] == len(IMPLEMENTED_RULES) == 8
    assert registry["unimplemented_candidate_count"] == 9
    assert {item["rule_id"] for item in implemented} == set(IMPLEMENTED_RULE_BY_ID)
    for entry in implemented:
        assert entry["guideline_clause"]
        assert entry["guideline_page"]
        assert entry["official_reference"]
        assert entry["test_coverage_identifier"]
        for chunk_id in entry["guideline_chunk_ids"]:
            get_guideline_chunk(chunk_id, chunks)
        for clause in entry["guideline_clause"].split(";"):
            get_guideline_clause(clause.strip(), chunks)


def test_compliance_engine_full_summary_cardinality(
    feature_table, operational_bundle, snapshot_date
):
    evidence = build_compliance_evidence(
        feature_table, operational_bundle.assets, snapshot_date
    )
    summary = build_compliance_summary(feature_table, evidence)
    assert len(evidence) == 3_000 * len(IMPLEMENTED_RULES)
    assert len(summary) == summary["work_id"].nunique() == 3_000
    count_columns = [
        "rules_passed_count",
        "rules_review_count",
        "rules_non_compliant_count",
        "rules_insufficient_data_count",
        "rules_not_applicable_count",
    ]
    assert summary[count_columns].sum(axis=1).eq(len(IMPLEMENTED_RULES)).all()
    assert set(evidence["result"]).issubset(
        {result.value for result in ComplianceResult}
    )


def test_compliance_production_source_has_no_prohibited_inputs_or_decision_service(
    project_paths,
):
    directory = project_paths.project_root / "code" / "intelligence" / "compliance"
    forbidden = (
        "duplicate_group_reference",
        "07_anomaly_ground_truth",
        "load_evaluation_ground_truth",
        "injected_anomaly_",
        "expected_risk_",
        "grok",
        "openai",
        "anthropic",
    )
    for path in directory.glob("*.py"):
        source = path.read_text(encoding="utf-8").casefold()
        assert not any(term in source for term in forbidden)
        assert re.search(r"\bllm\b", source) is None


def test_day5_outputs_and_language_guardrails(project_paths):
    processed = project_paths.processed_data_dir
    evidence = pd.read_csv(processed / "compliance_evidence.csv")
    summary = pd.read_csv(processed / "compliance_summary.csv")
    manifest = json.loads(
        (processed / "guideline_manifest.json").read_text(encoding="utf-8")
    )
    chunks = json.loads(
        (processed / "guideline_chunks.json").read_text(encoding="utf-8")
    )
    assert len(summary) == summary["work_id"].nunique() == 3_000
    assert manifest["sha256"] == _sha256(
        project_paths.guidelines_dir / GUIDELINE_FILENAME
    )
    assert all(1 <= item["page_start"] <= item["page_end"] <= 70 for item in chunks)
    assert set(evidence["result"]).issubset(
        {result.value for result in ComplianceResult}
    )
    production_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            processed / "compliance_evidence.csv",
            processed / "compliance_summary.csv",
            processed / "compliance_rule_registry.json",
            processed / "day5_compliance_summary.json",
        )
    ).casefold()
    assert not any(term in production_text for term in ("fraudulent", "guilty", "corrupt"))
    assert "risk_score" not in production_text


def test_prior_day_artifacts_are_frozen(project_paths):
    for relative_path, expected in PRIOR_DAY_HASHES.items():
        assert _sha256(project_paths.project_root / relative_path) == expected

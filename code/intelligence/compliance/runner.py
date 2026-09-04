"""Generate verified guideline and deterministic Day-5 compliance artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd

from intelligence.data.config import load_settings
from intelligence.data.loader import load_operational_data
from intelligence.data.paths import ProjectPaths

from .engine import build_compliance_evidence, build_compliance_summary
from .guideline import (
    GUIDELINE_FILENAME,
    get_guideline_chunk,
    get_guideline_clause,
    write_guideline_artifacts,
)
from .models import ComplianceResult
from .rule_registry import (
    UNIMPLEMENTED_RULE_CANDIDATES,
    write_rule_registry,
)
from .rules import IMPLEMENTED_RULES


@dataclass(frozen=True, slots=True)
class ComplianceArtifacts:
    evidence: Path
    summary: Path
    rule_registry: Path
    guideline_chunks: Path
    guideline_manifest: Path
    day5_summary: Path


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _status_counts(frame: pd.DataFrame) -> dict[str, int]:
    counts = frame["result"].value_counts().to_dict()
    return {result.value: int(counts.get(result.value, 0)) for result in ComplianceResult}


def _validate_rule_traceability(chunks: list[dict[str, Any]]) -> None:
    for rule in IMPLEMENTED_RULES:
        spec = rule.spec
        for chunk_id in spec.guideline_chunk_ids:
            get_guideline_chunk(chunk_id, chunks)
        for clause in (item.strip() for item in spec.guideline_clause.split(";")):
            get_guideline_clause(clause, chunks)


def run_compliance_engine(
    paths: ProjectPaths | None = None,
) -> ComplianceArtifacts:
    """Run Day 5 without rewriting any prior-day artifact."""

    resolved = paths or ProjectPaths.discover()
    settings = load_settings(resolved)
    processed = resolved.ensure_processed_data_dir().resolve()
    expected = (resolved.project_root / "data" / "processed").resolve()
    if processed != expected:
        raise ValueError(f"Day-5 outputs must use {expected}, not {processed}")

    feature_path = processed / "project_features.csv"
    if not feature_path.is_file():
        raise FileNotFoundError("Day 5 requires frozen project_features.csv")
    date_columns = [
        "recommendation_date",
        "sanction_date_as_of",
        "expected_completion_date",
    ]
    features = pd.read_csv(feature_path, parse_dates=date_columns)
    if len(features) != 3_000 or not features["work_id"].is_unique:
        raise ValueError("Day 5 requires 3,000 unique frozen feature rows")
    bundle = load_operational_data(resolved)

    guideline_path = resolved.guidelines_dir / GUIDELINE_FILENAME
    manifest_path, chunks_path, chunks, manifest = write_guideline_artifacts(
        guideline_path, processed
    )
    if manifest["verification_status"] != "VERIFIED_IDENTITY_AND_EDITION":
        raise RuntimeError("Guideline identity was not verified")
    _validate_rule_traceability(chunks)

    registry_path = write_rule_registry(processed / "compliance_rule_registry.json")
    evidence = build_compliance_evidence(
        features,
        bundle.assets,
        settings.as_of_date,
    )
    summary = build_compliance_summary(features, evidence)
    evidence_path = processed / "compliance_evidence.csv"
    summary_path = processed / "compliance_summary.csv"
    evidence.to_csv(evidence_path, index=False, encoding="utf-8")
    summary.to_csv(summary_path, index=False, encoding="utf-8")

    by_rule = {
        str(rule_id): _status_counts(group)
        for rule_id, group in evidence.groupby("rule_id", sort=True)
    }
    by_category = {
        str(category): _status_counts(group)
        for category, group in evidence.groupby("rule_category", sort=True)
    }
    day5_payload = {
        "artifact_type": "Day-5 deterministic compliance evidence summary",
        "as_of_date": settings.as_of_date.isoformat(),
        "governance": (
            "Rule outcomes are clause-linked deterministic evidence for authorized "
            "human review; counts are not a final project risk score."
        ),
        "verified_guideline_identity": {
            "document_title": manifest["document_title"],
            "guideline_version": manifest["guideline_version"],
            "effective_date": manifest["effective_date"],
            "official_source_url": manifest["official_source_url"],
            "verification_date": manifest["verification_date"],
        },
        "guideline_sha256": manifest["sha256"],
        "guideline_page_count": manifest["page_count"],
        "guideline_extractable_page_count": manifest["extractable_page_count"],
        "guideline_chunk_count": manifest["chunk_count"],
        "implemented_rule_count": len(IMPLEMENTED_RULES),
        "unimplemented_candidate_rule_count": len(UNIMPLEMENTED_RULE_CANDIDATES),
        "result_counts_by_rule": by_rule,
        "result_counts_by_category": by_category,
        "overall_result_counts": _status_counts(evidence),
        "works_with_review_evidence": int(
            evidence.loc[evidence["result"].eq("REVIEW"), "work_id"].nunique()
        ),
        "works_with_deterministic_non_compliant_evidence": int(
            evidence.loc[evidence["result"].eq("NON_COMPLIANT"), "work_id"].nunique()
        ),
        "works_with_insufficient_data_evidence": int(
            evidence.loc[evidence["result"].eq("INSUFFICIENT_DATA"), "work_id"].nunique()
        ),
        "artifact_paths": {
            "compliance_evidence": str(evidence_path),
            "compliance_summary": str(summary_path),
            "compliance_rule_registry": str(registry_path),
            "guideline_chunks": str(chunks_path),
            "guideline_manifest": str(manifest_path),
        },
    }
    day5_summary_path = _write_json(
        processed / "day5_compliance_summary.json", day5_payload
    )
    return ComplianceArtifacts(
        evidence=evidence_path,
        summary=summary_path,
        rule_registry=registry_path,
        guideline_chunks=chunks_path,
        guideline_manifest=manifest_path,
        day5_summary=day5_summary_path,
    )


def main() -> int:
    artifacts = run_compliance_engine()
    print(f"Compliance evidence: {artifacts.evidence}")
    print(f"Compliance summary: {artifacts.summary}")
    print(f"Rule registry: {artifacts.rule_registry}")
    print(f"Guideline chunks: {artifacts.guideline_chunks}")
    print(f"Guideline manifest: {artifacts.guideline_manifest}")
    print(f"Day-5 summary: {artifacts.day5_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

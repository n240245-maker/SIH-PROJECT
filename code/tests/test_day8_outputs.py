"""Day-8 artifact outputs plus frozen Day-7 and source integrity."""

from __future__ import annotations

import hashlib
import json


FROZEN_DAY7_OUTPUT_HASHES = {
    "data/processed/trend_timeseries.csv": "375F0938631B084D973B01A0B8656CAA83220217319B10C981CDD90029846EA8",
    "data/processed/trend_alerts.csv": "261FFDD9CB825C595F20AF85A76263A336518456A4F60EAF432767194D0067B1",
    "data/processed/detector_hotspots.csv": "B96CA3E8AE88CFA15A8E48BF8C790F4E30998A189357210BEF16ED478B79FA61",
    "data/processed/work_trend_context.csv": "3C7B8B34AA5CFC1F90AFD5F93A11EEE35A671D4D19841BB1B9A6D3B9A014D119",
    "data/processed/risk_fusion_policy.json": "D44DAC7E132EADAF58AB3AED9888429F0141ACF286ADC0CEABF2B62871B97646",
    "data/processed/review_priority_evidence.csv": "4972463BC69A50DEF8442E9244B23652647423BA073BF9D48E8D6D2230BB5755",
    "data/processed/review_priority_scores.csv": "982809F441DCEF8EE4EB835A216F81747D9820B3036DC66EE21EFB76C14B2696",
    "data/processed/review_priority_queue.csv": "91C414F4D71F54B1413DADE6EDDF1CA2246DDFC948DAF871DD0BC2324BBD6A75",
    "data/processed/review_alerts.csv": "C02829B7B873168EBB4E6F6D71C053A7167DD79F107A644D3226F0C6A1DB56FE",
    "data/processed/review_priority_authority_summary.csv": "ACD327341E3DB617638F531C16F5C426CED248AE75A01235FEF527F131721B18",
    "data/processed/day7_intelligence_summary.json": "AF82A05A891F6963251735935056370D5E6849C366F2DCDCC2BF225FEAEB2B3E",
    "data/processed/guideline_chunks.json": "699933873A80B52F01D87AE7DF30C501A4116B3D7E71A03F19DF777C0CDABF77",
    "data/processed/guideline_manifest.json": "04789FB28A3C824949B9D4125D633B4DD45FE32A359F23A4D2A7DA3E2C10E2D0",
    "data/processed/compliance_rule_registry.json": "55841F2468AECAB0FE4545932D343036ADCA4C999E3250672B1167F1F16DF6BE",
}


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def test_required_day8_artifacts_and_summary(project_paths):
    processed = project_paths.processed_data_dir
    required = [
        "guideline_embeddings.npy",
        "guideline_embedding_metadata.json",
        "rag_retrieval_audit.json",
        "explanation_context.jsonl",
        "day8_rag_summary.json",
        "evaluation/day8_groq_live_smoke.json",
    ]
    assert all((processed / name).is_file() for name in required)
    summary = json.loads((processed / "day8_rag_summary.json").read_text())
    assert summary["chunk_count"] == 61
    assert summary["explanation_context_count"] == 3_000
    assert summary["llm_provider"] == "groq"
    assert summary["configured_model"] == "openai/gpt-oss-120b"
    assert summary["api_base"] == "https://api.groq.com/openai/v1"
    assert summary["api_endpoint"] == "/chat/completions"
    assert summary["external_tools_enabled"] is False
    assert summary["live_smoke_status"] in {
        "SKIPPED_NO_GROQ_API_KEY",
        "SKIPPED_NOT_EXPLICITLY_REQUESTED",
        "COMPLETED",
        "COMPLETED_WITH_FALLBACK",
    }
    assert summary["integrity"]["prior_artifacts_unchanged"] is True
    assert summary["integrity"]["demo_data_hashes_unchanged"] is True


def test_retrieval_audit_covers_required_cases(project_paths):
    audit = json.loads(
        (project_paths.processed_data_dir / "rag_retrieval_audit.json").read_text()
    )
    categories = {row["category"] for row in audit["representative_cases"]}
    assert {
        "COMPLIANCE",
        "DUPLICATE",
        "PAYMENT_EXECUTION",
        "COST_OVERRUN_WARNING",
        "TREND_CONTEXT",
    }.issubset(categories)
    assert audit["direct_compliance_references_tested"] > 0
    assert all(
        row["direct_references_retained"]
        for row in audit["representative_cases"]
        if row["category"] == "COMPLIANCE"
    )


def test_day7_and_guideline_artifacts_remain_byte_identical(project_paths):
    for relative, expected in FROZEN_DAY7_OUTPUT_HASHES.items():
        assert _sha256(project_paths.project_root / relative) == expected


def test_day8_local_index_and_retrieval_audit_remain_valid(project_paths):
    expected = {
        "data/processed/guideline_embeddings.npy": "D2F9C6C59444BAD4EC4B3C8C9D28271EB31B920332DEAB1A0EEF4D9117E236F8",
        "data/processed/guideline_embedding_metadata.json": "840E82553EF27F4093F32E5BCC1D3B68C3CF988A6CF940C6E3445EBAAD5D9CFB",
        "data/processed/rag_retrieval_audit.json": "C478C66C89D6D10954A0D269027999DA9FE72372DFF8B3F6BF603E5F2A632838",
    }
    for relative, digest in expected.items():
        assert _sha256(project_paths.project_root / relative) == digest


def test_no_real_groq_secret_is_committed(project_paths):
    example = (project_paths.project_root / ".env.example").read_text(encoding="utf-8")
    assert "GROQ_API_KEY=\n" in example.replace("\r\n", "\n")
    summary = (project_paths.processed_data_dir / "day8_rag_summary.json").read_text()
    smoke = (
        project_paths.processed_data_dir / "evaluation/day8_groq_live_smoke.json"
    ).read_text()
    assert "gsk_" not in (example + summary + smoke)

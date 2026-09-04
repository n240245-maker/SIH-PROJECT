"""Output-location and immutable-source checks."""

from __future__ import annotations

import hashlib
import json

import pandas as pd

from intelligence.data.reports import write_validation_outputs


EXPECTED_DEMO_HASHES = {
    "00_manifest.csv": "FED603CC37851D9BFA29ADD517427D984FCCEFB22B29F0D940762FF2F308EF12",
    "01_mp_master.csv": "4A9BC44CC74FE24D0495704B062937C903CF7B9C7B1E60B8355BFD6EF4BCA4C9",
    "02_agencies_vendors.csv": "DFBED64F7114DF4DC7E227320E132500728171F7F47F3E245C5DF0671388A89A",
    "03_works.csv": "D462366241D83523725C6158F983822D5E6435BDCF53E414B119DECE457E61DC",
    "04_payments.csv": "B4A860D1204D14092B0766BA9952BC536E125248ED34343E9380FA13E8892620",
    "05_progress.csv": "1F866CC550EB66A3D3B7840807ECE05451D24901463F928FE0E96C8847923E1B",
    "06_assets_compliance.csv": "A624CFF43BB007A94E4C312FBCB876638B6FE9FA4DCD4F071E689ADA5671FCD2",
    "07_anomaly_ground_truth.csv": "E9E3E810FFC1EB7B6ABFF029C3A0B520889D3525CD2AF3E2B55AEC350EE9A97D",
    "08_data_dictionary.csv": "270ADA5B985E3E60BCFE1D3577747DB5D5BB9CFB32D482EBF6CCFC58DC1140AF",
    "09_source_acquisition_plan.csv": "98D83B35F22484B88F7B50EC3A7A547F121694DE69A752011195B6EAEBDFDCC2",
    "Allocated Limit for Honble MPs.csv": "775F7CB9F3F29B180CB7461EAE23215BC7FAF6439760F5D7375A6755221BAFD8",
    "Amount consented for Calamity.csv": "7F75CF2105B1084AC47BA5E4C6A794A3C878EDEA5D66BF47FDF6C9C26762E4D6",
}


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def test_demo_data_hashes_are_unchanged(project_paths):
    actual = {
        path.name: _sha256(path)
        for path in sorted(project_paths.demo_data_dir.glob("*.csv"))
    }
    assert actual == EXPECTED_DEMO_HASHES


def test_validation_outputs_are_only_written_to_processed_directory(
    project_paths,
    validation_result,
):
    summary_path, issues_path = write_validation_outputs(validation_result, project_paths)
    expected_directory = (project_paths.project_root / "data" / "processed").resolve()
    assert summary_path.parent == expected_directory
    assert issues_path.parent == expected_directory
    assert summary_path.name == "validation_summary.json"
    assert issues_path.name == "validation_issues.csv"
    assert summary_path.is_file()
    assert issues_path.is_file()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    issues = pd.read_csv(issues_path)
    assert summary["as_of_date"] == "2026-09-01"
    assert summary["issue_counts_by_severity"]["ERROR"] == 0
    assert len(issues) == sum(summary["issue_counts_by_severity"].values())
    assert not (project_paths.demo_data_dir / summary_path.name).exists()
    assert not (project_paths.demo_data_dir / issues_path.name).exists()

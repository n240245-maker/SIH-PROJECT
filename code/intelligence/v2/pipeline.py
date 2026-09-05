"""Build governed demo-v2 features, models, evaluation, and serving artifacts."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from intelligence.data.paths import ProjectPaths
from intelligence.v2.geo import (
    completion_evidence_status,
    first_working_days,
    haversine_metres,
    location_status,
    monthly_evidence_status,
)
from intelligence.v2.loader import (
    V2DataBundle,
    load_v2_data,
    load_v2_evaluation_ground_truth,
    v2_data_dir,
    v2_models_dir,
    v2_processed_dir,
    verify_v2_integrity,
)


SEED = 26102
MODEL_VERSION = "DEMO_V2_MODELS_1_0"
POLICY_VERSION = "REVIEW_PRIORITY_POLICY_V0_1_DEMO_V2"
AS_OF = date(2026, 9, 5)

NUMERIC_FEATURES = [
    "technical_estimate_amount_inr", "sanctioned_amount_inr",
    "estimate_to_sanction_ratio", "planned_duration_days", "schedule_elapsed_ratio",
    "released_to_sanction_ratio", "expenditure_to_sanction_ratio",
    "physical_progress_pct", "financial_progress_pct", "financial_physical_gap_pct",
    "progress_velocity_pct_per_30d", "payment_count", "sanction_revision_count",
    "payment_chronology_flag",
]
CATEGORICAL_FEATURES = ["sector"]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
PROHIBITED_FEATURES = {
    "final_actual_expenditure_inr", "actual_completion_date", "cost_overrun_target",
    "anomaly_label", "anomaly_types", "duplicate_group_id", "scenario_tags",
}


@dataclass(slots=True)
class BuildResult:
    processed_dir: Path
    models_dir: Path
    summary: dict[str, Any]


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding="utf-8")


def _date(value: Any) -> date | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    return date.fromisoformat(str(value)[:10])


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator > 0 else float("nan")


def _groups(frame: pd.DataFrame, key: str = "work_id") -> dict[str, pd.DataFrame]:
    return {str(value): group.copy() for value, group in frame.groupby(key, sort=False)}


def _snapshot(
    work: pd.Series,
    cutoff: date,
    payments: pd.DataFrame,
    progress: pd.DataFrame,
) -> dict[str, Any]:
    sanctioned = float(work.get("sanctioned_amount_inr") or 0)
    estimate = float(work.get("technical_estimate_amount_inr") or 0)
    start = _date(work.get("actual_start_date"))
    expected_completion = _date(work.get("expected_completion_date"))
    planned_days = (expected_completion - start).days if start and expected_completion else float("nan")
    elapsed = (cutoff - start).days if start else float("nan")

    current_payments = payments.loc[
        pd.to_datetime(payments.get("payment_release_date"), errors="coerce").dt.date.le(cutoff)
    ].copy() if len(payments) else payments
    released = float(pd.to_numeric(current_payments.get("payment_amount_inr"), errors="coerce").sum()) if len(current_payments) else 0.0
    chronology = False
    if len(current_payments):
        request = pd.to_datetime(current_payments["payment_request_date"], errors="coerce")
        authorization = pd.to_datetime(current_payments["authorization_date"], errors="coerce")
        chronology = bool(authorization.lt(request).any())

    current_progress = progress.loc[
        pd.to_datetime(progress.get("report_date"), errors="coerce").dt.date.le(cutoff)
    ].copy() if len(progress) else progress
    current_progress = current_progress.sort_values("report_date") if len(current_progress) else current_progress
    physical = financial = velocity = float("nan")
    if len(current_progress):
        latest = current_progress.iloc[-1]
        physical = float(latest["physical_progress_pct"])
        financial = float(latest["financial_progress_pct"])
        if len(current_progress) >= 2:
            earlier = current_progress.iloc[-2]
            days = max(1, (_date(latest["report_date"]) - _date(earlier["report_date"])).days)
            velocity = (physical - float(earlier["physical_progress_pct"])) / days * 30
    expenditure = released
    return {
        "work_id": str(work["work_id"]),
        "snapshot_date": cutoff.isoformat(),
        "technical_estimate_amount_inr": estimate,
        "sanctioned_amount_inr": sanctioned,
        "estimate_to_sanction_ratio": _safe_ratio(estimate, sanctioned),
        "planned_duration_days": planned_days,
        "schedule_elapsed_ratio": _safe_ratio(elapsed, planned_days),
        "released_to_sanction_ratio": _safe_ratio(released, sanctioned),
        "expenditure_to_sanction_ratio": _safe_ratio(expenditure, sanctioned),
        "physical_progress_pct": physical,
        "financial_progress_pct": financial,
        "financial_physical_gap_pct": financial - physical,
        "progress_velocity_pct_per_30d": velocity,
        "payment_count": len(current_payments),
        "sanction_revision_count": float(work.get("sanction_revision_count") or 0),
        "payment_chronology_flag": int(chronology),
        "sector": str(work.get("sector") or "Unknown"),
    }


def build_cost_snapshots(bundle: V2DataBundle) -> tuple[pd.DataFrame, pd.DataFrame]:
    payment_groups = _groups(bundle.payments)
    progress_groups = _groups(bundle.progress)
    training: list[dict[str, Any]] = []
    serving: list[dict[str, Any]] = []
    empty_payments = bundle.payments.iloc[0:0]
    empty_progress = bundle.progress.iloc[0:0]
    for _, work in bundle.works.iterrows():
        work_id = str(work["work_id"])
        lifecycle = str(work["lifecycle_stage"])
        start = _date(work.get("actual_start_date"))
        expected = _date(work.get("expected_completion_date"))
        completion = _date(work.get("actual_completion_date"))
        if lifecycle == "COMPLETION" and start and expected and completion:
            planned_days = max(60, (expected - start).days)
            candidate = start.fromordinal(start.toordinal() + int(planned_days * 0.60))
            cutoff = min(candidate, completion.fromordinal(completion.toordinal() - 30))
            if cutoff > start:
                row = _snapshot(
                    work, cutoff, payment_groups.get(work_id, empty_payments),
                    progress_groups.get(work_id, empty_progress),
                )
                final = float(work["final_actual_expenditure_inr"])
                sanctioned = float(work["sanctioned_amount_inr"])
                row["cost_overrun_target"] = int(final > sanctioned)
                training.append(row)
        if lifecycle == "EXECUTION" and start:
            serving.append(_snapshot(
                work, AS_OF, payment_groups.get(work_id, empty_payments),
                progress_groups.get(work_id, empty_progress),
            ))
    return pd.DataFrame(training), pd.DataFrame(serving)


def _preprocessor() -> ColumnTransformer:
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer([
        ("numeric", numeric, NUMERIC_FEATURES),
        ("categorical", categorical, CATEGORICAL_FEATURES),
    ])


def _metric_set(y_true: pd.Series, probabilities: np.ndarray, threshold: float) -> dict[str, Any]:
    prediction = probabilities >= threshold
    return {
        "positive_prevalence": float(y_true.mean()),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "precision": float(precision_score(y_true, prediction, zero_division=0)),
        "recall": float(recall_score(y_true, prediction, zero_division=0)),
        "f1": float(f1_score(y_true, prediction, zero_division=0)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "threshold": float(threshold),
        "confusion_matrix": confusion_matrix(y_true, prediction, labels=[0, 1]).tolist(),
    }


def _best_threshold(y_true: pd.Series, probabilities: np.ndarray) -> float:
    candidates = np.linspace(0.15, 0.85, 71)
    scores = [f1_score(y_true, probabilities >= value, zero_division=0) for value in candidates]
    return float(candidates[int(np.argmax(scores))])


def train_cost_models(
    snapshots: pd.DataFrame, serving: pd.DataFrame, processed: Path, models: Path
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if PROHIBITED_FEATURES & set(MODEL_FEATURES):
        raise RuntimeError("Prohibited future/outcome field entered the model feature schema")
    development, test = train_test_split(
        snapshots, test_size=0.20, random_state=SEED,
        stratify=snapshots["cost_overrun_target"],
    )
    train, validation = train_test_split(
        development, test_size=0.25, random_state=SEED,
        stratify=development["cost_overrun_target"],
    )
    split_rows = pd.concat([
        train[["work_id"]].assign(split="TRAIN"),
        validation[["work_id"]].assign(split="VALIDATION"),
        test[["work_id"]].assign(split="TEST"),
    ], ignore_index=True)
    if split_rows["work_id"].duplicated().any():
        raise RuntimeError("A work appears in more than one model split")
    split_rows.to_csv(processed / "modeling" / "cost_model_split.csv", index=False)

    positive = int(train["cost_overrun_target"].sum())
    negative = len(train) - positive
    candidates = {
        "logistic_regression": LogisticRegression(
            max_iter=1_000, class_weight="balanced", random_state=SEED
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=260, min_samples_leaf=6, class_weight="balanced_subsample",
            random_state=SEED, n_jobs=-1,
        ),
        "xgboost": XGBClassifier(
            n_estimators=260, max_depth=4, learning_rate=0.035,
            subsample=0.85, colsample_bytree=0.85,
            eval_metric="logloss", random_state=SEED, n_jobs=1,
            scale_pos_weight=negative / max(positive, 1),
        ),
    }
    reports: dict[str, Any] = {}
    fitted: dict[str, Pipeline] = {}
    for name, estimator in candidates.items():
        pipeline = Pipeline([("preprocessor", _preprocessor()), ("model", estimator)])
        pipeline.fit(train[MODEL_FEATURES], train["cost_overrun_target"])
        validation_prob = pipeline.predict_proba(validation[MODEL_FEATURES])[:, 1]
        threshold = _best_threshold(validation["cost_overrun_target"], validation_prob)
        test_prob = pipeline.predict_proba(test[MODEL_FEATURES])[:, 1]
        reports[name] = {
            "validation": _metric_set(validation["cost_overrun_target"], validation_prob, threshold),
            "test": _metric_set(test["cost_overrun_target"], test_prob, threshold),
        }
        fitted[name] = pipeline

    selected = max(
        reports,
        key=lambda name: (
            reports[name]["validation"]["pr_auc"],
            reports[name]["validation"]["roc_auc"],
        ),
    )
    selected_report = reports[selected]
    prevalence = selected_report["test"]["positive_prevalence"]
    useful = (
        selected_report["test"]["roc_auc"] >= 0.65
        and selected_report["test"]["pr_auc"] >= prevalence + 0.05
    )
    quality = "SYNTHETIC_HOLDOUT_SUPPORTED" if useful else "SYNTHETIC_HOLDOUT_WEAK"
    selected_path = models / "cost_overrun" / f"{selected}.joblib"
    selected_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(fitted[selected], selected_path)

    serving_scores = serving[["work_id"]].copy()
    probabilities = fitted[selected].predict_proba(serving[MODEL_FEATURES])[:, 1]
    threshold = reports[selected]["validation"]["threshold"]
    serving_scores["model_score_0_1"] = probabilities
    serving_scores["serving_percentile_0_100"] = pd.Series(probabilities).rank(pct=True, method="average") * 100
    serving_scores["early_warning_status"] = np.where(
        not useful,
        "UNAVAILABLE",
        np.where(probabilities >= min(0.95, threshold * 1.35), "HIGH_EARLY_WARNING",
                 np.where(probabilities >= threshold, "ELEVATED_EARLY_WARNING", "NO_EARLY_WARNING")),
    )
    serving_scores["model_name"] = selected
    serving_scores["model_version"] = MODEL_VERSION
    serving_scores["model_quality_status"] = quality
    serving_scores["prediction_timestamp"] = f"{AS_OF.isoformat()}T00:00:00+00:00"

    report = {
        "evaluation_label": "Synthetic Holdout Evaluation",
        "target": "final_actual_expenditure_inr > sanctioned_amount_inr",
        "selected_model": selected, "selected_model_path": str(selected_path),
        "model_version": MODEL_VERSION, "serving_eligible": useful,
        "model_quality_status": quality, "calibration": "NOT_APPLIED",
        "candidate_metrics": reports,
        "feature_schema": MODEL_FEATURES,
        "prohibited_features": sorted(PROHIBITED_FEATURES),
        "split_counts": split_rows["split"].value_counts().to_dict(),
        "limitations": [
            "Evaluation uses deterministic synthetic demo data and is not real-world performance.",
            "The model is an execution-stage early warning, not an observed cost-overrun fact.",
            "Observed final expenditure remains authoritative when available.",
        ],
    }
    _json(processed / "evaluation" / "cost_model_evaluation.json", report)
    _json(models / "cost_overrun" / "feature_schema.json", report)
    snapshots.to_csv(processed / "modeling" / "cost_model_snapshots.csv", index=False)
    serving_scores.to_csv(processed / "cost_overrun_scores.csv", index=False)
    return serving_scores, report


def build_work_features(bundle: V2DataBundle) -> pd.DataFrame:
    works = bundle.works.copy()
    works["sanctioned_amount_inr"] = pd.to_numeric(works["sanctioned_amount_inr"], errors="coerce")
    works["current_expenditure_inr"] = pd.to_numeric(works["current_expenditure_inr"], errors="coerce")
    works["final_actual_expenditure_inr"] = pd.to_numeric(works["final_actual_expenditure_inr"], errors="coerce")
    payment = bundle.payments.copy()
    payment["authorization_before_request"] = pd.to_datetime(payment["authorization_date"]).lt(pd.to_datetime(payment["payment_request_date"]))
    pay_agg = payment.groupby("work_id").agg(
        released_payments_inr=("payment_amount_inr", "sum"),
        payment_count=("payment_id", "count"),
        payment_chronology_flag=("authorization_before_request", "max"),
        latest_payment_release=("payment_release_date", "max"),
    ).reset_index()
    prog = bundle.progress.sort_values(["work_id", "report_date"]).copy()
    latest = prog.groupby("work_id", as_index=False).tail(1)[[
        "work_id", "report_date", "physical_progress_pct", "financial_progress_pct",
        "expected_progress_pct_by_date",
    ]].rename(columns={"report_date": "latest_progress_report"})
    profile = works.merge(pay_agg, on="work_id", how="left", validate="one_to_one")
    profile = profile.merge(latest, on="work_id", how="left", validate="one_to_one")
    profile["payment_count"] = profile["payment_count"].fillna(0).astype(int)
    profile["released_payments_inr"] = profile["released_payments_inr"].fillna(0)
    profile["payment_chronology_flag"] = (
        profile["payment_chronology_flag"].astype("boolean").fillna(False).astype(bool)
    )
    profile["physical_progress_pct"] = profile["physical_progress_pct"].fillna(profile["current_physical_progress_pct"])
    profile["financial_progress_pct"] = profile["financial_progress_pct"].fillna(
        profile["current_expenditure_inr"] / profile["sanctioned_amount_inr"] * 100
    )
    profile["financial_physical_gap_pct"] = profile["financial_progress_pct"] - profile["physical_progress_pct"]
    profile["observed_delay"] = (
        profile["lifecycle_stage"].eq("EXECUTION")
        & pd.to_datetime(profile["expected_completion_date"], errors="coerce").dt.date.lt(AS_OF)
    )
    profile["observed_cost_overrun"] = (
        profile["final_actual_expenditure_inr"].notna()
        & profile["final_actual_expenditure_inr"].gt(profile["sanctioned_amount_inr"])
    )
    profile["release_above_visible_sanction"] = profile["released_payments_inr"].gt(profile["sanctioned_amount_inr"])
    return profile


def build_anomaly_models(
    profile: pd.DataFrame, processed: Path, models: Path
) -> tuple[pd.DataFrame, dict[str, Any]]:
    features = [
        "recommended_amount_inr", "technical_estimate_amount_inr", "sanctioned_amount_inr",
        "released_payments_inr", "current_expenditure_inr", "physical_progress_pct",
        "financial_progress_pct", "financial_physical_gap_pct", "payment_count",
        "sanction_revision_count",
    ]
    output: list[pd.DataFrame] = []
    lifecycle_metadata: dict[str, Any] = {}
    for lifecycle in ("PRE_SANCTION", "EXECUTION", "COMPLETION"):
        current = profile.loc[profile["lifecycle_stage"].eq(lifecycle)].copy()
        lifecycle_features = [
            feature for feature in features
            if current[feature].notna().any() and current[feature].nunique(dropna=True) > 1
        ]
        matrix = current[lifecycle_features]
        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", IsolationForest(
                n_estimators=300, contamination=0.04, random_state=SEED, n_jobs=-1,
            )),
        ])
        pipeline.fit(matrix)
        unusualness = -pipeline.named_steps["model"].score_samples(
            pipeline.named_steps["imputer"].transform(matrix)
        )
        current["anomaly_unusualness"] = unusualness
        current["within_lifecycle_percentile_0_100"] = pd.Series(unusualness, index=current.index).rank(pct=True) * 100
        current["anomaly_flag"] = pipeline.predict(matrix) == -1
        if current["financial_physical_gap_pct"].notna().any():
            medians = current.groupby("sector")["financial_physical_gap_pct"].transform("median")
            mad = current.groupby("sector")["financial_physical_gap_pct"].transform(
                lambda values: (values - values.median()).abs().median()
            )
            current["peer_robust_deviation"] = (
                (current["financial_physical_gap_pct"] - medians)
                / (1.4826 * mad.replace(0, np.nan))
            )
        else:
            current["peer_robust_deviation"] = np.nan
        output.append(current[[
            "work_id", "lifecycle_stage", "anomaly_unusualness",
            "within_lifecycle_percentile_0_100", "anomaly_flag", "peer_robust_deviation",
        ]])
        model_path = models / "anomaly" / f"isolation_forest_{lifecycle.casefold()}.joblib"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, model_path)
        lifecycle_metadata[lifecycle] = {"rows": len(current), "features": lifecycle_features, "model_path": str(model_path)}
    scores = pd.concat(output, ignore_index=True)
    scores.to_csv(processed / "anomaly_scores.csv", index=False)

    # Evaluation labels are loaded only after production fitting/scoring is complete.
    truth = load_v2_evaluation_ground_truth()[["work_id", "anomaly_label"]]
    truth["anomaly_label"] = truth["anomaly_label"].astype(str).str.casefold().eq("true")
    evaluated = scores.merge(truth, on="work_id", validate="one_to_one")
    evaluation = {
        "evaluation_label": "Synthetic Holdout Evaluation",
        "ground_truth_used_for_training": False,
        "roc_auc": float(roc_auc_score(evaluated["anomaly_label"], evaluated["anomaly_unusualness"])),
        "pr_auc": float(average_precision_score(evaluated["anomaly_label"], evaluated["anomaly_unusualness"])),
        "label_prevalence": float(evaluated["anomaly_label"].mean()),
        "lifecycle_models": lifecycle_metadata,
        "limitations": "Synthetic labels evaluate unusualness only and are not production fraud labels.",
    }
    _json(processed / "evaluation" / "anomaly_evaluation.json", evaluation)
    return scores, evaluation


def build_duplicate_index(
    profile: pd.DataFrame, processed: Path, models: Path
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    cache = ProjectPaths.discover().project_root / "code" / "models" / "duplicates" / "sentence_transformers_cache"
    model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2", cache_folder=str(cache), local_files_only=True
    )
    descriptions = profile["work_description"].fillna("").astype(str).tolist()
    embeddings = model.encode(
        descriptions, batch_size=128, show_progress_bar=False,
        normalize_embeddings=True, convert_to_numpy=True,
    ).astype("float32")
    duplicate_dir = models / "duplicates"
    duplicate_dir.mkdir(parents=True, exist_ok=True)
    np.save(duplicate_dir / "work_embeddings.npy", embeddings)
    index = NearestNeighbors(n_neighbors=6, metric="cosine", algorithm="brute", n_jobs=-1)
    index.fit(embeddings)
    distances, neighbours = index.kneighbors(embeddings)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    profile_index = profile.reset_index(drop=True)
    for left_index, candidate_indexes in enumerate(neighbours):
        left = profile_index.iloc[left_index]
        for rank, right_index in enumerate(candidate_indexes[1:], 1):
            if int(right_index) == left_index:
                continue
            right = profile_index.iloc[int(right_index)]
            pair = tuple(sorted((str(left["work_id"]), str(right["work_id"]))))
            if pair in seen:
                continue
            seen.add(pair)
            similarity = float(1 - distances[left_index, rank])
            left_amount = float(left["sanctioned_amount_inr"] or 0)
            right_amount = float(right["sanctioned_amount_inr"] or 0)
            amount_similarity = min(left_amount, right_amount) / max(left_amount, right_amount) if max(left_amount, right_amount) else 0
            distance_metres = haversine_metres(
                float(left["registered_latitude"]), float(left["registered_longitude"]),
                float(right["registered_latitude"]), float(right["registered_longitude"]),
            )
            corroborated = bool(
                similarity >= 0.90
                and str(left["sector"]) == str(right["sector"])
                and amount_similarity >= 0.90
                and distance_metres <= 1_500
            )
            rows.append({
                "work_id_a": pair[0], "work_id_b": pair[1],
                "semantic_similarity_0_1": similarity, "amount_similarity_0_1": amount_similarity,
                "location_distance_metres": distance_metres,
                "same_sector": str(left["sector"]) == str(right["sector"]),
                "same_district": str(left["district"]) == str(right["district"]),
                "review_candidate": corroborated,
                "candidate_language": "Duplicate Work Candidate" if corroborated else "Near-neighbour context only",
            })
    candidates = pd.DataFrame(rows).sort_values(
        ["review_candidate", "semantic_similarity_0_1"], ascending=[False, False]
    )
    candidates.to_csv(processed / "duplicate_candidates.csv", index=False)
    summary_rows: list[dict[str, Any]] = []
    for work_id in profile["work_id"].astype(str):
        related = candidates.loc[
            candidates["work_id_a"].eq(work_id) | candidates["work_id_b"].eq(work_id)
        ]
        best = related.iloc[0] if len(related) else None
        summary_rows.append({
            "work_id": work_id,
            "has_duplicate_candidate": bool(best is not None and best["review_candidate"]),
            "best_candidate_work_id": (
                best["work_id_b"] if best is not None and best["work_id_a"] == work_id else best["work_id_a"]
            ) if best is not None else "",
            "best_similarity_0_1": float(best["semantic_similarity_0_1"]) if best is not None else np.nan,
        })
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(processed / "duplicate_summary.csv", index=False)

    truth = load_v2_evaluation_ground_truth()[["work_id", "duplicate_group_id"]].fillna("")
    known_groups = truth.loc[truth["duplicate_group_id"].ne("")].groupby("duplicate_group_id")["work_id"].apply(set)
    known_pairs = {
        tuple(sorted(pair))
        for group in known_groups
        for pair in __import__("itertools").combinations(group, 2)
    }
    predicted_pairs = {
        (str(row.work_id_a), str(row.work_id_b))
        for row in candidates.loc[candidates["review_candidate"]].itertuples()
    }
    duplicate_report = {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "model_version": MODEL_VERSION,
        "retrieval": "local normalized embeddings + top-5 nearest neighbours",
        "all_pairs_used": False,
        "candidate_threshold": 0.90,
        "corroboration": "same sector, amount similarity >= 0.90, synthetic registered locations within 1,500 metres",
        "known_synthetic_pairs": len(known_pairs),
        "known_pairs_retrieved": len(known_pairs & predicted_pairs),
        "review_candidate_pairs": len(predicted_pairs),
        "candidate_is_not_confirmation": True,
        "ground_truth_used_for_candidate_generation": False,
    }
    _json(processed / "evaluation" / "duplicate_evaluation.json", duplicate_report)
    _json(duplicate_dir / "embedding_metadata.json", duplicate_report)
    return candidates, summary, duplicate_report


def build_geo_status(bundle: V2DataBundle, profile: pd.DataFrame, processed: Path) -> pd.DataFrame:
    geo = bundle.geo_evidence.copy()
    geo["capture_date"] = pd.to_datetime(geo["capture_timestamp"], errors="coerce").dt.date
    geo_groups = _groups(geo)
    rows: list[dict[str, Any]] = []
    for work in profile.to_dict(orient="records"):
        work_id = str(work["work_id"])
        items = geo_groups.get(work_id, geo.iloc[0:0]).sort_values("capture_timestamp")
        monthly = items.loc[items["evidence_stage"].eq("MONTHLY_PROGRESS")]
        completion = items.loc[items["evidence_stage"].eq("COMPLETION")]
        latest = items.iloc[-1] if len(items) else None
        late_count = 0
        for evidence in monthly.to_dict(orient="records"):
            captured = _date(evidence.get("capture_timestamp"))
            if captured is not None:
                window_end = first_working_days(captured.year, captured.month)[-1]
                late_count += int(captured > window_end)
        monthly_status = monthly_evidence_status(
            lifecycle=str(work["lifecycle_stage"]), as_of=AS_OF,
            capture_dates=monthly["capture_date"].dropna().tolist(),
        )
        completion_status = completion_evidence_status(
            lifecycle=str(work["lifecycle_stage"]),
            completion_date=_date(work.get("actual_completion_date")),
            capture_date=(completion.iloc[-1]["capture_date"] if len(completion) else None),
            as_of=AS_OF,
        )
        status, distance = location_status(
            work.get("registered_latitude"), work.get("registered_longitude"),
            latest["latitude"] if latest is not None else None,
            latest["longitude"] if latest is not None else None,
        )
        rows.append({
            "work_id": work_id, "monthly_evidence_status": monthly_status,
            "completion_evidence_status": completion_status,
            "latest_evidence_id": latest["evidence_id"] if latest is not None else "",
            "latest_capture_timestamp": latest["capture_timestamp"] if latest is not None else "",
            "location_status": status, "distance_from_registered_metres": distance,
            "late_evidence_count": late_count,
            "missing_monthly_site_evidence": monthly_status == "OVERDUE" and len(
                monthly.loc[monthly["reporting_month"].eq(AS_OF.strftime("%Y-%m"))]
            ) == 0,
            "geo_warning_only": True,
        })
    result = pd.DataFrame(rows)
    result.to_csv(processed / "geo_evidence_status.csv", index=False)
    return result


def build_record_status(bundle: V2DataBundle, profile: pd.DataFrame, processed: Path) -> pd.DataFrame:
    record_types = [
        "SANCTION_RECORD", "PROGRESS_REPORT", "PAYMENT_RELEASE", "COMPLETION_CERTIFICATE",
        "UTILIZATION_CERTIFICATE", "HANDOVER_RECORD", "PUBLIC_USE_EVIDENCE",
        "COMPLETED_WORK_PHOTO", "ASSET_REGISTER", "AUDIT_RECORD",
    ]
    present = bundle.records.assign(value=1).pivot_table(
        index="work_id", columns="record_type", values="value", aggfunc="max", fill_value=0
    )
    rows: list[dict[str, Any]] = []
    for work in profile.to_dict(orient="records"):
        lifecycle = str(work["lifecycle_stage"])
        values: dict[str, Any] = {"work_id": work["work_id"]}
        for record_type in record_types:
            has_record = bool(work["work_id"] in present.index and present.loc[work["work_id"]].get(record_type, 0))
            if record_type in {"SANCTION_RECORD", "PROGRESS_REPORT", "PAYMENT_RELEASE"}:
                applicable = lifecycle in {"EXECUTION", "COMPLETION"}
            else:
                applicable = lifecycle == "COMPLETION"
            values[record_type.casefold()] = "RECORDED" if has_record else "NOT_RECORDED" if applicable else "NOT_APPLICABLE"
        values["closure_requires_review"] = lifecycle == "COMPLETION" and any(
            values[key.casefold()] == "NOT_RECORDED"
            for key in ("UTILIZATION_CERTIFICATE", "HANDOVER_RECORD", "PUBLIC_USE_EVIDENCE")
        )
        rows.append(values)
    result = pd.DataFrame(rows)
    result.to_csv(processed / "record_status.csv", index=False)
    return result


def build_priority(
    profile: pd.DataFrame, anomaly: pd.DataFrame, duplicate: pd.DataFrame,
    cost: pd.DataFrame, geo: pd.DataFrame, records: pd.DataFrame, processed: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    merged = profile.merge(anomaly, on=["work_id", "lifecycle_stage"], validate="one_to_one")
    merged = merged.merge(duplicate, on="work_id", validate="one_to_one")
    merged = merged.merge(cost[["work_id", "serving_percentile_0_100", "early_warning_status"]], on="work_id", how="left", validate="one_to_one")
    merged = merged.merge(geo, on="work_id", validate="one_to_one")
    merged = merged.merge(records[["work_id", "closure_requires_review"]], on="work_id", validate="one_to_one")
    weights = {
        "PRE_SANCTION": {"ANOMALY": 30, "PEER_DEVIATION": 25, "DUPLICATE_REVIEW": 25},
        "EXECUTION": {"ANOMALY": 10, "PEER_DEVIATION": 10, "DUPLICATE_REVIEW": 15, "PAYMENT_EXECUTION": 25, "OBSERVED_CONDITIONS": 20, "COMPLIANCE": 10, "COST_OVERRUN_PREDICTION": 5},
        # Completion has authoritative final-cost evidence. Keep the full
        # lifecycle budget at 100 points and let deterministic observed
        # conditions dominate without double-counting the same condition in
        # another family.
        "COMPLETION": {
            "ANOMALY": 5,
            "PEER_DEVIATION": 5,
            "DUPLICATE_REVIEW": 10,
            "PAYMENT_EXECUTION": 10,
            "OBSERVED_CONDITIONS": 50,
            "COMPLIANCE": 20,
        },
    }
    evidence_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    alert_rows: list[dict[str, Any]] = []
    peer_strength = merged["peer_robust_deviation"].abs().rank(pct=True).fillna(0) * 100
    for position, row in merged.iterrows():
        lifecycle = str(row["lifecycle_stage"])
        gap_strength = min(100.0, max(0.0, float(row["financial_physical_gap_pct"] or 0) / 75 * 100))
        payment_strength = max(80.0 if row["payment_chronology_flag"] else 0.0, gap_strength)
        observed = 100.0 if row["observed_cost_overrun"] else 80.0 if row["observed_delay"] else 75.0 if row["release_above_visible_sanction"] else 0.0
        compliance = 80.0 if row["closure_requires_review"] else 0.0
        normalized = {
            "ANOMALY": float(row["within_lifecycle_percentile_0_100"]),
            "PEER_DEVIATION": float(peer_strength.loc[position]),
            "DUPLICATE_REVIEW": float(row["best_similarity_0_1"] * 100) if row["has_duplicate_candidate"] else 0.0,
            "PAYMENT_EXECUTION": payment_strength,
            "OBSERVED_CONDITIONS": observed,
            "COMPLIANCE": compliance,
            "COST_OVERRUN_PREDICTION": float(row["serving_percentile_0_100"] or 0) if pd.notna(row["serving_percentile_0_100"]) else 0.0,
        }
        total = 0.0
        for family, weight in weights[lifecycle].items():
            contribution = normalized[family] * weight / 100
            total += contribution
            evidence_rows.append({
                "work_id": row["work_id"], "lifecycle_stage": lifecycle, "family": family,
                "normalized_strength_0_100": normalized[family], "weight_pct": weight,
                "contribution_points": contribution, "policy_version": POLICY_VERSION,
            })
        total = round(min(100.0, total), 6)
        band = "LOW" if total < 25 else "MEDIUM" if total < 50 else "HIGH" if total < 75 else "CRITICAL"
        actionable = bool(
            row["payment_chronology_flag"] or row["observed_delay"] or row["observed_cost_overrun"]
            or row["release_above_visible_sanction"] or row["closure_requires_review"]
            or row["has_duplicate_candidate"] or row["missing_monthly_site_evidence"]
            or row["location_status"] == "LOCATION_REQUIRES_REVIEW"
        )
        score_rows.append({
            "work_id": row["work_id"], "lifecycle_stage": lifecycle,
            "review_priority_score_0_100": total, "review_priority_band": band,
            "requires_review": actionable, "geo_warning_contribution_points": 0,
            "policy_version": POLICY_VERSION,
        })
        signals = [
            ("OBSERVED_COST_OVERRUN", row["observed_cost_overrun"], "Observed final expenditure is above sanction."),
            ("OBSERVED_DELAY", row["observed_delay"], "Expected completion has passed while the work remains in execution."),
            ("PAYMENT_CHRONOLOGY_REVIEW", row["payment_chronology_flag"], "A payment authorization precedes its request date."),
            ("RELEASE_ABOVE_VISIBLE_SANCTION", row["release_above_visible_sanction"], "Released payments exceed the visible sanctioned amount; reconciliation is required."),
            ("MISSING_MONTHLY_SITE_EVIDENCE", row["missing_monthly_site_evidence"], "Current-month site evidence is overdue; this warning adds no Review Priority points."),
            ("LOCATION_REQUIRES_REVIEW", row["location_status"] == "LOCATION_REQUIRES_REVIEW", "Latest capture is outside the prototype 500-metre comparison threshold."),
            ("COMPLETION_RECORDS_REVIEW", row["closure_requires_review"], "One or more applicable closure records are not recorded."),
            ("DUPLICATE_WORK_CANDIDATE", row["has_duplicate_candidate"], "A corroborated semantic near-neighbour requires human comparison; it is not a confirmed duplicate."),
        ]
        for code, present, message in signals:
            if present:
                alert_rows.append({
                    "alert_id": f"V2-{row['work_id']}-{code}", "work_id": row["work_id"],
                    "alert_type": code, "status": "REQUIRES_REVIEW", "message": message,
                })
    scores = pd.DataFrame(score_rows)
    evidence = pd.DataFrame(evidence_rows)
    alerts = pd.DataFrame(alert_rows)
    scores.to_csv(processed / "review_priority_scores.csv", index=False)
    evidence.to_csv(processed / "review_priority_evidence.csv", index=False)
    alerts.to_csv(processed / "review_alerts.csv", index=False)
    _json(processed / "risk_fusion_policy.json", {
        "policy_version": POLICY_VERSION,
        "based_on": "REVIEW_PRIORITY_POLICY_V0_1 lifecycle design; v2 completion weights explicitly prioritize deterministic observed conditions",
        "geo_evidence": "warning-only with exactly zero contribution points",
        "ground_truth_used": False,
        "language": "Review Priority is human-review triage, not wrongdoing probability.",
        "weights": weights,
    })
    return scores, evidence, alerts


def write_profile_and_manifest(
    profile: pd.DataFrame, scores: pd.DataFrame, anomaly: pd.DataFrame,
    duplicate: pd.DataFrame, cost: pd.DataFrame, geo: pd.DataFrame,
    records: pd.DataFrame, processed: Path, models: Path,
) -> dict[str, Any]:
    work_profile = profile.merge(scores, on=["work_id", "lifecycle_stage"], validate="one_to_one")
    work_profile = work_profile.merge(anomaly, on=["work_id", "lifecycle_stage"], validate="one_to_one")
    work_profile = work_profile.merge(duplicate, on="work_id", validate="one_to_one")
    work_profile = work_profile.merge(cost, on="work_id", how="left", validate="one_to_one")
    work_profile = work_profile.merge(geo, on="work_id", validate="one_to_one")
    work_profile = work_profile.merge(records, on="work_id", validate="one_to_one")
    work_profile.to_csv(processed / "work_profile.csv", index=False)

    manifest_rows: list[dict[str, Any]] = []
    for path in sorted(processed.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows = len(pd.read_csv(path, low_memory=False)) if path.suffix == ".csv" else None
            manifest_rows.append({"file": path.relative_to(processed).as_posix(), "sha256": digest, "rows": rows})
    model_rows = []
    for path in sorted(models.rglob("*")):
        if path.is_file():
            model_rows.append({"file": path.relative_to(models).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {
        "dataset_profile": "demo_v2", "generated_at": f"{AS_OF.isoformat()}T00:00:00+00:00",
        "synthetic_demo_data": True, "files": manifest_rows, "models": model_rows,
    }
    _json(processed / "manifest.json", manifest)
    return manifest


def run(paths: ProjectPaths | None = None) -> BuildResult:
    resolved = paths or ProjectPaths.discover()
    processed = v2_processed_dir(resolved)
    models = v2_models_dir(resolved)
    processed.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    (processed / "modeling").mkdir(parents=True, exist_ok=True)
    integrity = verify_v2_integrity(resolved)
    if integrity["hash_failures"] or integrity["row_count_failures"] or not all(integrity["key_checks"].values()) or not all(integrity["foreign_key_checks"].values()):
        raise RuntimeError(f"demo_v2 integrity failed: {integrity}")
    bundle = load_v2_data(resolved)
    snapshots, serving = build_cost_snapshots(bundle)
    cost_scores, cost_report = train_cost_models(snapshots, serving, processed, models)
    profile = build_work_features(bundle)
    anomaly_scores, anomaly_report = build_anomaly_models(profile, processed, models)
    duplicate_candidates, duplicate_summary, duplicate_report = build_duplicate_index(profile, processed, models)
    geo_status = build_geo_status(bundle, profile, processed)
    record_status = build_record_status(bundle, profile, processed)
    priority_scores, _, alerts = build_priority(
        profile, anomaly_scores, duplicate_summary, cost_scores, geo_status, record_status, processed
    )
    manifest = write_profile_and_manifest(
        profile, priority_scores, anomaly_scores, duplicate_summary, cost_scores,
        geo_status, record_status, processed, models,
    )
    summary = {
        "dataset_profile": "demo_v2", "synthetic_demo_data": True,
        "work_count": len(profile), "cost_model": cost_report,
        "anomaly_evaluation": anomaly_report, "duplicate_evaluation": duplicate_report,
        "review_priority_distribution": priority_scores["review_priority_band"].value_counts().to_dict(),
        "requires_review_count": int(priority_scores["requires_review"].sum()),
        "geo_warning_count": int(geo_status["missing_monthly_site_evidence"].sum()),
        "alert_count": len(alerts), "manifest_file_count": len(manifest["files"]),
        "baseline_modified": False,
    }
    _json(processed / "build_summary.json", summary)
    return BuildResult(processed, models, summary)


def main() -> None:
    result = run()
    print(json.dumps({
        "processed_dir": str(result.processed_dir), "models_dir": str(result.models_dir),
        "selected_cost_model": result.summary["cost_model"]["selected_model"],
        "review_priority_distribution": result.summary["review_priority_distribution"],
    }, indent=2))


if __name__ == "__main__":
    main()

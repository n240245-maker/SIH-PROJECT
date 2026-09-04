"""Deterministic target-stratified train/validation/test splits at work level."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import pandas as pd
from sklearn.model_selection import train_test_split


RANDOM_STATE = 42


@dataclass(frozen=True, slots=True)
class WorkLevelSplit:
    assignments: pd.DataFrame
    train_work_ids: tuple[str, ...]
    validation_work_ids: tuple[str, ...]
    test_work_ids: tuple[str, ...]
    stratified: bool


def _can_stratify(labels: pd.Series) -> bool:
    counts = labels.value_counts()
    return len(counts) == 2 and bool(counts.min() >= 2)


def make_work_level_split(
    rows: pd.DataFrame,
    target: str,
    *,
    random_state: int = RANDOM_STATE,
) -> WorkLevelSplit:
    """Split unique work IDs 70/15/15 and keep all landmark rows together."""

    labels_per_work = rows.groupby("work_id", sort=True)[target].agg(["first", "nunique"])
    if labels_per_work["nunique"].gt(1).any():
        raise ValueError(f"{target} changes across landmarks for the same work")
    labels_per_work = labels_per_work.rename(columns={"first": target})[[target]]
    work_ids = labels_per_work.index.to_numpy()
    labels = labels_per_work[target].astype("int64")
    use_stratify = _can_stratify(labels)

    train_ids, remaining_ids = train_test_split(
        work_ids,
        test_size=0.30,
        random_state=random_state,
        stratify=labels if use_stratify else None,
    )
    remaining_labels = labels_per_work.loc[remaining_ids, target].astype("int64")
    second_stratify = _can_stratify(remaining_labels)
    validation_ids, test_ids = train_test_split(
        remaining_ids,
        test_size=0.50,
        random_state=random_state,
        stratify=remaining_labels if second_stratify else None,
    )

    groups = {
        "TRAIN": tuple(sorted(map(str, train_ids))),
        "VALIDATION": tuple(sorted(map(str, validation_ids))),
        "TEST": tuple(sorted(map(str, test_ids))),
    }
    assignments = pd.DataFrame(
        [
            {"work_id": work_id, "split": split}
            for split, identifiers in groups.items()
            for work_id in identifiers
        ]
    ).sort_values("work_id", kind="stable", ignore_index=True)
    if assignments["work_id"].duplicated().any() or len(assignments) != len(work_ids):
        raise ValueError("Work-level split assignments are not mutually exclusive")
    return WorkLevelSplit(
        assignments=assignments,
        train_work_ids=groups["TRAIN"],
        validation_work_ids=groups["VALIDATION"],
        test_work_ids=groups["TEST"],
        stratified=bool(use_stratify and second_stratify),
    )


def attach_split(rows: pd.DataFrame, split: WorkLevelSplit) -> pd.DataFrame:
    assigned = rows.merge(split.assignments, on="work_id", how="left", validate="many_to_one")
    if assigned["split"].isna().any():
        raise ValueError("At least one training row has no work-level split")
    return assigned


def stable_id_hash(work_ids: tuple[str, ...]) -> str:
    payload = "\n".join(sorted(work_ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def split_metadata(split: WorkLevelSplit) -> dict[str, object]:
    result: dict[str, object] = {"stratified_where_mathematically_possible": split.stratified}
    for label, identifiers in (
        ("train", split.train_work_ids),
        ("validation", split.validation_work_ids),
        ("test", split.test_work_ids),
    ):
        result[f"{label}_work_count"] = len(identifiers)
        result[f"{label}_work_ids"] = list(identifiers)
        result[f"{label}_work_ids_sha256"] = stable_id_hash(identifiers)
    return result

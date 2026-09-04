"""Operational outcome labels for completed works; never anomaly labels."""

from __future__ import annotations

from datetime import date

import pandas as pd

from intelligence.data.loader import OperationalDataBundle


DELAY_TARGET = "delay_outcome"
COST_OVERRUN_TARGET = "cost_overrun_outcome"


def build_completed_work_outcomes(
    bundle: OperationalDataBundle,
    as_of_date: date,
) -> pd.DataFrame:
    """Build final operational outcomes known by the controlled snapshot.

    Delay becomes known on visible completion. Cost overrun requires every
    completed asset row for a work to have a visible completion-marked date and
    non-null final expenditure. This preserves Day-2's conservative final-spend
    availability policy while supporting future multiple-asset inputs.
    """

    as_of = pd.Timestamp(as_of_date)
    assets = bundle.assets.loc[bundle.assets["completion_date"].le(as_of)].copy()
    if assets.empty:
        return pd.DataFrame(
            columns=["work_id", "completion_date", DELAY_TARGET, COST_OVERRUN_TARGET]
        )

    assets["_final_spend_visible"] = (
        assets["completion_marked_date"].notna()
        & assets["completion_marked_date"].le(as_of)
        & assets["final_expenditure_inr"].notna()
    )
    assets["_visible_final_expenditure"] = assets["final_expenditure_inr"].where(
        assets["_final_spend_visible"]
    )
    grouped = assets.groupby("work_id", sort=False)
    outcomes = grouped.agg(
        completion_date=("completion_date", "max"),
        final_expenditure_inr_target=(
            "_visible_final_expenditure",
            lambda values: values.sum(min_count=1),
        ),
        final_expenditure_fully_visible=("_final_spend_visible", "all"),
    ).reset_index()

    work_fields = bundle.works[
        [
            "work_id",
            "expected_completion_date",
            "sanctioned_amount_inr",
        ]
    ]
    outcomes = outcomes.merge(work_fields, on="work_id", how="left", validate="one_to_one")
    delay_known = outcomes["expected_completion_date"].notna()
    outcomes[DELAY_TARGET] = pd.Series(pd.NA, index=outcomes.index, dtype="Int64")
    outcomes.loc[delay_known, DELAY_TARGET] = (
        outcomes.loc[delay_known, "completion_date"]
        > outcomes.loc[delay_known, "expected_completion_date"]
    ).astype("int64")

    cost_known = (
        outcomes["final_expenditure_fully_visible"]
        & outcomes["final_expenditure_inr_target"].notna()
        & outcomes["sanctioned_amount_inr"].gt(0)
    )
    outcomes[COST_OVERRUN_TARGET] = pd.Series(pd.NA, index=outcomes.index, dtype="Int64")
    outcomes.loc[cost_known, COST_OVERRUN_TARGET] = (
        outcomes.loc[cost_known, "final_expenditure_inr_target"]
        > outcomes.loc[cost_known, "sanctioned_amount_inr"]
    ).astype("int64")
    return outcomes


def target_population_summary(outcomes: pd.DataFrame, target: str) -> dict[str, object]:
    eligible = outcomes.loc[outcomes[target].notna(), ["work_id", target]]
    positives = int(eligible[target].eq(1).sum())
    negatives = int(eligible[target].eq(0).sum())
    return {
        "eligible_work_count": int(len(eligible)),
        "positive_work_count": positives,
        "negative_work_count": negatives,
        "positive_prevalence": positives / len(eligible) if len(eligible) else None,
    }

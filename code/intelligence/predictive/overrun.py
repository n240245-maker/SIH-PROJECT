"""Independent final cost-overrun outcome training and model entry points."""

from __future__ import annotations

import pandas as pd

from .feature_sets import COST_OVERRUN_PREDICTORS
from .modeling import TrainedTargetModels, assess_model_feasibility, train_target_models
from .splitting import WorkLevelSplit
from .targets import COST_OVERRUN_TARGET


def cost_overrun_training_rows(snapshots: pd.DataFrame) -> pd.DataFrame:
    return snapshots.loc[snapshots[COST_OVERRUN_TARGET].notna()].copy()


def cost_overrun_feasibility(rows: pd.DataFrame) -> dict[str, object]:
    return assess_model_feasibility(rows, COST_OVERRUN_TARGET)


def train_cost_overrun_models(
    rows: pd.DataFrame,
    split: WorkLevelSplit,
) -> TrainedTargetModels:
    return train_target_models(rows, COST_OVERRUN_TARGET, COST_OVERRUN_PREDICTORS, split)

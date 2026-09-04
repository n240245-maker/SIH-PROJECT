"""Independent delay-outcome training-row and model entry points."""

from __future__ import annotations

import pandas as pd

from .feature_sets import DELAY_PREDICTORS
from .modeling import TrainedTargetModels, assess_model_feasibility, train_target_models
from .splitting import WorkLevelSplit
from .targets import DELAY_TARGET


def delay_training_rows(snapshots: pd.DataFrame) -> pd.DataFrame:
    return snapshots.loc[snapshots[DELAY_TARGET].notna()].copy()


def delay_feasibility(rows: pd.DataFrame) -> dict[str, object]:
    return assess_model_feasibility(rows, DELAY_TARGET)


def train_delay_models(rows: pd.DataFrame, split: WorkLevelSplit) -> TrainedTargetModels:
    return train_target_models(rows, DELAY_TARGET, DELAY_PREDICTORS, split)

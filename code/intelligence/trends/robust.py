"""Causal robust-statistics helpers for monthly operational trends."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


ROBUST_Z_THRESHOLD = 3.5
EWMA_ALPHA = 0.30
MINIMUM_PRIOR_MONTHS = 4
LOOKBACK_MONTHS = 6
MINIMUM_HISTORICAL_EVENTS = 20


@dataclass(frozen=True, slots=True)
class RobustBaseline:
    median: float
    mad: float
    q1: float
    q3: float
    iqr: float
    p10: float
    p90: float
    robust_z: float | None
    method: str


def robust_baseline(current: float, history: pd.Series) -> RobustBaseline:
    """Calculate robust statistics without allowing ``current`` into history."""

    values = pd.to_numeric(history, errors="coerce").dropna().astype("float64")
    if values.empty:
        nan = float("nan")
        return RobustBaseline(nan, nan, nan, nan, nan, nan, nan, None, "NO_HISTORY")

    median = float(values.median())
    deviations = (values - median).abs()
    mad = float(deviations.median())
    q1 = float(values.quantile(0.25))
    q3 = float(values.quantile(0.75))
    iqr = q3 - q1
    p10 = float(values.quantile(0.10))
    p90 = float(values.quantile(0.90))

    if mad > 0:
        robust_z = 0.6745 * (float(current) - median) / mad
        method = "MAD"
    elif iqr > 0:
        robust_z = (float(current) - median) / (iqr / 1.349)
        method = "IQR_FALLBACK"
    else:
        robust_z = None
        method = "CONSTANT_BASELINE_NO_DEVIATION"
    return RobustBaseline(median, mad, q1, q3, iqr, p10, p90, robust_z, method)


def percentile_0_100(values: pd.Series) -> pd.Series:
    """Deterministic inclusive percentile where the largest value receives 100."""

    result = pd.Series(np.nan, index=values.index, dtype="float64")
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return result
    if len(clean) == 1:
        result.loc[clean.index] = 100.0
    else:
        ranks = clean.rank(method="average", ascending=True)
        result.loc[clean.index] = (ranks - 1.0) / (len(clean) - 1.0) * 100.0
    return result

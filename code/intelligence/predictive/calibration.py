"""Validation-only Platt-style probability calibration."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression


def _logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probabilities, dtype="float64"), 1e-6, 1 - 1e-6)
    return np.log(clipped / (1.0 - clipped)).reshape(-1, 1)


@dataclass(slots=True)
class SigmoidProbabilityCalibrator:
    """A one-dimensional sigmoid calibrator fit only on validation predictions."""

    model: LogisticRegression
    fit_work_ids: tuple[str, ...]

    @classmethod
    def fit(
        cls,
        uncalibrated_probabilities: np.ndarray,
        outcomes: np.ndarray,
        work_ids: np.ndarray,
    ) -> "SigmoidProbabilityCalibrator":
        labels = np.asarray(outcomes, dtype="int64")
        if len(np.unique(labels)) != 2:
            raise ValueError("Sigmoid calibration requires both classes in validation")
        model = LogisticRegression(random_state=42, solver="lbfgs")
        model.fit(_logit(uncalibrated_probabilities), labels)
        return cls(model=model, fit_work_ids=tuple(sorted(set(map(str, work_ids)))))

    def predict(self, uncalibrated_probabilities: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(_logit(uncalibrated_probabilities))[:, 1]


def expected_calibration_error(
    outcomes: np.ndarray,
    probabilities: np.ndarray,
    *,
    bins: int = 10,
) -> float:
    labels = np.asarray(outcomes, dtype="float64")
    scores = np.asarray(probabilities, dtype="float64")
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    total = max(1, len(labels))
    error = 0.0
    for index in range(bins):
        lower, upper = boundaries[index], boundaries[index + 1]
        mask = (scores >= lower) & (scores < upper if index < bins - 1 else scores <= upper)
        if mask.any():
            error += mask.sum() / total * abs(labels[mask].mean() - scores[mask].mean())
    return float(error)

"""Guideline-grounded explanation layer for MPLADS Sentinel.

The package consumes frozen Day 1--7 evidence. It never calculates detector,
compliance, prediction, or review-priority results.
"""

from typing import TYPE_CHECKING

from .models import GroundedExplanation

if TYPE_CHECKING:
    from .service import ExplanationService

__all__ = ["ExplanationService", "GroundedExplanation"]


def __getattr__(name: str):
    """Keep the transformer-backed batch service out of normal API startup."""

    if name == "ExplanationService":
        from .service import ExplanationService

        return ExplanationService
    raise AttributeError(name)

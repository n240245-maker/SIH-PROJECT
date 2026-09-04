"""Guideline-grounded explanation layer for MPLADS Sentinel.

The package consumes frozen Day 1--7 evidence. It never calculates detector,
compliance, prediction, or review-priority results.
"""

from .models import GroundedExplanation
from .service import ExplanationService

__all__ = ["ExplanationService", "GroundedExplanation"]

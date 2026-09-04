"""Lifecycle-aware anomaly detection and robust peer evidence.

An anomaly is a statistically unusual pattern, not a finding of misconduct.
Ground-truth access is confined to the explicit evaluation module.
"""

from .feature_selection import LIFECYCLE_STAGES, select_lifecycle_feature_sets

__all__ = ["LIFECYCLE_STAGES", "select_lifecycle_feature_sets"]

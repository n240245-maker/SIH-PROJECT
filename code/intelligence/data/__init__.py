"""CSV loading and deterministic validation for the Day-1 data foundation."""

from typing import TYPE_CHECKING

from .paths import ProjectPaths

if TYPE_CHECKING:
    from .config import Day1Settings
    from .loader import OperationalDataBundle

__all__ = [
    "Day1Settings",
    "OperationalDataBundle",
    "ProjectPaths",
    "load_evaluation_ground_truth",
    "load_operational_data",
    "load_settings",
]


def __getattr__(name: str):
    """Load validation-only modules only when their public exports are requested."""

    if name in {"Day1Settings", "load_settings"}:
        from .config import Day1Settings, load_settings

        return {"Day1Settings": Day1Settings, "load_settings": load_settings}[name]
    if name in {
        "OperationalDataBundle",
        "load_evaluation_ground_truth",
        "load_operational_data",
    }:
        from .loader import (
            OperationalDataBundle,
            load_evaluation_ground_truth,
            load_operational_data,
        )

        return {
            "OperationalDataBundle": OperationalDataBundle,
            "load_evaluation_ground_truth": load_evaluation_ground_truth,
            "load_operational_data": load_operational_data,
        }[name]
    raise AttributeError(name)

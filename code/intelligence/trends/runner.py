"""Standalone Day-7 operational-trend runner."""

from __future__ import annotations

from intelligence.data.config import load_settings
from intelligence.data.loader import load_operational_data
from intelligence.data.paths import ProjectPaths

from .context import build_work_trend_context
from .monthly import build_trend_alerts, build_trend_timeseries, latest_complete_month


def run_trends(paths: ProjectPaths, as_of_date=None):
    settings = load_settings(paths, as_of_date=as_of_date)
    bundle = load_operational_data(paths)
    timeseries = build_trend_timeseries(bundle, settings.as_of_date)
    alerts = build_trend_alerts(timeseries)
    import pandas as pd

    features = pd.read_csv(paths.processed_data_dir / "project_features.csv", low_memory=False)
    context = build_work_trend_context(
        features, timeseries, str(latest_complete_month(settings.as_of_date))
    )
    paths.ensure_processed_data_dir()
    timeseries.to_csv(paths.processed_data_dir / "trend_timeseries.csv", index=False)
    alerts.to_csv(paths.processed_data_dir / "trend_alerts.csv", index=False)
    context.to_csv(paths.processed_data_dir / "work_trend_context.csv", index=False)
    return timeseries, alerts, context


def main() -> int:
    timeseries, alerts, context = run_trends(ProjectPaths.discover())
    print(
        f"Created {len(timeseries):,} trend rows, {len(alerts):,} trend alerts, "
        f"and {len(context):,} work contexts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

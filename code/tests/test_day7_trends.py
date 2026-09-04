"""Day-7 causal trend, support, robustness, and no-feedback tests."""

from __future__ import annotations

from datetime import date
import inspect

import numpy as np
import pandas as pd
import pytest

from intelligence.trends import context, monthly
from intelligence.trends.robust import robust_baseline


def test_latest_complete_month_and_future_event_exclusion(operational_bundle):
    assert str(monthly.latest_complete_month(date(2026, 9, 1))) == "2026-08"
    event_frames = monthly._event_metric_frames(operational_bundle, date(2026, 9, 1))
    assert set(event_frames) == set(monthly.TREND_METRICS)
    for frame in event_frames.values():
        assert frame["event_date"].le(pd.Timestamp("2026-09-01")).all()
        assert frame["month"].le(pd.Period("2026-08", freq="M")).all()


def _monthly_frame(values: list[float], support: list[int] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "group_type": "STATE",
            "group_value": "state_name=Test",
            "metric": "progress_report_count",
            "month": pd.period_range("2026-01", periods=len(values), freq="M"),
            "current_value": values,
            "current_event_count": support or [10] * len(values),
        }
    )


def test_target_month_never_contributes_to_its_own_baseline():
    result = monthly._add_causal_statistics(_monthly_frame([1, 2, 3, 4, 5, 6, 10_000]))
    target = result.iloc[-1]
    assert target["baseline_month_count"] == 6
    assert target["median"] == pytest.approx(3.5)
    assert target["p90"] < 10_000


def test_minimum_prior_month_and_event_support_are_enforced():
    too_few_months = monthly._add_causal_statistics(_monthly_frame([1, 1, 1, 100]))
    assert too_few_months.iloc[-1]["deviation_method"] == "INSUFFICIENT_PRIOR_MONTHS"
    assert pd.isna(too_few_months.iloc[-1]["robust_z"])

    low_support = monthly._add_causal_statistics(
        _monthly_frame([1, 2, 3, 4, 5], support=[1, 1, 1, 1, 100])
    )
    assert low_support.iloc[-1]["historical_event_support"] == 4
    assert low_support.iloc[-1]["deviation_method"] == "INSUFFICIENT_HISTORICAL_EVENT_SUPPORT"
    assert not bool(low_support.iloc[-1]["trend_deviation_flag"])


def test_mad_iqr_and_constant_baseline_behaviour():
    mad = robust_baseline(20, pd.Series([1, 2, 3, 4, 5, 6]))
    assert mad.method == "MAD"
    assert mad.robust_z > 0

    iqr = robust_baseline(10, pd.Series([1, 1, 1, 1, 2, 3]))
    assert iqr.mad == 0
    assert iqr.iqr > 0
    assert iqr.method == "IQR_FALLBACK"
    assert iqr.robust_z > 0

    constant = robust_baseline(100, pd.Series([5, 5, 5, 5, 5, 5]))
    assert constant.method == "CONSTANT_BASELINE_NO_DEVIATION"
    assert constant.robust_z is None


def test_signed_robust_z_orientation():
    positive = robust_baseline(20, pd.Series([1, 2, 3, 4, 5, 6]))
    negative = robust_baseline(-20, pd.Series([1, 2, 3, 4, 5, 6]))
    assert positive.robust_z > 0
    assert negative.robust_z < 0


def test_trend_outputs_use_only_allowed_operational_streams(project_paths):
    timeseries = pd.read_csv(project_paths.processed_data_dir / "trend_timeseries.csv")
    alerts = pd.read_csv(project_paths.processed_data_dir / "trend_alerts.csv")
    work_context = pd.read_csv(project_paths.processed_data_dir / "work_trend_context.csv")
    assert set(timeseries["metric"]) == set(monthly.TREND_METRICS)
    assert not any(
        forbidden in metric.casefold()
        for metric in timeseries["metric"].unique()
        for forbidden in ("completion", "uc", "audit", "handover", "public_use")
    )
    assert timeseries["month"].max() == "2026-08"
    flagged = timeseries["trend_deviation_flag"].astype(bool)
    assert timeseries.loc[flagged, "baseline_month_count"].ge(4).all()
    assert timeseries.loc[flagged, "historical_event_support"].ge(20).all()
    assert timeseries.loc[flagged, "robust_z"].abs().ge(3.5).all()
    assert len(alerts) == int(flagged.sum())
    assert len(work_context) == work_context["work_id"].nunique() == 3_000
    scores = work_context["operational_trend_context_score_0_100"]
    assert scores.between(0, 100).all()
    assert work_context.loc[
        ~work_context["operational_trend_deviation_flag"].astype(bool),
        "operational_trend_context_score_0_100",
    ].eq(0).all()


def test_detector_hotspots_cannot_feed_work_trend_context():
    source = inspect.getsource(context).casefold()
    assert "detector_hotspot" not in source
    assert "hotspot" not in inspect.signature(context.build_work_trend_context).parameters
    source_monthly = inspect.getsource(monthly).casefold()
    assert "completion_date" not in source_monthly
    assert "audit_date" not in source_monthly

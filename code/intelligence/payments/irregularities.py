"""As-of payment chronology and consistency evidence for Day 4."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

import pandas as pd

from intelligence.features.aggregations import released_payments_as_of


SIGNAL_POLICY: Mapping[str, tuple[str, str]] = {
    "PAYMENT_AUTH_BEFORE_REQUEST": (
        "WARNING",
        "authorization date should ordinarily not precede request date",
    ),
    "PAYMENT_RELEASE_BEFORE_AUTH": (
        "STRONG_WARNING",
        "release date should ordinarily not precede authorization date",
    ),
    "DUPLICATE_PFMS_REFERENCE": (
        "STRONG_WARNING",
        "PFMS reference should ordinarily identify one released payment",
    ),
    "ZERO_VALUE_RELEASED_PAYMENT": (
        "WARNING",
        "released payment amount should ordinarily be greater than zero",
    ),
    "PAYMENT_AFTER_COMPLETION": (
        "WARNING",
        "released payment follows the visible completion date and requires settlement-timing review",
    ),
    "PAYMENT_AFTER_FINAL_PAYMENT": (
        "STRONG_WARNING",
        "no later released installment is ordinarily expected after a final-payment marker",
    ),
    "MULTIPLE_FINAL_PAYMENTS": (
        "STRONG_WARNING",
        "one released payment is ordinarily expected to carry the final-payment marker",
    ),
    "RELEASED_TOTAL_EXCEEDS_SANCTION": (
        "STRONG_WARNING",
        "released-payment total should ordinarily not exceed the visible sanctioned amount",
    ),
}

SUMMARY_COLUMN_BY_SIGNAL = {
    code: f"{code.lower()}_count" for code in SIGNAL_POLICY
}


def _signal(
    *,
    work_id: str,
    payment_id: str | None,
    signal_code: str,
    observed_value: object,
    evidence: str,
    event_date: object,
) -> dict[str, Any]:
    severity, expected = SIGNAL_POLICY[signal_code]
    return {
        "work_id": work_id,
        "payment_id": payment_id,
        "signal_code": signal_code,
        "signal_severity": severity,
        "observed_value": observed_value,
        "expected_pattern": expected,
        "evidence": evidence,
        "event_date": event_date,
    }


def build_payment_irregularities(
    payments: pd.DataFrame,
    project_features: pd.DataFrame,
    as_of_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build long-form evidence only from released payments visible by snapshot."""

    required_features = {
        "work_id",
        "sanctioned_amount_inr",
        "completion_date_as_of",
    }
    missing = sorted(required_features.difference(project_features.columns))
    if missing:
        raise ValueError(f"Payment intelligence feature inputs missing: {missing}")

    visible = released_payments_as_of(payments, as_of_date).reset_index(drop=True)
    completion_by_work = pd.to_datetime(
        project_features.set_index("work_id")["completion_date_as_of"],
        errors="coerce",
    )
    sanction_by_work = pd.to_numeric(
        project_features.set_index("work_id")["sanctioned_amount_inr"],
        errors="coerce",
    )
    rows: list[dict[str, Any]] = []

    for payment in visible.itertuples(index=False):
        if payment.authorization_date < payment.payment_request_date:
            rows.append(
                _signal(
                    work_id=payment.work_id,
                    payment_id=payment.payment_id,
                    signal_code="PAYMENT_AUTH_BEFORE_REQUEST",
                    observed_value=(
                        f"authorization={payment.authorization_date.date()}; "
                        f"request={payment.payment_request_date.date()}"
                    ),
                    evidence="Authorization precedes the recorded request date.",
                    event_date=payment.authorization_date,
                )
            )
        if payment.payment_release_date < payment.authorization_date:
            rows.append(
                _signal(
                    work_id=payment.work_id,
                    payment_id=payment.payment_id,
                    signal_code="PAYMENT_RELEASE_BEFORE_AUTH",
                    observed_value=(
                        f"release={payment.payment_release_date.date()}; "
                        f"authorization={payment.authorization_date.date()}"
                    ),
                    evidence="Release precedes the recorded authorization date.",
                    event_date=payment.payment_release_date,
                )
            )
        if payment.payment_amount_inr == 0:
            rows.append(
                _signal(
                    work_id=payment.work_id,
                    payment_id=payment.payment_id,
                    signal_code="ZERO_VALUE_RELEASED_PAYMENT",
                    observed_value=0,
                    evidence="A released payment row records zero INR.",
                    event_date=payment.payment_release_date,
                )
            )
        completion_date = completion_by_work.get(payment.work_id, pd.NaT)
        if pd.notna(completion_date) and payment.payment_release_date > completion_date:
            days_after = int((payment.payment_release_date - completion_date).days)
            rows.append(
                _signal(
                    work_id=payment.work_id,
                    payment_id=payment.payment_id,
                    signal_code="PAYMENT_AFTER_COMPLETION",
                    observed_value=(
                        f"amount_inr={payment.payment_amount_inr}; "
                        f"days_after_completion={days_after}"
                    ),
                    evidence=(
                        f"Released {payment.payment_amount_inr} INR on "
                        f"{payment.payment_release_date.date()}, {days_after} days after "
                        f"visible completion {completion_date.date()}."
                    ),
                    event_date=payment.payment_release_date,
                )
            )

    duplicate_pfms = visible["pfms_reference"].notna() & visible[
        "pfms_reference"
    ].duplicated(keep="first")
    for payment in visible.loc[duplicate_pfms].itertuples(index=False):
        rows.append(
            _signal(
                work_id=payment.work_id,
                payment_id=payment.payment_id,
                signal_code="DUPLICATE_PFMS_REFERENCE",
                observed_value=payment.pfms_reference,
                evidence="PFMS reference was already present on an earlier visible released payment.",
                event_date=payment.payment_release_date,
            )
        )

    for work_id, group in visible.groupby("work_id", sort=False):
        seen_final = False
        final_count = 0
        for payment in group.itertuples(index=False):
            if seen_final:
                rows.append(
                    _signal(
                        work_id=work_id,
                        payment_id=payment.payment_id,
                        signal_code="PAYMENT_AFTER_FINAL_PAYMENT",
                        observed_value=payment.payment_stage,
                        evidence="A released installment appears later in canonical order than a final-payment marker.",
                        event_date=payment.payment_release_date,
                    )
                )
            if bool(payment.is_final_payment):
                final_count += 1
                if final_count > 1:
                    rows.append(
                        _signal(
                            work_id=work_id,
                            payment_id=payment.payment_id,
                            signal_code="MULTIPLE_FINAL_PAYMENTS",
                            observed_value=final_count,
                            evidence="This is an additional released row marked as final payment.",
                            event_date=payment.payment_release_date,
                        )
                    )
                seen_final = True

        released_total = float(group["payment_amount_inr"].sum())
        sanctioned = sanction_by_work.get(work_id, float("nan"))
        if pd.notna(sanctioned) and float(sanctioned) > 0 and released_total > float(sanctioned):
            latest_date = group["payment_release_date"].max()
            rows.append(
                _signal(
                    work_id=work_id,
                    payment_id=None,
                    signal_code="RELEASED_TOTAL_EXCEEDS_SANCTION",
                    observed_value=(
                        f"released_total_inr={released_total:.0f}; "
                        f"sanctioned_amount_inr={float(sanctioned):.0f}"
                    ),
                    evidence="Visible released-payment aggregate exceeds the visible sanctioned amount.",
                    event_date=latest_date,
                )
            )

    columns = [
        "work_id",
        "payment_id",
        "signal_code",
        "signal_severity",
        "observed_value",
        "expected_pattern",
        "evidence",
        "event_date",
    ]
    irregularities = pd.DataFrame.from_records(rows, columns=columns)
    if not irregularities.empty:
        irregularities = irregularities.sort_values(
            ["work_id", "event_date", "signal_code", "payment_id"],
            kind="stable",
            na_position="last",
        ).reset_index(drop=True)

    summary = project_features.loc[:, ["work_id"]].copy()
    for code, column in SUMMARY_COLUMN_BY_SIGNAL.items():
        counts = (
            irregularities.loc[irregularities["signal_code"].eq(code)]
            .groupby("work_id")
            .size()
        )
        summary[column] = summary["work_id"].map(counts).fillna(0).astype("int64")
    count_columns = list(SUMMARY_COLUMN_BY_SIGNAL.values())
    summary["payment_irregularity_evidence_count"] = summary[count_columns].sum(axis=1)
    summary["has_payment_irregularity_evidence"] = summary[
        "payment_irregularity_evidence_count"
    ].gt(0)
    return irregularities, summary

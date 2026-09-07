"""Readable, offline-capable case-review support PDF generation."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.presentation import REVIEW_NOTE, humanize_narrative


NAVY = colors.HexColor("#102A43")
TEAL = colors.HexColor("#0C756F")
AMBER = colors.HexColor("#D97706")
RED = colors.HexColor("#B42318")
INK = colors.HexColor("#1C2B39")
MUTED = colors.HexColor("#637282")
LINE = colors.HexColor("#DCE4EB")
PALE = colors.HexColor("#F3F6F8")


def _safe(value: Any, fallback: str = "Not available") -> str:
    if value is None or value == "" or str(value).casefold() in {"nan", "none"}:
        return fallback
    return str(value)


def _money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Not available"
    compact = (
        f"INR {number / 10_000_000:,.2f} crore"
        if abs(number) >= 10_000_000
        else f"INR {number / 100_000:,.2f} lakh"
        if abs(number) >= 100_000
        else f"INR {number:,.0f}"
    )
    return f"{compact} (INR {number:,.0f})" if abs(number) >= 100_000 else compact


def _decimal(value: Any, suffix: str = "") -> str:
    try:
        return f"{float(value):,.1f}{suffix}"
    except (TypeError, ValueError):
        return "Not available"


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(_safe(value)).replace("\n", "<br/>"), style)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover": ParagraphStyle("Cover", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20,
                                leading=24, textColor=NAVY, alignment=TA_CENTER, spaceAfter=5 * mm),
        "kicker": ParagraphStyle("Kicker", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9,
                                 leading=12, textColor=TEAL, alignment=TA_CENTER, spaceAfter=2 * mm),
        "h1": ParagraphStyle("H1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=13,
                             leading=16, textColor=NAVY, spaceBefore=4 * mm, spaceAfter=2 * mm, keepWithNext=True),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=10,
                             leading=13, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=1.5 * mm, keepWithNext=True),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=8.3,
                               leading=11.2, textColor=INK, spaceAfter=1.8 * mm),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.2,
                                leading=9.2, textColor=MUTED, spaceAfter=1 * mm),
        "label": ParagraphStyle("Label", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.2,
                                leading=9.2, textColor=MUTED),
        "warning": ParagraphStyle("Warning", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8.3,
                                  leading=11.2, textColor=RED),
        "review": ParagraphStyle("Review", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8.3,
                                 leading=11.2, textColor=AMBER),
        "footer": ParagraphStyle("Footer", parent=base["BodyText"], fontName="Helvetica", fontSize=6.5,
                                 leading=8, textColor=MUTED, alignment=TA_LEFT),
    }


def _meta_table(rows: Iterable[tuple[str, Any]], styles: dict[str, ParagraphStyle],
                widths: tuple[float, float] = (52 * mm, 118 * mm)) -> Table:
    data = [[_paragraph(label, styles["label"]), _paragraph(value, styles["body"])] for label, value in rows]
    table = Table(data, colWidths=list(widths), hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _section(story: list[Any], number: int, title: str, styles: dict[str, ParagraphStyle]) -> None:
    story.append(Paragraph(f"{number}. {escape(title)}", styles["h1"]))


def _bullet(story: list[Any], value: str, styles: dict[str, ParagraphStyle], kind: str = "body") -> None:
    story.append(Paragraph(f"- {escape(value)}", styles[kind]))


def _page_frame(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Decision-support report - authorized human verification required.")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_case_review_pdf(detail: dict[str, Any], explanation_bundle: dict[str, Any],
                          generated_at: datetime) -> bytes:
    """Generate a deterministic PDF from structured backend evidence only."""

    profile = detail["profile"]
    priority = detail["priority"]
    presentation = detail["presentation"]
    financial = presentation["financial"]
    chronology = presentation["payment_chronology"]
    timeline = presentation["timeline"]
    readiness = presentation["document_readiness"]
    compliance = detail["compliance"]
    duplicates = detail["duplicates"].get("review_candidates") or []
    prediction = detail["prediction"].get("scores") or {}
    narrative = explanation_bundle.get("explanation") or {}
    styles = _styles()
    work_id = _safe(profile.get("work_id"))
    report_id = f"TRACEX-KAVACH-{work_id}-{generated_at:%Y%m%d-%H%M%S}"

    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title=f"TRACE-X KAVACH Case Review Support Report - {work_id}",
        author="TRACE-X KAVACH", subject="Officer decision-support report",
    )
    story: list[Any] = [
        Paragraph("TRACE-X KAVACH", styles["kicker"]),
        Paragraph("CASE REVIEW SUPPORT REPORT", styles["cover"]),
        Paragraph("MPLADS Monitoring & Management Platform", styles["kicker"]),
        _meta_table([
            ("Report ID", report_id), ("Work ID", work_id),
            ("Work title", profile.get("work_description")),
            ("Generated timestamp", generated_at.isoformat()),
            ("Analytical snapshot date", presentation.get("as_of_date")),
            ("Lifecycle", profile.get("lifecycle_stage")),
            ("Attention Level", presentation.get("attention_level_label")),
            ("Review Priority", f"{_decimal(priority.get('review_priority_score_0_100'))} / 100"),
            ("Review Priority band", priority.get("review_priority_band")),
            ("Officer case status", detail.get("current_review_status")),
            ("Report purpose", "Officer review support"),
        ], styles), Spacer(1, 4 * mm),
    ]

    _section(story, 1, "Case Overview", styles)
    story.append(_meta_table([
        ("Location", f"{_safe(profile.get('village'))}, {_safe(profile.get('block'))}, {_safe(profile.get('district'))}, {_safe(profile.get('state_name'))}"),
        ("MP / constituency", f"{_safe(profile.get('mp_name'))} / {_safe(profile.get('constituency'))}"),
        ("Sector / sub-sector", f"{_safe(profile.get('sector'))} / {_safe(profile.get('sub_sector'))}"),
        ("Implementing agency", profile.get("implementing_agency_name")),
        ("Recorded status", profile.get("source_current_status")),
    ], styles))

    _section(story, 2, "Why This Work Needs Attention", styles)
    story.append(_paragraph(
        f"{_safe(presentation.get('attention_level_label'))}; Review Priority "
        f"{_decimal(priority.get('review_priority_score_0_100'))}/100. "
        "The score prioritizes review; it is not a probability of wrongdoing.", styles["body"]))
    for item in presentation.get("main_attention_areas", [])[:5]:
        _bullet(story, _safe(item), styles)

    _section(story, 3, "Warnings & Review Signals", styles)
    warnings = presentation.get("warning_signals") or []
    for signal in warnings:
        kind = "warning" if signal.get("state") == "strong_issue" else "review" if signal.get("state") == "review" else "body"
        story.append(KeepTogether([
            Paragraph(f"{escape(_safe(signal.get('severity_label')))} - {escape(_safe(signal.get('title')))}", styles[kind]),
            _paragraph(humanize_narrative(signal.get("summary")), styles["body"]),
        ]))
    if not warnings:
        story.append(_paragraph("No current governed warning or review signal is present.", styles["body"]))

    _section(story, 4, "Fund Utilization & Payments", styles)
    story.append(_meta_table([
        ("Estimated cost", _money(financial.get("estimated_cost_inr"))),
        ("Sanctioned amount", _money(financial.get("sanctioned_amount_inr"))),
        ("Released amount", _money(financial.get("released_payments_inr"))),
        ("Recorded expenditure", _money(financial.get("recorded_expenditure_inr"))),
        ("Released vs sanction difference", _money(financial.get("released_minus_sanction_inr"))),
        ("Released above sanction", _decimal(financial.get("percentage_above_sanction"), "%")),
        ("Fund Utilization Health", (financial.get("exceedance_display_severity") or {}).get("label")),
    ], styles))
    story.append(_paragraph(financial.get("health_interpretation"), styles["body"]))
    if chronology.get("authorization_before_request"):
        story.append(_paragraph(
            f"Payment chronology requires verification: authorization {_safe(chronology.get('authorization_date'))}; "
            f"request {_safe(chronology.get('request_date'))}.", styles["review"]))

    _section(story, 5, "Progress & Schedule", styles)
    story.append(_meta_table([
        ("Physical progress", _decimal(financial.get("physical_progress_pct"), "%")),
        ("Financial progress", _decimal(financial.get("financial_progress_pct"), "%")),
        ("Finance vs physical gap", _decimal(financial.get("financial_minus_physical_gap_percentage_points"), " percentage points")),
        ("Expected completion", profile.get("expected_completion_date")),
        ("Recorded completion", profile.get("completion_date_as_of")),
    ], styles))
    for event in timeline.get("events", []):
        marker = "planned / expected" if event.get("kind") == "planned" else "recorded"
        detail_text = f": {_safe(event.get('detail'))}" if event.get("detail") else ""
        _bullet(story, f"{_safe(event.get('date'))} - {_safe(event.get('label'))} [{marker}]{detail_text}", styles)

    _section(story, 6, "Records & Completion Readiness", styles)
    story.append(_paragraph(readiness.get("headline"), styles["body"]))
    for item in readiness.get("entries", []):
        kind = "warning" if item.get("state") == "strong_issue" else "review" if item.get("state") == "review" else "body"
        _bullet(story, f"{_safe(item.get('label'))}: {_safe(item.get('status_label'))}", styles, kind)

    _section(story, 7, "MPLADS Compliance", styles)
    actionable_rules = [rule for rule in compliance.get("rules", []) if rule.get("result") in {"NON_COMPLIANT", "REVIEW"}]
    for rule in actionable_rules:
        kind = "warning" if rule.get("result") == "NON_COMPLIANT" else "review"
        story.append(KeepTogether([
            Paragraph(f"{escape(_safe(rule.get('rule_title')))} - {escape(_safe(rule.get('result')).replace('_', ' '))}", styles[kind]),
            _paragraph(f"Observed: {_safe(rule.get('observed_value'))}", styles["body"]),
            _paragraph(f"Expected: {_safe(rule.get('expected_condition'))}", styles["body"]),
            _paragraph(f"Clause {rule.get('guideline_clause')}; page {rule.get('guideline_page')}; technical rule {rule.get('rule_id')}", styles["small"]),
        ]))
    if not actionable_rules:
        story.append(_paragraph("No actionable compliance issue is present.", styles["body"]))
    story.append(_paragraph("Requires Review and Non-Compliant remain distinct states.", styles["small"]))

    _section(story, 8, "Duplicate and Similar-Work Comparison", styles)
    if duplicates:
        for candidate in duplicates:
            paired = candidate.get("paired_work") or {}
            _bullet(story, f"Duplicate Review Candidate {_safe(paired.get('work_id'))}: {_safe(paired.get('work_description'))}. Officer comparison is required; the pairing is not confirmation.", styles, "review")
    else:
        story.append(_paragraph("No corroborated duplicate-review candidate is present.", styles["body"]))
    for peer in (presentation.get("peer_comparisons") or [])[:5]:
        _bullet(story, f"{_safe(peer.get('label'))}: {_safe(peer.get('comparison'))}; this work {_decimal(peer.get('observed_value'))}; typical similar work {_decimal(peer.get('peer_median'))}.", styles)
    story.append(_paragraph("Peer comparison is analytical context and does not establish a violation.", styles["small"]))

    _section(story, 9, "Forecast / Predictive Signal", styles)
    if prediction.get("already_overdue_as_of"):
        story.append(_paragraph(f"Observed now: {_decimal(profile.get('overdue_days_as_of'), ' days')} past expected completion.", styles["warning"]))
    story.append(_paragraph("Delay prediction is not served because the available outcomes do not support a defensible classifier.", styles["body"]))
    if prediction.get("cost_overrun_serving_percentile_0_100") is not None:
        story.append(_paragraph(f"Cost-overrun early-warning percentile: {_decimal(prediction.get('cost_overrun_serving_percentile_0_100'))}. Reliability: Limited; secondary context only.", styles["body"]))

    _section(story, 10, "Case Summary", styles)
    assessment = presentation.get("case_assessment") or {}
    project = assessment.get("project") or {}
    story.append(Paragraph("About this work", styles["h2"]))
    story.append(_paragraph(f"{_safe(project.get('work_title'))} is a {_safe(project.get('lifecycle')).replace('_', ' ').lower()}-stage work in {_safe(project.get('location'))}.", styles["body"]))
    story.append(Paragraph("What happened", styles["h2"]))
    if explanation_bundle.get("generation_mode") == "GROQ_GROUNDED" and narrative.get("summary"):
        story.append(_paragraph(humanize_narrative(narrative.get("summary")), styles["body"]))
    else:
        story.append(_paragraph(assessment.get("executive_summary"), styles["body"]))
    story.append(Paragraph("Main issues", styles["h2"]))
    for signal in warnings[:3]:
        _bullet(story, humanize_narrative(signal.get("summary")), styles)
    if not warnings:
        story.append(_paragraph("No current recorded issue requires additional interpretation.", styles["body"]))

    _section(story, 11, "Officer Verification and Follow-up", styles)
    for item in presentation.get("officer_verification_checklist", []):
        _bullet(story, f"[ ] {_safe(item)}", styles)
    story.append(_paragraph("The authorized officer selects and records any follow-up action. No escalation or administrative conclusion is automatic.", styles["review"]))

    story.append(KeepTogether([
        Paragraph("12. Review Note", styles["h1"]),
        _paragraph(REVIEW_NOTE, styles["body"]),
        _paragraph("Decision-support report - not an official sanction order, audit finding, adjudication, certificate, or legal conclusion.", styles["warning"]),
    ]))

    doc.build(story, onFirstPage=_page_frame, onLaterPages=_page_frame)
    return output.getvalue()

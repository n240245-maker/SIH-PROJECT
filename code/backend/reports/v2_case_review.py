"""Deterministic demo-v2 officer case-review PDF."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NAVY = colors.HexColor("#102A43")
TEAL = colors.HexColor("#0C756F")
INK = colors.HexColor("#1C2B39")
MUTED = colors.HexColor("#637282")
LINE = colors.HexColor("#DCE4EB")
PALE = colors.HexColor("#F3F6F8")


def _safe(value: Any, fallback: str = "Not available") -> str:
    if value is None or value == "" or str(value).strip().casefold() in {"nan", "none", "nat"}:
        return fallback
    return str(value)


def _money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Not available"
    if number >= 10_000_000:
        return f"INR {number / 10_000_000:,.2f} crore"
    if number >= 100_000:
        return f"INR {number / 100_000:,.2f} lakh"
    return f"INR {number:,.0f}"


def _percent(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "Not available"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("TitleV2", parent=base["Title"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=NAVY, spaceAfter=4 * mm),
        "kicker": ParagraphStyle("KickerV2", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=TEAL, spaceAfter=2 * mm),
        "h1": ParagraphStyle("H1V2", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=NAVY, spaceBefore=4 * mm, spaceAfter=2 * mm, keepWithNext=True),
        "body": ParagraphStyle("BodyV2", parent=base["BodyText"], fontName="Helvetica", fontSize=8.2, leading=11, textColor=INK, spaceAfter=1.5 * mm),
        "small": ParagraphStyle("SmallV2", parent=base["BodyText"], fontName="Helvetica", fontSize=7, leading=9, textColor=MUTED, spaceAfter=1 * mm),
        "label": ParagraphStyle("LabelV2", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.2, leading=9, textColor=MUTED),
    }


def _p(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(_safe(value)).replace("\n", "<br/>"), style)


def _table(rows: list[tuple[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    table = Table(
        [[_p(label, styles["label"]), _p(value, styles["body"])] for label, value in rows],
        colWidths=[53 * mm, 117 * mm], hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE), ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _section(story: list[Any], number: int, title: str, styles: dict[str, ParagraphStyle]) -> None:
    story.append(Paragraph(f"{number}. {escape(title)}", styles["h1"]))


def _bullet(story: list[Any], value: Any, styles: dict[str, ParagraphStyle]) -> None:
    story.append(Paragraph(f"- {escape(_safe(value))}", styles["body"]))


def _frame(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Decision-support report - authorized human verification required.")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_v2_case_review_pdf(detail: dict[str, Any], generated_at: datetime) -> bytes:
    styles = _styles()
    header = detail["header"]
    project = detail["project_details"]
    risks = detail["key_risk_areas"]
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title=f"TRACE-X KAVACH case review - {header['work_id']}",
        author="TRACE-X KAVACH",
    )
    story: list[Any] = [
        Paragraph("TRACE-X KAVACH", styles["kicker"]),
        Paragraph("CASE REVIEW SUPPORT REPORT", styles["title"]),
        _p("MPLADS Monitoring & Management Platform", styles["small"]),
        _table([
            ("Work ID", header["work_id"]), ("Project", header["project_title"]),
            ("Location", header["location"]), ("Generated", generated_at.isoformat()),
            ("Attention", header["attention_level"]),
            ("Review Priority", f"{float(header['review_priority_score_0_100']):.1f} / 100"),
            ("Officer case status", project["officer_case_status"]),
            ("Report purpose", "Officer review support"),
        ], styles), Spacer(1, 2 * mm),
    ]

    _section(story, 1, "Project Details", styles)
    story.append(_table([
        ("Lifecycle", project["lifecycle"]), ("Recorded status", project["recorded_work_status"]),
        ("Member of Parliament", f"{project['member_of_parliament']} ({project['mp_id']})"),
        ("Constituency", project["constituency"]), ("Sanctioned", _money(project["sanctioned_amount_inr"])),
        ("Released", _money(project["released_payments_inr"])),
        ("Physical progress", _percent(project["physical_progress_pct"])),
        ("Financial progress", _percent(project["financial_progress_pct"])),
    ], styles))

    _section(story, 2, "Monitoring Health", styles)
    for item in detail["monitoring_health"]:
        _bullet(story, f"{item['label']}: {item['status']}", styles)

    _section(story, 3, "Anomalies & Irregularities", styles)
    for item in detail["anomalies_irregularities"]:
        _bullet(story, f"{item['title']} - {item['value']} ({item['status']})", styles)
    story.append(_p("Anomaly and irregularity do not mean fraud or wrongdoing.", styles["small"]))

    _section(story, 4, "Key Risk Areas", styles)
    fund = risks["fund_utilization"]
    cost = risks["cost_overrun"]
    duplicate = risks["duplicate_works"]
    story.append(_table([
        ("Fund Utilization", fund["status"]), ("Released minus sanction", _money(fund["difference_inr"])),
        ("Schedule", risks["delays"]["status"]), ("Observed cost status", cost["observed_status"]),
        ("Cost Overrun Early Warning", cost["early_warning_status"]),
        ("Duplicate review", duplicate["status"]),
    ], styles))
    story.append(_p("Release above visible sanction, observed cost overrun, predictive early warning, and a duplicate-review candidate are distinct concepts.", styles["small"]))

    _section(story, 5, "Progress & Schedule", styles)
    for item in detail["progress_schedule"]["timeline"]:
        _bullet(story, f"{item['date']} - {item['label']} [{item['kind']}]", styles)

    _section(story, 6, "Geo-Tagged Progress Evidence", styles)
    geo = detail["geo_evidence"]
    story.append(_table([
        ("Current-month status", geo["summary"]["current_month_status"]),
        ("Latest capture", geo["summary"]["latest_capture"]),
        ("Location status", geo["summary"]["location_status"]),
        ("Late evidence count", geo["summary"]["late_evidence_count"]),
        ("Priority points", "0 - governed warning only"),
    ], styles))
    for item in geo["items"][:6]:
        _bullet(story, f"{item.get('reporting_month')} {item.get('evidence_stage')}: {item.get('window_status')} - {item.get('verification_status')}", styles)
    story.append(_p(geo["integrity_note"], styles["small"]))

    _section(story, 7, "Records & Completion Readiness", styles)
    records = detail["records_completion"]
    story.append(_p(f"Completion readiness: {records['completion_readiness']}", styles["body"]))
    for name, status in records["statuses"].items():
        _bullet(story, f"{name.replace('_', ' ').title()}: {status}", styles)

    _section(story, 8, "Case Summary", styles)
    explanation = detail["ai_explanation"]["explanation"]
    story.append(_p(explanation["what_the_work_is"], styles["body"]))
    for issue in explanation["main_issues"]:
        _bullet(story, issue, styles)
    story.append(_p("The case summary cannot change recorded evidence, rule results or the officer's decision.", styles["small"]))

    _section(story, 9, "Officer Review & Corrective Action", styles)
    review = detail["officer_review"]
    story.append(_p(f"Current case status: {review['current_status']}", styles["body"]))
    for item in review["reviews"][-8:]:
        _bullet(story, f"{item.get('created_at')} - {item.get('status')}: {item.get('note')}", styles)
    story.append(_table([
        ("Verification owner", "________________________________________"),
        ("Supporting records checked", "________________________________________"),
        ("Corrective action / clarification", "________________________________________"),
        ("Target date", "________________________________________"),
        ("Authorized decision and signature", "________________________________________"),
    ], styles))
    story.append(_p("Suggested actions require authorized human judgement. This document is not an official order, audit finding, adjudication, or certificate.", styles["small"]))

    doc.build(story, onFirstPage=_frame, onLaterPages=_frame)
    return output.getvalue()

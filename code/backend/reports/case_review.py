"""Professional, offline-capable case-review support PDF generation."""

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
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.presentation import REVIEW_NOTE, friendly_group, friendly_metric_label, humanize_narrative


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
        return f"INR {float(value):,.0f}"
    except (TypeError, ValueError):
        return "Not available"


def _decimal(value: Any, suffix: str = "") -> str:
    try:
        return f"{float(value):,.1f}{suffix}"
    except (TypeError, ValueError):
        return "Not available"


def _duplicate_reason(value: Any) -> str:
    raw = _safe(value)
    if raw.startswith("SELECTED:"):
        labels = {
            "semantic": "description similarity",
            "locality": "locality",
            "distance": "geographic proximity",
            "amount": "amount",
            "date": "date",
            "taxonomy": "work type",
        }
        parts = [labels.get(part, part.replace("_", " ")) for part in raw.removeprefix("SELECTED:").split("+")]
        return "Corroborated by " + ", ".join(parts) + "."
    return humanize_narrative(raw.replace("_", " "))


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
                             leading=16, textColor=NAVY, spaceBefore=4 * mm, spaceAfter=2 * mm,
                             keepWithNext=True),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=10,
                             leading=13, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=1.5 * mm,
                             keepWithNext=True),
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


def _meta_table(rows: Iterable[tuple[str, Any]], styles: dict[str, ParagraphStyle], widths=(52 * mm, 118 * mm)) -> Table:
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


def _bullet(story: list[Any], text: str, styles: dict[str, ParagraphStyle], kind: str = "body") -> None:
    story.append(Paragraph(f"- {escape(text)}", styles[kind]))


def _page_frame(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Prototype decision-support document - requires authorized human verification.")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_case_review_pdf(detail: dict[str, Any], explanation_bundle: dict[str, Any],
                          generated_at: datetime) -> bytes:
    """Generate a PDF exclusively from structured backend evidence."""

    profile = detail["profile"]
    priority = detail["priority"]
    presentation = detail["presentation"]
    financial = presentation["financial"]
    chronology = presentation["payment_chronology"]
    compliance = detail["compliance"]
    prediction = detail["prediction"]
    duplicates = detail["duplicates"].get("review_candidates") or []
    peers = detail["peer_benchmark"].get("top_deviations") or []
    timeline = presentation["timeline"]
    narrative = explanation_bundle.get("explanation") or {}
    styles = _styles()
    work_id = _safe(profile.get("work_id"))
    report_id = f"MPLADS-SENTINEL-{work_id}-{generated_at.strftime('%Y%m%d-%H%M%S')}"

    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title=f"MPLADS Sentinel Case Review Support Report - {work_id}",
        author="MPLADS Sentinel prototype",
        subject="Prototype decision-support document",
    )
    story: list[Any] = [
        Paragraph("MPLADS SENTINEL", styles["kicker"]),
        Paragraph("AI-Powered Monitoring &amp; Decision Support", styles["kicker"]),
        Paragraph("CASE REVIEW SUPPORT REPORT", styles["cover"]),
        Paragraph("Prototype Decision-Support Document", styles["kicker"]),
        _meta_table([
            ("Report ID", report_id),
            ("Work ID", work_id),
            ("Work title", profile.get("work_description")),
            ("Generated timestamp", generated_at.isoformat()),
            ("Analytical snapshot date", presentation.get("as_of_date")),
            ("Lifecycle", profile.get("lifecycle_stage")),
            ("Attention Level", presentation.get("attention_level_label")),
            ("Review Priority", f"{_decimal(priority.get('review_priority_score_0_100'))} / 100"),
            ("Review Priority band", priority.get("review_priority_band")),
            ("Officer case status", detail.get("current_review_status")),
            ("Explanation mode", explanation_bundle.get("generation_mode", "DETERMINISTIC_FALLBACK")),
        ], styles),
        Spacer(1, 4 * mm),
    ]

    _section(story, 1, "Work Details", styles)
    story.append(_meta_table([
        ("Location", f"{_safe(profile.get('village'))}, {_safe(profile.get('block'))}, {_safe(profile.get('district'))}, {_safe(profile.get('state_name'))}"),
        ("Sector / sub-sector", f"{_safe(profile.get('sector'))} / {_safe(profile.get('sub_sector'))}"),
        ("MP / constituency", f"{_safe(profile.get('mp_name'))} / {_safe(profile.get('constituency'))}"),
        ("Implementing agency", profile.get("implementing_agency_name")),
        ("Recorded status", profile.get("source_current_status")),
    ], styles))

    _section(story, 2, "Executive Review Summary", styles)
    story.append(_paragraph(
        f"Attention Level is {_safe(presentation.get('attention_level_label'))}. Review Priority is "
        f"{_decimal(priority.get('review_priority_score_0_100'))}/100 ({_safe(priority.get('review_priority_band'))}). "
        "It indicates review urgency, not evidence of wrongdoing.", styles["body"]))
    for item in presentation["main_attention_areas"]:
        _bullet(story, _safe(item), styles)

    _section(story, 3, "Key Observations Requiring Attention", styles)
    for signal in presentation["warning_signals"]:
        kind = "warning" if signal["state"] == "strong_issue" else "review" if signal["state"] == "review" else "body"
        story.append(KeepTogether([
            Paragraph(escape(signal["title"]), styles[kind]),
            _paragraph(humanize_narrative(signal.get("summary")), styles["body"]),
            _paragraph(f"Why this needs attention: {humanize_narrative(signal.get('why_attention'))}", styles["body"]),
            _paragraph(f"Verification: {humanize_narrative(signal.get('officer_verification'))}", styles["small"]),
        ]))
    if not presentation["warning_signals"]:
        story.append(_paragraph("No governed work-specific warning is present.", styles["body"]))

    _section(story, 4, "Financial Review", styles)
    story.append(_meta_table([
        ("Sanctioned amount", _money(financial.get("sanctioned_amount_inr"))),
        ("Released payments", _money(financial.get("released_payments_inr"))),
        ("Difference", _money(financial.get("released_minus_sanction_inr"))),
        ("Percentage above sanction", _decimal(financial.get("percentage_above_sanction"), "%")),
        ("Financial exceedance display severity", (financial.get("exceedance_display_severity") or {}).get("label")),
    ], styles))
    if financial.get("released_exceeds_visible_sanction"):
        story.append(_paragraph(
            "Released payments exceed the visible sanctioned amount. Verify whether an approved revised sanction or authorized variation applies.",
            styles["warning"] if (financial.get("exceedance_display_severity") or {}).get("state") == "strong_issue" else styles["review"],
        ))

    _section(story, 5, "Physical & Financial Progress", styles)
    story.append(_meta_table([
        ("Physical progress", _decimal(financial.get("physical_progress_pct"), "%")),
        ("Financial progress", _decimal(financial.get("financial_progress_pct"), "%")),
        ("Financial minus physical gap", _decimal(financial.get("financial_minus_physical_gap_percentage_points"), " percentage points")),
        ("Persistent mismatch evidence", "Yes" if financial.get("persistent_gap") else "No"),
    ], styles))

    _section(story, 6, "Payment Review", styles)
    if chronology.get("authorization_before_request"):
        story.append(_meta_table([
            ("Authorization", chronology.get("authorization_date")),
            ("Request", chronology.get("request_date")),
            ("Recorded chronology", "Authorization is recorded before the request - requires review"),
        ], styles))
        story.append(_paragraph("Verify the payment request, authorization order and PFMS/source records.", styles["review"]))
    else:
        story.append(_paragraph("No payment-chronology warning is present in the governed evidence.", styles["body"]))

    _section(story, 7, "Project Timeline & Event Checks", styles)
    story.append(_paragraph(f"Timeline attention points: {timeline.get('attention_count', 0)}", styles["body"]))
    for item in timeline.get("events", []):
        marker = {"recorded": "RECORDED", "planned": "PLANNED", "review": "REQUIRES REVIEW", "strong_issue": "OBSERVED ISSUE"}.get(item.get("state"), "RECORDED")
        _bullet(story, f"{_safe(item.get('date'))} - {_safe(item.get('label'))} [{marker}]" + (f": {_safe(item.get('detail'))}" if item.get("detail") else ""), styles)

    _section(story, 8, "Records & Completion Readiness", styles)
    readiness = presentation.get("document_readiness") or {}
    story.append(_paragraph(readiness.get("headline"), styles["body"]))
    for item in readiness.get("entries", []):
        kind = "warning" if item.get("state") == "strong_issue" else "review" if item.get("state") == "review" else "body"
        _bullet(story, f"{_safe(item.get('label'))}: {_safe(item.get('status_label'))}", styles, kind)

    _section(story, 9, "Duplicate-Work Review", styles)
    if duplicates:
        for candidate in duplicates:
            paired = candidate.get("paired_work") or {}
            story.append(_meta_table([
                ("Candidate work", paired.get("work_id")),
                ("Description", paired.get("work_description")),
                ("Location", f"{_safe(paired.get('village'))}, {_safe(paired.get('block'))}, {_safe(paired.get('district'))}"),
                ("Review score", _decimal(candidate.get("duplicate_similarity_score_0_100"), "/100")),
                ("Text similarity", _decimal(float(candidate.get("text_cosine_similarity") or 0) * 100, "%")),
                ("Distance", _decimal(candidate.get("geographic_distance_km"), " km")),
                ("Reason", _duplicate_reason(candidate.get("review_policy_reason"))),
            ], styles))
            story.append(_paragraph("Duplicate Review Candidate - this is not confirmation that the works are the same.", styles["review"]))
    else:
        story.append(_paragraph("No corroborated duplicate-review candidate is present.", styles["body"]))

    _section(story, 10, "MPLADS Rule & Compliance Check", styles)
    counts = presentation["compliance_counts"]
    story.append(_paragraph(" | ".join(f"{key.replace('_', ' ')}: {value}" for key, value in counts.items()), styles["small"]))
    actionable = [rule for rule in compliance.get("rules", []) if rule.get("result") in {"NON_COMPLIANT", "REVIEW"}]
    for rule in actionable:
        story.append(KeepTogether([
            Paragraph(f"{escape(_safe(rule.get('rule_title')))} - {escape(_safe(rule.get('result')).replace('_', ' '))}",
                      styles["warning"] if rule.get("result") == "NON_COMPLIANT" else styles["review"]),
            _paragraph(f"Observed: {_safe(rule.get('observed_value'))}", styles["body"]),
            _paragraph(f"Expected: {_safe(rule.get('expected_condition'))}", styles["body"]),
            _paragraph(f"Rule {rule.get('rule_id')}; clause {rule.get('guideline_clause')}; page {rule.get('guideline_page')}; chunk {rule.get('guideline_chunk_ids')}; {rule.get('guideline_version')}", styles["small"]),
        ]))
    if not actionable:
        story.append(_paragraph("No actionable compliance issue is present; ordinary rule checks remain available in the application.", styles["body"]))

    _section(story, 11, "Strongest Differences From Similar Works", styles)
    friendly_peers = presentation.get("peer_comparisons") or []
    for peer in friendly_peers[:5]:
        _bullet(story, f"{_safe(peer.get('label'))}: {_safe(peer.get('comparison'))}. This work: {_decimal(peer.get('observed_value'))}; typical similar work: {_decimal(peer.get('peer_median'))}; compared with {_safe(peer.get('peer_group_size'))} works.", styles)
    if not friendly_peers:
        story.append(_paragraph("No significant peer-comparison outlier is currently flagged.", styles["body"]))
    story.append(_paragraph("Statistical comparison helps prioritize review. It does not establish a violation or wrongdoing.", styles["small"]))

    _section(story, 12, "Forecast & Early Warning", styles)
    scores = prediction.get("scores") or {}
    if scores.get("already_overdue_as_of"):
        story.append(_paragraph(f"Observed now: work is overdue by {_decimal(profile.get('overdue_days_as_of'), ' days')}.", styles["warning"]))
    if scores.get("already_over_sanction_as_of"):
        story.append(_paragraph("Observed now: released expenditure is above the visible sanction.", styles["warning"]))
    story.append(_paragraph(
        "Delay prediction unavailable. The available outcome data did not contain enough balanced examples to train a defensible delay classifier.", styles["body"]))
    serving = scores.get("cost_overrun_serving_percentile_0_100")
    if serving is not None:
        story.append(_paragraph(f"Cost-overrun early-warning serving percentile: {_decimal(serving, '%')}. Model reliability: Limited.", styles["body"]))
    story.append(_paragraph("The cost model is secondary early-warning evidence because held-out discrimination is weak.", styles["small"]))

    _section(story, 13, "Operational Trend Context", styles)
    trend = presentation.get("trend") or {}
    story.append(_paragraph(
        f"{_safe(trend.get('title'))}. Current month: {_safe(trend.get('current_value'))}; recent baseline: {_safe(trend.get('baseline_value'))}. Assessment: {_safe(trend.get('assessment'))}.", styles["body"]))
    story.append(_paragraph("This describes the surrounding operational environment and is not direct evidence against this individual work.", styles["small"]))

    _section(story, 14, "AI-Assisted Case Assessment", styles)
    assessment = presentation.get("case_assessment") or {}
    project = assessment.get("project") or {}
    story.append(_paragraph(f"{_safe(project.get('work_title'))} ({work_id}); {_safe(project.get('location'))}; lifecycle {_safe(project.get('lifecycle'))}.", styles["body"]))
    story.append(_paragraph(assessment.get("executive_summary"), styles["body"]))
    if explanation_bundle.get("generation_mode") == "GROQ_GROUNDED":
        story.append(_paragraph(humanize_narrative(narrative.get("summary")), styles["body"]))
    else:
        story.append(_paragraph(
            "This local deterministic assessment is organized from the observed conditions, exact rule checks, "
            "comparisons and verification actions shown in the preceding sections.", styles["body"]))

    _section(story, 15, "Officer Verification Checklist", styles)
    for item in presentation["officer_verification_checklist"]:
        _bullet(story, f"[ ] {item}", styles)

    _section(story, 16, "Evidence & Supporting Records", styles)
    for signal in presentation["warning_signals"]:
        ref = signal.get("technical_reference") or {}
        _bullet(story, f"{signal['title']}: code {_safe(ref.get('evidence_code'))}; source {_safe(ref.get('source_artifact'))}", styles)
    for rule in actionable:
        _bullet(story, f"{rule.get('rule_id')}: {rule.get('result')}; clause {rule.get('guideline_clause')}; page {rule.get('guideline_page')}; chunk {rule.get('guideline_chunk_ids')}", styles)

    story.append(KeepTogether([
        Paragraph("17. Review Note", styles["h1"]),
        _paragraph(REVIEW_NOTE, styles["body"]),
        _paragraph("Prototype Decision-Support Document - not an official sanction order, audit finding, adjudication, or government-issued legal finding.", styles["warning"]),
    ]))

    doc.build(story, onFirstPage=_page_frame, onLaterPages=_page_frame)
    return output.getvalue()

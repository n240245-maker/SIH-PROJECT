"""Synthetic demo-v2 dashboards, dossier, geo evidence, and explicit explanations."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.authorization import request_scope
from backend.dependencies import (
    get_geo_evidence_repository,
    get_reviews,
    get_v2_application_service,
    get_v2_artifacts,
)
from backend.reports import build_v2_case_review_pdf
from backend.repositories.geo_evidence import GeoEvidenceRepository
from backend.repositories.reviews import ReviewRepository
from backend.repositories.v2_artifacts import V2ArtifactRepository
from backend.schemas import (
    ExplainRequest,
    ExplainResponse,
    GeoEvidenceCreate,
    GeoEvidenceVerify,
    ReviewCreate,
    ReviewResponse,
)
from backend.serialization import json_safe
from backend.services import Scope
from backend.services.v2_application import V2ApplicationService
from intelligence.data.paths import ProjectPaths
from rag.groq_client import GroqClient, load_groq_settings


router = APIRouter(prefix="/api/v2", tags=["synthetic-demo-v2"])
PROHIBITED_VERDICTS = ("fraud detected", "confirmed fraud", "confirmed misuse", "guilty", "corrupt")


def _not_found() -> HTTPException:
    return HTTPException(404, "Work was not found in the authorized scope")


@router.get("/scope/options")
def scope_options(service: V2ApplicationService = Depends(get_v2_application_service)) -> dict:
    return service.scope_options()


@router.get("/dashboard/overview")
def overview(
    scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
) -> dict:
    return service.overview(scope)


@router.get("/review-queue")
def review_queue(
    scope: Scope = Depends(request_scope), page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100), search: str | None = Query(None, max_length=120),
    lifecycle: str | None = None, band: str | None = None, sector: str | None = None,
    sub_sector: str | None = None, review_need: str | None = None,
    service: V2ApplicationService = Depends(get_v2_application_service),
) -> dict:
    return service.review_queue(
        scope, page=page, page_size=page_size, search=search, lifecycle=lifecycle,
        band=band, sector=sector, sub_sector=sub_sector, review_need=review_need,
    )


@router.get("/works/{work_id}")
def work_detail(
    work_id: str, scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
) -> dict:
    try:
        service.authorize_work(work_id, scope)
        return service.work_detail(work_id)
    except KeyError:
        raise _not_found() from None


@router.get("/works/{work_id}/case-report.pdf", response_class=Response)
def case_report(
    work_id: str, scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
) -> Response:
    try:
        service.authorize_work(work_id, scope)
        detail = service.work_detail(work_id)
    except KeyError:
        raise _not_found() from None
    generated_at = datetime.now(ZoneInfo("Asia/Kolkata"))
    content = build_v2_case_review_pdf(detail, generated_at)
    return Response(
        content=content, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="TraceX_Kavach_{work_id}_{generated_at:%Y-%m-%d}.pdf"'},
    )


def _fallback(detail: dict, status: str = "OFFLINE_DEFAULT") -> dict:
    return {
        "work_id": detail["header"]["work_id"], "generation_mode": "DETERMINISTIC_FALLBACK",
        "api_status": status, "provider": "groq", "model": "openai/gpt-oss-120b",
        "explanation": detail["ai_explanation"]["explanation"],
        "retrieved_guidelines": [], "fallback_used": True,
    }


def _selected_guidelines(artifacts: V2ArtifactRepository) -> list[dict]:
    keywords = ("monitoring", "implementing agencies", "utilization certificates", "audit")
    selected = [
        chunk for chunk in artifacts.guideline_chunks
        if any(word in str(chunk.get("text", "")).casefold() for word in keywords)
    ][:4]
    return selected


@router.post("/works/{work_id}/explain", response_model=ExplainResponse)
def explain_work(
    payload: ExplainRequest, work_id: str, scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
    artifacts: V2ArtifactRepository = Depends(get_v2_artifacts),
) -> dict:
    try:
        service.authorize_work(work_id, scope)
        detail = service.work_detail(work_id)
    except KeyError:
        raise _not_found() from None
    if not payload.use_llm:
        return _fallback(detail)
    try:
        guidelines = _selected_guidelines(artifacts)
        evidence_codes = [str(item["alert_type"]) for item in detail.get("technical_details", {}).get("review_priority", {}).get("contributions", []) if item.get("alert_type")]
        if not evidence_codes:
            evidence_codes = [str(item.get("alert_type")) for item in artifacts.group("alerts", work_id)] or ["WORK_PROFILE"]
        guideline_payload = [
            {"chunk_id": row["chunk_id"], "page": row["page_start"], "clause": row.get("section_or_clause"), "text": str(row["text"])[:900]}
            for row in guidelines
        ]
        facts = {
            "work_id": work_id, "project": detail["project_details"],
            "anomalies": detail["anomalies_irregularities"][:5],
            "geo_summary": detail["geo_evidence"]["summary"],
            "record_statuses": detail["records_completion"]["statuses"],
            "guideline_context": guideline_payload,
        }
        system_prompt = (
            "Explain only supplied structured evidence and guideline excerpts. Use cautious officer-facing language. "
            "Anomaly is not fraud; a duplicate candidate is not confirmation. Do not decide compliance, guilt, payment action, or escalation."
        )
        user_prompt = json.dumps(facts, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        result = GroqClient(load_groq_settings(ProjectPaths.discover())).explain(
            system_prompt, user_prompt, allowed_work_id=work_id,
            allowed_evidence_codes=evidence_codes,
            allowed_chunk_ids=[row["chunk_id"] for row in guideline_payload],
            allowed_clause_ids=[row["clause"] for row in guideline_payload if row["clause"]],
        )
        rendered = result.model_dump(mode="json")
        content = json.dumps(rendered).casefold()
        if any(term in content for term in PROHIBITED_VERDICTS):
            return _fallback(detail, "FALLBACK_PROHIBITED_VERDICT")
        return json_safe({
            "work_id": work_id, "generation_mode": "GROQ_GROUNDED", "api_status": "SUCCESS",
            "provider": "groq", "model": "openai/gpt-oss-120b", "explanation": rendered,
            "retrieved_guidelines": guideline_payload, "fallback_used": False,
        })
    except Exception:
        return _fallback(detail, "FALLBACK_SERVICE_UNAVAILABLE")


@router.post("/dashboard/brief")
def dashboard_brief(
    payload: ExplainRequest, scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
) -> dict:
    overview_data = service.overview(scope)
    # The structured brief is always immediately available. AI wording is never
    # automatic; the work-explanation endpoint remains the grounded schema path.
    return {
        "generation_mode": "DETERMINISTIC_STRUCTURED",
        "api_status": "AI_BRIEF_NOT_REQUIRED" if payload.use_llm else "OFFLINE_DEFAULT",
        "facts": overview_data["morning_brief"]["facts"],
        "fallback_used": True,
    }


@router.get("/works/{work_id}/reviews", response_model=list[ReviewResponse])
def list_reviews(
    work_id: str, scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
    reviews: ReviewRepository = Depends(get_reviews),
) -> list[dict]:
    try:
        service.authorize_work(work_id, scope)
    except KeyError:
        raise _not_found() from None
    return reviews.list_for_work(work_id)


@router.post("/works/{work_id}/reviews", response_model=ReviewResponse, status_code=201)
def create_review(
    work_id: str, payload: ReviewCreate, scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
    reviews: ReviewRepository = Depends(get_reviews),
) -> dict:
    try:
        service.authorize_work(work_id, scope)
    except KeyError:
        raise _not_found() from None
    values = payload.model_dump(mode="json")
    values["actor_role"] = scope.role.value
    return reviews.append(work_id, values)


@router.get("/works/{work_id}/geo-evidence")
def list_geo_evidence(
    work_id: str, scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
) -> dict:
    try:
        service.authorize_work(work_id, scope)
        return service.work_detail(work_id)["geo_evidence"]
    except KeyError:
        raise _not_found() from None


@router.post("/works/{work_id}/geo-evidence", status_code=201)
def create_geo_evidence(
    work_id: str, payload: GeoEvidenceCreate, scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
) -> dict:
    try:
        return service.create_geo_evidence(work_id, scope, payload.model_dump(mode="json"))
    except KeyError:
        raise _not_found() from None
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post("/geo-evidence/{evidence_id}/verify", status_code=201)
def verify_geo_evidence(
    evidence_id: str, payload: GeoEvidenceVerify, scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
) -> dict:
    try:
        return service.verify_geo_evidence(evidence_id, scope, payload.model_dump(mode="json"))
    except KeyError:
        raise HTTPException(404, "Geo evidence was not found") from None
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None


@router.get("/geo-evidence/{evidence_id}/image", response_class=Response)
def geo_image(
    evidence_id: str,
    scope: Scope = Depends(request_scope),
    service: V2ApplicationService = Depends(get_v2_application_service),
    artifacts: V2ArtifactRepository = Depends(get_v2_artifacts),
    runtime: GeoEvidenceRepository = Depends(get_geo_evidence_repository),
) -> Response:
    seeded = artifacts.data.geo_evidence.loc[artifacts.data.geo_evidence["evidence_id"].eq(evidence_id)]
    if len(seeded):
        try:
            service.authorize_work(str(seeded.iloc[0]["work_id"]), scope)
        except KeyError:
            raise HTTPException(404, "Geo evidence image was not found") from None
        path = artifacts.image_path(str(seeded.iloc[0]["image_path_or_object_id"]))
        return Response(content=path.read_bytes(), media_type="image/svg+xml")
    try:
        submission = next(
            row for row in runtime._rows(runtime.submissions_path)
            if row["evidence_id"] == evidence_id
        )
        service.authorize_work(str(submission["work_id"]), scope)
        content, media_type = runtime.image(evidence_id)
        return Response(content=content, media_type=media_type)
    except (KeyError, StopIteration):
        raise HTTPException(404, "Geo evidence image was not found") from None


@router.get("/alerts")
def alerts(
    scope: Scope = Depends(request_scope), limit: int = Query(200, ge=1, le=1000),
    service: V2ApplicationService = Depends(get_v2_application_service),
) -> dict:
    return service.alerts(scope, limit=limit)

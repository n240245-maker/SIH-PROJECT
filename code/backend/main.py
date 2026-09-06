"""TraceX - Kavach FastAPI entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.dependencies import get_artifacts, get_v2_artifacts
from backend.routers import application_router, explanations_router, reviews_router, system_router, v2_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.dataset_profile == "demo_v2":
        get_v2_artifacts()
    else:
        get_artifacts()
    yield


settings = get_settings()
app = FastAPI(
    title=f"{settings.app_name} API",
    description="Governed decision-support API over frozen MPLADS prototype intelligence artifacts.",
    version="1.0.0", lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                   allow_credentials=True, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type", "Authorization"])
app.include_router(system_router)
if settings.dataset_profile == "baseline":
    app.include_router(application_router)
    app.include_router(explanations_router)
    app.include_router(reviews_router)
app.include_router(v2_router)

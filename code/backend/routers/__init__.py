"""FastAPI routers."""

from .application import router as application_router
from .explanations import router as explanations_router
from .reviews import router as reviews_router
from .system import router as system_router

__all__ = ["application_router", "explanations_router", "reviews_router", "system_router"]


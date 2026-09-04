"""Local duplicate-work candidate retrieval for authorized review."""

from .detector import DUPLICATE_CANDIDATE_THRESHOLD, build_duplicate_candidates
from .text import build_duplicate_search_text, normalize_duplicate_text

__all__ = [
    "DUPLICATE_CANDIDATE_THRESHOLD",
    "build_duplicate_candidates",
    "build_duplicate_search_text",
    "normalize_duplicate_text",
]

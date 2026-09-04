"""Lightweight, deterministic duplicate-search text construction."""

from __future__ import annotations

import re
import unicodedata

import pandas as pd


DUPLICATE_TEXT_FIELDS = (
    "work_description",
    "sector",
    "sub_sector",
    "state_name",
    "district",
    "block",
    "village",
)


def normalize_duplicate_text(value: object) -> str:
    """Normalize case, punctuation, and whitespace without removing key words."""

    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"[_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_duplicate_search_text(works: pd.DataFrame) -> pd.Series:
    """Build one labeled semantic-search text per work from safe source fields."""

    missing = sorted(set(DUPLICATE_TEXT_FIELDS).difference(works.columns))
    if missing:
        raise ValueError(f"Duplicate text fields missing from works: {missing}")

    labels = {
        "work_description": "work",
        "sector": "sector",
        "sub_sector": "sub sector",
        "state_name": "state",
        "district": "district",
        "block": "block",
        "village": "village",
    }
    texts: list[str] = []
    for _, row in works.iterrows():
        parts = [
            f"{labels[field]} {normalize_duplicate_text(row[field])}"
            for field in DUPLICATE_TEXT_FIELDS
            if normalize_duplicate_text(row[field])
        ]
        texts.append(" | ".join(parts))
    return pd.Series(texts, index=works.index, name="normalized_duplicate_search_text")

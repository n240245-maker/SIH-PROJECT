"""Verified local MPLADS guideline extraction and deterministic clause lookup."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import pymupdf


GUIDELINE_TITLE = "Members of Parliament Local Area Development Scheme Guidelines"
GUIDELINE_VERSION = "MPLADS Guidelines 2023 - Second Edition, 14 March 2023"
GUIDELINE_EFFECTIVE_DATE = date(2023, 4, 1)
GUIDELINE_FILENAME = "official_mplads_guidelines.pdf"
OFFICIAL_GUIDELINE_URL = (
    "https://www.mplads.gov.in/MPLADS/UploadedFiles/"
    "MPLADSGuidelines2023_English_.pdf"
)
OFFICIAL_GUIDELINE_INDEX_URL = (
    "https://www.mplads.gov.in/mplads/En/2010-mplads-guidelines.aspx"
)
VERIFICATION_DATE = date(2026, 9, 2)
EXPECTED_PAGE_COUNT = 70
EXPECTED_EDITION_MARKERS = (
    "First Edition, 22nd February, 2023",
    "Second Edition, 14th March, 2023",
)
EXPECTED_EFFECTIVE_MARKER = "come into force with effect from 1st April, 2023"

_HEADER = "MEMBERS OF PARLIAMENT LOCAL AREA DEVELOPMENT SCHEME GUIDELINES"
_CLAUSE_PATTERN = re.compile(r"(?m)^\s*\*?(\d+(?:\.\d+){1,3})\s")
_CHAPTER_PATTERN = re.compile(r"(?im)^\s*CHAPTER\s+(\d+)\s*$")
_ANNEXURE_PATTERN = re.compile(r"(?im)^\s*ANNEXURE\s*[-–—]?\s*([IVX]+)\s*$")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _clean_page_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\u00a0", " ").splitlines()]
    lines = [line for line in lines if line.strip() != _HEADER]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and re.fullmatch(r"(?:\d{1,2}|[ivx]+)", lines[-1].strip(), re.I):
        lines.pop()
    cleaned = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _printed_page(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if re.fullmatch(r"(?:\d{1,2}|[ivx]+)", line, re.I):
            return line
    return None


def _chapter_for_page(text: str, prior: str) -> str:
    annexure = _ANNEXURE_PATTERN.search(text)
    if annexure:
        return f"ANNEXURE {annexure.group(1).upper()}"
    chapter = _CHAPTER_PATTERN.search(text)
    if chapter:
        return f"CHAPTER {chapter.group(1)}"
    if re.search(r"(?im)^\s*DEFINITIONS\s*$", text):
        return "DEFINITIONS"
    return prior


def _clause_references(text: str) -> list[str]:
    return list(dict.fromkeys(_CLAUSE_PATTERN.findall(text)))


def extract_guideline_chunks(
    pdf_path: str | Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract stable page-aligned chunks without OCR or semantic inference."""

    source = Path(pdf_path).resolve()
    source_hash = sha256_file(source)
    document = pymupdf.open(source)
    try:
        if document.page_count != EXPECTED_PAGE_COUNT:
            raise ValueError(
                f"Expected {EXPECTED_PAGE_COUNT} guideline pages, found "
                f"{document.page_count}"
            )
        chunks: list[dict[str, Any]] = []
        raw_character_count = 0
        extractable_pages = 0
        chapter = "FRONT MATTER"
        all_text: list[str] = []
        for page_index in range(document.page_count):
            raw_text = document.load_page(page_index).get_text("text", sort=True)
            raw_character_count += len(raw_text)
            if raw_text.strip():
                extractable_pages += 1
            all_text.append(raw_text)
            cleaned = _clean_page_text(raw_text)
            if not cleaned:
                continue
            chapter = _chapter_for_page(cleaned, chapter)
            clauses = _clause_references(cleaned)
            pdf_page = page_index + 1
            chunks.append(
                {
                    "chunk_id": f"MPLADS-2023-P{pdf_page:03d}",
                    "guideline_version": GUIDELINE_VERSION,
                    "page_start": pdf_page,
                    "page_end": pdf_page,
                    "printed_page": _printed_page(raw_text),
                    "chapter": chapter,
                    "section_or_clause": ", ".join(clauses) if clauses else None,
                    "text": cleaned,
                    "source_file_sha256": source_hash,
                }
            )
        joined = "\n".join(all_text)
        for marker in (*EXPECTED_EDITION_MARKERS, EXPECTED_EFFECTIVE_MARKER):
            if marker not in joined:
                raise ValueError(f"Verified guideline marker not found: {marker}")
        diagnostics = {
            "page_count": document.page_count,
            "extractable_page_count": extractable_pages,
            "extraction_character_count": raw_character_count,
            "chunk_count": len(chunks),
            "pdf_metadata": {
                key: value
                for key, value in document.metadata.items()
                if value not in (None, "")
            },
        }
        return chunks, diagnostics
    finally:
        document.close()


def build_guideline_manifest(
    pdf_path: str | Path,
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    source = Path(pdf_path).resolve()
    return {
        "document_title": GUIDELINE_TITLE,
        "guideline_version": GUIDELINE_VERSION,
        "effective_date": GUIDELINE_EFFECTIVE_DATE.isoformat(),
        "edition_text": list(EXPECTED_EDITION_MARKERS),
        "local_filename": source.name,
        "local_path": str(source),
        "sha256": sha256_file(source),
        "page_count": int(diagnostics["page_count"]),
        "extractable_page_count": int(diagnostics["extractable_page_count"]),
        "official_source_url": OFFICIAL_GUIDELINE_URL,
        "official_index_url": OFFICIAL_GUIDELINE_INDEX_URL,
        "verification_date": VERIFICATION_DATE.isoformat(),
        "verification_status": "VERIFIED_IDENTITY_AND_EDITION",
        "verification_basis": (
            "The official MPLADS portal lists English Guidelines 2023 at the "
            "recorded PDF URL. The local cover, editions page, Clause 1.1, and "
            "indexed official PDF text agree on title, edition, and effective date."
        ),
        "official_byte_comparison_status": (
            "NOT_AVAILABLE_OFFICIAL_HOST_TIMEOUT_LOCAL_SHA_RECORDED"
        ),
        "extraction_method": f"PyMuPDF {pymupdf.version[0]} text extraction; no OCR",
        "extraction_status": "NORMAL_TEXT_EXTRACTION_SUCCESSFUL",
        "extraction_character_count": int(
            diagnostics["extraction_character_count"]
        ),
        "chunk_count": int(diagnostics["chunk_count"]),
        "pdf_metadata": diagnostics["pdf_metadata"],
        "metadata_timestamp_is_edition": False,
    }


def write_guideline_artifacts(
    pdf_path: str | Path,
    output_dir: str | Path,
) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    chunks, diagnostics = extract_guideline_chunks(pdf_path)
    manifest = build_guideline_manifest(pdf_path, diagnostics)
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    chunks_path = destination / "guideline_chunks.json"
    manifest_path = destination / "guideline_manifest.json"
    chunks_path.write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path, chunks_path, chunks, manifest


def load_guideline_chunks(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Guideline chunk artifact must contain a JSON list")
    return payload


def get_guideline_chunk(
    chunk_id: str,
    chunks: Iterable[dict[str, Any]] | str | Path,
) -> dict[str, Any]:
    records = load_guideline_chunks(chunks) if isinstance(chunks, (str, Path)) else chunks
    matches = [record for record in records if record.get("chunk_id") == chunk_id]
    if len(matches) != 1:
        raise KeyError(f"Expected one guideline chunk for {chunk_id!r}, found {len(matches)}")
    return matches[0]


def get_guideline_clause(
    reference: str,
    chunks: Iterable[dict[str, Any]] | str | Path,
) -> list[dict[str, Any]]:
    records = load_guideline_chunks(chunks) if isinstance(chunks, (str, Path)) else chunks
    pattern = re.compile(rf"(?m)^\s*\*?{re.escape(reference)}\s")
    matches = [record for record in records if pattern.search(record.get("text", ""))]
    if not matches:
        raise KeyError(f"Guideline clause {reference!r} was not found")
    return matches

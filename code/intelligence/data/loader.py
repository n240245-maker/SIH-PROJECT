"""Strict CSV loaders that preserve lifecycle tables as separate DataFrames."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pandera.errors import SchemaErrors

from .paths import ProjectPaths
from .schemas import (
    ASSETS_SCHEMA,
    ENTITIES_SCHEMA,
    GROUND_TRUTH_SCHEMA,
    MP_SCHEMA,
    OPERATIONAL_SCHEMAS,
    PAYMENTS_SCHEMA,
    PROGRESS_SCHEMA,
    WORKS_SCHEMA,
    ColumnSpec,
    TableSchema,
)


class DataLoadError(ValueError):
    """Raised when a source file cannot satisfy the exact Day-1 contract."""


@dataclass(slots=True)
class OperationalDataBundle:
    """Six separate operational tables; no merged lifecycle table is exposed."""

    mp: pd.DataFrame
    entities: pd.DataFrame
    works: pd.DataFrame
    payments: pd.DataFrame
    progress: pd.DataFrame
    assets: pd.DataFrame

    @property
    def source_files(self) -> list[str]:
        return [schema.filename for schema in OPERATIONAL_SCHEMAS]

    @property
    def row_counts(self) -> dict[str, int]:
        return {
            "mp": len(self.mp),
            "entities": len(self.entities),
            "works": len(self.works),
            "payments": len(self.payments),
            "progress": len(self.progress),
            "assets": len(self.assets),
        }


@dataclass(slots=True)
class MetadataBundle:
    manifest: pd.DataFrame
    data_dictionary: pd.DataFrame
    source_acquisition_plan: pd.DataFrame


@dataclass(slots=True)
class SupplementalDataBundle:
    allocated_limits: pd.DataFrame
    calamity_consents: pd.DataFrame


def validate_exact_columns(actual_columns: list[str], schema: TableSchema) -> None:
    expected = schema.expected_columns
    missing = [column for column in expected if column not in actual_columns]
    unexpected = [column for column in actual_columns if column not in expected]
    if missing or unexpected or actual_columns != expected:
        raise DataLoadError(
            f"{schema.filename}: exact schema mismatch; "
            f"missing={missing}, unexpected={unexpected}, "
            f"expected_order={expected}, actual_order={actual_columns}"
        )


def _invalid_examples(values: pd.Series, mask: pd.Series) -> list[str]:
    return values.loc[mask].astype("string").dropna().head(5).tolist()


def _parse_column(values: pd.Series, spec: ColumnSpec, filename: str) -> pd.Series:
    if spec.kind in {"string", "category"}:
        parsed = values.astype("string")
        blank = parsed.notna() & parsed.str.strip().eq("")
        if blank.any():
            parsed = parsed.mask(blank, pd.NA)
    elif spec.kind == "date":
        parsed = pd.to_datetime(values, format="%Y-%m-%d", errors="coerce")
        invalid = values.notna() & parsed.isna()
        if invalid.any():
            raise DataLoadError(
                f"{filename}.{spec.name}: malformed date values "
                f"{_invalid_examples(values, invalid)}; expected YYYY-MM-DD"
            )
    elif spec.kind in {"integer", "float"}:
        parsed = pd.to_numeric(values, errors="coerce")
        invalid = values.notna() & parsed.isna()
        if invalid.any():
            raise DataLoadError(
                f"{filename}.{spec.name}: non-numeric values "
                f"{_invalid_examples(values, invalid)}"
            )
        if spec.kind == "integer":
            fractional = parsed.notna() & parsed.mod(1).ne(0)
            if fractional.any():
                raise DataLoadError(
                    f"{filename}.{spec.name}: non-integer values "
                    f"{_invalid_examples(values, fractional)}"
                )
            parsed = parsed.astype("Int64" if parsed.isna().any() else "int64")
        else:
            parsed = parsed.astype("float64")
    elif spec.kind == "boolean":
        normalized = values.astype("string").str.strip().str.lower()
        parsed = normalized.map({"true": True, "false": False})
        invalid = values.notna() & parsed.isna()
        if invalid.any():
            raise DataLoadError(
                f"{filename}.{spec.name}: invalid boolean values "
                f"{_invalid_examples(values, invalid)}; expected true/false"
            )
        parsed = parsed.astype("boolean" if parsed.isna().any() else "bool")
    else:
        raise DataLoadError(f"Unsupported logical type {spec.kind!r} for {filename}.{spec.name}")

    if not spec.nullable and parsed.isna().any():
        raise DataLoadError(
            f"{filename}.{spec.name}: {int(parsed.isna().sum())} null required values"
        )
    return parsed


def load_table(path: str | Path, schema: TableSchema) -> pd.DataFrame:
    source_path = Path(path)
    if not source_path.is_file():
        raise DataLoadError(f"Missing required file: {source_path}")

    raw = pd.read_csv(
        source_path,
        dtype="string",
        encoding="utf-8-sig",
        keep_default_na=True,
        low_memory=False,
    )
    validate_exact_columns(raw.columns.tolist(), schema)

    parsed = pd.DataFrame(index=raw.index)
    for spec in schema.columns:
        parsed[spec.name] = _parse_column(raw[spec.name], spec, schema.filename)

    try:
        schema.pandera_schema().validate(parsed, lazy=True)
    except SchemaErrors as exc:
        failures = exc.failure_cases.head(20).to_dict(orient="records")
        raise DataLoadError(f"{schema.filename}: typed schema validation failed: {failures}") from exc
    return parsed


def load_operational_data(paths: ProjectPaths | None = None) -> OperationalDataBundle:
    """Load the six approved operational tables without joining them."""

    resolved_paths = paths or ProjectPaths.discover()
    data_dir = resolved_paths.demo_data_dir
    return OperationalDataBundle(
        mp=load_table(data_dir / MP_SCHEMA.filename, MP_SCHEMA),
        entities=load_table(data_dir / ENTITIES_SCHEMA.filename, ENTITIES_SCHEMA),
        works=load_table(data_dir / WORKS_SCHEMA.filename, WORKS_SCHEMA),
        payments=load_table(data_dir / PAYMENTS_SCHEMA.filename, PAYMENTS_SCHEMA),
        progress=load_table(data_dir / PROGRESS_SCHEMA.filename, PROGRESS_SCHEMA),
        assets=load_table(data_dir / ASSETS_SCHEMA.filename, ASSETS_SCHEMA),
    )


def load_metadata_files(paths: ProjectPaths | None = None) -> MetadataBundle:
    resolved_paths = paths or ProjectPaths.discover()
    data_dir = resolved_paths.demo_data_dir
    return MetadataBundle(
        manifest=pd.read_csv(data_dir / "00_manifest.csv", encoding="utf-8-sig"),
        data_dictionary=pd.read_csv(data_dir / "08_data_dictionary.csv", encoding="utf-8-sig"),
        source_acquisition_plan=pd.read_csv(
            data_dir / "09_source_acquisition_plan.csv", encoding="utf-8-sig"
        ),
    )


def load_official_supplements(paths: ProjectPaths | None = None) -> SupplementalDataBundle:
    """Load official supplements separately; no unsafe MP-name merge is performed."""

    resolved_paths = paths or ProjectPaths.discover()
    data_dir = resolved_paths.demo_data_dir
    return SupplementalDataBundle(
        allocated_limits=pd.read_csv(
            data_dir / "Allocated Limit for Honble MPs.csv",
            dtype="string",
            encoding="utf-8-sig",
        ),
        calamity_consents=pd.read_csv(
            data_dir / "Amount consented for Calamity.csv",
            dtype="string",
            encoding="utf-8-sig",
        ),
    )


def load_evaluation_ground_truth(paths: ProjectPaths | None = None) -> pd.DataFrame:
    """EVALUATION ONLY: explicitly load isolated synthetic labels for validation/evaluation."""

    resolved_paths = paths or ProjectPaths.discover()
    return load_table(
        resolved_paths.demo_data_dir / GROUND_TRUTH_SCHEMA.filename,
        GROUND_TRUTH_SCHEMA,
    )

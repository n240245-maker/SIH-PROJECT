"""Central, repository-relative filesystem paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    """Resolved paths used by the CSV-first MVP."""

    project_root: Path
    demo_data_dir: Path
    processed_data_dir: Path
    guidelines_dir: Path
    models_dir: Path

    @classmethod
    def from_root(cls, project_root: str | Path) -> "ProjectPaths":
        root = Path(project_root).expanduser().resolve()
        return cls(
            project_root=root,
            demo_data_dir=root / "Demo-data",
            processed_data_dir=root / "data" / "processed",
            guidelines_dir=root / "guidelines",
            models_dir=root / "code" / "models",
        )

    @classmethod
    def discover(cls, start: str | Path | None = None) -> "ProjectPaths":
        """Find the repository root without relying on a machine-specific absolute path."""

        if start is not None:
            current = Path(start).expanduser().resolve()
            if current.is_file():
                current = current.parent
            for candidate in (current, *current.parents):
                if (candidate / "AGENTS.md").is_file() and (candidate / "Demo-data").is_dir():
                    return cls.from_root(candidate)

        # paths.py -> data -> intelligence -> code -> repository root
        module_root = Path(__file__).resolve().parents[3]
        if not (module_root / "Demo-data").is_dir():
            raise RuntimeError("Unable to discover project root containing Demo-data")
        return cls.from_root(module_root)

    def ensure_processed_data_dir(self) -> Path:
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        return self.processed_data_dir


DEFAULT_PATHS = ProjectPaths.discover()
PROJECT_ROOT = DEFAULT_PATHS.project_root
DEMO_DATA_DIR = DEFAULT_PATHS.demo_data_dir
PROCESSED_DATA_DIR = DEFAULT_PATHS.processed_data_dir
GUIDELINES_DIR = DEFAULT_PATHS.guidelines_dir
MODELS_DIR = DEFAULT_PATHS.models_dir


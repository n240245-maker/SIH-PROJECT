"""Generate one deterministic local synthetic-demo-v2 case review PDF."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.dependencies import get_v2_application_service
from backend.reports.v2_case_review import build_v2_case_review_pdf
from intelligence.data.paths import ProjectPaths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-id", default="W-001937")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    paths = ProjectPaths.discover()
    output = (args.output or paths.project_root / "output" / "pdf" / f"MPLADS_Sentinel_V2_{args.work_id}.pdf").resolve()
    if paths.project_root.resolve() not in output.parents:
        raise SystemExit("Output must remain inside the project root")
    output.parent.mkdir(parents=True, exist_ok=True)
    detail = get_v2_application_service().work_detail(args.work_id)
    content = build_v2_case_review_pdf(detail, datetime.now(ZoneInfo("Asia/Kolkata")))
    output.write_bytes(content)
    print(f"Generated {output} ({len(content)} bytes)")


if __name__ == "__main__":
    main()

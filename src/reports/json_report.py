"""
Structured JSON report generator for Smart File Organizer.
Enables machine-readable auditing, external tool integration, and programmatic undo inspection.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from src.core.models import FileItem, ScanConfig, ScanSummary


def generate_json_report(
    items: List[FileItem],
    config: ScanConfig,
    summary: ScanSummary,
    output_path: Path,
    session_timestamp: datetime,
    session_id: str
) -> Path:
    """
    Generates a structured JSON report.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report_data = {
        "report_version": "1.0.0",
        "session_id": session_id,
        "timestamp": session_timestamp.isoformat(),
        "configuration": config.to_dict(),
        "summary": {
            "total_files": len(items),
            "renamed": sum(1 for i in items if i.status.value == "RENAMED"),
            "unchanged": sum(1 for i in items if i.status.value == "UNCHANGED"),
            "skipped": sum(1 for i in items if i.status.value == "SKIPPED"),
            "errors": sum(1 for i in items if i.status.value == "ERROR"),
            "duration_seconds": summary.duration_seconds,
        },
        "files": [item.to_dict() for item in items]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    return output_path

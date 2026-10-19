"""
Excel-compatible CSV report generator for Smart File Organizer.
Writes UTF-8 with BOM (utf-8-sig) so Excel displays international characters correctly.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List

from src.core.models import FileItem


def generate_csv_report(
    items: List[FileItem],
    output_path: Path,
    session_timestamp: datetime
) -> Path:
    """
    Generates a comprehensive CSV report matching all specification requirements.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ts_str = session_timestamp.strftime("%Y-%m-%d %H:%M:%S")

    fieldnames = [
        "Timestamp",
        "Original Full Path",
        "Original Filename",
        "New Full Path",
        "New Filename",
        "Extension",
        "Detected File Type",
        "Extracted Title or Summary",
        "File Size (Bytes)",
        "Formatted Size",
        "Status",
        "Explanation",
        "SHA-256 Hash"
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for item in items:
            writer.writerow({
                "Timestamp": ts_str,
                "Original Full Path": str(item.original_path),
                "Original Filename": item.original_name,
                "New Full Path": str(item.new_path) if item.new_path else "",
                "New Filename": item.new_name,
                "Extension": item.original_ext,
                "Detected File Type": item.file_type,
                "Extracted Title or Summary": item.detected_title or item.content_summary or "",
                "File Size (Bytes)": item.file_size,
                "Formatted Size": item.formatted_size,
                "Status": item.status.value,
                "Explanation": item.explanation,
                "SHA-256 Hash": item.sha256 or "N/A"
            })

    return output_path

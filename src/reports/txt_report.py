"""
Human-readable TXT report generator for Smart File Organizer.
"""

from datetime import datetime
from pathlib import Path
from typing import List

from src.core.models import FileItem, ScanConfig, ScanSummary


def generate_txt_report(
    items: List[FileItem],
    config: ScanConfig,
    summary: ScanSummary,
    output_path: Path,
    session_timestamp: datetime
) -> Path:
    """
    Generates a readable, formatted text report of the operation.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ts_str = session_timestamp.strftime("%Y-%m-%d %H:%M:%S")

    total_scanned = len(items)
    renamed = sum(1 for i in items if i.status.value == "RENAMED")
    unchanged_or_skipped = sum(1 for i in items if i.status.value in ("UNCHANGED", "SKIPPED"))
    errors = sum(1 for i in items if i.status.value == "ERROR")

    lines = []
    lines.append("=" * 80)
    lines.append(" SMART FILE ORGANIZER & INTELLIGENT FILE RENAMER - AUDIT REPORT")
    lines.append("=" * 80)
    lines.append(f"Scan Date & Time  : {ts_str}")
    lines.append(f"Selected Folder   : {config.root_path}")
    lines.append(f"Subfolders        : {'Included (Recursive)' if config.recursive else 'Excluded (Top-level only)'}")
    lines.append(f"Naming Convention : {config.naming_convention.value}")
    lines.append(f"Space Replacement : '{config.space_replacement}'")
    lines.append(f"Max Name Length   : {config.max_filename_length} characters")
    lines.append(f"Date Prefix       : {'Enabled' if config.add_date_prefix else 'Disabled'}")
    lines.append("-" * 80)
    lines.append("SUMMARY STATISTICS")
    lines.append(f"  Total Files Scanned      : {total_scanned}")
    lines.append(f"  Files Successfully Renamed: {renamed}")
    lines.append(f"  Files Unchanged / Skipped : {unchanged_or_skipped}")
    lines.append(f"  Processing / IO Errors   : {errors}")
    lines.append("=" * 80)
    lines.append("DETAILED FILE PROCESSING ENTRIES")
    lines.append("=" * 80)

    for idx, item in enumerate(items, 1):
        status_tag = f"[{item.status.value}]"
        lines.append(f"\n#{idx:04d} {status_tag} {item.original_name}")
        lines.append(f"  Original Path : {item.original_path}")
        if item.new_name and item.new_name != item.original_name:
            lines.append(f"  New Filename  : {item.new_name}")
            lines.append(f"  New Path      : {item.new_path}")
        lines.append(f"  File Type     : {item.file_type} ({item.formatted_size})")
        if item.detected_title:
            lines.append(f"  Detected Title: {item.detected_title}")
        lines.append(f"  Explanation   : {item.explanation}")
        if item.sha256:
            lines.append(f"  SHA-256 Hash  : {item.sha256}")
        if item.error_message:
            lines.append(f"  Error Details : {item.error_message}")

    lines.append("\n" + "=" * 80)
    lines.append(" END OF REPORT")
    lines.append("=" * 80 + "\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path

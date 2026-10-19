"""
Report Manager for Smart File Organizer.
Orchestrates CSV, TXT, and JSON report generation with collision-free timestamps,
manages export directories, and opens reporting folders in the native file manager.
"""

import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from src.core.models import FileItem, ScanConfig, ScanSummary
from src.reports.csv_report import generate_csv_report
from src.reports.txt_report import generate_txt_report
from src.reports.json_report import generate_json_report
from src.utils.platform_utils import get_default_reports_dir, is_windows, is_macos


class ReportManager:
    """Handles report generation and viewing across platforms."""

    def __init__(self, export_dir: Optional[Path] = None):
        self.export_dir = export_dir or get_default_reports_dir()
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_reports(
        self,
        items: List[FileItem],
        config: ScanConfig,
        summary: ScanSummary,
        session_id: Optional[str] = None,
        custom_dir: Optional[Path] = None
    ) -> Tuple[Path, Path, Path]:
        """
        Generates CSV, TXT, and JSON reports with a unified unique timestamp.
        Returns: (csv_path, txt_path, json_path)
        """
        target_dir = custom_dir or self.export_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        ts_filename = now.strftime("%Y%m%d_%H%M%S")
        sess_id = session_id or str(uuid.uuid4())

        base_name = f"smart_organizer_report_{ts_filename}"
        csv_path = target_dir / f"{base_name}.csv"
        txt_path = target_dir / f"{base_name}.txt"
        json_path = target_dir / f"{base_name}.json"

        # Prevent overwriting if multiple reports happen in the same second
        counter = 1
        while csv_path.exists() or txt_path.exists() or json_path.exists():
            base_name = f"smart_organizer_report_{ts_filename}_{counter}"
            csv_path = target_dir / f"{base_name}.csv"
            txt_path = target_dir / f"{base_name}.txt"
            json_path = target_dir / f"{base_name}.json"
            counter += 1

        generate_csv_report(items, csv_path, now)
        generate_txt_report(items, config, summary, txt_path, now)
        generate_json_report(items, config, summary, json_path, now, sess_id)

        return csv_path, txt_path, json_path

    @staticmethod
    def open_folder_in_file_manager(folder_path: Path) -> bool:
        """Opens the specified folder in Windows Explorer, macOS Finder, or Linux file manager."""
        try:
            folder_str = str(folder_path.resolve())
            if is_windows():
                os.startfile(folder_str)
            elif is_macos():
                subprocess.Popen(["open", folder_str])
            else:
                subprocess.Popen(["xdg-open", folder_str])
            return True
        except Exception:
            return False

"""
Intelligent directory scanner and file analyzer.
Performs safe filesystem traversal, detects file types, extracts metadata/titles,
generates proposed filenames, and resolves collisions in preview mode.
"""

import os
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Set

from src.core.models import FileItem, FileStatus, ScanConfig, ScanSummary
from src.core.file_classifier import FileClassifier
from src.core.title_generator import TitleGenerator
from src.core.collision_handler import CollisionHandler
from src.utils.platform_utils import split_filename_and_ext


# Directories and files to automatically skip during scanning
IGNORED_DIR_NAMES = {
    ".git", ".svn", ".hg", "__pycache__", ".venv", "venv", "node_modules",
    "$recycle.bin", "system volume information", ".idea", ".vscode"
}

IGNORED_FILE_NAMES = {
    "thumbs.db", "desktop.ini", ".ds_store"
}


def compute_sha256(file_path: Path, max_bytes: int = 10 * 1024 * 1024) -> Optional[str]:
    """Computes SHA-256 hash using streaming chunks (at most max_bytes)."""
    try:
        hasher = hashlib.sha256()
        bytes_read = 0
        with open(file_path, "rb") as f:
            while bytes_read < max_bytes:
                chunk = f.read(65536)
                if not chunk:
                    break
                hasher.update(chunk)
                bytes_read += len(chunk)
        return hasher.hexdigest()
    except Exception:
        return None


class DirectoryScanner:
    """
    Scans a directory, analyzes files, and generates rename proposals with safety checks.
    """

    def __init__(
        self,
        config: ScanConfig,
        classifier: Optional[FileClassifier] = None,
        title_generator: Optional[TitleGenerator] = None,
    ):
        self.config = config
        self.classifier = classifier or FileClassifier()
        self.title_generator = title_generator or TitleGenerator(config)
        self.collision_handler = CollisionHandler()
        self._is_cancelled = False

    def cancel(self) -> None:
        """Flags the current scan operation to cancel."""
        self._is_cancelled = True

    def scan(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        item_found_callback: Optional[Callable[[FileItem], None]] = None
    ) -> tuple[List[FileItem], ScanSummary]:
        """
        Executes directory scanning and file analysis.
        Returns: (list_of_analyzed_items, scan_summary)
        """
        self._is_cancelled = False
        start_time = datetime.now()
        root = self.config.root_path.resolve()

        # Step 1: Collect all candidate file paths
        candidate_paths: List[Path] = []
        try:
            if self.config.recursive:
                for dirpath, dirnames, filenames in os.walk(root):
                    # Filter out ignored directories in-place
                    dirnames[:] = [
                        d for d in dirnames
                        if d.lower() not in IGNORED_DIR_NAMES and (self.config.include_hidden or not d.startswith("."))
                    ]
                    for fname in filenames:
                        if fname.lower() in IGNORED_FILE_NAMES:
                            continue
                        if not self.config.include_hidden and fname.startswith("."):
                            continue
                        candidate_paths.append(Path(dirpath) / fname)
            else:
                for entry in root.iterdir():
                    if entry.is_file():
                        if entry.name.lower() in IGNORED_FILE_NAMES:
                            continue
                        if not self.config.include_hidden and entry.name.startswith("."):
                            continue
                        candidate_paths.append(entry)
        except (OSError, PermissionError) as e:
            # Root directory permission error
            summary = ScanSummary(errors=1, start_time=start_time, end_time=datetime.now())
            error_item = FileItem(
                original_path=root,
                original_name=root.name,
                status=FileStatus.ERROR,
                explanation=f"Cannot access directory: {str(e)}",
                error_message=str(e),
                is_supported=False
            )
            return [error_item], summary

        total_files = len(candidate_paths)
        analyzed_items: List[FileItem] = []

        summary = ScanSummary(
            total_files=total_files,
            start_time=start_time
        )

        # Step 2: Analyze each file
        for idx, file_path in enumerate(candidate_paths, 1):
            if self._is_cancelled:
                break

            if progress_callback:
                progress_callback(idx, total_files, file_path.name)

            item = self._analyze_file(file_path)
            analyzed_items.append(item)

            if item_found_callback:
                item_found_callback(item)

        # Step 3: Group files with matching domains into dedicated folders
        if getattr(self.config, "group_by_domain", True):
            from src.core.domain_matcher import DomainMatcher
            DomainMatcher.group_files_by_domain(analyzed_items, self.config)

        # Step 4: Resolve collisions across the entire batch
        self.collision_handler.resolve_batch_collisions(analyzed_items)

        # Step 5: Finalize summary counts and selection states
        for item in analyzed_items:
            if item.status == FileStatus.READY_TO_RENAME:
                item.is_selected = True
                summary.ready_to_rename += 1
            elif item.status == FileStatus.UNCHANGED:
                item.is_selected = False
                summary.unchanged += 1
            elif item.status == FileStatus.ERROR:
                item.is_selected = False
                summary.errors += 1

            if item.is_supported:
                summary.supported_files += 1
            else:
                summary.unsupported_files += 1

        summary.end_time = datetime.now()
        return analyzed_items, summary

    def _analyze_file(self, file_path: Path) -> FileItem:
        """Analyzes a single file and extracts its descriptive title."""
        t0 = time.time()
        stem, ext = split_filename_and_ext(file_path.name)

        item = FileItem(
            original_path=file_path,
            original_name=file_path.name,
            original_stem=stem,
            original_ext=ext,
            status=FileStatus.ANALYZING
        )

        # Check symlink safety
        if file_path.is_symlink():
            try:
                target = file_path.resolve()
                if not target.exists():
                    item.status = FileStatus.ERROR
                    item.is_supported = False
                    item.error_message = "Broken symbolic link"
                    item.explanation = "Broken symbolic link target does not exist."
                    item.new_name = item.original_name
                    item.analysis_time_ms = (time.time() - t0) * 1000
                    return item
            except Exception as e:
                item.status = FileStatus.ERROR
                item.error_message = str(e)
                item.explanation = f"Symbolic link error: {str(e)}"
                item.new_name = item.original_name
                return item

        # Read file stat
        try:
            st = file_path.stat()
            item.file_size = st.st_size
            mtime = datetime.fromtimestamp(st.st_mtime)
        except (OSError, PermissionError) as e:
            item.status = FileStatus.ERROR
            item.error_message = str(e)
            item.explanation = f"Permission or access error: {str(e)}"
            item.new_name = item.original_name
            item.is_supported = False
            item.analysis_time_ms = (time.time() - t0) * 1000
            return item

        # Get specialized extractor
        extractor = self.classifier.get_extractor_for_file(file_path)

        # Extract content safely
        try:
            result = extractor.extract(file_path, config=self.config)
            item.file_type = result.file_type
            item.detected_title = result.title
            item.content_summary = result.summary
            item.is_supported = result.is_supported if result.is_supported is not None else True

            if result.error:
                item.error_message = result.error

            # Generate proposed filename
            proposed_name, status, explanation = self.title_generator.generate_proposed_filename(
                item=item,
                result=result,
                file_mtime=mtime
            )
            item.new_name = proposed_name
            item.status = status
            item.explanation = explanation

        except Exception as e:
            item.status = FileStatus.ERROR
            item.error_message = str(e)
            item.explanation = f"Unexpected analysis error: {str(e)}"
            item.new_name = item.original_name

        item.analysis_time_ms = (time.time() - t0) * 1000
        return item

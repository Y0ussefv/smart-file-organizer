"""
Collision Handler for Smart File Organizer.
Ensures no existing file is ever overwritten, detects naming collisions within the current batch
as well as against existing files on disk, and deterministically generates unique suffixes (_2, _3, etc.).
"""

from pathlib import Path
from typing import Dict, Set, List, Optional
from src.utils.platform_utils import split_filename_and_ext
from src.core.models import FileItem, FileStatus


class CollisionHandler:
    """
    Tracks and resolves destination collisions for a batch of files.
    """

    def __init__(self, target_directory: Optional[Path] = None):
        self.target_directory = target_directory
        # Maps parent directory -> set of lowercased filenames claimed or existing
        self._claimed_names: Dict[Path, Set[str]] = {}
        # Maps parent directory -> set of original lowercased filenames in this batch
        self._batch_originals: Dict[Path, Set[str]] = {}

    def register_existing_disk_files(self, directory: Path) -> None:
        """Indexes files currently existing on disk in the given directory."""
        if directory not in self._claimed_names:
            self._claimed_names[directory] = set()

        if directory.exists() and directory.is_dir():
            try:
                for entry in directory.iterdir():
                    if entry.is_file():
                        self._claimed_names[directory].add(entry.name.lower())
            except (OSError, PermissionError):
                pass

    def register_batch_item(self, item: FileItem) -> None:
        """Registers an item's original name so we know it belongs to the current batch."""
        parent = item.original_path.parent
        if parent not in self._batch_originals:
            self._batch_originals[parent] = set()
        self._batch_originals[parent].add(item.original_name.lower())

    def resolve_proposed_name(
        self,
        item: FileItem,
        candidate_name: str,
        claim: bool = True
    ) -> str:
        """
        Determines the safe, collision-free filename for the given item.
        - If candidate_name equals original_name, returns it directly.
        - If candidate_name is already claimed or exists on disk (and is not item's own original name),
          appends _2, _3, etc.
        - If claim is True, claims the resulting name in memory to prevent future collisions in this batch.
        """
        parent = item.original_path.parent
        self.register_existing_disk_files(parent)

        stem, ext = split_filename_and_ext(candidate_name)
        claimed = self._claimed_names[parent]
        batch_orig = self._batch_originals.get(parent, set())

        # If candidate name matches the file's own original name, it's not a collision
        if candidate_name.lower() == item.original_name.lower():
            if claim:
                claimed.add(candidate_name.lower())
            return candidate_name

        proposed = candidate_name
        counter = 2

        # Check collision:
        # A collision occurs if proposed.lower() is already claimed,
        # OR if it exists on disk and is NOT an item in our current batch that is being renamed away
        while True:
            lower_prop = proposed.lower()

            # Is it claimed by another item in this batch?
            is_claimed_in_batch = lower_prop in claimed

            # Does it exist on disk as a file that is NOT this item itself?
            disk_path = parent / proposed
            exists_on_disk = disk_path.exists()
            is_same_file = (disk_path.resolve() == item.original_path.resolve()) if exists_on_disk and item.original_path.exists() else False

            if not is_claimed_in_batch and (not exists_on_disk or is_same_file):
                # Safe to use!
                break

            # Need suffix
            proposed = f"{stem}_{counter}{ext}"
            counter += 1

        if claim:
            claimed.add(proposed.lower())

        return proposed

    def resolve_batch_collisions(self, items: List[FileItem]) -> None:
        """
        Processes a full batch of items, ensuring all proposed names are unique and safe.
        """
        # First register all original names
        for item in items:
            self.register_batch_item(item)
            parent = item.original_path.parent
            self.register_existing_disk_files(parent)

        # Then resolve each candidate name
        for item in items:
            if not item.new_name:
                item.new_name = item.original_name

            resolved = self.resolve_proposed_name(item, item.new_name, claim=True)
            item.new_name = resolved
            item.new_path = item.original_path.parent / resolved

            # Update status if unchanged
            if item.new_name == item.original_name:
                if item.status in (FileStatus.READY_TO_RENAME, FileStatus.FOUND, FileStatus.ANALYZING):
                    item.status = FileStatus.UNCHANGED
                    if not item.explanation:
                        item.explanation = "Proposed name is identical to original filename."

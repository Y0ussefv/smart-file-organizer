"""
Domain Matcher and Organizer for Smart File Organizer.
Detects common domains, projects, client names, or entities across scanned files
and organizes matching files into dedicated domain folders.
"""

import re
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple

from src.core.models import FileItem, FileStatus, ScanConfig
from src.core.filename_sanitizer import sanitize_component_name


# Category words, file formats, and document types that describe file nature rather than entity domain
DOMAIN_EXCLUDED_TOKENS = {
    # File kinds & media
    "logo", "logos", "icon", "icons", "image", "images", "img", "photo", "photos",
    "pic", "pics", "picture", "pictures", "screenshot", "screenshots", "vector",
    "drawing", "artwork", "illustration", "banner", "thumbnail", "thumb",
    "pdf", "doc", "docx", "document", "documents", "word", "excel", "sheet",
    "sheets", "xlsx", "csv", "tsv", "powerpoint", "ppt", "pptx", "presentation",
    "slides", "text", "txt", "file", "files", "scan", "scans", "scanned", "page",
    "pages", "mp3", "wav", "audio", "video", "mp4", "mkv", "zip", "archive",

    # Generic status & document boilerplate
    "report", "reports", "summary", "contract", "contracts", "agreement",
    "invoice", "invoices", "receipt", "receipts", "statement", "proposal",
    "notes", "memo", "letter", "form", "forms", "paper", "manual", "guide",
    "overview", "brief", "draft", "copy", "final", "v1", "v2", "v3", "v4",
    "new", "old", "backup", "sample", "test", "tests", "demo", "temp", "tmp",
    "export", "data", "archive", "code", "script", "source", "module", "asset",
    "assets", "untitled", "raw", "edit", "edited", "version",

    # Stop words (English, French, Spanish, German)
    "the", "and", "or", "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "a", "an", "is", "le", "la", "les", "de", "des", "du", "en",
    "un", "une", "et", "pour", "dans", "el", "los", "las", "del", "der",
    "die", "das", "und", "mit", "von"
}


class DomainMatcher:
    """
    Analyzes scanned files, identifies common domain/project/entity names,
    and assigns matching files to target domain subfolders.
    """

    @staticmethod
    def extract_entity_candidates(text: str) -> List[str]:
        """
        Extracts candidate domain tokens and clean multi-word phrases from text.
        Excludes generic categories (logo, pdf, report) and stop words.
        """
        if not text:
            return []

        # Split into alphanumeric word tokens
        raw_tokens = re.findall(r'[A-Za-z0-9\u0080-\uffff]+', text)
        filtered_tokens = []
        for t in raw_tokens:
            t_low = t.lower()
            if len(t) < 2 or t.isdigit() or t_low in DOMAIN_EXCLUDED_TOKENS:
                continue
            filtered_tokens.append(t)

        candidates = []

        # 1. Unigrams
        for t in filtered_tokens:
            candidates.append(t)

        # 2. Bigrams (e.g. "Acme Corp")
        for i in range(len(filtered_tokens) - 1):
            candidates.append(f"{filtered_tokens[i]} {filtered_tokens[i+1]}")

        return candidates

    @classmethod
    def find_file_domain_candidates(cls, item: FileItem) -> Set[str]:
        """Collects candidate domain entities from an item's title, stem, and summary."""
        candidates = set()

        # Check detected title
        if item.detected_title:
            candidates.update(cls.extract_entity_candidates(item.detected_title))

        # Check proposed new name
        if item.new_name:
            stem = Path(item.new_name).stem
            candidates.update(cls.extract_entity_candidates(stem))

        # Check original stem
        if item.original_stem:
            candidates.update(cls.extract_entity_candidates(item.original_stem))

        return candidates

    @classmethod
    def group_files_by_domain(
        cls,
        items: List[FileItem],
        config: ScanConfig
    ) -> Dict[str, List[FileItem]]:
        """
        Groups matching files into domains and assigns target_subfolder on eligible FileItems.
        Returns mapping of domain_name -> list of FileItems.
        """
        if not getattr(config, "group_by_domain", True):
            return {}

        min_files = getattr(config, "min_domain_files", 2)
        if len(items) < min_files:
            return {}

        # Group items by parent folder so we don't group unrelated directories together
        items_by_parent: Dict[Path, List[FileItem]] = defaultdict(list)
        for item in items:
            items_by_parent[item.original_path.parent].append(item)

        domain_groups: Dict[str, List[FileItem]] = defaultdict(list)

        for parent_dir, parent_items in items_by_parent.items():
            # If the directory itself is already named after an entity, check to avoid duplicate nesting
            parent_name = parent_dir.name.lower()

            # Map domain candidate (lowercased) -> list of (item, original_casing)
            candidate_map: Dict[str, List[Tuple[FileItem, str]]] = defaultdict(list)

            for item in parent_items:
                cands = cls.find_file_domain_candidates(item)
                for cand in cands:
                    cand_low = cand.lower()
                    if cand_low != parent_name:
                        candidate_map[cand_low].append((item, cand))

            # Filter candidates that meet the min_files threshold
            # Prefer longer candidate phrases first (e.g., "acme corp" over "acme")
            sorted_candidates = sorted(
                candidate_map.keys(),
                key=lambda k: (len(k.split()), len(candidate_map[k]), len(k)),
                reverse=True
            )

            assigned_items: Set[str] = set()

            for cand_low in sorted_candidates:
                matched_entries = candidate_map[cand_low]
                # Only items not yet assigned to a longer/more specific domain
                available_entries = [e for e in matched_entries if e[0].id not in assigned_items]

                # Check if enough files share this domain
                unique_available_items = {e[0].id: e for e in available_entries}
                if len(unique_available_items) >= min_files:
                    # Determine display name (use most common original casing)
                    casing_counts: Dict[str, int] = defaultdict(int)
                    for _, orig_casing in available_entries:
                        casing_counts[orig_casing] += 1
                    best_casing = max(casing_counts.keys(), key=lambda c: casing_counts[c])

                    # Clean subfolder name according to naming convention or safe path
                    subfolder_name = sanitize_component_name(
                        best_casing.replace(" ", config.space_replacement)
                    )

                    for item_id, (item, _) in unique_available_items.items():
                        item.domain = best_casing
                        item.target_subfolder = subfolder_name
                        assigned_items.add(item.id)
                        domain_groups[best_casing].append(item)

                        # Mark as ready to rename/move so the engine executes the folder organization
                        if item.status in (FileStatus.FOUND, FileStatus.UNCHANGED, FileStatus.READY_TO_RENAME):
                            item.status = FileStatus.READY_TO_RENAME
                            item.is_selected = True
                            if not item.new_name:
                                item.new_name = item.original_name

                        # Enhance explanation
                        folder_notice = f"Grouped into domain folder '{subfolder_name}'"
                        if folder_notice not in item.explanation:
                            if item.explanation:
                                item.explanation = f"{item.explanation} | {folder_notice}"
                            else:
                                item.explanation = folder_notice

        return domain_groups

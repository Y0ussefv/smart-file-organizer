"""
Smart organizer.

Organizes the Downloads folder like a careful human (or agent) would:

1. Unwrap useless nesting:      folderX/folderY/FILES          ->  folderX/FILES
2. Software projects (.git, package.json, ...) are only unwrapped, never rearranged.
3. Everything else gets a project folder and, only when useful, subfolders:
                                 Project Delfa/Contact, Project Delfa/Assets ...
   chosen by OpenAI from the real content of each file, with exact file names.
4. New things that belong to an existing project folder are merged into it.

Every move is recorded in the undo history (one session per operation) and nothing is
ever overwritten.
"""

import logging
import os
import re
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.filename_sanitizer import build_safe_filename, sanitize_stem
from src.core.models import RenameHistoryRecord
from src.core.openai_titler import chat_json
from src.storage.history import HistoryManager
from src.storage.settings import SettingsManager
from src.utils.platform_utils import split_filename_and_ext

logger = logging.getLogger("SmartFileOrganizer")

JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini", ".localized", "__macosx", "icon\r"}
CODE_MARKERS = {
    ".git", ".svn", ".hg", "package.json", "pyproject.toml", "setup.py", "requirements.txt",
    "cargo.toml", "go.mod", "pom.xml", "build.gradle", "composer.json", "gemfile", "makefile",
    "cmakelists.txt", "node_modules", ".venv", "venv", "pubspec.yaml", "project.godot",
}
CODE_SUFFIXES = (".sln", ".xcodeproj", ".xcworkspace", ".csproj", ".uproject")
# Folders that are really "files" (apps, bundles, libraries): never opened or rearranged
BUNDLE_SUFFIXES = (".app", ".bundle", ".framework", ".download", ".photoslibrary",
                   ".fcpbundle", ".logicx", ".pkg", ".plugin", ".kext", ".lrdata", ".band")
PREFIX_RE = re.compile(r"^\d{2}-\d{2}[ _]")

MAX_FILES = 300        # files considered in one folder
MAX_AI_TITLES = 40     # files that get an OpenAI title per operation (cost control)
MAX_DEPTH = 2          # subfolder levels below a project folder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_prefix(name: str) -> str:
    return PREFIX_RE.sub("", name or "").strip()


def is_junk(p: Path) -> bool:
    n = p.name.lower()
    return n in JUNK_NAMES or n.startswith("._") or n.startswith("~$")


def is_bundle(p: Path) -> bool:
    return p.name.lower().endswith(BUNDLE_SUFFIXES)


def _entries(folder: Path) -> List[Path]:
    try:
        return sorted(e for e in folder.iterdir() if not is_junk(e))
    except OSError:
        return []


def is_code_project(folder: Path) -> bool:
    """True when the folder (or its first level) looks like a software project."""
    for level in (folder, *[e for e in _entries(folder) if e.is_dir()][:20]):
        for e in _entries(level):
            n = e.name.lower()
            if n in CODE_MARKERS or n.endswith(CODE_SUFFIXES):
                return True
    return False


def unwrap(folder: Path) -> Path:
    """Follow single-subfolder chains: folderX/folderY/(files) -> returns folderY."""
    cur = folder
    for _ in range(10):
        entries = _entries(cur)
        if len(entries) == 1 and entries[0].is_dir() and not is_bundle(entries[0]):
            cur = entries[0]
        else:
            break
    return cur


def list_files(root: Path, limit: int = MAX_FILES) -> List[Path]:
    out: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        keep = []
        for name in sorted(dirnames):
            sub = d / name
            if is_junk(sub) or name.startswith("."):
                continue
            if is_bundle(sub):
                out.append(sub)  # bundles move as a whole
                continue
            keep.append(name)
        dirnames[:] = keep
        for name in sorted(filenames):
            p = d / name
            if not is_junk(p) and not name.startswith("."):
                out.append(p)
        if len(out) >= limit:
            break
    return out[:limit]


def clean_folder_name(name: str) -> str:
    name = strip_prefix(name)
    name = re.sub(r"[_]+", " ", name)
    return sanitize_stem(name, max_length=60).strip(" .") if name else ""


def clean_rel_folder(rel: str, max_depth: int) -> List[str]:
    parts = [p for p in re.split(r"[\\/]+", rel or "") if p.strip() and p.strip() not in (".", "..")]
    return [c for c in (clean_folder_name(p) for p in parts[:max_depth]) if c]


def remove_empty_dirs(root: Path, keep: Tuple[Path, ...] = ()) -> None:
    """Delete folders under (and including) root that are empty or contain only junk."""
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        d = Path(dirpath)
        if any(d == k for k in keep):
            continue
        try:
            remaining = list(d.iterdir())
            if all(is_junk(e) for e in remaining):
                for e in remaining:
                    shutil.rmtree(e) if e.is_dir() else e.unlink()
                d.rmdir()
        except OSError:
            continue


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

@dataclass
class Move:
    src: Path
    dst: Path


@dataclass
class OrganizePlan:
    base: Path                       # Downloads folder
    cleanup: List[Path] = field(default_factory=list)   # folders to remove if left empty
    moves: List[Move] = field(default_factory=list)
    explanation: str = ""

    @property
    def renamed(self) -> int:
        return sum(1 for m in self.moves if m.src.name != m.dst.name)

    @property
    def top_folders(self) -> List[Path]:
        tops = set()
        for m in self.moves:
            try:
                rel = m.dst.relative_to(self.base)
            except ValueError:
                continue
            if len(rel.parts) > 1:
                tops.add(self.base / rel.parts[0])
        return sorted(tops)

    def summary(self) -> str:
        if not self.moves:
            return "Nothing to change."
        return (f"{len(self.moves)} item(s) moved into {len(self.top_folders)} folder(s), "
                f"{self.renamed} renamed.")

    def details(self, limit: int = 60) -> str:
        lines = []
        for m in self.moves[:limit]:
            try:
                src = m.src.relative_to(self.base)
                dst = m.dst.relative_to(self.base)
            except ValueError:
                src, dst = m.src, m.dst
            lines.append(f"{src}  →  {dst}")
        if len(self.moves) > limit:
            lines.append(f"… and {len(self.moves) - limit} more")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI prompts
# ---------------------------------------------------------------------------

PROJECT_SYSTEM = """You are a meticulous professional organizer arranging ONE downloaded folder, like a careful human assistant.
Design a clean structure for its files:
- project_folder: a short, specific name for the whole folder from its content (client / company / project / event / topic), e.g. "Project Delfa", "Bee Diagnostic Mission", "Marrakech Trip 2026". 2-5 words, no date.
- existing_folder: if this content clearly belongs to one of the user's EXISTING folders listed, give its exact name (the files will be merged into it); otherwise "".
- For each file: a subfolder path inside the project ("" = project root) and a precise title (3-10 words, no extension, keep the given title if it is already good; use exact names, numbers and dates found in it).
Rules for subfolders:
- Create subfolders ONLY when the project has more than 5 files, and only for a category with at least 2 files. Small projects stay flat.
- Use human categories in the content's language, e.g. Contracts, Invoices, Contact, Assets, Logos, Photos, Presentations, Reports, Documents, Data, Design, Videos, Audio, Admin.
- At most 2 levels (e.g. "Assets/Logos"). Never a folder that would only contain one other folder.
Every file id must appear exactly once. Return JSON only."""

PROJECT_SCHEMA = {
    "name": "project_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "project_folder": {"type": "string"},
            "existing_folder": {"type": "string"},
            "items": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"id": {"type": "integer"}, "folder": {"type": "string"}, "title": {"type": "string"}},
                "required": ["id", "folder", "title"],
            }},
        },
        "required": ["project_folder", "existing_folder", "items"],
    },
}

SORT_SYSTEM = """You are a meticulous professional organizer tidying a Downloads folder, like a careful human assistant.
You get loose files (with their content titles) and the user's existing folders.
For each file decide where it belongs:
- folder "" = leave it loose in Downloads (use this when unsure).
- an EXISTING folder (exact name, optionally with one subfolder inside it, existing or new, e.g. "Project Delfa/Contracts") when the file clearly belongs to that project / client / topic.
- a NEW folder only when at least 2 of these files clearly share the same project / client / topic; give it a short specific name (2-5 words, no date), optionally with one subfolder.
Also give each file a precise title (3-10 words, no extension; keep the given title if it is already good).
Every file id must appear exactly once. Return JSON only."""

SORT_SCHEMA = {
    "name": "sort_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"id": {"type": "integer"}, "folder": {"type": "string"}, "title": {"type": "string"}},
                "required": ["id", "folder", "title"],
            }},
        },
        "required": ["items"],
    },
}

PLACE_SYSTEM = """You file ONE newly downloaded file into the user's existing folders, like a careful human assistant.
Choose a folder only when the file clearly belongs to that project / client / company / topic (same names, same project).
You may add ONE subfolder inside the chosen existing folder (existing or new, e.g. "Project Delfa/Contracts") when that matches how the folder is organized.
If unsure, answer folder "" (the file stays in Downloads). Return JSON only."""

PLACE_SCHEMA = {
    "name": "placement",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"folder": {"type": "string"}, "reason": {"type": "string"}},
        "required": ["folder", "reason"],
    },
}


# ---------------------------------------------------------------------------
# Organizer
# ---------------------------------------------------------------------------

class SmartOrganizer:
    def __init__(self, downloads: Path, settings: Optional[SettingsManager] = None,
                 history: Optional[HistoryManager] = None):
        self.base = Path(downloads)
        self.settings = settings or SettingsManager()
        self.history = history or HistoryManager()
        self.config = self.settings.get_scan_config(self.base)
        self.api_key = (self.config.openai_api_key or "").strip()
        self.model = self.config.openai_model or "gpt-5-mini"

    # ---- settings -----------------------------------------------------------
    @property
    def prefix(self) -> str:
        if self.settings.get("watcher_date_prefix", True):
            return datetime.now().strftime("%y-%m")
        return ""

    def _file_name(self, title: str, original: str) -> str:
        p = self.prefix
        return build_safe_filename(
            candidate_name=title,
            original_filename=original,
            convention=self.config.naming_convention,
            space_replacement=self.config.space_replacement,
            max_length=self.config.max_filename_length,
            date_prefix=p or None,
            date_prefix_separator=" ",
        )

    def _new_top_folder_name(self, name: str) -> str:
        name = clean_folder_name(name)
        return f"{self.prefix} {name}" if self.prefix and name else name

    def existing_folders(self, exclude: Optional[Path] = None, limit: int = 80) -> Dict[str, Path]:
        """Top-level folders of Downloads, keyed by lower-case name without date prefix."""
        out: Dict[str, Path] = {}
        for e in _entries(self.base):
            if e.is_dir() and not is_bundle(e) and not e.name.startswith(".") and e != exclude:
                out.setdefault(strip_prefix(e.name).lower(), e)
            if len(out) >= limit:
                break
        return out

    def folder_tree_text(self, exclude: Optional[Path] = None) -> str:
        lines = []
        for _, top in self.existing_folders(exclude).items():
            subs = [s.name for s in _entries(top) if s.is_dir() and not is_bundle(s)][:15]
            lines.append(f"- {top.name}" + (f"  (subfolders: {', '.join(subs)})" if subs else ""))
        return "\n".join(lines) or "(none)"

    # ---- describing files ------------------------------------------------------
    def describe(self, files: List[Path], rel_to: Path) -> List[Dict[str, Any]]:
        """Local analysis for every file + an OpenAI title for the first MAX_AI_TITLES."""
        from src.core.scanner import DirectoryScanner
        import copy

        local_cfg = copy.copy(self.config)
        local_cfg.openai_api_key = ""
        local_cfg.groq_api_key = ""
        local_cfg.google_api_key = ""
        local_cfg.enable_google_ai = False
        local_scanner = DirectoryScanner(local_cfg)
        ai_scanner = DirectoryScanner(self.config) if self.api_key else local_scanner

        def one(args):
            idx, p = args
            if p.is_dir():  # bundle
                return {"id": idx, "path": p, "rel": str(p.relative_to(rel_to)), "type": "Application / bundle",
                        "title": strip_prefix(split_filename_and_ext(p.name)[0]), "summary": ""}
            scanner = ai_scanner if idx < MAX_AI_TITLES else local_scanner
            try:
                item = scanner.analyze_file(p)
                title = item.detected_title or split_filename_and_ext(p.name)[0]
                ftype, summary = item.file_type, (item.content_summary or "")[:200]
            except Exception:
                title, ftype, summary = split_filename_and_ext(p.name)[0], "Unknown", ""
            return {"id": idx, "path": p, "rel": str(p.relative_to(rel_to)), "type": ftype,
                    "title": strip_prefix(title), "summary": summary}

        with ThreadPoolExecutor(max_workers=6) as pool:
            return list(pool.map(one, enumerate(files)))

    @staticmethod
    def _files_text(desc: List[Dict[str, Any]]) -> str:
        return "\n".join(
            f'{d["id"]}. {d["rel"]} | type: {d["type"]} | title: {d["title"]}'
            + (f' | {d["summary"]}' if d["summary"] else "")
            for d in desc
        )

    # ---- destination helpers ---------------------------------------------------------
    def _claim(self, dst: Path, src: Path, claimed: set) -> Path:
        """Collision-free destination (never overwrite)."""
        stem, ext = split_filename_and_ext(dst.name)
        cand, n = dst, 2
        while (str(cand).lower() in claimed) or (cand.exists() and cand.resolve() != src.resolve()):
            cand = dst.with_name(f"{stem}_{n}{ext}")
            n += 1
        claimed.add(str(cand).lower())
        return cand

    # ---- 1. a folder that arrived in Downloads -------------------------------------
    def plan_folder(self, folder: Path) -> OrganizePlan:
        folder = Path(folder)
        plan = OrganizePlan(base=self.base, cleanup=[folder])
        content = unwrap(folder)
        claimed: set = set()

        if is_code_project(content) or not self.api_key:
            # Only remove useless nesting; keep the inside exactly as it is.
            if content != folder:
                for e in _entries(content):
                    plan.moves.append(Move(e, self._claim(folder / e.name, e, claimed)))
            plan.explanation = ("Software project: only unwrapped." if is_code_project(content)
                                else "Unwrapped (add an OpenAI key for smart project folders).")
            return plan

        files = list_files(content)
        if not files:
            return plan
        desc = self.describe(files, content)
        data, err = chat_json(
            self.api_key, self.model, PROJECT_SYSTEM,
            f"Downloaded folder name: {folder.name}\n\nUser's existing folders in Downloads:\n"
            f"{self.folder_tree_text(exclude=folder)}\n\nFiles ({len(desc)}):\n{self._files_text(desc)}",
            PROJECT_SCHEMA,
        )
        if err or not data:
            logger.warning("Project plan failed for %s: %s", folder, err)
            if content != folder:
                for e in _entries(content):
                    plan.moves.append(Move(e, self._claim(folder / e.name, e, claimed)))
            plan.explanation = f"Unwrapped only ({err})."
            return plan

        existing = self.existing_folders(exclude=folder)
        ex_name = strip_prefix(data.get("existing_folder", "")).lower()
        if ex_name and ex_name in existing:
            target = existing[ex_name]
            plan.explanation = f"Merged into existing folder '{target.name}'."
        else:
            name = clean_folder_name(data.get("project_folder", "")) or clean_folder_name(folder.name) or "Project"
            if strip_prefix(folder.name).lower() == name.lower():
                target = folder  # keep the same folder
            else:
                target = self.base / self._new_top_folder_name(name)
                if target.exists() and not target.is_dir():
                    target = self.base / f"{target.name} (2)"
            plan.explanation = f"Organized as '{target.name}'."

        by_id = {int(i["id"]): i for i in data.get("items", []) if isinstance(i.get("id"), int)}
        for d in desc:
            src: Path = d["path"]
            choice = by_id.get(d["id"])
            if choice:
                sub = clean_rel_folder(choice.get("folder", ""), MAX_DEPTH)
                title = (choice.get("title") or d["title"]).strip()
            else:  # model forgot it: keep its relative place
                sub = clean_rel_folder(str(Path(d["rel"]).parent), MAX_DEPTH)
                title = d["title"]
            new_name = src.name if src.is_dir() else (self._file_name(title, src.name) if title else src.name)
            dst = self._claim(target.joinpath(*sub, new_name), src, claimed)
            if dst != src:
                plan.moves.append(Move(src, dst))
        return plan

    # ---- 2. one new file: put it in the right existing folder ------------------------
    def plan_placement(self, file: Path, title: str = "", file_type: str = "", summary: str = "") -> OrganizePlan:
        plan = OrganizePlan(base=self.base)
        existing = self.existing_folders()
        if not self.api_key or not existing or not file.exists():
            return plan
        data, err = chat_json(
            self.api_key, self.model, PLACE_SYSTEM,
            f"New file: {file.name}\nType: {file_type}\nContent title: {title}\nDetails: {summary}\n\n"
            f"User's folders in Downloads:\n{self.folder_tree_text()}",
            PLACE_SCHEMA, timeout_seconds=60,
        )
        if err or not data:
            return plan
        parts = clean_rel_folder(data.get("folder", ""), 2)
        if not parts or parts[0].lower() not in existing:
            return plan
        top = existing[parts[0].lower()]
        dst = self._claim(top.joinpath(*parts[1:], file.name), file, set())
        plan.moves.append(Move(file, dst))
        plan.explanation = data.get("reason", "")
        return plan

    # ---- 3. "Organize Downloads now" ---------------------------------------------------
    def plan_downloads(self) -> OrganizePlan:
        plan = OrganizePlan(base=self.base)
        claimed: set = set()
        loose: List[Path] = []
        for e in _entries(self.base):
            if e.name.startswith("."):
                continue
            if e.is_dir() and not is_bundle(e):
                content = unwrap(e)
                if content != e:  # remove useless nesting inside existing folders
                    plan.cleanup.append(e)
                    for c in _entries(content):
                        plan.moves.append(Move(c, self._claim(e / c.name, c, claimed)))
            elif e.is_file() or is_bundle(e):
                from src.watcher.download_watcher import TEMP_SUFFIXES
                if not e.name.lower().endswith(TEMP_SUFFIXES):
                    loose.append(e)

        if not loose or not self.api_key:
            plan.explanation = "Unwrapped nested folders." + ("" if self.api_key else " Add an OpenAI key to sort files.")
            return plan

        loose = loose[:MAX_FILES]
        desc = self.describe(loose, self.base)
        data, err = chat_json(
            self.api_key, self.model, SORT_SYSTEM,
            f"User's existing folders in Downloads:\n{self.folder_tree_text()}\n\n"
            f"Loose files ({len(desc)}):\n{self._files_text(desc)}",
            SORT_SCHEMA,
        )
        if err or not data:
            plan.explanation = f"Could not sort loose files ({err})."
            return plan

        existing = self.existing_folders()
        new_tops: Dict[str, Path] = {}
        by_id = {int(i["id"]): i for i in data.get("items", []) if isinstance(i.get("id"), int)}
        for d in desc:
            src: Path = d["path"]
            choice = by_id.get(d["id"]) or {}
            parts = clean_rel_folder(choice.get("folder", ""), 2)
            title = (choice.get("title") or "").strip()
            already_named = bool(PREFIX_RE.match(src.name))
            new_name = src.name if (src.is_dir() or already_named or not title) else self._file_name(title, src.name)
            if parts:
                key = parts[0].lower()
                if key in existing:
                    top = existing[key]
                else:
                    top = new_tops.setdefault(key, self.base / self._new_top_folder_name(parts[0]))
                dst_dir = top.joinpath(*parts[1:])
            else:
                dst_dir = self.base
            dst = self._claim(dst_dir / new_name, src, claimed)
            if dst != src:
                plan.moves.append(Move(src, dst))
        plan.explanation = "Sorted loose files into project folders."
        return plan

    # ---- apply -------------------------------------------------------------------------
    def apply(self, plan: OrganizePlan, label: str = "Smart organize") -> Dict[str, Any]:
        if not plan.moves:
            return {"status": "UNCHANGED", "moved": 0, "session_id": None, "message": plan.explanation}
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        records: List[RenameHistoryRecord] = []
        moved, errors = 0, []
        for m in plan.moves:
            try:
                if m.dst.exists():
                    raise FileExistsError(f"{m.dst.name} already exists")
                m.dst.parent.mkdir(parents=True, exist_ok=True)
                size = m.src.stat().st_size if m.src.is_file() else 0
                shutil.move(str(m.src), str(m.dst))
                moved += 1
                try:
                    shown = str(m.dst.relative_to(self.base))
                except ValueError:
                    shown = m.dst.name
                records.append(RenameHistoryRecord(
                    session_id=session_id, timestamp=now, original_path=str(m.src), new_path=str(m.dst),
                    original_name=m.src.name, new_name=shown, file_size=size, status="RENAMED"))
            except Exception as e:
                errors.append(f"{m.src.name}: {e}")
        for folder in plan.cleanup:
            if folder != self.base:
                remove_empty_dirs(folder)
        if records:
            self.history.record_session(session_id, f"{label}: {self.base}", len(records), records)
        return {
            "status": "ORGANIZED" if moved else "ERROR",
            "moved": moved,
            "errors": errors,
            "session_id": session_id if records else None,
            "folders": [str(p) for p in plan.top_folders],
            "message": plan.explanation if not errors else f"{plan.explanation} ({len(errors)} error(s))",
        }

    def organize_folder(self, folder: Path) -> Dict[str, Any]:
        plan = self.plan_folder(folder)
        result = self.apply(plan, label="Folder")
        result["original_name"] = Path(folder).name
        return result

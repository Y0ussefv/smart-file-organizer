"""
process_new_item(): the reference algorithm of the specification (§7), in this order:

    excluded / symlink / outside      -> preserved, explicit error (T22, T28)
    already processed (same content at the same path) -> nothing (AC-08, T17)
    local reading + P0/P1/P2/INCONNU  -> privacy event (no content)
    rank against ALL approved projects (local)
    optional cloud title: switch on + P0 + no alert + no "always local" project + excerpt
    safe name, rename without overwrite (transactional, Undo)
    decision matrix: auto move / proposal / kept in Downloads
    unknown project seen in >= 3 distinct files -> new-project proposal (no folder before yes)

Nothing here uses a "current" or "last used" folder (AC-03).
"""

import hashlib
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.bee import RULES_VERSION
from src.bee import ledger as L
from src.bee.cloud_title import title_from_excerpt
from src.bee.ledger import Ledger, Project
from src.bee.matcher import (AUTO_MOVE, KEEP, PROPOSE, PROPOSE_SCORE, Candidate, Facts, decide, entities,
                             pick_category, rank)
from src.bee.minimize import minimize
from src.bee.mover import MoveRefused, Mover, check_source, project_depth
from src.bee.reader import read_local
from src.bee.sensitivity import P0, P1, P2, UNKNOWN, classify
from src.core.filename_sanitizer import build_safe_filename, sanitize_stem
from src.privacy import cloud_gate

logger = logging.getLogger("SmartFileOrganizer")

ALREADY_PREFIXED = re.compile(r"^\d{2}-\d{2}[ _]")
NEW_PROJECT_MIN_FILES = 3
SOFTWARE_MARKERS = (".git", "package.json", "pyproject.toml", "setup.py", "Cargo.toml", "go.mod", "pom.xml",
                    "build.gradle", "composer.json", "Gemfile", ".sln", ".csproj")


def content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def folder_name(name: str) -> str:
    return sanitize_stem(name, max_length=60).replace("_", " ").strip() or "Projet"


class BeePipeline:
    def __init__(self, downloads: Path, projects_root: Optional[Path] = None, ledger: Optional[Ledger] = None,
                 settings=None, api_key_provider=None, model: str = "gpt-5-mini",
                 date_prefix: bool = True, clock=None):
        self.downloads = Path(downloads)
        self.projects_root = Path(projects_root) if projects_root else self.downloads / "Projets"
        self.ledger = ledger or Ledger()
        self.settings = settings
        self.mover = Mover(self.ledger, self.downloads, self.projects_root)
        self.api_key_provider = api_key_provider or (lambda: "")
        self.model = model
        self.date_prefix = date_prefix
        self.clock = clock or datetime.now
        cloud_gate.set_enabled_provider(self.ledger.cloud_enabled)

    # ---- cloud switch (PR-02, PR-22) ----------------------------------------------------
    def set_cloud(self, enabled: bool) -> None:
        self.ledger.set_cloud(enabled)
        if not enabled:
            cloud_gate.revoke_all()

    # ---- main entry ---------------------------------------------------------------------
    def process_new_item(self, path: Path) -> Dict[str, Any]:
        path = Path(path)
        base = {"original_name": path.name, "new_name": path.name, "new_path": str(path),
                "original_path": str(path)}
        try:
            check_source(path, [self.downloads])
        except MoveRefused as e:
            return {**base, "status": "ERROR", "message": str(e)}
        if path.is_dir():
            return {**base, "status": "SKIPPED", "message": "Folder left as it is (§5.3)"}
        if not path.is_file():
            return {**base, "status": "ERROR", "message": "File not found"}

        digest = content_hash(path)
        if self.ledger.find_completed(digest, path):
            return {**base, "status": "SKIPPED", "message": "Already processed"}

        fid = self.ledger.new_file(digest, path)
        dup = next((r for r in self.ledger.find_by_hash(digest)
                    if r["file_id"] != fid and Path(r["current_path"]).exists()
                    and Path(r["current_path"]) != path), None)
        if dup:
            self.ledger.update_file(fid, duplicate_of=dup["file_id"])  # T26: noted, nothing deleted

        batch = self.ledger.new_batch(f"Download {path.name}")
        try:
            result = self._process(fid, batch, path, base)
            self.ledger.set_batch(batch, "done" if self.ledger.operations(batch) else "empty")
            result["batch_id"] = batch
            result["file_id"] = fid
            if dup:
                result["duplicate_of"] = dup["current_path"]
            return result
        except Exception as e:
            logger.exception("Processing failed")
            self.ledger.update_file(fid, state=L.FAILED, block_code=type(e).__name__)
            self.ledger.set_batch(batch, "failed")
            return {**base, "status": "ERROR", "message": f"Not processed ({type(e).__name__}); file kept as it was"}

    def _process(self, fid: str, batch: str, path: Path, base: Dict[str, Any]) -> Dict[str, Any]:
        self.ledger.update_file(fid, state=L.ANALYSING, rules_version=RULES_VERSION)

        # 1. local inspection, no network (PR-17 steps 1-2)
        content = read_local(path)
        cls = classify(path.name, content)
        self.ledger.update_file(fid, sensitivity=cls.level, block_code=",".join(cls.codes)[:200] or None)

        local_title = self._local_title(path)
        facts = Facts(filename=path.name, title=local_title or "", text=content.text)
        projects = self.ledger.projects()
        candidates = rank(facts, projects)

        # 2. optional cloud title (PR-17 steps 3-6)
        title, cloud_action = self._cloud_title(fid, cls, content, path, candidates)
        title = title or local_title

        # 3. safe name + rename (RN-01..RN-06)
        new_name = self._safe_name(path, title)
        current = path
        if new_name != path.name:
            current = self.mover.move(batch, fid, path, path.parent, new_name)
            self.ledger.update_file(fid, state=L.RENAMED, current_path=str(current))

        # 4. destination (PR-17 step 7: classification never re-checks cloud permission)
        decision = decide(candidates, destination_ok=self._destination_ok)
        result = {**base, "new_name": current.name, "new_path": str(current), "status": "RENAMED"
                  if current != path else "UNCHANGED", "sensitivity": cls.level,
                  "confidential": cls.level in (P1, P2), "cloud": cloud_action,
                  "decision": decision.choice, "reason": decision.reason}

        if decision.choice == AUTO_MOVE:
            best = decision.best
            target = Path(best.project.path)
            category = pick_category(facts, self.ledger.categories(best.project.project_id))
            if category:
                target = target / folder_name(category.name)
            moved = self.mover.move(batch, fid, current, target)
            self.ledger.update_file(fid, state=L.DONE, current_path=str(moved), project_id=best.project.project_id)
            self._decision(fid, candidates, "auto_move", best.project.project_id, True, decision.reason)
            rel = moved.parent.relative_to(self.projects_root)
            result.update(status="FILED", new_path=str(moved), new_name=moved.name,
                          placed_in=str(Path(self.projects_root.name) / rel))
        elif decision.choice == PROPOSE:
            best = decision.best
            pid = self.ledger.add_proposal("file_move", {
                "file_id": fid, "project_id": best.project.project_id, "project": best.project.name,
                "score": best.score, "evidence": best.evidence, "contradictions": best.contradictions,
                "path": str(current), "name": current.name, "reason": decision.reason})
            self.ledger.update_file(fid, state=L.PROPOSED)
            self._decision(fid, candidates, "propose", best.project.project_id, True, decision.reason)
            result.update(proposal_id=pid, proposed_project=best.project.name)
        else:
            self.ledger.update_file(fid, state=L.KEPT)
            self._decision(fid, candidates, "keep", None, True, decision.reason)
            if not candidates:
                proposal = self._track_unknown_project(fid, facts)
                if proposal:
                    result["new_project_proposal"] = proposal
        return result

    # ---- helpers ------------------------------------------------------------------------
    def _decision(self, fid, candidates: List[Candidate], choice, project_id, automatic, why) -> None:
        self.ledger.record_decision(fid, [c.as_dict() for c in candidates[:5]], choice, project_id,
                                    automatic, why, RULES_VERSION)

    def _destination_ok(self, cand: Candidate) -> bool:
        target = Path(cand.project.path)
        try:
            return (cand.project.status == "active" and project_depth(target, self.projects_root) == 1)
        except ValueError:
            return False

    def _local_title(self, path: Path) -> str:
        """Title from the existing local extractors (scan config never carries an API key)."""
        try:
            from src.core.models import ScanConfig
            from src.core.scanner import DirectoryScanner
            cfg = ScanConfig(root_path=path.parent, recursive=False, group_by_domain=False)
            item = DirectoryScanner(cfg).analyze_file(path)
            from src.core.models import FileStatus
            if item.status == FileStatus.READY_TO_RENAME and item.detected_title:
                return item.detected_title
        except Exception:
            logger.info("Local title failed")
        return ""

    def _cloud_title(self, fid: str, cls, content, path: Path, candidates: List[Candidate]):
        """Returns (title or None, action code). Every branch writes one privacy event."""
        def event(action, rule, status="ok"):
            self.ledger.privacy_event(fid, cls.level, action, rule, status)

        if not cloud_gate.cloud_enabled():
            event("local", "cloud_off")
            return None, "local"
        if cls.level != P0 or not cls.cloud_eligible:
            event("cloud_blocked", f"class_{cls.level}")
            return None, "cloud_blocked"
        if any(c.project.always_local for c in candidates if c.score >= PROPOSE_SCORE):
            event("cloud_blocked", "project_always_local")
            return None, "cloud_blocked"
        api_key = (self.api_key_provider() or "").strip()
        if not api_key:
            event("local", "no_api_key")
            return None, "local"
        excerpt = minimize(content)
        if excerpt is None:
            event("cloud_blocked", "minimisation_failed")
            return None, "cloud_blocked"
        permit = cloud_gate.issue(fid)
        if permit is None:
            event("cloud_blocked", "cloud_off")
            return None, "cloud_blocked"
        title, err = title_from_excerpt(excerpt, path.suffix.lower(), api_key, self.model, permit)
        if title:
            event("cloud_allowed_excerpt", "P0_minimised")
            return title, "cloud_allowed_excerpt"
        event("cloud_failed", err or "unknown", "error")
        return None, "local"

    def _safe_name(self, path: Path, title: str) -> str:
        if ALREADY_PREFIXED.match(path.name):
            return path.name  # RN-05: no second prefix
        if not title:
            return path.name  # prudent: no invented name (T07)
        prefix = self.clock().strftime("%y-%m") if self.date_prefix else None
        return build_safe_filename(candidate_name=title, original_filename=path.name, date_prefix=prefix,
                                   date_prefix_separator=" ")

    def _track_unknown_project(self, fid: str, facts: Facts) -> Optional[str]:
        """Proposes a new project once 3 distinct files name the same unknown project (§5.1)."""
        proposed = None
        for key, label in entities(facts):
            count = self.ledger.add_entity_hit(key, label, fid)
            if count < NEW_PROJECT_MIN_FILES:
                continue
            known = [p for kind in ("pending", "refused", "accepted")
                     for p in self.ledger.proposals(kind, "new_project") if p["payload"].get("entity") == key]
            if known:
                continue
            files = []
            for f in self.ledger.entity_files(key):
                rec = self.ledger.file(f)
                if rec and Path(rec["current_path"]).exists() and Path(rec["current_path"]).parent == self.downloads:
                    files.append({"file_id": f, "name": Path(rec["current_path"]).name})
            if len(files) >= NEW_PROJECT_MIN_FILES:
                proposed = self.ledger.add_proposal("new_project", {
                    "entity": key, "name": label, "files": files,
                    "target": str(self.projects_root / folder_name(label))})
        return proposed

    # ---- user decisions (§5.1, §9.1) -------------------------------------------------------
    def create_project(self, name: str, aliases=(), refs=(), exclusions=(), always_local=False) -> Project:
        return self.ledger.add_project(name, self.projects_root / folder_name(name), aliases, refs, exclusions,
                                       always_local)

    def add_category(self, project_id: str, name: str, keywords=()):
        project = self.ledger.project(project_id)
        target = Path(project.path) / folder_name(name)
        if project_depth(target, self.projects_root) != 2:
            raise MoveRefused("Categories live directly in a project folder.")
        return self.ledger.add_category(project_id, name, keywords)

    def move_file_to_project(self, file_id: str, project_id: str, category: Optional[str] = None,
                             label: str = "Filed by you") -> Dict[str, Any]:
        rec = self.ledger.file(file_id)
        project = self.ledger.project(project_id)
        src = Path(rec["current_path"])
        target = Path(project.path) / folder_name(category) if category else Path(project.path)
        batch = self.ledger.new_batch(label)
        moved = self.mover.move(batch, file_id, src, target)
        self.ledger.set_batch(batch, "done")
        self.ledger.update_file(file_id, state=L.DONE, current_path=str(moved), project_id=project_id)
        self.ledger.record_decision(file_id, [], "human_move", project_id, False, label, RULES_VERSION)
        return {"status": "FILED", "new_path": str(moved), "batch_id": batch}

    def accept_proposal(self, proposal_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        prop = self.ledger.proposal(proposal_id)
        if not prop or prop["status"] != "pending":
            return {"status": "ERROR", "message": "This proposal is no longer pending."}
        data = prop["payload"]
        if prop["kind"] == "file_move":
            out = self.move_file_to_project(data["file_id"], project_id or data["project_id"],
                                            label=f"Proposal accepted: {data['project']}")
        elif prop["kind"] == "new_project":
            project = self.create_project(data["name"])
            batch = self.ledger.new_batch(f"New project {project.name}")
            moved = []
            for f in data["files"]:
                rec = self.ledger.file(f["file_id"])
                src = Path(rec["current_path"]) if rec else None
                if src and src.exists() and src.parent == self.downloads:
                    dst = self.mover.move(batch, f["file_id"], src, Path(project.path))
                    self.ledger.update_file(f["file_id"], state=L.DONE, current_path=str(dst),
                                            project_id=project.project_id)
                    moved.append(str(dst))
            self.ledger.set_batch(batch, "done")
            out = {"status": "FILED", "project_id": project.project_id, "moved": moved, "batch_id": batch}
        else:
            return {"status": "ERROR", "message": "Unknown proposal"}
        self.ledger.set_proposal(proposal_id, "accepted")
        return out

    def refuse_proposal(self, proposal_id: str) -> None:
        """Nothing moves, no folder is created (T04)."""
        self.ledger.set_proposal(proposal_id, "refused")

    def undo(self, batch_id: str) -> Dict[str, Any]:
        return self.mover.undo(batch_id)

    # ---- restart (T17) ------------------------------------------------------------------------
    def recover(self) -> Dict[str, int]:
        """After a crash: settle half-done operations without guessing, clean temp copies."""
        fixed = 0
        for op in self.ledger.planned_operations():
            src = Path(op["src"]) if op["src"] else None
            dst = Path(op["dst"]) if op["dst"] else None
            if op["kind"] == "mkdir":
                self.ledger.set_op(op["operation_id"], "done" if dst and dst.exists() else "failed", "interrupted")
            elif dst and dst.exists() and not (src and src.exists()):
                self.ledger.set_op(op["operation_id"], "done", "completed_before_restart")
                if op["file_id"]:
                    self.ledger.update_file(op["file_id"], current_path=str(dst))
            else:
                self.ledger.set_op(op["operation_id"], "failed", "interrupted")
            fixed += 1
        for rec in self.ledger.unfinished_files():
            self.ledger.update_file(rec["file_id"], state=L.FAILED, block_code="INTERRUPTED")
            fixed += 1
        for root in (self.downloads, self.projects_root):
            if root.exists():
                for tmp in root.rglob(".*.beepart"):
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
        self.ledger.purge()
        return {"recovered": fixed}


def is_software_project(folder: Path) -> bool:
    return any((folder / m).exists() for m in SOFTWARE_MARKERS) or any(
        p.suffix in (".sln", ".csproj") for p in folder.iterdir() if p.is_file())

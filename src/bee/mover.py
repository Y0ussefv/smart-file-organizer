"""
Transactional rename / move with full Undo (spec V2 §6.2, §9.3, RN-03, RN-04, §2).

For every operation:
 1. validate the target: inside an allowed root, depth limit (Projets/<project>/<category>/file),
    no symlink leaving the allowed area, no overwrite;
 2. reserve a collision-free name (_2, _3...) and write the planned operation to the ledger;
 3. move atomically on the same volume (os.replace), else copy to a temp name next to the
    target, check size and hash, then switch;
 4. check the target exists and is readable, mark the operation done;
 5. on any error before that: put the original back, remove folders created by the app
    if they are still empty, mark the operation failed. Never delete or overwrite a user file.
"""

import errno
import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from src.bee.ledger import Ledger

logger = logging.getLogger("SmartFileOrganizer")

MAX_PROJECT_DEPTH = 2   # Projets/<project>/<category> (the Projets root is not counted)


class MoveRefused(Exception):
    """The target breaks a safety rule (path outside the allowed roots, too deep, symlink...)."""


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def project_depth(target_dir: Path, projects_root: Path) -> int:
    """0 = the Projets root itself, 1 = a project folder, 2 = a category folder."""
    rel = target_dir.resolve().relative_to(projects_root.resolve())
    return len(rel.parts)


def check_target_dir(target_dir: Path, downloads: Path, projects_root: Path) -> None:
    """Allowed: the Downloads root itself, or Projets/<project>[/<category>] (T12)."""
    if target_dir.resolve() == downloads.resolve():
        return
    if not _inside(target_dir, projects_root):
        raise MoveRefused("Target is outside Downloads and the Projets folder.")
    depth = project_depth(target_dir, projects_root)
    if depth < 1 or depth > MAX_PROJECT_DEPTH:
        raise MoveRefused(f"Target depth {depth} is not allowed (Projets/<project>/<category> at most).")
    # an existing component must not be a symlink that leaves the area
    p = target_dir
    while p != projects_root and p != p.parent:
        if p.exists() and p.is_symlink():
            raise MoveRefused("A folder on the path is a symbolic link.")
        p = p.parent


def check_source(path: Path, allowed_roots: Sequence[Path]) -> None:
    if path.is_symlink():
        raise MoveRefused("The item is a symbolic link; it is not analysed or moved (T28).")
    if not any(_inside(path, r) for r in allowed_roots):
        raise MoveRefused("The item is outside the watched folders.")


def free_name(directory: Path, name: str, reserved: Optional[set] = None) -> str:
    """name, then name_2, name_3... never an existing file (RN-04)."""
    reserved = reserved or set()
    stem, suffix = os.path.splitext(name)
    candidate, n = name, 1
    while (directory / candidate).exists() or candidate.lower() in reserved:
        n += 1
        candidate = f"{stem}_{n}{suffix}"
    return candidate


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _transfer(src: Path, dst: Path) -> None:
    if dst.exists():
        raise FileExistsError(str(dst))  # never overwrite (RN-04)
    try:
        os.rename(src, dst)  # atomic on the same volume
        return
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise
    # different volume: copy to a temp name next to the target, verify, then switch
    tmp = dst.with_name(f".{dst.name}.beepart")
    try:
        shutil.copy2(src, tmp)
        if tmp.stat().st_size != src.stat().st_size or _digest(tmp) != _digest(src):
            raise OSError("Copy check failed")
        if dst.exists():
            raise FileExistsError(str(dst))
        os.replace(tmp, dst)
        os.remove(src)
    finally:
        if tmp.exists():
            tmp.unlink()


class Mover:
    def __init__(self, ledger: Ledger, downloads: Path, projects_root: Path):
        self.ledger = ledger
        self.downloads = Path(downloads)
        self.projects_root = Path(projects_root)
        self.fail_after_mkdir = False  # test hook for T24

    def move(self, batch_id: str, file_id: Optional[str], src: Path, target_dir: Path,
             new_name: Optional[str] = None) -> Path:
        """Rename and/or move one file. Returns the final path. Raises on refusal or failure,
        after restoring the original state."""
        src = Path(src)
        target_dir = Path(target_dir)
        check_source(src, [self.downloads, self.projects_root])
        check_target_dir(target_dir, self.downloads, self.projects_root)
        name = new_name or src.name
        if target_dir == src.parent and name == src.name:
            return src

        created: List[Path] = []
        dst = None
        op = None
        try:
            # create missing folders only now, for this first file (§5.2: no empty folders in advance)
            missing = []
            p = target_dir
            while not p.exists():
                missing.append(p)
                p = p.parent
            for d in reversed(missing):
                mk = self.ledger.plan_op(batch_id, file_id, "mkdir", None, d)
                d.mkdir()
                created.append(d)
                self.ledger.set_op(mk, "done")
            if self.fail_after_mkdir:
                raise OSError("Simulated failure after creating the folder")

            final = free_name(target_dir, name)
            dst = target_dir / final
            op = self.ledger.plan_op(batch_id, file_id, "rename" if target_dir == src.parent else "move", src, dst)
            _transfer(src, dst)
            if not dst.exists() or not os.access(dst, os.R_OK):
                raise OSError("Target not readable after the move")
            self.ledger.set_op(op, "done")
            return dst
        except Exception as e:
            if dst is not None and dst.exists() and not src.exists():
                try:
                    os.rename(dst, src)
                except OSError:
                    logger.exception("Could not restore after a failed move")
            if op:
                self.ledger.set_op(op, "failed", type(e).__name__)
            for d in reversed(created):
                try:
                    d.rmdir()  # only if still empty
                except OSError:
                    pass
            for o in self.ledger.operations(batch_id):
                if o["kind"] == "mkdir" and o["status"] == "done" and o["dst"] and not Path(o["dst"]).exists():
                    self.ledger.set_op(o["operation_id"], "rolled_back")
            raise

    # ---- Undo (§9.3) --------------------------------------------------------------------
    def undo(self, batch_id: str) -> Dict:
        """Restores the original names and places of a whole batch, newest operation first.
        If an original place is taken, restores next to it under a free name and says so."""
        ops = [o for o in self.ledger.operations(batch_id) if o["status"] == "done"]
        restored, notes, errors = [], [], []
        for o in reversed(ops):
            try:
                if o["kind"] in ("rename", "move"):
                    src, dst = Path(o["src"]), Path(o["dst"])
                    if not dst.exists():
                        errors.append(f"{dst.name} is no longer there")
                        continue
                    src.parent.mkdir(parents=True, exist_ok=True)
                    back = src
                    if src.exists():
                        back = src.parent / free_name(src.parent, src.name)
                        notes.append(f"{src.name} was taken: restored as {back.name}")
                    os.rename(dst, back)
                    self.ledger.set_op(o["operation_id"], "undone")
                    if o["file_id"]:
                        self.ledger.update_file(o["file_id"], current_path=str(back), state="ANNULE")
                    restored.append(str(back))
                elif o["kind"] == "mkdir":
                    d = Path(o["dst"])
                    try:
                        d.rmdir()  # only removes it if empty: never deletes user files
                        self.ledger.set_op(o["operation_id"], "undone")
                    except OSError:
                        pass
            except OSError as e:
                errors.append(f"{Path(o['dst'] or '').name}: {type(e).__name__}")
        self.ledger.set_batch(batch_id, "reverted" if not errors else "partly_reverted")
        return {"status": "REVERTED" if restored and not errors else ("PARTIAL" if restored else "ERROR"),
                "restored": restored, "notes": notes, "errors": errors}

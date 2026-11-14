"""
BeeOrganizer V2 ledger (spec §8): one SQLite file with the minimal data model.

    projects / categories  approved catalog (stable UUIDs, never just a folder name)
    files                  FileRecord: identity, states, sensitivity code, no content
    decisions              candidates, evidence codes, scores, choice, justification
    operations             every rename / move / mkdir, in order, for rollback and Undo
    proposals              pending suggestions (file -> project, new project)
    entity_hits            files sharing an unknown project name (for new-project proposals)
    privacy_events         P0/P1/P2/INCONNU, action, rule; no excerpt, no PII, no key
    cloud_permission       the user's cloud choice and the information version shown

Never stored: extracted text, excerpts, API payloads or keys (PR-24, PR-25).
"""

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from src.utils.platform_utils import get_app_data_dir

DAY = 86400
DEFAULT_EVENT_RETENTION_DAYS = 30
DEFAULT_UNDO_RETENTION_DAYS = 90
PRIVACY_INFO_VERSION = "2026-11-v1"

# File states (spec §6.1)
DETECTED, WAITING, READY, ANALYSING, RENAMED = "DETECTE", "ATTENTE_FIN", "PRET", "ANALYSE", "RENOMME"
FILED, PROPOSED, KEPT, DONE = "CLASSE", "PROPOSITION_EN_ATTENTE", "CONSERVE", "TERMINE"
FAILED, CANCELLED = "ECHEC", "ANNULE"
TERMINAL = (DONE, FAILED, CANCELLED)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY, name TEXT NOT NULL, aliases TEXT NOT NULL DEFAULT '[]',
    refs TEXT NOT NULL DEFAULT '[]', exclusions TEXT NOT NULL DEFAULT '[]',
    path TEXT NOT NULL, approved_at REAL NOT NULL, status TEXT NOT NULL DEFAULT 'active',
    always_local INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS categories (
    category_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL,
    keywords TEXT NOT NULL DEFAULT '[]', approved_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS files (
    file_id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, original_name TEXT NOT NULL,
    original_path TEXT NOT NULL, current_path TEXT NOT NULL, state TEXT NOT NULL,
    project_id TEXT, sensitivity TEXT, block_code TEXT, duplicate_of TEXT,
    rules_version TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS files_hash ON files(content_hash);
CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY, file_id TEXT NOT NULL, candidates TEXT NOT NULL,
    choice TEXT NOT NULL, project_id TEXT, automatic INTEGER NOT NULL, justification TEXT,
    classifier_version TEXT, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS operations (
    operation_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, file_id TEXT, seq INTEGER NOT NULL,
    kind TEXT NOT NULL, src TEXT, dst TEXT, status TEXT NOT NULL, error TEXT, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ops_batch ON operations(batch_id);
CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY, label TEXT, status TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
    status TEXT NOT NULL, created_at REAL NOT NULL, decided_at REAL);
CREATE TABLE IF NOT EXISTS entity_hits (
    entity TEXT NOT NULL, label TEXT NOT NULL, file_id TEXT NOT NULL, at REAL NOT NULL,
    PRIMARY KEY (entity, file_id));
CREATE TABLE IF NOT EXISTS privacy_events (
    event_id TEXT PRIMARY KEY, file_id TEXT, level TEXT NOT NULL, action TEXT NOT NULL,
    rule TEXT, status TEXT, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS cloud_permission (
    profile TEXT PRIMARY KEY, enabled INTEGER NOT NULL, scope TEXT, info_version TEXT,
    chosen_at REAL NOT NULL);
"""


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Project:
    project_id: str
    name: str
    path: str
    aliases: List[str] = field(default_factory=list)
    refs: List[str] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)
    always_local: bool = False
    status: str = "active"
    approved_at: float = 0.0


@dataclass
class Category:
    category_id: str
    project_id: str
    name: str
    keywords: List[str] = field(default_factory=list)


class Ledger:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else get_app_data_dir() / "beeorganizer_v2.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    # ---- projects (approved catalog) -------------------------------------------------
    def add_project(self, name: str, path: Path, aliases=(), refs=(), exclusions=(),
                    always_local: bool = False) -> Project:
        p = Project(_new_id(), name.strip(), str(path), [a.strip() for a in aliases if a.strip()],
                    [r.strip() for r in refs if r.strip()], [e.strip() for e in exclusions if e.strip()],
                    bool(always_local), "active", time.time())
        with self._conn() as c:
            c.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?)",
                      (p.project_id, p.name, json.dumps(p.aliases), json.dumps(p.refs),
                       json.dumps(p.exclusions), p.path, p.approved_at, p.status, int(p.always_local)))
        return p

    def update_project(self, project_id: str, **fields: Any) -> None:
        cols = {"aliases", "refs", "exclusions", "always_local", "status", "name"}
        sets, vals = [], []
        for k, v in fields.items():
            if k not in cols:
                raise ValueError(k)
            sets.append(f"{k}=?")
            vals.append(json.dumps(v) if k in ("aliases", "refs", "exclusions") else
                        int(v) if k == "always_local" else v)
        with self._conn() as c:
            c.execute(f"UPDATE projects SET {', '.join(sets)} WHERE project_id=?", (*vals, project_id))

    def projects(self, include_archived: bool = False) -> List[Project]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM projects" + ("" if include_archived else " WHERE status='active'")
                             + " ORDER BY name").fetchall()
        return [Project(r["project_id"], r["name"], r["path"], json.loads(r["aliases"]), json.loads(r["refs"]),
                        json.loads(r["exclusions"]), bool(r["always_local"]), r["status"], r["approved_at"])
                for r in rows]

    def project(self, project_id: str) -> Optional[Project]:
        return next((p for p in self.projects(True) if p.project_id == project_id), None)

    def add_category(self, project_id: str, name: str, keywords=()) -> Category:
        cat = Category(_new_id(), project_id, name.strip(), [k.strip() for k in keywords if k.strip()])
        with self._conn() as c:
            c.execute("INSERT INTO categories VALUES (?,?,?,?,?)",
                      (cat.category_id, project_id, cat.name, json.dumps(cat.keywords), time.time()))
        return cat

    def categories(self, project_id: str) -> List[Category]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM categories WHERE project_id=? ORDER BY name", (project_id,)).fetchall()
        return [Category(r["category_id"], r["project_id"], r["name"], json.loads(r["keywords"])) for r in rows]

    # ---- files -----------------------------------------------------------------
    def new_file(self, content_hash: str, path: Path) -> str:
        fid, now = _new_id(), time.time()
        with self._conn() as c:
            c.execute("INSERT INTO files (file_id, content_hash, original_name, original_path, current_path,"
                      " state, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                      (fid, content_hash, path.name, str(path), str(path), READY, now, now))
        return fid

    def update_file(self, file_id: str, **fields: Any) -> None:
        allowed = {"state", "current_path", "project_id", "sensitivity", "block_code", "duplicate_of",
                   "rules_version"}
        assert set(fields) <= allowed, fields
        sets = ", ".join(f"{k}=?" for k in fields)
        with self._conn() as c:
            c.execute(f"UPDATE files SET {sets}, updated_at=? WHERE file_id=?",
                      (*fields.values(), time.time(), file_id))

    def file(self, file_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM files WHERE file_id=?", (file_id,)).fetchone()
        return dict(r) if r else None

    def find_completed(self, content_hash: str, path: Path) -> Optional[Dict[str, Any]]:
        """Already processed: the same content at this very path (restart, rescan: AC-08)."""
        with self._conn() as c:
            r = c.execute("SELECT * FROM files WHERE content_hash=? AND current_path=? AND state IN (?,?,?,?)",
                          (content_hash, str(path), DONE, FILED, PROPOSED, KEPT)).fetchone()
        return dict(r) if r else None

    def find_by_hash(self, content_hash: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM files WHERE content_hash=?", (content_hash,))]

    def unfinished_files(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM files WHERE state IN (?,?,?,?,?)", (DETECTED, WAITING, READY, ANALYSING, RENAMED))]

    # ---- decisions ---------------------------------------------------------------
    def record_decision(self, file_id: str, candidates: List[Dict], choice: str, project_id: Optional[str],
                        automatic: bool, justification: str, classifier_version: str) -> str:
        did = _new_id()
        with self._conn() as c:
            c.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?)",
                      (did, file_id, json.dumps(candidates), choice, project_id, int(automatic),
                       justification, classifier_version, time.time()))
        return did

    def decisions(self, file_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM decisions WHERE file_id=? ORDER BY at", (file_id,))]

    # ---- operations / batches (rollback + Undo) --------------------------------------
    def new_batch(self, label: str) -> str:
        bid = _new_id()
        with self._conn() as c:
            c.execute("INSERT INTO batches VALUES (?,?,?,?)", (bid, label, "open", time.time()))
        return bid

    def set_batch(self, batch_id: str, status: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE batches SET status=? WHERE batch_id=?", (status, batch_id))

    def batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
        return dict(r) if r else None

    def plan_op(self, batch_id: str, file_id: Optional[str], kind: str, src: Optional[Path],
                dst: Optional[Path]) -> str:
        oid = _new_id()
        with self._conn() as c:
            seq = c.execute("SELECT COUNT(*) FROM operations WHERE batch_id=?", (batch_id,)).fetchone()[0]
            c.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (oid, batch_id, file_id, seq, kind, str(src) if src else None,
                       str(dst) if dst else None, "planned", None, time.time()))
        return oid

    def set_op(self, operation_id: str, status: str, error: Optional[str] = None) -> None:
        with self._conn() as c:
            c.execute("UPDATE operations SET status=?, error=? WHERE operation_id=?", (status, error, operation_id))

    def operations(self, batch_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM operations WHERE batch_id=? ORDER BY seq", (batch_id,))]

    def planned_operations(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM operations WHERE status='planned' ORDER BY at, seq")]

    def recent_batches(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM batches WHERE status='done' ORDER BY at DESC LIMIT ?", (limit,))]

    # ---- proposals ---------------------------------------------------------------
    def add_proposal(self, kind: str, payload: Dict[str, Any]) -> str:
        pid = _new_id()
        with self._conn() as c:
            c.execute("INSERT INTO proposals VALUES (?,?,?,?,?,?)",
                      (pid, kind, json.dumps(payload), "pending", time.time(), None))
        return pid

    def proposals(self, status: str = "pending", kind: Optional[str] = None) -> List[Dict[str, Any]]:
        q, args = "SELECT * FROM proposals WHERE status=?", [status]
        if kind:
            q += " AND kind=?"
            args.append(kind)
        with self._conn() as c:
            rows = c.execute(q + " ORDER BY created_at", args).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]

    def proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
        return {**dict(r), "payload": json.loads(r["payload"])} if r else None

    def set_proposal(self, proposal_id: str, status: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE proposals SET status=?, decided_at=? WHERE proposal_id=?",
                      (status, time.time(), proposal_id))

    # ---- unknown-project grouping ------------------------------------------------------
    def add_entity_hit(self, entity: str, label: str, file_id: str) -> int:
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO entity_hits VALUES (?,?,?,?)", (entity, label, file_id, time.time()))
            return c.execute("SELECT COUNT(DISTINCT f.content_hash) FROM entity_hits e JOIN files f "
                             "ON f.file_id=e.file_id WHERE e.entity=?", (entity,)).fetchone()[0]

    def entity_files(self, entity: str) -> List[str]:
        with self._conn() as c:
            return [r[0] for r in c.execute("SELECT file_id FROM entity_hits WHERE entity=? ORDER BY at", (entity,))]

    # ---- privacy -------------------------------------------------------------------
    def privacy_event(self, file_id: Optional[str], level: str, action: str, rule: str,
                      status: str = "ok") -> None:
        with self._conn() as c:
            c.execute("INSERT INTO privacy_events VALUES (?,?,?,?,?,?,?)",
                      (_new_id(), file_id, level, action, rule, status, time.time()))

    def privacy_events(self, file_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._conn() as c:
            if file_id:
                rows = c.execute("SELECT * FROM privacy_events WHERE file_id=? ORDER BY at", (file_id,))
            else:
                rows = c.execute("SELECT * FROM privacy_events ORDER BY at")
            return [dict(r) for r in rows]

    def set_cloud(self, enabled: bool, scope: str = "P0-excerpt") -> None:
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO cloud_permission VALUES (?,?,?,?,?)",
                      ("default", int(enabled), scope, PRIVACY_INFO_VERSION, time.time()))

    def cloud_enabled(self) -> bool:
        """Off unless the user turned it on after the information screen of this version (PR-02)."""
        with self._conn() as c:
            r = c.execute("SELECT * FROM cloud_permission WHERE profile='default'").fetchone()
        return bool(r and r["enabled"] and r["info_version"] == PRIVACY_INFO_VERSION)

    # ---- retention (PR-26) ---------------------------------------------------------------
    def purge(self, event_days: int = DEFAULT_EVENT_RETENTION_DAYS,
              undo_days: int = DEFAULT_UNDO_RETENTION_DAYS, now: Optional[float] = None) -> Dict[str, int]:
        now = now or time.time()
        ev_cut, undo_cut = now - event_days * DAY, now - undo_days * DAY
        with self._conn() as c:
            out = {
                "privacy_events": c.execute("DELETE FROM privacy_events WHERE at<?", (ev_cut,)).rowcount,
                "decisions": c.execute("DELETE FROM decisions WHERE at<?", (ev_cut,)).rowcount,
                "operations": c.execute("DELETE FROM operations WHERE at<?", (undo_cut,)).rowcount,
            }
            c.execute("DELETE FROM batches WHERE at<?", (undo_cut,))
            c.execute("DELETE FROM entity_hits WHERE at<?", (ev_cut,))
        return out

    def purge_all_history(self) -> None:
        """Manual purge button: technical events, decisions and Undo history. Projects stay."""
        with self._conn() as c:
            for table in ("privacy_events", "decisions", "operations", "batches", "entity_hits"):
                c.execute(f"DELETE FROM {table}")

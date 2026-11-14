"""
Document -> project matching and decision matrix (spec V2 §4).

Every document is compared to ALL approved projects of the catalog. There is no
"current" or "last used" folder anywhere in this module (AC-03, T08).

Signals (§4.1)
    strong         project name (exact), project reference / mission id
    medium         approved alias
    weak           ignored: generic words (rapport, contrat, GIZ...), dates, extension, recency
    contradiction  an exclusion term of the project, or a strong signal of ANOTHER project

Indicative score (calibrate on the pilot corpus, §12.2)
    name + reference                    97
    one strong signal + k aliases       85 + 5k  (k <= 2)
    aliases only                        76 + 4(k-1)
Decision (§4.3): automatic only if score >= 95, lead >= 15 over the second project,
a specific (strong) signal and no contradiction; 75-94 or close scores: proposal;
below 75: kept in Downloads.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from src.bee.ledger import Category, Project
from src.bee.sensitivity import fold

AUTO_SCORE = 95
AUTO_LEAD = 15
PROPOSE_SCORE = 75

AUTO_MOVE, PROPOSE, KEEP = "AUTO_MOVE", "PROPOSE", "KEEP"


@dataclass
class Facts:
    """What is known about one file, in memory only."""
    filename: str
    title: str = ""
    text: str = ""

    def haystack(self) -> str:
        return fold("\n".join((self.filename, self.title, self.text)))


@dataclass
class Candidate:
    project: Project
    score: int
    evidence: List[str] = field(default_factory=list)       # codes, e.g. "name", "ref:ABC-2026"
    contradictions: List[str] = field(default_factory=list)

    @property
    def has_specific_evidence(self) -> bool:
        return any(e == "name" or e.startswith("ref:") for e in self.evidence)

    @property
    def has_conflict(self) -> bool:
        return bool(self.contradictions)

    def as_dict(self) -> Dict:
        return {"project_id": self.project.project_id, "project": self.project.name, "score": self.score,
                "evidence": self.evidence, "contradictions": self.contradictions}


@dataclass
class Decision:
    choice: str
    best: Optional[Candidate]
    reason: str


def _term(term: str) -> Optional[re.Pattern]:
    words = [re.escape(w) for w in re.split(r"[\s_\-]+", fold(term).strip()) if w]
    if not words or (len(words) == 1 and len(words[0].replace("\\", "")) < 3):
        return None  # too short to be specific
    return re.compile(r"(?<![a-z0-9])" + r"[\s_\-]*".join(words) + r"(?![a-z0-9])")


def _found(term: str, hay: str) -> bool:
    rx = _term(term)
    return bool(rx and rx.search(hay))


def _strong_signals(project: Project, hay: str) -> List[str]:
    out = []
    if _found(project.name, hay):
        out.append("name")
    out += [f"ref:{r}" for r in project.refs if _found(r, hay)]
    return out


def rank(facts: Facts, projects: Sequence[Project]) -> List[Candidate]:
    hay = facts.haystack()
    strong = {p.project_id: _strong_signals(p, hay) for p in projects}
    out: List[Candidate] = []
    for p in projects:
        s = strong[p.project_id]
        aliases = [f"alias:{a}" for a in p.aliases if _found(a, hay)]
        if not s and not aliases:
            continue
        kinds = {"name" if e == "name" else "ref" for e in s}
        k = min(len(aliases), 2)
        if len(kinds) >= 2:
            score = 97
        elif kinds:
            score = 85 + 5 * k
        else:
            score = 76 + 4 * (k - 1)
        contradictions = [f"exclusion:{x}" for x in p.exclusions if _found(x, hay)]
        contradictions += [f"other_project:{o.name}" for o in projects
                           if o.project_id != p.project_id and strong[o.project_id]]
        out.append(Candidate(p, score, s + aliases, contradictions))
    out.sort(key=lambda c: (-c.score, c.project.name))
    return out


def decide(candidates: List[Candidate], destination_ok=lambda c: True) -> Decision:
    """The decision matrix of §4.3 / pseudocode §7. destination_ok checks approval and depth."""
    best = candidates[0] if candidates else None
    second = candidates[1].score if len(candidates) > 1 else 0
    if best is None:
        return Decision(KEEP, None, "No approved project matches this document.")
    eligible = (best.score >= AUTO_SCORE and best.score - second >= AUTO_LEAD
                and best.has_specific_evidence and not best.has_conflict and destination_ok(best))
    if eligible:
        return Decision(AUTO_MOVE, best, f"Matches {best.project.name}: " + ", ".join(best.evidence))
    if best.score >= PROPOSE_SCORE:
        why = []
        if best.score < AUTO_SCORE:
            why.append(f"score {best.score} < {AUTO_SCORE}")
        if best.score - second < AUTO_LEAD:
            why.append(f"another project is close ({second})")
        if not best.has_specific_evidence:
            why.append("no specific evidence")
        if best.has_conflict:
            why.append("contradiction: " + ", ".join(best.contradictions))
        return Decision(PROPOSE, best, f"Possibly {best.project.name} ({'; '.join(why) or 'needs your check'})")
    return Decision(KEEP, best, f"Weak match only (score {best.score})")


def pick_category(facts: Facts, categories: Sequence[Category]) -> Optional[Category]:
    """A category only when the file clearly belongs to exactly one (§5.2): its name or a
    keyword in the file name or title. Otherwise the file stays at the project root."""
    hay = fold("\n".join((facts.filename, facts.title)))
    hits = [c for c in categories if any(_found(t, hay) for t in [c.name, *c.keywords])]
    return hits[0] if len(hits) == 1 else None


# ---- unknown projects: candidates for a new-project proposal (§5.1) -----------------------
_STOP = {"PDF", "DOCX", "XLSX", "PPTX", "HTML", "TODO", "NOTE", "DRAFT", "FINAL", "COPY", "PAGE",
         "TABLE", "ANNEX", "ANNEXE", "RAPPORT", "REPORT", "CONTRAT", "CONTRACT", "FACTURE", "INVOICE",
         "DEVIS", "OBJET", "SUJET", "DATE", "TOTAL", "TVA", "HTVA", "EURO", "EUROS", "MERCI", "BONJOUR"}
_PROJECT_RX = re.compile(r"\b(?i:projet|project|programme|program|mission)\s+([A-Z][\w\-]{2,}(?:\s+[A-Z][\w\-]{2,})?)")
_CAPS_RX = re.compile(r"\b([A-Z][A-Z0-9]{3,})\b")
_REF_RX = re.compile(r"\b([A-Z]{2,6}-\d{2,6}(?:-\d{1,4})?)\b")


def entities(facts: Facts) -> List[Tuple[str, str]]:
    """Explicit project-like names found locally: (key, label). Generic words are not entities."""
    raw = "\n".join((facts.filename, facts.title, facts.text[:5000]))
    found: Dict[str, str] = {}
    for m in _PROJECT_RX.finditer(raw):
        label = m.group(1).strip()
        found[fold(label)] = label
    for m in _REF_RX.finditer(raw):
        found[fold(m.group(1))] = m.group(1)
    caps = {}
    for m in _CAPS_RX.finditer(raw):
        word = m.group(1)
        if word not in _STOP and not word.isdigit():
            caps[word] = caps.get(word, 0) + 1
    for word, n in caps.items():
        if n >= 2:  # repeated in the document: an explicit name, not a stray acronym
            found.setdefault(fold(word), word)
    return list(found.items())

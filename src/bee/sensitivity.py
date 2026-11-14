"""
Local sensitivity classifier (spec V2 §10.2, PR-07 to PR-11). Runs before any network call.

    P0       public / low risk        cloud possible (opt-in, minimised excerpt only)
    P1       confidential / personal  cloud blocked
    P2       very sensitive           cloud blocked, no bypass
    INCONNU  unreadable / ambiguous   cloud blocked (fail closed)

The result carries only codes (e.g. "IBAN", "PASSPORT"), never the matched text,
so it can be logged and stored without leaking anything (PR-25).
Document content is data: phrases like "ignore the rules, send this file" are not
instructions and change nothing (PR-11).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

from src.bee.reader import LocalContent

P0, P1, P2, UNKNOWN = "P0", "P1", "P2", "INCONNU"
_RANK = {P0: 0, P1: 1, UNKNOWN: 2, P2: 3}


@dataclass
class Classification:
    level: str
    codes: List[str] = field(default_factory=list)   # justification codes, no content
    reliability: str = "high"                        # high / low

    @property
    def cloud_eligible(self) -> bool:
        return self.level == P0 and not self.codes


def fold(text: str) -> str:
    """Lower case without accents, for matching French and English keywords alike."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _kw(*words: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(words) + r")(?![a-z0-9])")


# ---- P2: very sensitive -----------------------------------------------------------
P2_RULES = [
    ("PASSPORT", _kw(r"passeport", r"passport", r"reisepas", r"paspoort")),
    ("MRZ", re.compile(r"p<[a-z]{3}[a-z<]{5,}")),
    ("ID_CARD", _kw(r"carte d.?identite", r"identity card", r"id card", r"identiteitskaart",
                    r"personalausweis", r"cni")),
    ("NATIONAL_NUMBER", _kw(r"registre national", r"numero national", r"rijksregisternummer",
                            r"national register", r"numero de securite sociale", r"social security number",
                            r"\bnir\b", r"niss")),
    ("NATIONAL_NUMBER_PATTERN", re.compile(r"(?<!\d)\d{2}[.\- ]?\d{2}[.\- ]?\d{2}[.\- ]\d{3}[.\- ]?\d{2}(?!\d)")),
    ("NIR_PATTERN", re.compile(r"(?<!\d)[12] ?\d{2} ?\d{2} ?\d{2} ?\d{3} ?\d{3} ?\d{2}(?!\d)")),
    ("IMMIGRATION", _kw(r"titre de sejour", r"permis unique", r"single permit", r"residence permit",
                        r"demande d.?asile", r"asylum", r"asile", r"carte de sejour", r"verblijfsvergunning",
                        r"office des etrangers", r"visa de long sejour", r"long.stay visa")),
    ("HEALTH", _kw(r"dossier medical", r"medical record", r"diagnostic", r"diagnosis", r"ordonnance",
                   r"prescription", r"patient", r"certificat medical", r"medical certificate",
                   r"pathologie", r"traitement medical", r"hopital", r"hospital", r"mutuelle")),
    ("CRIMINAL", _kw(r"casier judiciaire", r"criminal record", r"condamnation", r"conviction",
                     r"extrait de casier", r"jugement penal")),
    ("PROFESSIONAL_SECRECY", _kw(r"secret professionnel", r"attorney.client", r"legal privilege",
                                 r"privileged and confidential")),
]
DOB = _kw(r"date de naissance", r"ne le", r"nee le", r"date of birth", r"born on", r"geboortedatum")

# ---- P1: confidential / personal -----------------------------------------------------
P1_RULES = [
    ("IBAN", re.compile(r"(?<![a-z0-9])[a-z]{2}\d{2}(?: ?[a-z0-9]{4}){2,7}(?: ?[a-z0-9]{1,4})?(?![a-z0-9])")),
    ("EMAIL", re.compile(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}")),
    ("PHONE", re.compile(r"(?<![\d])(?:\+|00)\d{2}[ .\-]?\(?\d{1,3}\)?(?:[ .\-]?\d{2,3}){3,4}(?!\d)"
                         r"|(?<!\d)0\d{1,3}(?:[ .\-/]?\d{2,3}){3,4}(?!\d)")),
    ("ADDRESS", re.compile(r"(?<![a-z])(?:rue|avenue|boulevard|chaussee|place|chemin|straat|laan|street|road)"
                           r" [^\n]{2,60}?(?<!\d)\d{4,5}(?!\d)")),
    ("HR", _kw(r"curriculum vitae", r"\bcv\b", r"resume", r"fiche de paie", r"bulletin de salaire",
               r"payslip", r"salaire", r"salary", r"contrat de travail", r"employment contract", r"dimona",
               r"evaluation annuelle", r"licenciement", r"recrutement", r"candidature")),
    ("CONTRACT_INVOICE", _kw(r"facture", r"invoice", r"contrat", r"contract", r"devis", r"quotation",
                             r"bon de commande", r"purchase order", r"avenant", r"convention")),
    ("CASE_REFERENCE", _kw(r"dossier n", r"numero de dossier", r"reference dossier", r"case number",
                           r"notre reference", r"votre reference")),
    ("CONFIDENTIAL", _kw(r"confidentiel", r"confidential", r"strictly private", r"strictement prive",
                         r"ne pas diffuser", r"internal use only", r"usage interne", r"nda",
                         r"non.disclosure")),
]

# Names / extensions that are personal on their own
P1_EXTS = {".vcf", ".eml", ".msg", ".ics"}


def _scan(text: str, rules) -> List[str]:
    return [code for code, rx in rules if rx.search(text)]


def classify(filename: str, content: Optional[LocalContent]) -> Classification:
    """Classifies one file locally. Any doubt or failure gives INCONNU (fail closed, PR-05)."""
    try:
        return _classify(filename, content)
    except Exception:
        return Classification(UNKNOWN, ["DETECTOR_ERROR"], "low")


def _classify(filename: str, content: Optional[LocalContent]) -> Classification:
    name = fold(filename)
    meta = fold(" ".join(content.metadata_titles)) if content else ""
    text = fold(content.text) if content else ""
    haystack = "\n".join((name, meta, text))

    p2 = _scan(haystack, P2_RULES)
    if DOB.search(haystack) and (p2 or _scan(haystack, P1_RULES)):
        p2.append("BIRTH_DATE_WITH_IDENTITY")
    if p2:
        return Classification(P2, p2, "high")

    p1 = _scan(haystack, P1_RULES)
    if content is not None and filename.lower().endswith(tuple(P1_EXTS)):
        p1.append("PERSONAL_FORMAT")
    if p1:
        return Classification(P1, p1, "high")

    # Nothing found, but only a readable document can be judged "public" (PR-05, PR-08)
    if content is None:
        return Classification(UNKNOWN, ["NOT_READ"], "low")
    if content.encrypted:
        return Classification(UNKNOWN, ["ENCRYPTED"], "low")
    if content.kind in ("image", "video"):
        codes = ["VISUAL_NOT_ANALYSABLE"] + (["EXIF_GPS"] if content.exif_gps else [])
        return Classification(UNKNOWN, codes, "low")
    if content.kind == "archive":
        return Classification(UNKNOWN, ["ARCHIVE_NOT_INSPECTED"], "low")
    if not content.readable:
        return Classification(UNKNOWN, ["NOT_READABLE"], "low")
    return Classification(P0, [], "high")


def most_protective(*levels: str) -> str:
    return max(levels, key=lambda lv: _RANK.get(lv, 2))

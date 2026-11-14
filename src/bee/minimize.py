"""
Minimised excerpt for the optional cloud title (spec PR-13, PR-14, RG13).

Only for documents already classified P0. Removes contact details, identifiers,
long numbers, URLs and paths, keeps a short head of the text, then re-runs the
local detector on the result: if anything risky remains, or too little is left
to be useful, the call is abandoned (None) and naming stays local.
The original file, its name, path and metadata are never part of the excerpt.
"""

import re
from typing import Optional

from src.bee.reader import LocalContent
from src.bee.sensitivity import P1_RULES, P2_RULES, fold

MAX_EXCERPT = 1200
MIN_USEFUL = 60

_REDACTIONS = [
    re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),          # e-mails
    re.compile(r"(?:https?://|www\.)\S+"),                                     # URLs
    re.compile(r"(?:[A-Za-z]:\\|/(?:Users|home|var|tmp)/)\S*"),                # paths
    re.compile(r"[A-Za-z]{2}\d{2}(?: ?[A-Za-z0-9]{4}){2,7}(?: ?[A-Za-z0-9]{1,4})?"),  # IBAN-like
    re.compile(r"(?:\+|00)?\d[\d .\-/()]{6,}\d"),                              # phones, long numbers
    re.compile(r"\b(?=[A-Za-z0-9\-]*\d[A-Za-z0-9\-]*\d[A-Za-z0-9\-]*\d)[A-Za-z0-9\-]{6,}\b"),  # IDs
]


def minimize(content: LocalContent) -> Optional[str]:
    if not content.readable or not content.text:
        return None
    text = content.text
    for rx in _REDACTIONS:
        text = rx.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()[:MAX_EXCERPT]

    useful = "".join(ch for ch in text if ch.isalpha())
    if len(useful) < MIN_USEFUL:
        return None  # PR-14: never widen the payload to get a better name
    folded = fold(text)
    if any(rx.search(folded) for _, rx in P2_RULES + P1_RULES):
        return None  # residual risk (RG13)
    return text

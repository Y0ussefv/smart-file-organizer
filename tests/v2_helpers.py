"""Shared helpers for the V2 acceptance tests (synthetic documents only, spec §11)."""

import json
from datetime import datetime
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest
import requests

from src.bee.ledger import Ledger
from src.bee.pipeline import BeePipeline

FIXED_NOW = datetime(2026, 11, 14, 10, 0, 0)
YM = "26-11"


class NetworkRecorder:
    """Intercepts every requests.post / get (spec AC-07: network interception)."""

    def __init__(self):
        self.calls: List[dict] = []
        self.reply_title = "Rapport Public Intelligence Artificielle Entreprises"
        self.fail = None  # an exception instance to raise instead of answering

    def post(self, url, *args, **kwargs):
        self.calls.append({"url": url, "json": kwargs.get("json"), "headers": kwargs.get("headers")})
        if self.fail:
            raise self.fail
        return _Resp(200, {"choices": [{"message": {"content": json.dumps({"title": self.reply_title})}}]})

    def get(self, url, *args, **kwargs):
        self.calls.append({"url": url, "json": None, "headers": kwargs.get("headers")})
        return _Resp(200, {})

    def all_payload_text(self) -> str:
        return json.dumps([c["json"] for c in self.calls], ensure_ascii=False)


class _Resp:
    def __init__(self, status, data):
        self.status_code = status
        self._data = data
        self.text = json.dumps(data)

    def json(self):
        return self._data


@pytest.fixture
def net():
    rec = NetworkRecorder()
    with patch.object(requests, "post", side_effect=rec.post), patch.object(requests, "get", side_effect=rec.get):
        yield rec


class Env:
    def __init__(self, root: Path):
        self.root = root
        self.dl = root / "Downloads"
        self.dl.mkdir()
        self.ledger = Ledger(root / "ledger.sqlite3")
        self.pipe = BeePipeline(self.dl, ledger=self.ledger, api_key_provider=lambda: "sk-test",
                                clock=lambda: FIXED_NOW)

    @property
    def projets(self) -> Path:
        return self.dl / "Projets"

    def doc(self, name: str, text: str) -> Path:
        p = self.dl / name
        p.write_text(text, encoding="utf-8")
        return p

    def root_files(self):
        return sorted(p.name for p in self.dl.iterdir() if p.is_file())

    def all_files(self):
        return sorted(str(p.relative_to(self.dl)).replace("\\", "/") for p in self.dl.rglob("*") if p.is_file())


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


# Synthetic documents ------------------------------------------------------------------------
PUBLIC_BROCHURE = ("Brochure publique sur l'intelligence artificielle dans les entreprises europeennes. "
                   "Ce guide presente les usages, les limites et les bonnes pratiques pour les petites "
                   "structures qui souhaitent automatiser des taches simples.")
SINELAC_AUDIT = ("Rapport d'audit SINELAC\nMission SIN-2026-04 : audit des procedures internes de SINELAC, "
                 "constats et recommandations pour la direction.")
SINELAC_CONTRACT = ("Contrat de prestation SINELAC\nReference SIN-2026-04\nEntre SINELAC et Nodalis, "
                    "pour la mission d'audit des procedures internes.")
GIZ_HYDROGEN = ("Rapport GIZ sur l'hydrogene vert en Afrique du Nord. Etude de marche, potentiel de production "
                "et recommandations pour les politiques publiques de la GIZ.")
BEESTART_REPORT = ("Rapport final BeeStart\nProgramme d'accompagnement BeeStart, bilan de la cohorte et "
                   "resultats obtenus par les participants BeeStart.")

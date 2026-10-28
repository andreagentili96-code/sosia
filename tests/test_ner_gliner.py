"""Optional tests with the local GLiNER model. Skipped when gliner or the model files are missing
(download them with scripts/download_models.py). Invented data only."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("gliner")

from sosia import Configurazione, Sessione  # noqa: E402
from sosia import ner  # noqa: E402

_MODELLO = Path(os.environ.get("SOSIA_GLINER") or ner.GLINER_PREDEFINITO)
_BASE = Path(os.environ.get("SOSIA_MDEBERTA") or ner.MDEBERTA_PREDEFINITO)

pytestmark = [
    pytest.mark.gliner,
    pytest.mark.skipif(not (_MODELLO / "pytorch_model.bin").exists() or not (_BASE / "spm.model").exists(),
                       reason="GLiNER model not found: run scripts/download_models.py or set SOSIA_GLINER/SOSIA_MDEBERTA"),
]


@pytest.fixture(scope="module")
def modello():
    return ner.carica("gliner")


def test_gliner_trova_nomi_rari_e_ritorno_identico(modello):
    testo = "Sabato ceniamo da Xiomara a Squinzano, poi passiamo da Oyelaran."
    s = Sessione(Configurazione(seme=5), ner=modello)
    e = s.pseudonimizza(testo)
    assert "Xiomara" not in e.testo and "Squinzano" not in e.testo
    assert s.ripristina(e.testo).testo == testo


def test_gliner_testo_inglese(modello):
    testo = "Patient Tahmahkera was seen by Dr. Okonkwo-Bassey at the clinic in Many Farms."
    s = Sessione(Configurazione(seme=5), ner=modello)
    e = s.pseudonimizza(testo)
    assert "Okonkwo-Bassey" not in e.testo
    assert s.ripristina(e.testo).testo == testo

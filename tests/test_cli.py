"""Command line: works on a console or pipe whose encoding lacks «⟦» (cp1252 on Windows). Invented data only."""
from __future__ import annotations

import io
import sys

from sosia.cli import principale


def test_cli_con_uscita_cp1252(tmp_path, monkeypatch):
    monkeypatch.setenv("SOSIA_PAROLA", "una-parola-lunga-di-prova")
    uscita = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", uscita)
    doc = tmp_path / "lettera.txt"
    doc.write_text("La Sig.ra Anna Rossi, nata a Milano il 02/11/1981, paga entro il 25/10/2026.", encoding="utf-8")
    principale(["--cassaforte", str(tmp_path / "cassa"), "pseudonimizza", str(doc), "--sessione", "prova"])
    finto = (tmp_path / "lettera.finto.txt").read_text(encoding="utf-8")
    assert "Rossi" not in finto and "02/11/1981" not in finto
    principale(["--cassaforte", str(tmp_path / "cassa"), "ripristina", str(tmp_path / "lettera.finto.txt"),
                "--sessione", "prova", "-o", str(tmp_path / "tornata.txt")])
    assert (tmp_path / "tornata.txt").read_text(encoding="utf-8") == doc.read_text(encoding="utf-8")

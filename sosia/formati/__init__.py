"""Gestione dei formati di file: testo e Markdown, JSON, DOCX, XLSX, PDF, email (.eml).

Ogni gestore riceve un `Verso` (pseudonimizza o ripristina) e restituisce i byte nuovi più un rapporto
con conteggi e avvisi (mai i valori)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..sessione import Esito, Sessione


@dataclass
class Rapporto:
    conteggi: dict = field(default_factory=dict)
    avvisi: list = field(default_factory=list)
    incerti: int = 0

    def aggiungi(self, e: Esito):
        for k, v in e.conteggi.items():
            self.conteggi[k] = self.conteggi.get(k, 0) + v
        for a in e.avvisi:
            if a not in self.avvisi:
                self.avvisi.append(a)
        self.incerti += len(e.incerti)


class Verso:
    """Direzione della trasformazione, con le stesse operazioni per tutti i formati."""

    def __init__(self, sessione: Sessione, verso: str = "pseudonimizza"):
        if verso not in ("pseudonimizza", "ripristina"):
            raise ValueError(verso)
        self.s = sessione
        self.verso = verso
        self.rapporto = Rapporto()

    @property
    def avanti(self) -> bool:
        return self.verso == "pseudonimizza"

    def testo(self, t: str) -> Esito:
        e = self.s.pseudonimizza(t) if self.avanti else self.s.ripristina(t)
        self.rapporto.aggiungi(e)
        return e

    def stringa(self, t: str) -> str:
        return self.testo(t).testo if t and t.strip() else t

    def noti(self, t: str) -> str:
        """Per formule, nomi di fogli e metadati: solo valori già in mappa."""
        if not t:
            return t
        return self.s.sostituisci_noti(t) if self.avanti else self.s.ripristina(t).testo

    def giorni(self) -> int:
        return self.s.delta if self.avanti else -self.s.delta


ESTENSIONI = {".txt": "testo", ".md": "testo", ".markdown": "testo", ".csv": "testo", ".log": "testo",
              ".json": "json", ".docx": "docx", ".xlsx": "xlsx", ".xlsm": "xlsx", ".pdf": "pdf", ".eml": "email"}


def elabora_bytes(dati: bytes, estensione: str, verso: Verso) -> tuple[bytes, str]:
    """Restituisce (byte nuovi, estensione d'uscita)."""
    tipo = ESTENSIONI.get(estensione.lower())
    if tipo == "testo":
        from .testo import elabora
    elif tipo == "json":
        from .json_ import elabora
    elif tipo == "docx":
        from .docx import elabora
    elif tipo == "xlsx":
        from .xlsx import elabora
    elif tipo == "pdf":
        from .pdf import elabora
    elif tipo == "email":
        from .email_ import elabora
    else:
        raise ValueError(f"Formato non gestito: {estensione}")
    return elabora(dati, verso, estensione.lower())


def elabora_file(ingresso: str | Path, uscita: str | Path | None, sessione: Sessione,
                 verso: str = "pseudonimizza") -> tuple[Path, Rapporto]:
    ingresso = Path(ingresso)
    v = Verso(sessione, verso)
    nuovi, est = elabora_bytes(ingresso.read_bytes(), ingresso.suffix, v)
    if uscita is None:
        suff = ".finto" if verso == "pseudonimizza" else ".ripristinato"
        uscita = ingresso.with_name(ingresso.stem + suff + est)
    uscita = Path(uscita)
    uscita.write_bytes(nuovi)
    return uscita, v.rapporto

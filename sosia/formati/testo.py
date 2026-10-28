"""Testo semplice, Markdown e CSV: il testo passa intero (il contesto aiuta il riconoscimento)."""
from __future__ import annotations


def decodifica(dati: bytes) -> tuple[str, str]:
    for cod in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return dati.decode(cod), ("utf-8" if cod.startswith("utf-8") else cod)
        except UnicodeDecodeError:
            continue
    return dati.decode("latin-1"), "latin-1"


def elabora(dati: bytes, verso, est: str):
    testo, cod = decodifica(dati)
    if est == ".csv":
        # Le intestazioni Nome/Cognome aiutano: le righe diventano «Nome Cognome» registrati prima.
        _registra_csv(testo, verso)
    nuovo = verso.testo(testo).testo
    return nuovo.encode(cod), est


def _registra_csv(testo: str, verso):
    import csv
    import io
    if not verso.avanti:
        return
    try:
        dialetto = csv.Sniffer().sniff(testo[:4000], delimiters=",;\t|")
    except csv.Error:
        return
    righe = list(csv.reader(io.StringIO(testo), dialetto))
    if len(righe) < 2:
        return
    from .xlsx import classifica_colonne, registra_riga
    col = classifica_colonne({i: h for i, h in enumerate(righe[0])})
    for r in righe[1:]:
        registra_riga({i: v for i, v in enumerate(r)}, col, verso.s)

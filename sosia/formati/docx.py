"""DOCX: corpo, intestazioni, piè di pagina, note, commenti, revisioni (testo cancellato compreso) e metadati.
Si modifica solo il testo dentro <w:t>/<w:delText>: stili, tabelle, immagini e impaginazione restano identici."""
from __future__ import annotations

import io
import re
import zipfile

from ._xml import trasforma_core, trasforma_xml

TESTO = re.compile(r"(?P<apri><w:(?:t|delText)(?:\s[^>]*)?>)(?P<t>[^<]*)(?P<chiudi></w:(?:t|delText)>)")
CONFINE = re.compile(r"<w:p[\s>/]|</w:p>|<w:tab/>|<w:br\s?[^>]*/>|<w:cr/>|<w:tc[\s>]|</w:tc>")
PARTI = re.compile(r"word/(?:document|header\d*|footer\d*|footnotes|endnotes|comments\w*)\.xml$")


def elabora(dati: bytes, verso, est: str):
    zin = zipfile.ZipFile(io.BytesIO(dati))
    out = io.BytesIO()
    immagini = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        # Il corpo prima dei metadati: così l'autore, se compare nel testo, è già in mappa.
        nomi = sorted(zin.namelist(), key=lambda n: (0 if n == "word/document.xml" else 1, n))
        contenuti = {}
        for n in nomi:
            b = zin.read(n)
            if PARTI.fullmatch(n):
                b = trasforma_xml(b.decode("utf-8"), verso, TESTO, CONFINE).encode("utf-8")
            elif n in ("docProps/core.xml", "docProps/app.xml"):
                b = trasforma_core(b.decode("utf-8"), verso).encode("utf-8")
            elif n.startswith("word/media/"):
                immagini += 1
            contenuti[n] = b
        for info in zin.infolist():
            zout.writestr(info, contenuti[info.filename])
    if immagini and verso.avanti:
        verso.rapporto.avvisi.append(f"{immagini} immagini nel documento NON sono protette (servirebbe l'OCR): "
                                     "toglierle se contengono dati personali")
    return out.getvalue(), est

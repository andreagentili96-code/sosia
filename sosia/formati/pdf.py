"""PDF: si estrae il testo (pypdf), lo si trasforma e si scrive un PDF NUOVO solo testo.

Limiti dichiarati: impaginazione, tabelle, immagini, firme e moduli NON sono conservati; un PDF scansionato
non ha testo (serve l'OCR); l'estrazione può spezzare parole o righe. Non si «cancella» nulla dentro il PDF
originale: si produce un documento diverso, adatto a essere letto da un modello."""
from __future__ import annotations

import io
import zlib


def estrai_testo(dati: bytes) -> list[str]:
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(dati))
    return [(p.extract_text() or "") for p in r.pages]


def elabora(dati: bytes, verso, est: str):
    pagine = estrai_testo(dati)
    if not any(p.strip() for p in pagine):
        verso.rapporto.avvisi.append("PDF senza testo estraibile (forse scansionato): serve l'OCR, nulla è stato inviato")
        raise ValueError("PDF senza testo: serve l'OCR")
    separatore = "\n\f\n"
    nuovo = verso.testo(separatore.join(pagine)).testo
    verso.rapporto.avvisi.append("PDF: prodotto un PDF nuovo solo testo; impaginazione, immagini e tabelle non sono conservate")
    return scrivi_pdf(nuovo.split("\f")), ".pdf"


# ------------------------------------------------------------------ scrittore PDF minimo (Helvetica, WinAnsi)
_LARGHEZZE = {c: 556 for c in "abcdeghnopqu0123456789"}
_LARGHEZZE.update({c: 222 for c in "ijl"}, **{c: 278 for c in "ft !.,:;'"}, **{"m": 833, "w": 722, "r": 333,
                  "s": 500, "v": 500, "x": 500, "y": 500, "z": 500, "k": 500, "-": 333, "(": 333, ")": 333})


def _larghezza(s: str, corpo: float) -> float:
    return sum(_LARGHEZZE.get(c, 667 if c.isupper() else 556) for c in s) * corpo / 1000


def _a_capo(riga: str, massimo: float, corpo: float) -> list[str]:
    if _larghezza(riga, corpo) <= massimo:
        return [riga]
    out, cur = [], ""
    for parola in riga.split(" "):
        prova = (cur + " " + parola) if cur else parola
        if _larghezza(prova, corpo) <= massimo:
            cur = prova
        else:
            if cur:
                out.append(cur)
            while _larghezza(parola, corpo) > massimo:  # parola lunghissima
                k = max(1, int(len(parola) * massimo / _larghezza(parola, corpo)))
                out.append(parola[:k])
                parola = parola[k:]
            cur = parola
    out.append(cur)
    return out


def _esc(s: str) -> bytes:
    b = s.encode("cp1252", errors="replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def scrivi_pdf(pagine_testo: list[str], corpo: float = 10.5) -> bytes:
    L, H, M = 595.28, 841.89, 56
    interlinea = corpo * 1.35
    righe_per_pagina = int((H - 2 * M) / interlinea)
    pagine: list[list[str]] = []
    for testo in pagine_testo:
        righe = []
        for r in testo.strip("\n").split("\n"):
            righe += _a_capo(r.replace("\t", "    "), L - 2 * M, corpo)
        for i in range(0, max(1, len(righe)), righe_per_pagina):
            pagine.append(righe[i:i + righe_per_pagina])
    oggetti: list[bytes] = []

    def nuovo(b: bytes) -> int:
        oggetti.append(b)
        return len(oggetti)

    catalogo = nuovo(b"")  # riempito dopo
    radice_pagine = nuovo(b"")
    font = nuovo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    figli = []
    for righe in pagine:
        flusso = [b"BT", f"/F1 {corpo} Tf {interlinea:.2f} TL {M} {H - M - corpo:.2f} Td".encode()]
        for r in righe:
            flusso.append(b"(" + _esc(r) + b") Tj T*")
        flusso.append(b"ET")
        dati = zlib.compress(b"\n".join(flusso))
        cont = nuovo(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(dati) + dati + b"\nendstream")
        figli.append(nuovo(f"<< /Type /Page /Parent {radice_pagine} 0 R /MediaBox [0 0 {L} {H}] "
                           f"/Resources << /Font << /F1 {font} 0 R >> >> /Contents {cont} 0 R >>".encode()))
    oggetti[catalogo - 1] = f"<< /Type /Catalog /Pages {radice_pagine} 0 R >>".encode()
    oggetti[radice_pagine - 1] = (f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in figli)}] "
                                  f"/Count {len(figli)} >>").encode()
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    posizioni = []
    for i, o in enumerate(oggetti, 1):
        posizioni.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(oggetti) + 1}\n0000000000 65535 f \n".encode()
    for p in posizioni:
        out += f"{p:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(oggetti) + 1} /Root {catalogo} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)

"""Trasformazione del testo dentro XML di Office senza riscrivere l'albero (niente lxml, formattazione intatta).

Il testo di un paragrafo è spezzato in più «run» con formattazioni diverse. Si ricompone il paragrafo,
lo si trasforma intero (così «Mario» in grassetto e «Rossi» normale restano una persona) e si ridistribuisce:
ogni sostituzione va nel run in cui inizia, i caratteri sostituiti spariscono dai run successivi."""
from __future__ import annotations

import html
import re


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ridistribuisci(pezzi: list[str], sostituzioni: list[tuple]) -> list[str]:
    inizi = {a: (b, n) for a, b, n, _ in sostituzioni}
    coperti = []
    for a, b, _, _ in sostituzioni:
        coperti.append((a, b))
    out, o = [], 0
    for p in pezzi:
        buf = []
        for i in range(o, o + len(p)):
            if i in inizi:
                buf.append(inizi[i][1])
            if any(a <= i < b for a, b in coperti):
                continue
            buf.append(p[i - o])
        out.append("".join(buf))
        o += len(p)
    return out


def trasforma_xml(xml: str, verso, testo_rx: re.Pattern, confine_rx: re.Pattern) -> str:
    """testo_rx: gruppi «apri», «t», «chiudi». confine_rx: tag che chiudono un segmento (paragrafo, tab, a capo)."""
    eventi = []
    for m in testo_rx.finditer(xml):
        eventi.append((m.start(), "t", m))
    for m in confine_rx.finditer(xml):
        eventi.append((m.start(), "c", m))
    eventi.sort(key=lambda x: x[0])
    modifiche = []  # (inizio, fine, nuovo) sul testo XML
    segmento: list = []

    def chiudi():
        if not segmento:
            return
        pezzi = [html.unescape(m.group("t")) for m in segmento]
        intero = "".join(pezzi)
        if intero.strip():
            e = verso.testo(intero)
            if e.sostituzioni:
                nuovi = ridistribuisci(pezzi, e.sostituzioni)
                for m, n in zip(segmento, nuovi):
                    if n == html.unescape(m.group("t")):
                        continue
                    apri = m.group("apri")
                    if (n[:1].isspace() or n[-1:].isspace()) and "xml:space" not in apri:
                        apri = apri[:-1] + ' xml:space="preserve">'
                    modifiche.append((m.start(), m.end(), apri + _esc(n) + m.group("chiudi")))
        segmento.clear()

    for _, tipo, m in eventi:
        if tipo == "c":
            chiudi()
        else:
            segmento.append(m)
    chiudi()
    for a, b, n in sorted(modifiche, reverse=True):
        xml = xml[:a] + n + xml[b:]
    return xml


def trasforma_core(xml: str, verso) -> str:
    """Metadati docProps/core.xml e app.xml: autore, ultimo autore, titolo, oggetto, azienda…"""
    return re.sub(r"<(dc:creator|cp:lastModifiedBy|dc:title|dc:subject|dc:description|cp:keywords|Company|Manager)((?:\s[^>]*)?)>(.*?)</\1>",
                  lambda m: _sost_core(m, verso), xml, flags=re.S)


def _dividi(valore: str):
    parole = valore.split()
    if len(parole) >= 2:
        return parole[0], " ".join(parole[1:])
    return None, valore


def _sost_core(m, verso):
    tag, attr, val = m.group(1), m.group(2) or "", html.unescape(m.group(3))
    if not val.strip():
        return m.group(0)
    if verso.avanti and tag in ("dc:creator", "cp:lastModifiedBy", "Manager"):
        # Un nome da solo nei metadati non ha contesto: si registra come persona.
        n, c = _dividi(val.strip())
        if re.fullmatch(r"[\w'’ .-]+", val.strip()) and val.strip()[:1].isupper():
            verso.s.registra_persona(n, c)
    nuovo = verso.stringa(val)
    return f"<{tag}{attr}>{_esc(nuovo)}</{tag}>"

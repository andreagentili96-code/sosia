"""XLSX: stringhe condivise, stringhe in linea, formule, date numeriche e nomi dei fogli, senza openpyxl
(che perderebbe grafici e immagini). Le intestazioni di colonna guidano il riconoscimento:
una cella «Rossi» sotto «Cognome» è un cognome anche senza contesto."""
from __future__ import annotations

import datetime as dt
import html
import io
import re
import zipfile

from .. import riconoscitori as R
from ..dati import norm
from ._xml import _esc, trasforma_core, trasforma_xml

TESTO = re.compile(r"(?P<apri><t(?:\s[^>]*)?>)(?P<t>[^<]*)(?P<chiudi></t>)")
CONFINE_SI = re.compile(r"<si>|</si>|<is>|</is>")
RE_CELLA = re.compile(r"<c\s(?P<attr>[^>]*?)(?:/>|>(?P<corpo>.*?)</c>)", re.S)
RE_V = re.compile(r"<v>([^<]*)</v>")
RE_F = re.compile(r"(<f(?:\s[^>]*)?>)([^<]*)(</f>)")
DATE_INCORPORATE = set(range(14, 23)) | set(range(27, 37)) | {45, 46, 47} | set(range(50, 59))


def classifica_colonne(intestazioni: dict) -> dict:
    col = {}
    for c, h in intestazioni.items():
        n = norm(str(h or "")).strip()
        if not n:
            continue
        if re.search(r"\bcognome\b", n) and "nome e cognome" not in n and "cognome e nome" not in n and "cognome nome" not in n:
            col[c] = "cognome"
        elif re.fullmatch(r"nome(?: (?:di battesimo|proprio|dipendente))?|first name|given name", n):
            col[c] = "nome"
        elif re.search(r"nominativo|nome e cognome|cognome e nome|cognome nome|dipendente|lavorat|paziente|cliente|intestatari|beneficiari|full name|nome completo", n):
            col[c] = "nominativo"
        elif re.fullmatch(r"sesso|genere|sex|gender", n):
            col[c] = "sesso"
        elif re.search(r"citta|comune|residenza|luogo di nascita|localita", n):
            col[c] = "citta"
        elif re.search(r"matricola|badge|codice dipendente|cod\. dip|id dipendente|n\. pratica|numero pratica|codice cliente", n):
            col[c] = "codice"
    return col


def sembra_nome(v: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-zÀ-ÿ'’. -]{2,40}", v)) and len(v.split()) <= 4


def registra_riga(riga: dict, col: dict, s):
    genere = None
    for c, t in col.items():
        if t == "sesso":
            v = str(riga.get(c, "")).strip().upper()[:1]
            genere = v if v in ("M", "F") else None
    nome = next((str(riga[c]).strip() for c, t in col.items() if t == "nome" and riga.get(c) and sembra_nome(str(riga[c]).strip())), None)
    cognome = next((str(riga[c]).strip() for c, t in col.items() if t == "cognome" and riga.get(c) and sembra_nome(str(riga[c]).strip())), None)
    if nome or cognome:
        s.registra_persona(nome, cognome, genere)
    for c, t in col.items():
        v = str(riga.get(c) or "").strip()
        if not v:
            continue
        if t == "nominativo" and sembra_nome(v):
            parole = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"[^\s]+", v)]
            nomi, cg = [], []
            for ruolo, a, b, _ in R.ruoli(parole, genere):
                (nomi if ruolo == "nome" else cg).append(v[a:b])
            s.registra_persona(" ".join(nomi) or None, " ".join(cg) or None, genere)
        elif t == "citta" and sembra_nome(v):
            s._citta(v)


def _formati_data(styles: str) -> list[bool]:
    personalizzati = {}
    for m in re.finditer(r'<numFmt\s+numFmtId="(\d+)"\s+formatCode="([^"]*)"', styles):
        codice = html.unescape(m.group(2))
        pulito = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", codice).lower()
        personalizzati[int(m.group(1))] = bool(re.search(r"[dy]", pulito)) or ("m" in pulito and "h" not in pulito and "s" not in pulito and "0" not in pulito)
    xfs = re.search(r"<cellXfs[^>]*>(.*?)</cellXfs>", styles, re.S)
    out = []
    if xfs:
        for m in re.finditer(r"<xf\s[^>]*?numFmtId=\"(\d+)\"", xfs.group(1)):
            i = int(m.group(1))
            out.append(i in DATE_INCORPORATE or personalizzati.get(i, False))
    return out


def _stringhe(ss: str) -> list[str]:
    return ["".join(html.unescape(t) for t in re.findall(r"<t(?:\s[^>]*)?>([^<]*)</t>", si))
            for si in re.findall(r"<si>(.*?)</si>", ss, re.S)]


def _col(rif: str) -> str:
    return re.match(r"[A-Z]+", rif).group(0)


def elabora(dati: bytes, verso, est: str):
    zin = zipfile.ZipFile(io.BytesIO(dati))
    nomi = zin.namelist()
    contenuti = {n: zin.read(n) for n in nomi}
    styles = contenuti.get("xl/styles.xml", b"").decode("utf-8")
    sono_date = _formati_data(styles)
    condivise = _stringhe(contenuti["xl/sharedStrings.xml"].decode("utf-8")) if "xl/sharedStrings.xml" in contenuti else []
    fogli = sorted(n for n in nomi if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
    colonne_codice: dict[str, set] = {}
    # 1) intestazioni → persone e città registrate prima di trasformare le stringhe
    for f in fogli:
        xml = contenuti[f].decode("utf-8")
        griglia: dict[int, dict] = {}
        for m in RE_CELLA.finditer(xml):
            attr, corpo = m.group("attr"), m.group("corpo") or ""
            rif = re.search(r'r="([A-Z]+)(\d+)"', attr)
            if not rif:
                continue
            tipo = re.search(r'\st="(\w+)"', " " + attr)
            tipo = tipo.group(1) if tipo else "n"
            v = RE_V.search(corpo)
            if tipo == "s" and v:
                testo = condivise[int(v.group(1))]
            elif tipo == "inlineStr":
                testo = "".join(html.unescape(t) for t in re.findall(r"<t(?:\s[^>]*)?>([^<]*)</t>", corpo))
            elif v:
                testo = v.group(1)
            else:
                continue
            griglia.setdefault(int(rif.group(2)), {})[rif.group(1)] = testo
        righe = sorted(griglia)
        intest = next((r for r in righe if sum(1 for x in griglia[r].values() if re.search(r"[A-Za-z]", x)) >= 2), None)
        if intest is None:
            continue
        col = classifica_colonne(griglia[intest])
        colonne_codice[f] = {c for c, t in col.items() if t == "codice"}
        if verso.avanti:
            for r in righe:
                if r > intest:
                    registra_riga(griglia[r], col, verso.s)
    # 2) stringhe condivise
    if "xl/sharedStrings.xml" in contenuti:
        contenuti["xl/sharedStrings.xml"] = trasforma_xml(contenuti["xl/sharedStrings.xml"].decode("utf-8"), verso,
                                                          TESTO, CONFINE_SI).encode("utf-8")
    # 3) fogli: stringhe in linea, formule, date numeriche, codici numerici
    giorni = verso.giorni()
    for f in fogli:
        xml = contenuti[f].decode("utf-8")
        cod = colonne_codice.get(f, set())

        def cella(m):
            attr, corpo = m.group("attr"), m.group("corpo")
            if corpo is None:
                return m.group(0)
            tipo = re.search(r'\st="(\w+)"', " " + attr)
            tipo = tipo.group(1) if tipo else "n"
            stile = re.search(r'\ss="(\d+)"', " " + attr)
            stile = int(stile.group(1)) if stile else 0
            rif = re.search(r'r="([A-Z]+)\d+"', attr)
            nuovo = corpo
            if tipo == "inlineStr":
                nuovo = trasforma_xml(nuovo, verso, TESTO, CONFINE_SI)
            nuovo = RE_F.sub(lambda x: x.group(1) + _esc(_formula(html.unescape(x.group(2)), verso, giorni)) + x.group(3), nuovo)
            if tipo == "str":
                nuovo = RE_V.sub(lambda x: "<v>" + _esc(verso.stringa(html.unescape(x.group(1)))) + "</v>", nuovo)
            if tipo == "n":
                v = RE_V.search(nuovo)
                if v and stile < len(sono_date) and sono_date[stile] and giorni:
                    try:
                        num = float(v.group(1))
                        nv = num + giorni
                        testo_v = str(int(nv)) if nv.is_integer() else repr(nv)
                        nuovo = nuovo[:v.start(1)] + testo_v + nuovo[v.end(1):]
                        verso.rapporto.conteggi["DATA"] = verso.rapporto.conteggi.get("DATA", 0) + 1
                    except ValueError:
                        pass
                elif v and rif and rif.group(1) in cod and re.fullmatch(r"\d{3,}", v.group(1)):
                    nuovo = nuovo[:v.start(1)] + _codice(v.group(1), verso) + nuovo[v.end(1):]
            return f"<c {attr}>{nuovo}</c>"

        xml = RE_CELLA.sub(cella, xml)
        contenuti[f] = xml.encode("utf-8")
    # 4) nomi dei fogli e nomi definiti, metadati
    if "xl/workbook.xml" in contenuti:
        wb = contenuti["xl/workbook.xml"].decode("utf-8")
        wb = re.sub(r'(<sheet\s[^>]*?name=")([^"]*)(")', lambda m: m.group(1) + _esc(verso.stringa(html.unescape(m.group(2)))[:31]) + m.group(3), wb)
        wb = re.sub(r"(<definedName[^>]*>)([^<]*)(</definedName>)", lambda m: m.group(1) + _esc(verso.noti(html.unescape(m.group(2)))) + m.group(3), wb)
        contenuti["xl/workbook.xml"] = wb.encode("utf-8")
    for n in ("docProps/core.xml", "docProps/app.xml"):
        if n in contenuti:
            contenuti[n] = trasforma_core(contenuti[n].decode("utf-8"), verso).encode("utf-8")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            zout.writestr(info, contenuti[info.filename])
    if any(n.startswith("xl/media/") for n in nomi) and verso.avanti:
        verso.rapporto.avvisi.append("il foglio contiene immagini NON protette (servirebbe l'OCR)")
    return out.getvalue(), est


def _codice(valore: str, verso) -> str:
    s = verso.s
    if verso.avanti:
        from .. import generatori as G
        return s._valore("NUMERO", valore, lambda: G.finto_numero(s._rng, valore))["f"]
    k = s.valori_finti.get(f"NUMERO|{valore}")
    return s.valori[k]["r"] if k else valore


def _formula(f: str, verso, giorni: int) -> str:
    """DATE(aaaa;mm;gg) costanti si spostano; nomi di fogli e testi tra virgolette passano dalla mappa."""
    def data(m):
        try:
            d = dt.date(int(m.group(2)), int(m.group(3)), int(m.group(4))) + dt.timedelta(days=giorni)
        except ValueError:
            return m.group(0)
        sep = m.group(5)
        return f"{m.group(1)}({d.year}{sep}{d.month}{sep}{d.day})"
    f = re.sub(r"(DATE|DATA)\((\d{4})\s*([,;])?\s*(\d{1,2})\s*[,;]\s*(\d{1,2})\)", lambda m: data(_fix(m)), f, flags=re.I)
    f = re.sub(r'"([^"]*)"', lambda m: '"' + verso.noti(m.group(1)) + '"', f)
    f = re.sub(r"'([^']+)'!", lambda m: "'" + verso.noti(m.group(1)) + "'!", f)
    return f


class _fix:
    """Adatta il match di DATE(a,m,g) alla funzione data (gruppi normalizzati)."""

    def __init__(self, m):
        self.m = m
        sep = re.search(r"[,;]", m.group(0)).group(0)
        nums = re.findall(r"\d+", m.group(0))
        self._g = {1: m.group(1), 2: nums[0], 3: nums[1], 4: nums[2], 5: sep}

    def group(self, i):
        return self._g[i] if i else self.m.group(0)

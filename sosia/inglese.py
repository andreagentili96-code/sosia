"""English (US and UK): language detection, validators, detectors and surrogate generators.

Same architecture as the Italian rules: schemas with check digits where they exist (NHS mod 11, ABA routing,
Luhn, IBAN), context labels where they do not (passport, driver's licence, account, MRN, claim…), dictionaries and
cues for people and places. Returns spans; replacements are built by the session."""
from __future__ import annotations

import re

from . import dati_en as E
from .dati import norm
from .riconoscitori import PersonaCandidata, Span

# ------------------------------------------------------------------ language
_IT = set("il lo la gli le di del della dei delle che non per con una uno sono è nel nella alla dal dalla anche come più "
          "questo questa sig avv dott via presso nato nata residente sottoscritto gentile cordiali saluti oggetto".split())
_EN = set("the and of to is that for with on as was are be this by at from or an not have has will your you our "
          "their which been were would should dear sincerely regards please street mr mrs ms dr subject".split())
RE_PAROLE = re.compile(r"[a-zà-ÿ']+")


RE_SEGNALI_EN = re.compile(r"(?i)\b(?:patient|phone|address|number|date|birth|dob|ssn|nhs|zip|postcode|routing|account|street|"
                           r"road|drive|avenue|lane|born|dear|name|city|state|county|claim|policy|tenant|landlord|"
                           r"mr|mrs|ms|dr)\b")
RE_SEGNALI_IT = re.compile(r"(?i)\b(?:nat[oa]|via|tel|cell|indirizzo|numero|data|paziente|codice|fiscale|residente|"
                           r"sig|sig\.ra|dott|avv|comune|provincia|ciao|grazie|domani|oggi)\b")


def lingua(testo: str) -> str:
    """«it», «en» o «misto» (entrambe con almeno il 25% dei segnali)."""
    it = en = 0
    for w in RE_PAROLE.findall(testo.lower()[:20000]):
        if w in _IT:
            it += 1
        elif w in _EN:
            en += 1
    if it + en < 3:  # testo breve: contano anche le parole e le sigle tipiche dei documenti
        it += len(RE_SEGNALI_IT.findall(testo[:5000]))
        en += len(RE_SEGNALI_EN.findall(testo[:5000]))
        return "it" if it >= en else "en"
    if min(it, en) >= 3 and min(it, en) / (it + en) >= 0.25:
        return "misto"
    return "it" if it > en else "en"


# ------------------------------------------------------------------ validators
def ssn_valido(s: str) -> bool:
    d = re.sub(r"\D", "", s)
    if len(d) != 9:
        return False
    a, g, n = d[:3], d[3:5], d[5:]
    return a not in ("000", "666") and not a.startswith("9") and g != "00" and n != "0000"


def itin_valido(s: str) -> bool:
    d = re.sub(r"\D", "", s)
    if len(d) != 9 or d[0] != "9":
        return False
    m = int(d[3:5])
    return 50 <= m <= 65 or 70 <= m <= 88 or 90 <= m <= 92 or 94 <= m <= 99


_NINO = re.compile(r"(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]")


def nino_valido(s: str) -> bool:
    return bool(_NINO.fullmatch(s.upper().strip()))


def nhs_controllo(nove: str) -> int | None:
    tot = sum(int(c) * (10 - i) for i, c in enumerate(nove))
    c = 11 - tot % 11
    if c == 11:
        return 0
    return None if c == 10 else c


def nhs_valido(s: str) -> bool:
    d = re.sub(r"\D", "", s)
    return len(d) == 10 and nhs_controllo(d[:9]) == int(d[9])


def aba_valido(s: str) -> bool:
    d = re.sub(r"\D", "", s)
    if len(d) != 9:
        return False
    v = [int(c) for c in d]
    return (3 * (v[0] + v[3] + v[6]) + 7 * (v[1] + v[4] + v[7]) + (v[2] + v[5] + v[8])) % 10 == 0


def aba_controllo(otto: str) -> str:
    for c in "0123456789":
        if aba_valido(otto + c):
            return c
    raise ValueError


# ------------------------------------------------------------------ detectors
_UP = "A-ZÀ-Ý"
_LO = "a-zß-ÿ"
# dopo la parola chiave: «No.», «Number:», «#», «(ABA)», «/ state ID:» (poche parole prima dei due punti)
CTX = (r"(?i:(?:[ \t]*\([A-Za-z .]{1,12}\))?(?:[ \t]*(?:#|no\.?|num(?:ber)?\.?|n[o°]\.?|id|on\s+file|:))*"
       r"(?:[ \t]*/[^\n:]{1,20}:)?)[ \t]*[:\-]?[ \t]*")
VAL = r"(?=(?P<v>[A-Z0-9](?:[A-Z0-9\-/.]{0,24}[A-Z0-9])?)(?![A-Za-z0-9]))"
VAL_SPAZI = r"(?=(?P<v>[A-Z0-9*]{1,8}(?:[ \-/][A-Z0-9*]{1,8}){0,5})(?![A-Za-z0-9]))"  # «ABC D12», «493 817 265»


def _ctx(parole: str, tipo: str, cifre_min: int = 2, val: str = VAL):
    return (re.compile(r"(?i:\b(?:" + parole + r"))" + CTX + val), tipo, cifre_min)


CONTESTI = [
    _ctx(r"ssn|social\s+security(?:\s+number)?|soc\.?\s*sec\.?(?:\s*no)?", "SSN", 4),
    _ctx(r"itin|individual\s+taxpayer\s+identification(?:\s+number)?", "ITIN", 4),
    _ctx(r"nhs(?:\s+number)?", "NHS", 6),
    _ctx(r"national\s+insurance(?:\s+number)?|ni\s+number|nino", "NINO", 4),
    _ctx(r"passport(?:\s+number)?", "PASSAPORTO", 5),
    _ctx(r"driver'?s?\s+licen[cs]e(?:\s+number)?|driving\s+licen[cs]e(?:\s+number)?|licen[cs]e\s+(?:no|number|#)|\bdl\b|\bd/l\b|state\s+id", "PATENTE", 3, VAL_SPAZI),
    _ctx(r"routing(?:\s+(?:number|no|transit\s+number))?|aba(?:\s+(?:routing|number))?|rtn", "ROUTING", 7),
    _ctx(r"sort\s+code", "SORTCODE", 6),
    _ctx(r"(?:bank\s+|checking\s+|savings\s+|loan\s+|current\s+)?account(?:\s+(?:number|no|#|to\s+(?:debit|credit)|ending(?:\s+in)?))?|acct\.?(?:\s+(?:no|#))?|a/c", "CONTO", 4),
    _ctx(r"vin|vehicle\s+identification\s+number|chassis(?:\s+number)?", "VIN", 4),
    _ctx(r"(?:license|licence|registration|number)\s+plate|plate(?:\s+(?:number|no))?|tag\s+number|reg(?:istration)?(?:\s+(?:no|number|mark))?|vrm", "TARGA", 2, VAL_SPAZI),
    _ctx(r"mrn|medical\s+record(?:\s+number)?|hospital\s+(?:number|no|id)|patient\s+id|member\s+(?:id|number)|subscriber\s+id|"
         r"employee\s+(?:id|number|no)|staff\s+(?:id|number)|payroll\s+(?:number|no|id)|student\s+id|badge|customer\s+(?:id|number|no)|"
         r"client\s+(?:id|number|no)|utr|unique\s+taxpayer\s+reference|tax\s+reference|taxpayer\s+id|tin|ein|npi|dea|"
         r"group\s+(?:number|no)|beneficiary\s+id|insurance\s+id|id\s+(?:number|no)|identification\s+(?:number|no)|"
         r"card\s+(?:number|no)|membership\s+(?:number|no)|ticket|booking|reservation|confirmation|user\s+id|asset\s+tag", "DOCUMENTO", 2, VAL_SPAZI),
    _ctx(r"claim|policy|case|docket|file|matter|reference|ref\.?|our\s+ref|your\s+ref|invoice|order|incident|report|"
         r"complaint|citation|loan|mortgage|application|contract|agreement|title\s+(?:number|no)|crime\s+(?:number|reference)|"
         r"tracking|transaction|confirmation|receipt|statement|cause|index|charge|warrant|summons|appeal", "PRATICA", 3, VAL_SPAZI),
    _ctx(r"apn|assessor'?s\s+parcel(?:\s+number)?|parcel(?:\s+(?:number|id|no))?|lot|block|tract|title\s+number|uprn|plot", "CATASTO", 0, VAL_SPAZI),
]

RE_SSN = re.compile(r"(?<![\d-])(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?![\d-])")
RE_ITIN = re.compile(r"(?<![\d-])9\d{2}-(?:5\d|6[0-5]|7\d|8[0-8]|9[0-2]|9[4-9])-\d{4}(?![\d-])")
RE_NINO = re.compile(r"(?<![A-Z0-9])(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D](?![A-Z0-9])")
RE_NHS = re.compile(r"(?<![\d])\d{3}[ -]?\d{3}[ -]?\d{4}(?![\d])")
RE_ABA = re.compile(r"(?<![\d])\d{9}(?![\d])")
RE_UK_LICENCE = re.compile(r"(?<![A-Z0-9])[A-Z9]{5}\d{6}[A-Z9]{2}\d[A-Z]{2}(?:\s?\d{2})?(?![A-Z0-9])")
RE_VIN = re.compile(r"(?<![A-Z0-9])(?=[A-HJ-NPR-Z0-9]*\d)(?=[A-HJ-NPR-Z0-9]*[A-HJ-NPR-Z])[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])")
RE_UK_REG = re.compile(r"(?<![A-Z0-9])[A-Z]{2}\d{2}\s?[A-Z]{3}(?![A-Z0-9])")
RE_TEL_US = re.compile(r"(?<![\w+\-/])(?:\+?1[\s.-]?)?\(?[2-9]\d{2}\)?[\s.-]?[2-9]\d{2}[\s.-]\d{4}(?![\d\-/])|(?<![\w+\-/])\+1\s?[2-9]\d{2}\s?[2-9]\d{2}\s?\d{4}(?![\d\-/])")
RE_TEL_UK = re.compile(r"(?<![\w+])(?<!\d[ \t])(?:\+44[ \t]?\(?0?\)?[ \t]?|0)\d(?:[ \t]?\d){8,10}(?![\d]|[ \t]\d)")
RE_ZIP_STATO = re.compile(r"(?<![\w])(?P<citta>[" + _UP + r"][\w'.-]+(?:[ \t][" + _UP + r"][\w'.-]+){0,2}),?[ \t]+(?P<stato>" +
                          "|".join(list(E.US_STATES) + sorted(E.US_STATES.values(), key=len, reverse=True)) + r")[ \t]+(?P<zip>\d{5}(?:-\d{4})?)(?![\d-])")
RE_CITTA_STATO = re.compile(r"(?<![\w])(?P<citta>[" + _UP + r"][\w'.-]+(?:[ \t][" + _UP + r"][\w'.-]+){0,2}),[ \t]+(?P<stato>" +
                            "|".join([s for s in E.US_STATES if s not in ("MD", "PA", "DO")] + sorted(E.US_STATES.values(), key=len, reverse=True)) + r")(?![\w])(?![ \t]+\d{5})(?=[ \t]*(?:[,.;:)]|\n|$))")
RE_ZIP_CTX = re.compile(r"(?i:\bzip(?:\s+code)?|zip\+4)\s*:?\s*(?P<zip>\d{5}(?:-\d{4})?)(?![\d-])")
RE_POSTCODE = re.compile(r"(?<![A-Z0-9])(?:GIR\s?0AA|[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]?\s?\d[ABD-HJLNP-UW-Z]{2})(?![A-Z0-9])")
RE_CITTA_POSTCODE = re.compile(r"(?P<citta>[" + _UP + r"][\w'.-]+(?:[ \t][" + _UP + r"a-z][\w'.-]+){0,2})[ \t]*,?[ \t]*(?:\n[ \t]*)?" +
                               r"(?P<pc>(?:[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]?\s?\d[ABD-HJLNP-UW-Z]{2}))(?![A-Z0-9])")
_SUFFISSI = "|".join(sorted(map(re.escape, E.STREET_SUFFIXES), key=len, reverse=True))
RE_VIA_EN = re.compile(
    r"(?<![\w])(?P<num>\d{1,6}[A-Za-z]?(?:-\d{1,4})?)[ \t]+(?:(?P<dir>N|S|E|W|NE|NW|SE|SW|North|South|East|West)\.?[ \t]+)?"
    r"(?P<via>(?:(?:[" + _UP + r"0-9][\w'.-]*|de|del|la|of|y|on|upon)[ \t]+){0,3}?[" + _UP + r"][\w'.-]*)(?:[ \t]+|[ \t]*\n[ \t]*)(?P<suf>" + _SUFFISSI + r"|Mall|Gate)\.?(?![\w])")
RE_VIA_EN_SENZA_NUM = re.compile(
    r"(?<![\w])(?P<via>[" + _UP + r"][\w'.-]+(?:[ \t][" + _UP + r"][\w'.-]+){0,2})[ \t]+(?P<suf>Street|Road|Avenue|Lane|Drive|Close|Crescent|Gardens|Grove|Terrace|Way|Place|Square|Mews|Boulevard)(?![\w])")
RE_CITTA_EN_CTX = re.compile(r"(?i:\b(?:born\s+in|resident\s+(?:of|in)|residing\s+(?:at|in)|lives\s+in|living\s+in|moved\s+to|"
                             r"relocated\s+to|located\s+in|situated\s+in|town\s+of|city\s+of|village\s+of|county\s+of|hometown))\s+"
                             r"(?P<citta>[" + _UP + r"][\w'.-]+(?:[ \t][" + _UP + r"][\w'.-]+){0,2})")
_CITTA_NOTE = {norm(c[0]) for c in E.US_CITIES + E.UK_TOWNS}
RE_CITTA_NOTA = re.compile(r"(?<![\w])(?:" + "|".join(sorted((re.escape(c[0]) for c in E.US_CITIES + E.UK_TOWNS), key=len, reverse=True)) + r")(?![\w])")


def trova_schemi_en(testo: str) -> list[Span]:
    out: list[Span] = []
    add = out.append
    for rx, tipo, cmin in CONTESTI:
        for m in rx.finditer(testo):
            v = m.group("v").rstrip(".-/ ")
            cifre = sum(c.isdigit() for c in v)
            if tipo == "CATASTO" and not cifre and not re.fullmatch(r"[A-Z]{1,2}", v):
                continue  # «Block C», «Lot 12»; non «Lot OF»
            if cifre < cmin or re.fullmatch(r"(?:19|20)\d\d", v):
                continue
            if tipo != "SORTCODE" and re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", v):
                continue
            if " " in v:  # «ABC D12 was…»: solo gruppi brevi con almeno una cifra
                pezzi = v.split()
                while len(pezzi) > 1 and not re.search(r"\d", pezzi[-1]) and len(pezzi[-1]) > 3:
                    pezzi.pop()
                v = " ".join(pezzi)
            add(Span(m.start("v"), m.start("v") + len(v), tipo, v, 0.9))
    for m in RE_SSN.finditer(testo):
        add(Span(m.start(), m.end(), "SSN", m.group(0), 0.95))
    for m in RE_ITIN.finditer(testo):
        add(Span(m.start(), m.end(), "ITIN", m.group(0), 0.97))
    for m in RE_NINO.finditer(testo):
        add(Span(m.start(), m.end(), "NINO", m.group(0), 0.95))
    for m in RE_NHS.finditer(testo):
        vicino = testo[max(0, m.start() - 60):m.end()]
        if nhs_valido(m.group(0)) and (re.search(r"(?i)nhs|chi\s+number|health\s+(?:and\s+care\s+)?number", vicino)
                                       or (re.fullmatch(r"\d{3} \d{3} \d{4}", m.group(0)) and not RE_TEL_US.search(vicino[-len(m.group(0)) - 6:]))):
            add(Span(m.start(), m.end(), "NHS", m.group(0), 0.9))
    for m in RE_ABA.finditer(testo):
        if aba_valido(m.group(0)) and re.search(r"(?i)routing|aba|rtn|transit|wire|bank", testo[max(0, m.start() - 60):m.start()]):
            add(Span(m.start(), m.end(), "ROUTING", m.group(0), 0.95))
    for m in RE_UK_LICENCE.finditer(testo):
        add(Span(m.start(), m.end(), "PATENTE", m.group(0), 0.9))
    for m in RE_VIN.finditer(testo):
        add(Span(m.start(), m.end(), "VIN", m.group(0), 0.85))
    for m in RE_UK_REG.finditer(testo):
        add(Span(m.start(), m.end(), "TARGA", m.group(0), 0.7))
    for rx in (RE_TEL_US, RE_TEL_UK):
        for m in rx.finditer(testo):
            if 10 <= len(re.sub(r"\D", "", m.group(0))) <= 13:
                add(Span(m.start(), m.end(), "TELEFONO", m.group(0), 0.9, {"en": True}))
    for m in RE_ZIP_STATO.finditer(testo):
        add(Span(m.start("zip"), m.end("zip"), "CAP", m.group("zip"), 0.95))
        c = m.group("citta")
        parole = c.split()
        while parole and norm(parole[0]) in E.COMMON_WORDS:
            parole.pop(0)
        if parole:
            cc = " ".join(parole)
            a = m.end("citta") - len(cc)
            add(Span(a, m.end("stato"), "CITTA", testo[a:m.end("stato")], 0.9, {"citta": cc, "stato": m.group("stato")}))
    for m in RE_CITTA_STATO.finditer(testo):  # «of Lubbock, TX,» senza ZIP
        parole = m.group("citta").split()
        while parole and norm(parole[0]) in E.COMMON_WORDS:
            parole.pop(0)
        if parole:
            cc = " ".join(parole)
            a = m.end("citta") - len(cc)
            add(Span(a, m.end("stato"), "CITTA", testo[a:m.end("stato")], 0.85, {"citta": cc, "stato": m.group("stato")}))
    for m in RE_ZIP_CTX.finditer(testo):
        add(Span(m.start("zip"), m.end("zip"), "CAP", m.group("zip"), 0.95))
    for m in RE_POSTCODE.finditer(testo):
        add(Span(m.start(), m.end(), "CAP", m.group(0), 0.85))
    for m in RE_CITTA_POSTCODE.finditer(testo):
        c = m.group("citta").strip()
        parole = c.split()
        while parole and (norm(parole[0]) in E.COMMON_WORDS or parole[0][0].islower()):
            parole.pop(0)
        if parole and not re.search(r"\d", " ".join(parole)):
            cc = " ".join(parole)
            a = m.start("citta") + m.group("citta").rfind(cc)
            add(Span(a, a + len(cc), "CITTA", cc, 0.8))
    for m in RE_VIA_EN.finditer(testo):
        via = m.group("via")
        if norm(via.split()[0]) in ("the", "and", "of", "per", "for"):
            continue
        meta = {"via": via, "via_inizio": m.start("via"), "via_fine": m.end("via"), "civ": m.group("num"),
                "civ_inizio": m.start("num"), "civ_fine": m.end("num"), "pref": "", "en": True}
        add(Span(m.start(), m.end(), "INDIRIZZO", m.group(0), 0.95, meta))
        dopo = re.match(r"(?:,?[ \t]*(?:Apt|Apartment|Suite|Ste|Unit|Flat|Fl|#)\.?[ \t]*[\w-]+)?,?[ \t]*(?:\n[ \t]*)?(?P<c>[" + _UP +
                        r"][\w'.-]+(?:[ \t][" + _UP + r"][\w'.-]+){0,2})", testo[m.end():])
        if dopo and norm(dopo.group("c").split()[0]) not in E.COMMON_WORDS and not RE_POSTCODE.fullmatch(dopo.group("c")):
            a = m.end() + dopo.start("c")
            add(Span(a, a + len(dopo.group("c")), "CITTA", dopo.group("c"), 0.8))
    for m in RE_VIA_EN_SENZA_NUM.finditer(testo):
        via = m.group("via")
        parole = via.split()
        while parole and norm(parole[0]) in E.COMMON_WORDS:
            parole.pop(0)
        if not parole:
            continue
        via = " ".join(parole)
        a = m.end("via") - len(via)
        meta = {"via": via, "via_inizio": a, "via_fine": m.end("via"), "pref": "", "en": True}
        add(Span(a, m.end(), "INDIRIZZO", testo[a:m.end()], 0.85, meta))
    for m in RE_CITTA_EN_CTX.finditer(testo):
        c = m.group("citta")
        if norm(c.split()[0]) not in E.COMMON_WORDS:
            add(Span(m.start("citta"), m.end("citta"), "CITTA", c, 0.85))
    for m in RE_CITTA_NOTA.finditer(testo):
        add(Span(m.start(), m.end(), "CITTA", m.group(0), 0.75))
    out += luoghi_da_dizionario(testo)
    out += luoghi_gb_ufficiali(testo)
    return out


RE_SEQ_MAIUSCOLE = re.compile(r"(?<![\w'’-])[" + _UP + r"][\w'’.-]*(?:[ \t](?:[" + _UP + r"][\w'’.-]*|(?:upon|on|in|le|de|la|of|a|y|na|nan|an)(?=[ \t][" + _UP + r"])))*")
_STATI = {norm(x) for x in E.US_STATES.values()} | {"england", "scotland", "wales", "northern ireland", "britain", "ireland"}
from .prefiltro import LESSICO as _LESSICO_IT  # noqa: E402
RE_PREP_LUOGO = re.compile(r"(?i)\b(?:in|at|from|near|of|to|outside|around|toward|towards|between|via)\s+$")


def luoghi_da_dizionario(testo: str) -> list[Span]:
    """Città e quartieri US/UK del dizionario. Più parole («Newton Aycliffe») bastano da sole; una parola sola vale se non
    è una parola comune, un nome o una voce ambigua, oppure se c'è una preposizione di luogo davanti («in Reading»)."""
    out = []
    for m in RE_SEQ_MAIUSCOLE.finditer(testo):
        pos = [(x.start() + m.start(), x.end() + m.start()) for x in re.finditer(r"\S+", m.group(0))]
        parole = m.group(0).split()
        i = 0
        while i < len(parole):
            preso = 0
            for k in range(min(4, len(parole) - i), 0, -1):
                cand = " ".join(parole[i:i + k]).rstrip(".,")
                n = norm(cand)
                if n not in E.LUOGHI_EN or n in _STATI or n in _LESSICO_IT:
                    continue
                vicine = parole[i - 1:i] + parole[i + k:i + k + 1]  # «Riverside Housing», «Hotel Bellevue»: nomi di enti
                if any(norm(w.rstrip(".,")) in E.COMMON_WORDS for w in vicine):
                    continue
                inizio = pos[i][0]
                cand = testo[inizio:pos[i + k - 1][1]].rstrip(".,")
                if k == 1:
                    ambiguo = (n in E.AMBIGUI_LUOGHI_EN or n in E.COMMON_WORDS or n in NOMI_BASE or n in COGNOMI_BASE
                               or len(n) < 4 or cand.isupper())
                    if ambiguo and not RE_PREP_LUOGO.search(testo[max(0, inizio - 12):inizio]):
                        continue
                out.append(Span(inizio, inizio + len(cand), "CITTA", cand, 0.75))
                preso = k
                break
            i += preso or 1
    return out


RE_POSTCODE_DOPO = re.compile(r"[ \t]*,?[ \t]*(?:[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]?\s?\d[ABD-HJLNP-UW-Z]{2})(?![A-Z0-9])")
RE_CONTESTO_GB = re.compile(r"(?i)(?:\b(?:in|at|near|from|of|outside|village\s+of|parish\s+of|hamlet\s+of|lives\s+in|born\s+in)\s+|,\s*)$")
RE_CASA_UK = re.compile(r"(?<![\w])(?P<via>(?:The[ \t]+)?(?:Old|[A-Z][\w'’-]+)(?:[ \t][A-Z][\w'’-]+)?)[ \t]+"
                        r"(?P<suf>Cottage|Cottages|Farm|Farmhouse|Barn|Rectory|Vicarage|Manse|Croft|Steading|Bungalow|Ranch|Forge|Smithy)"
                        r"(?![\w])(?=[ \t]*,|[ \t]*\n)")
RE_VIA_GB_RIGA = re.compile(r"(?m)(?:^|(?<=, )|(?<=: ))[ \t]*(?P<via>[A-Z][\w'’-]+(?:[ \t](?:[A-Z][\w'’-]+|y|yr|an|na|of|on|le))*)"
                            r"(?=,[ \t]*[A-Z][\w'’ -]{2,40}?(?:,[ \t]*[A-Z][\w'’ -]{2,30}?)?[ \t]+[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]?\s?\d[ABD-HJLNP-UW-Z]{2}(?![A-Z0-9]))")
RE_CONTEA_US = re.compile(r"(?<![\w])(?P<n>[A-Z][\w'’-]+(?:[ \t][A-Z][\w'’-]+){0,2})(?=[ \t]+(?:County|Parish|Township|Reservation|Chapter|District)\b)")
TITOLI_NORM = {"mr", "mrs", "ms", "miss", "dr", "prof", "rev", "sir", "dame", "lady", "lord", "cllr", "capt"}
RE_RIGA_CASA = re.compile(r"(?m)^[ \t]*(?P<via>(?:The[ \t]+)?[A-Z][\w'’-]+(?:[ \t](?:y|yr|an|na|[A-Z][\w'’-]+)){0,3})[ \t]*,?[ \t]*\n"
                          r"(?=(?:[^\n]*\n)?[^\n]*[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]?\s?\d[ABD-HJLNP-UW-Z]{2}[ \t]*$)")
RE_RURALE_US = re.compile(r"(?<![\w])(?:(?:\d{1,5}\s+)?(?P<via>(?:RR|R\.R\.|Rural\s+Route|HC|Star\s+Route|PO\s+Box|P\.O\.\s+Box|"
                          r"County\s+Road|Co\.\s+Rd\.?|CR|FM|RM|Hwy|Highway|State\s+Highway|Navajo\s+Route|BIA\s+Route|Road)\s+[A-Z]?-?\d{1,5}[A-Z]?(?:-\d{1,3})?)"
                          r"(?:,?\s+Box\s+(?P<civ>\d{1,5}))?)(?![\w-])")
RE_CROFT_NUM = re.compile(r"(?<![\w])(?P<via>Croft)[ \t]+(?P<civ>\d{1,3}[A-Za-z]?)(?=[ \t]*,)")
RE_VIA_GB_NUDA = re.compile(r"(?<![\w,/-])(?P<num>\d{1,4}[A-Za-z]?)[ \t]+(?P<via>[A-Z][\w'’-]+(?:[ \t](?:[A-Z][\w'’-]+|y|yr|an|na|of|on|le))*)(?=[ \t]*,)")


def luoghi_gb_ufficiali(testo: str) -> list[Span]:
    """0.6.0, OS Open Names: villaggi e frazioni britanniche solo con contesto (preposizione o virgola davanti E postcode,
    contea o fine riga dopo; oppure postcode subito dopo); vie senza suffisso solo con il civico e la virgola («8
    Deansgate,»); nomi di case e fattorie solo in un indirizzo («Rose Cottage,», «Croft 7,»)."""
    out = []
    for m in RE_SEQ_MAIUSCOLE.finditer(testo):
        parole = m.group(0).split()
        for k in range(min(4, len(parole)), 0, -1):
            cand = " ".join(parole[-k:]).rstrip(".,")
            n = norm(cand)
            if n not in E.LUOGHI_GB_UFF or n in _STATI or n in _LESSICO_IT or n in E.COMMON_WORDS:
                continue
            fine = m.end() - (len(m.group(0)) - len(m.group(0).rstrip(".,")))
            inizio = fine - len(cand)
            dopo_pc = RE_POSTCODE_DOPO.match(testo, fine)
            davanti = RE_CONTESTO_GB.search(testo[max(0, inizio - 20):inizio])
            dopo_ok = re.match(r"[ \t]*(?:[,.;)]|\n|$)", testo[fine:fine + 3]) or (k > 1 and davanti)
            dopo_pc = dopo_pc or re.match(r"[ \t]*,[ \t]*[A-Z][\w'’-]+(?:[ \t][A-Z][\w'’-]+)?" + RE_POSTCODE_DOPO.pattern, testo[fine:fine + 60])
            if k == 1 and (n in NOMI_BASE or n in COGNOMI_BASE or n in _PAROLE_COMUNI or len(n) < 4) and not dopo_pc:
                continue
            if dopo_pc or (davanti and dopo_ok):
                out.append(Span(inizio, fine, "CITTA", testo[inizio:fine], 0.7))
            break
    for m in RE_VIA_GB_NUDA.finditer(testo):
        via = m.group("via")
        if norm(via) in E.VIE_GB_UFF and norm(via) not in E.COMMON_WORDS:
            meta = {"via": via, "via_inizio": m.start("via"), "via_fine": m.end("via"), "civ": m.group("num"),
                    "civ_inizio": m.start("num"), "civ_fine": m.end("num"), "pref": "", "en": True}
            out.append(Span(m.start(), m.end(), "INDIRIZZO", m.group(0), 0.85, meta))
    for m in RE_VIA_GB_RIGA.finditer(testo):
        via = m.group("via")
        if norm(via) in E.VIE_GB_UFF and norm(via) not in E.COMMON_WORDS and norm(via) not in E.LUOGHI_GB_UFF:
            meta = {"via": via, "via_inizio": m.start("via"), "via_fine": m.end("via"), "pref": "", "en": True}
            out.append(Span(m.start("via"), m.end("via"), "INDIRIZZO", via, 0.75, meta))
    for m in RE_CASA_UK.finditer(testo):
        via = m.group("via")
        parole = [w for w in via.split() if w not in ("The", "Old")] or via.split()[-1:]
        if all(norm(w) in E.COMMON_WORDS for w in parole) and not via.startswith(("The", "Old")):
            continue
        dopo = testo[m.end():m.end() + 120]
        if not (RE_POSTCODE.search(dopo) or RE_ZIP_STATO.search(dopo) or re.search(r"\d{1,4}[ \t]+[A-Z][\w'’-]+[ \t]+(?:Road|Street|Lane|Avenue|Drive|Close|Way)", dopo)
                or any(norm(w.strip(",")) in E.LUOGHI_GB_UFF | E.LUOGHI_EN for w in re.findall(r"[A-Z][\w'’-]+", dopo[:60]))):
            continue
        a = m.start("via") + via.find(parole[0])
        meta = {"via": testo[a:m.end("via")], "via_inizio": a, "via_fine": m.end("via"), "pref": "", "en": True}
        out.append(Span(a, m.end(), "INDIRIZZO", testo[a:m.end()], 0.8, meta))
    for m in RE_CONTEA_US.finditer(testo):
        nome = m.group("n")
        if all(norm(w) in E.COMMON_WORDS or norm(w) in _PAROLE_COMUNI for w in nome.split()):
            continue
        out.append(Span(m.start("n"), m.end("n"), "CITTA", nome, 0.8))
    for m in RE_RIGA_CASA.finditer(testo):  # «Ty Gwyn» / «Pen y Bryn» su una riga, poi località e postcode
        via = m.group("via").strip()
        parole = [w for w in via.split() if w[:1].isupper()]
        if (not parole or any(norm(w) in NOMI_BASE or norm(w) in TITOLI_NORM for w in parole) or norm(via) in E.LUOGHI_GB_UFF
                or norm(via) in E.LUOGHI_EN or all(norm(w) in E.COMMON_WORDS or norm(w) in _PAROLE_COMUNI for w in parole)):
            continue
        a = m.start("via")
        meta = {"via": via, "via_inizio": a, "via_fine": a + len(via), "pref": "", "en": True}
        out.append(Span(a, a + len(via), "INDIRIZZO", via, 0.75, meta))
    for m in RE_RURALE_US.finditer(testo):  # «RR 2 Box 14», «HC 49 Box 33», «PO Box 118», «County Road 1150», «FM 2093»
        # si cambiano solo le cifre («RR 7 Box 53»), come un codice: le parole restano e il ritorno è esatto
        out.append(Span(m.start(), m.end(), "PRATICA", m.group(0), 0.9))
    for m in RE_CROFT_NUM.finditer(testo):
        meta = {"via": m.group("via"), "via_inizio": m.start("via"), "via_fine": m.end("via"), "civ": m.group("civ"),
                "civ_inizio": m.start("civ"), "civ_fine": m.end("civ"), "pref": "", "en": True}
        out.append(Span(m.start(), m.end(), "INDIRIZZO", m.group(0), 0.8, meta))
    return out


# ------------------------------------------------------------------ people
from .prefiltro import LESSICO as _LESSICO  # noqa: E402

_FILTRO = _LESSICO | E.COMMON_WORDS | E.TITOLI_EN
NOMI_BASE = {norm(x) for x in E.FIRST_M + E.FIRST_F}
COGNOMI_BASE = {norm(x) for x in E.SURNAMES}
from .prefiltro import PAROLE_COMUNI as _PAROLE_COMUNI  # noqa: E402
NOMI = NOMI_BASE | {x for x in E.nomi_primi() if len(x) >= 3 and x not in _FILTRO}
NOMI |= {x for x in E.NOMI_UFF_M | E.NOMI_UFF_F if len(x) >= 3 and x not in _FILTRO and x not in _PAROLE_COMUNI}
COGNOMI = COGNOMI_BASE | {x for x in E.cognomi() if len(x) >= 3 and x not in _FILTRO}
COGNOMI |= {x for x in E.COGNOMI_UFF if len(x) >= 3 and x not in _FILTRO and x not in _PAROLE_COMUNI}
TITOLI = r"(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof|Professor|Sir|Dame|Lord|Lady|Rev|Reverend|Hon|Judge|Justice|Officer|Sgt|Sergeant|Det|Detective|Capt|Captain|Lt|Nurse|Dr\.|Atty|Attorney|Counsel)\.?"
RE_TITOLO = re.compile(r"(?<![\w.])" + TITOLI + r"\s+")
RE_INDIZIO = re.compile(r"(?i:\b(?:dear|hi|hello|attn|attention|patient|claimant|plaintiff|defendant|tenant|landlord|lessee|lessor|"
                        r"employee|employer|applicant|policyholder|insured|driver|witness|beneficiary|guarantor|borrower|co-borrower|"
                        r"spouse|husband|wife|son|daughter|mother|father|brother|sister|guardian|parent|child|student|pupil|"
                        r"signed|signature|sincerely|regards|thanks|cc|from|to|by|prepared\s+by|approved\s+by|reviewed\s+by|"
                        r"attending|physician|surgeon|consultant|gp|nurse|caseworker|adjuster|agent|officer|manager|supervisor|"
                        r"solicitor|counsel|attorney|landlady|owner|proprietor|residents?|guests?|members?|attendees?|occupant|deceased|testator|executor|"
                        r"president|vice\s+president|treasurer|secretary|chair(?:man|woman|person)?|director|trustee|notary|"
                        r"paralegal|banker|deputy|sergeant|inspector|constable|teacher|headteacher|principal|coach|therapist|"
                        r"midwife|carer|caregiver|neighbou?r|friend|colleague|partner|fianc[ée]e?|boyfriend|girlfriend|member|"
                        r"homeowner|seller|buyer|purchaser|vendor|lender|representative|advis[eo]r|accountant|broker|realtor|"
                        r"technician|contractor|plumber|electrician|engineer|appraiser|assessor|clerk|registrar|receptionist|"
                        r"dispatcher|paramedic|doctor|dentist|pharmacist|psychologist|psychiatrist|social\s+worker|"
                        r"case\s+manager|interpreter|translator|named|called|aka|a\.k\.a\.|known\s+as|nicknamed|goes\s+by))"
                        r"\b[\s:,]+(?:" + TITOLI + r"\s+)?")
RE_ETICHETTA = re.compile(r"(?im)(?:^|(?<=  )|(?<=\t))[ \t]*(?:full\s+name|name|patient(?:\s+name)?|first\s+name|forename\(?s?\)?|given\s+name|middle(?:\s+name)?|"
                          r"preferred\s+name(?:\s*/\s*nickname)?|nickname|known\s+as|"
                          r"last\s+name|surname|family\s+name|employee(?:\s+name)?|tenant\(?s?\)?|landlord|applicant|insured|policyholder|"
                          r"claimant|driver|witness|emergency\s+contact|next\s+of\s+kin|account\s+holder|cardholder|borrower|"
                          r"co-borrower|guarantor|beneficiary|owner|proprietor\(?s?\)?|from|to|cc|attn)[ \t]*[:\t][ \t]*")
_PARTICELLE = r"(?:O'|O’|Mc|Mac|Fitz|De\s+La\s+|De\s+|Del\s+|Van\s+der\s+|Van\s+|Von\s+|Le\s+|La\s+|Da\s+|Di\s+|St\.?\s+|ap\s+|bin\s+|al-|el-)"
PAROLA_EN = re.compile(r"(?:" + _PARTICELLE + r")?(?:[" + _UP + r"][" + _LO + r"]+(?:['’][" + _UP + r"][" + _LO + r"]+)?|[" + _UP + r"]{2,}(?:['’][" + _UP + r"]+)?)"
                       r"(?:-[" + _UP + r"][" + _LO + r"]+|-[" + _UP + r"]{2,}|-[" + _LO + r"]{2,})?(?![\w])")
RE_INIZIALE = re.compile(r"[" + _UP + r"]\.")
RE_PRESENTI = re.compile(r"(?im)^[ \t]*(?:present|absent|attendees|attendance|in\s+attendance|apologies|also\s+present|"
                         r"members\s+present|directors\s+present|parties|signatories|copied|distribution)[ \t]*:[ \t]*")
RE_RUOLO_INIZIO = re.compile(r"[ \t]*(?:and[ \t]+)?(?:(?i:vice[ \t]+)?(?i:president|treasurer|secretary|chair(?:man|woman|person)?|director|"
                             r"trustee|member|manager|officer|clerk|councillor|councilor|cllr|mayor|governor)\.?[ \t]+)*"
                             r"(?:" + TITOLI + r"[ \t]+)?")


def _comune(w: str) -> bool:
    n = norm(w).strip(".")
    return n in E.COMMON_WORDS


def leggi_parole_en(testo: str, pos: int, massimo: int = 4) -> list:
    parole, i = [], pos
    while len(parole) < massimo:
        m = PAROLA_EN.match(testo, i)
        if not m:
            mi = RE_INIZIALE.match(testo, i)  # iniziale in mezzo: «John R. Smith»
            if mi:
                sp = re.match(r"[ \t]{1,2}", testo[mi.end():])
                if sp:
                    i = mi.end() + sp.end()
                    continue
            break
        w = m.group(0)
        if _comune(w):
            break
        parole.append((m.start(), m.end(), w))
        sp = re.match(r"[ \t]{1,2}", testo[m.end():])
        if not sp:
            break
        i = m.end() + sp.end()
    return parole


def _inizio_frase(testo: str, i: int) -> bool:
    prima = testo[max(0, i - 4):i]
    return i == 0 or bool(re.search(r"(?:[.!?:;\n\"(]\s*|^\s*)$", prima))


def candidati_persone_en(testo: str) -> list[PersonaCandidata]:
    out: list[PersonaCandidata] = []

    def aggiungi(parole, fonte, conf, genere=None):
        if parole and len(parole) >= 2 and fonte in ("dictionary", "cue") and norm(" ".join(p[2] for p in parole)) in E.LUOGHI_EN:
            return  # «San Jose», «Santa Monica»: un luogo, non una persona
        if parole:
            out.append(PersonaCandidata(parole[0][0], parole[-1][1], parole, genere, conf, fonte))

    for m in RE_TITOLO.finditer(testo):
        t = m.group(0).strip().rstrip(".").lower()
        g = "F" if t in ("mrs", "ms", "miss", "dame", "lady") else "M" if t in ("mr", "sir", "lord") else None
        aggiungi(leggi_parole_en(testo, m.end()), "title", 0.95, g)
    for m in RE_INDIZIO.finditer(testo):
        parole = leggi_parole_en(testo, m.end(), 3)
        if parole and (len(parole) >= 2 or any(norm(p[2]) in NOMI or norm(p[2]) in COGNOMI for p in parole)):
            aggiungi(parole, "cue", 0.9)
    for m in RE_ETICHETTA.finditer(testo):
        aggiungi(leggi_parole_en(testo, m.end(), 4), "label", 0.9)
    # elenchi di presenti: «Present: President Walter Price; Vice President Dolores Hernandez-Ortiz; …»
    for m in RE_PRESENTI.finditer(testo):
        fine = testo.find("\n\n", m.end())
        fine = len(testo) if fine < 0 else min(fine, m.end() + 600)
        for pezzo in re.finditer(r"[^;,\n]+", testo[m.end():fine]):
            a = m.end() + pezzo.start()
            ruolo = RE_RUOLO_INIZIO.match(testo, a)
            if ruolo:
                a = ruolo.end()
            parole = leggi_parole_en(testo, a, 4)
            if len(parole) >= 2 or (parole and (norm(parole[0][2]) in NOMI or norm(parole[0][2]) in COGNOMI)):
                aggiungi(parole, "label", 0.85)
    # «SMITH, John», «O'CONNOR, Declan Seamus», «Name: Young, Terrence»
    for m in re.finditer(r"(?<![\w])(?P<c>(?:" + _PARTICELLE + r")?[" + _UP + r"][\w'’-]+),[ \t]+(?=[" + _UP + r"])", testo):
        nomi = leggi_parole_en(testo, m.end(), 3)
        if not nomi or _comune(m.group("c")):
            continue
        prima = testo[max(0, m.start() - 40):m.start()]
        etichetta = bool(re.search(r"(?i)(?:name|patient|client|tenant|employee|applicant|insured|claimant|driver|witness|suspect|"
                                   r"victim|subject|defendant|plaintiff|deceased|student|member)\s*:?[ \t]*$", prima))
        maiuscolo = m.group("c").isupper() and len(m.group("c")) > 2
        if etichetta or maiuscolo or norm(nomi[0][2]) in NOMI:
            aggiungi([(m.start("c"), m.end("c"), m.group("c"))] + nomi, "last-first", 0.9)
    # dizionario: nome di battesimo seguito da una parola maiuscola
    for m in PAROLA_EN.finditer(testo):
        w = m.group(0)
        n = norm(w)
        if n in NOMI and not _comune(w):
            dopo = leggi_parole_en(testo, m.end() + 1, 3) if testo[m.end():m.end() + 1] == " " else []
            if dopo:
                aggiungi([(m.start(), m.end(), w)] + dopo, "dictionary", 0.85)
            elif n in NOMI_BASE and (not _inizio_frase(testo, m.start()) or re.match(r"[ \t]*[,:]", testo[m.end():])):
                aggiungi([(m.start(), m.end(), w)], "first-name", 0.7)
        elif n in COGNOMI_BASE and n not in E.SURNAME_WORDS and not _comune(w) and not _inizio_frase(testo, m.start()):
            aggiungi([(m.start(), m.end(), w)], "surname", 0.75)
    return out


def ruoli_en(parole: list) -> list[tuple]:
    """«John R. Smith» → nome, cognome; «SMITH, John» (via last-first) → cognome, nome."""
    if not parole:
        return []
    if len(parole) == 1:
        return [("nome" if norm(parole[0][2]) in NOMI and norm(parole[0][2]) not in COGNOMI else "cognome", parole[0][0], parole[0][1], None)]
    tipi = ["nome"] * (len(parole) - 1) + ["cognome"]
    if parole[0][2].isupper() and not parole[-1][2].isupper():
        tipi = ["cognome"] + ["nome"] * (len(parole) - 1)
    elif norm(parole[0][2]) not in NOMI and norm(parole[-1][2]) in NOMI:
        tipi = ["cognome"] + ["nome"] * (len(parole) - 1)
    return [(t, a, b, None) for t, (a, b, _) in zip(tipi, parole)]


# ------------------------------------------------------------------ generators
def finto_ssn(rng) -> str:
    while True:
        a = rng.randint(1, 899)
        if a != 666:
            return f"{a:03d}{rng.randint(1, 99):02d}{rng.randint(1, 9999):04d}"


def finto_itin(rng) -> str:
    m = rng.choice([x for x in range(50, 100) if itin_valido("900" + f"{x:02d}" + "0000")])
    return f"9{rng.randint(0, 99):02d}{m:02d}{rng.randint(0, 9999):04d}"


def finto_nino(rng) -> str:
    primi = "ABCEGHJKLMNOPRSTWXYZ"
    secondi = "ABCEGHJKLMNPRSTWXYZ"
    while True:
        p = rng.choice(primi) + rng.choice(secondi)
        if p not in ("BG", "GB", "NK", "KN", "TN", "NT", "ZZ"):
            return p + "".join(rng.choice("0123456789") for _ in range(6)) + rng.choice("ABCD")


def finto_nhs(rng) -> str:
    while True:
        nove = "".join(rng.choice("0123456789") for _ in range(9))
        c = nhs_controllo(nove)
        if c is not None:
            return nove + str(c)


def finto_aba(rng) -> str:
    otto = f"{rng.choice([0, 1, 2, 3, 6, 7, 8]) * 10 + rng.randint(1, 2):02d}" + "".join(rng.choice("0123456789") for _ in range(6))
    return otto + aba_controllo(otto)


def finta_citta(rng, uk: bool, escludi: set) -> tuple:
    pool = [c for c in (E.UK_TOWNS if uk else E.US_CITIES) if c[0] not in escludi]
    if pool:
        return rng.choice(pool)
    # elenco breve esaurito (sessioni lunghe): i luoghi del dizionario, con il codice postale di una città vicina
    base = E.UK_TOWNS if uk else E.US_CITIES
    for _ in range(50):
        nome, zona = rng.choice(E.LUOGHI_UK if uk else E.LUOGHI_US)
        if nome not in escludi:
            vicine = [c for c in base if c[1] == zona] or base
            return (nome, zona, rng.choice(vicine)[2])
    return rng.choice(base)


def trova_telefoni_esteri(testo: str) -> list[Span]:
    out = []
    for rx in (RE_TEL_US, RE_TEL_UK):
        for m in rx.finditer(testo):
            if m.group(0).lstrip().startswith(("+1", "+44", "0044")) and 10 <= len(re.sub(r"\D", "", m.group(0))) <= 13:
                out.append(Span(m.start(), m.end(), "TELEFONO", m.group(0), 0.9, {"en": True}))
    return out


RE_SUFFISSO_FORTE = re.compile(r"(?:Street|Road|Avenue|Lane|Drive|Close|Crescent|Gardens|Grove|Terrace|Way|Place|Square|Boulevard|Mall)")


def indirizzi_esteri(testo: str) -> list[Span]:
    """In un testo italiano: «14 Egerton Road, Manchester M14 6RH», «1175 Ponce de Leon Avenue NE»."""
    out = []
    for m in RE_VIA_EN.finditer(testo):
        via = m.group("via")
        if not RE_SUFFISSO_FORTE.fullmatch(m.group("suf")) or norm(via.split()[0]) in ("the", "and", "of", "per", "for"):
            continue
        meta = {"via": via, "via_inizio": m.start("via"), "via_fine": m.end("via"), "civ": m.group("num"),
                "civ_inizio": m.start("num"), "civ_fine": m.end("num"), "pref": "", "en": True}
        out.append(Span(m.start(), m.end(), "INDIRIZZO", m.group(0), 0.95, meta))
    for m in RE_CITTA_POSTCODE.finditer(testo):
        c = m.group("citta").strip().split()[-1]
        if c[:1].isupper() and norm(c) not in E.COMMON_WORDS:
            a = m.start("citta") + m.group("citta").rfind(c)
            out.append(Span(a, a + len(c), "CITTA", c, 0.8))
        out.append(Span(m.start("pc"), m.end("pc"), "CAP", m.group("pc"), 0.85))
    out += [x for x in luoghi_gb_ufficiali(testo) if x.tipo != "PRATICA"]  # vie e case britanniche (0.6.0)
    return out


def paese(testo: str) -> str:
    """«UK» o «US» per i dati finti (città, CAP, telefoni) di un documento inglese."""
    from .date import RE_UK, RE_US
    return "UK" if len(RE_UK.findall(testo)) > len(RE_US.findall(testo)) else "US"


def finto_tel_en(rng, originale: str) -> str | None:
    """Numero finto nelle serie riservate alla finzione (US 555-01xx, UK 07700 900xxx / 020 7946 0xxx / 0113 496 0xxx).
    Restituisce tutte le cifre (prefisso internazionale compreso) o None se il numero non è US/UK."""
    c = re.sub(r"\D", "", originale)
    s = originale.strip()
    if s.startswith("+44") or s.startswith("0044") or (c.startswith("0") and 10 <= len(c) <= 12 and not c.startswith("00")):
        pre = c[:2] if s.startswith("+44") else c[:4] if s.startswith("0044") else ""
        naz = "0" + c[len(pre):] if pre else c
        if naz.startswith("07"):
            f = "07700900" + "".join(rng.choice("0123456789") for _ in range(3))
        elif naz.startswith("020"):
            f = "02079460" + "".join(rng.choice("0123456789") for _ in range(3))
        else:
            f = "01134960" + "".join(rng.choice("0123456789") for _ in range(3))
        f = f[:len(naz)].ljust(len(naz), "0")
        return pre + (f[1:] if pre else f)
    if s.startswith("+1") or len(c) == 10 or (len(c) == 11 and c.startswith("1")):
        pre = c[:-10]
        area = rng.choice(["212", "312", "415", "512", "617", "702", "713", "805", "916", "305", "503", "720"])
        return pre + area + "55501" + "".join(rng.choice("0123456789") for _ in range(2))
    return None


def finto_cap_en(rng, originale: str, uk: bool) -> str:
    v = originale.strip()
    if re.fullmatch(r"\d{5}(?:-\d{4})?", v):
        z = rng.choice(E.US_CITIES)[2][:3] + "".join(rng.choice("0123456789") for _ in range(2))
        return z + ("-" + "".join(rng.choice("0123456789") for _ in range(4)) if "-" in v else "")
    out = rng.choice(E.UK_TOWNS)[2].split()[0]
    inward = rng.choice("123456789") + rng.choice("ABDEFGHJLNPQRSTUWXYZ") + rng.choice("ABDEFGHJLNPQRSTUWXYZ")
    return out + (" " if " " in v else "") + inward

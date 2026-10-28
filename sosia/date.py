"""Date in italiano e in inglese (US e UK): riconoscimento e spostamento costante che conserva la linea temporale.

Ogni sessione ha uno spostamento Δ in giorni (di norma multiplo di 7, così resta anche il giorno della settimana).
Tutte le date si spostano dello stesso Δ: ordine e intervalli restano identici. La data si riscrive componente per
componente nello stesso formato e nella stessa lingua dell'originale («10 ottobre 2026» → «14 settembre 2024»,
«March 4th, 2025» → «February 26th, 2024», «04/03/2025» resta nell'ordine del documento: giorno/mese per l'Italia e il
Regno Unito, mese/giorno per gli Stati Uniti). La convenzione si sceglie per documento (vedi `convenzione_date`).
"""
from __future__ import annotations

import calendar
import datetime as dt
import re

from .intervalli import Intervalli
from dataclasses import dataclass, field

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
        "novembre", "dicembre"]
ABBR = {"gen": 1, "genn": 1, "feb": 2, "febb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7, "ago": 8,
        "set": 9, "sett": 9, "ott": 10, "nov": 11, "dic": 12}
ABBR_STD = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
GIORNI_ABBR = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
MON_ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
            "oct": 10, "nov": 11, "dec": 12}
MON_STD = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAYS_ABBR = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_MESE_RE = r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|genn?\.?|febb?\.?|mar\.|apr\.?|mag\.?|giu\.?|lug\.?|ago\.?|sett?\.?|ott\.?|nov\.?|dic\.?)"
_GIORNO_RE = r"(?:luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica|lun\.?|mar\.?|mer\.?|gio\.?|ven\.?|sab\.?|dom\.?)"
_MONTH_RE = r"(?:january|february|march|april|may\.?|june|july|august|september|october|november|december|jan\.?|feb\.?|mar\.?|apr\.?|jun\.?|jul\.?|aug\.?|sept?\.?|oct\.?|nov\.?|dec\.?)"
_DAY_RE = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon\.?|tues?\.?|wed\.?|thur?s?\.?|fri\.?|sat\.?|sun\.?)"
_ORD = r"(?:st|nd|rd|th)"

RE_TESTUALE = re.compile(
    rf"(?<![\w])(?:(?P<sett>{_GIORNO_RE})(?P<sep0>,?\s+))?(?P<g>[0-3]?\d)(?P<ord>°|º)?(?P<sep1>\s+|\s*-\s*)"
    rf"(?P<m>{_MESE_RE})(?:(?P<sep2>,?\s+|\s*-\s*)(?P<a>(?:19|20)\d\d|['’]\d\d))?(?![\w])", re.I)
# inglese: «March 4, 2025», «Mar. 4th», «Tuesday, March 4, 2025»
RE_EN_MDY = re.compile(
    rf"(?<![\w])(?:(?P<sett>{_DAY_RE})(?P<sep0>,?\s+))?(?P<m>{_MONTH_RE})(?P<sep1>\s+)(?P<g>[0-3]?\d)(?P<ord>{_ORD})?(?![\d\w])"
    rf"(?:(?P<sep2>,?\s+)(?P<a>(?:19|20)\d\d))?(?![\w])", re.I)
# inglese: «4 March 2025», «4th of March, 2025», «Tuesday 4th March»
RE_EN_DMY = re.compile(
    rf"(?<![\w])(?:(?P<sett>{_DAY_RE})(?P<sep0>,?\s+(?:the\s+)?))?(?P<g>[0-3]?\d)(?P<ord>{_ORD})?(?P<sep1>\s+(?:day\s+of\s+|of\s+)?)"
    rf"(?P<m>{_MONTH_RE})(?:(?P<sep2>,?\s+)(?P<a>(?:19|20)\d\d))?(?![\w])", re.I)
RE_NUMERICA_BREVE = re.compile(r"(?<![\w/.\-:])(?:(?P<sett>" + _DAY_RE + "|" + _GIORNO_RE + r")(?P<sep0>,?\s+))?(?P<p1>[0-3]?\d)/(?P<p2>[0-3]?\d)(?![\w/]|[.\-:]\d)", re.I)
RE_FRAZIONE_PRIMA = re.compile(r"(?i)(?:quota|quote|flat|gn|soffio|ettari|ha|are|age|ratio|score|rapporto|punteggio|lotto|interno|int\.|"
                                r"scala|piano|pari\s+a|su|grado|pain|dolore|scored?|scoring|voto|valutazione|rated|rating|vas|nrs|livello|level|severity|gravità|stage|stadio|classe|sezione|parte|parti)\s*(?:di\s+)?$")
RE_CONTESTO_DATA = re.compile(r"(?i)(?:\bil|\bon|\bdal|\bal|\bdel|\bentro|\bby|\bfrom|\buntil|\bdue|\bdate|\bdata|\bgiorno|\bday|"
                              r"\bsince|\bfino\s+al|\beffective|\bstarting|\bas\s+of|\bthrough|\bthru|\bafter|\bbefore|\btill|\bto|\bdopo|\bprima\s+del|:)\s*$")
RE_FRAZIONE_DOPO = re.compile(r"(?i)[ \t]*(?:(?:of|di|del|della|dei|degli|delle|cups?|tazz\w*|dos\w*|inch\w*|ml|l|kg|g|mg|lb|oz|ore|hours|giorni|days|x)\b|%)")
# mese e anno a due cifre di una scadenza: «Scad. 08/27», «Exp 03/28»
RE_SCADENZA_MMYY = re.compile(r"(?i)(?:scad\w*|exp\w*|valid\w*|validit[àa])[^\n\d]{0,12}(?P<m>0[1-9]|1[0-2])/(?P<a>\d\d)(?![\d/])")
# anni da soli: nel dubbio sono date (non dopo «n.», «€», «art.», non prima di un'unità di misura)
RE_ANNO_NUDO = re.compile(r"(?<![\w/.,:\-#€$£°])(?P<a>19[5-9]\d|20[0-4]\d)(?![\w/\-]|[.,]\d)")
RE_NON_ANNO_DOPO = re.compile(r"(?i)[ \t]*(?:€|euro|eur\b|\$|usd|£|gbp|km|kg|mq|m2|m²|ml|mm|cm|ore\b|h\b|giorni|days|pezzi|pz|units|unit[àa]|"
                              r"persone|people|dipendenti|employees|abitanti|metri|miles|lb|lbs|%|x\b|cc\b|kw|cv\b|hp\b|sq|square|acres?|ft\b|"
                              r"residents|users|members|students|pupils|patients|units|homes|households|mailboxes|staff|workers|"
                              r"iscritti|utenti|soci|studenti|alunni|pazienti|famiglie|lavoratori|posti|copies|copie)")
RE_NON_ANNO_PRIMA = re.compile(r"(?i)(?:€|\$|£|n\.|nr\.?|no\.|#|art\.|artt\.|iso|covid|versione|version|v\.|tot\w*|importo|amount|euro|eur|usd|cap|zip)\s*[:\-]?\s*$")
# mese da solo: «a giugno», «inizio luglio», «in June», «by April»
RE_MESE_SOLO_IT_MAIUSC = re.compile(r"(?<![\w])(?P<m>Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|Settembre|Ottobre|Novembre|Dicembre|"
                                    r"GENNAIO|FEBBRAIO|MARZO|APRILE|MAGGIO|GIUGNO|LUGLIO|AGOSTO|SETTEMBRE|OTTOBRE|NOVEMBRE|DICEMBRE)(?![\w])")
RE_MESE_SOLO_IT = re.compile(r"(?<![\w])(?P<m>gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)(?![\w])")
RE_MESE_SOLO_EN = re.compile(r"(?<![\w])(?:(?:in|by|since|until|till|from|through|thru|to|and|or|of|early|late|mid|end\s+of|beginning\s+of|"
                             r"during|before|after|each|every|this|next|last|In|By|From|Since|Until|Each|Every|Last|Next|This)\s+|mid-|Mid-|\(\s*)"
                             r"(?P<m>January|February|March|April|May|June|July|August|September|October|November|December)(?![\w])")
RE_MESE_SOLO_EN_MIN = re.compile(r"(?<![\w])(?:in|by|since|until|till|from|during|before|after|each|every|next|last|early|late|mid|end\s+of)(?:\s+|-)"
                                 r"(?P<m>january|february|march|april|june|july|august|september|october|november|december)(?![\w])")
# mese seguito da una parola di conti o di calendario: «April charges», «June payroll» (non «May», che è anche un verbo)
RE_MESE_SOLO_EN2 = re.compile(r"(?<![\w])(?P<m>January|February|March|April|June|July|August|September|October|November|December)"
                              r"(?=\s+(?:charges?|payments?|bills?|billing|statements?|invoices?|rent|balance|usage|meeting|session|deadline|"
                              r"reports?|newsletter|issue|edition|cycle|installment|period|readings?|close|closing|payroll|visit|appointment|arrears|fees|dues|"
                              r"renewal|premium|contribution|deposit|transfer|shipment|order|class|term|semester)\b)")
# parole relative, trasformate in data assoluta solo se la data del documento è nota
RE_PAROLA_RELATIVA = re.compile(
    r"(?i)(?<![\w])(?:(?P<p>ieri|domani|dopodomani|l['’]altro\s*ieri|altroieri|yesterday|tomorrow)|"
    r"(?P<sett>luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)['’]?\s+(?P<dir>scors[oa]|prossim[oa])|"
    r"(?P<dir2>last|next)\s+(?P<sett2>monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"(?P<n>a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})\s+(?P<u>days?|weeks?|fortnights?|months?)\s+ago|"
    r"(?P<n2>un|una|due|tre|quattro|cinque|sei|sette|otto|nove|dieci|\d{1,2})\s+(?P<u2>giorn[oi]|settiman[ae]|mes[ei])\s+fa)(?![\w])")
_NUMERI_PAROLA = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                  "nine": 9, "ten": 10, "un": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7,
                  "otto": 8, "nove": 9, "dieci": 10}
# mese e anno in cifre: «07/2025», «7-2025», «2025-07»
RE_MESI_INTERVALLO = re.compile(r"(?<![\w])(?P<m>gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|"
                                r"january|february|march|april|june|july|august|september|october|november|december)(?P<s>\s*[-–/]\s*)"
                                r"(?=(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|"
                                r"january|february|march|april|may|june|july|august|september|october|november|december),?\s+(?:19|20)\d\d)", re.I)
RE_MESE_NUM = re.compile(r"(?<![\w/.\-])(?:(?P<m>0?[1-9]|1[0-2])(?P<s>[/\-.])(?P<a>(?:19|20)\d\d)|(?P<a2>(?:19|20)\d\d)-(?P<m2>0[1-9]|1[0-2]))(?![\w/\-]|\.\d)")
RE_ETICHETTA_NUMERO = re.compile(r"(?i)(?:\bn\.|n°|\bnr\.?|\bno\.|#|\bnum(?:ero|ber)?\.?|\bprot\.?|\brif\.?|\bref\.?|\bpratica|\br\.\s?g\.|\brep\.?|\bart\.?|\bartt\.?|\blegge|\bd\.\s?lgs\.?|\bdpr|\bcircolare|\bdelibera)\s*[:\-]?\s*$")
# trimestri: «Q3 2025», «2025-Q3», «3° trimestre 2025», «terzo trimestre del 2025», «third quarter of 2025»
_Q_PAROLE = {"primo": 1, "secondo": 2, "terzo": 3, "quarto": 4, "first": 1, "second": 2, "third": 3, "fourth": 4}
_Q_IT = ["primo", "secondo", "terzo", "quarto"]
_Q_EN = ["first", "second", "third", "fourth"]
RE_TRIMESTRE = re.compile(
    r"(?<![\w])(?:(?P<q>Q[1-4])(?P<s>[ /\-]?)(?P<a>(?:19|20)\d\d|['’]?\d\d)|(?P<a2>(?:19|20)\d\d)(?P<s2>[ /\-]?)(?P<q2>Q[1-4])|"
    r"(?P<n>[1-4])[°º]\s+trimestre(?P<s3>\s+(?:del\s+|dell['’]anno\s+)?)(?P<a3>(?:19|20)\d\d)|"
    r"(?P<w>primo|secondo|terzo|quarto|first|second|third|fourth)\s+(?:trimestre|quarter)(?P<s4>\s+(?:del\s+|dell['’]anno\s+|of\s+)?)(?P<a4>(?:19|20)\d\d)|"
    r"(?P<r>IV|I{1,3})\s+trimestre(?P<s5>\s+(?:del\s+|dell['’]anno\s+)?)(?P<a5>(?:19|20)\d\d))(?![\w])",
    re.I)
# date relative al mese della lettera: «3 corr.», «il 9 corrente», «11 u.s.», «5 p.v.», «3 c.m.»
RE_RELATIVA = re.compile(r"(?<![\w/.])(?P<g>[0-3]?\d)(?P<sp>\s+|\s*)(?P<rel>u\.\s?s\.?|c\.\s?m\.|corr\.|corrente|p\.\s?v\.)(?![\w])", re.I)
RE_DATA_LETTERA = re.compile(r"(?i)(?:(?:^|[-–:|][ \t]*|[ \t]{2,})[A-ZÀ-Ý][\w'’ .]{1,40},[ \t]*(?:l[ìi]['’]?[ \t]+)?$|"
                             r"(?:^|[ \t]{2,}|\|)[ \t]*(?:[\w'’]+[ \t]+){0,2}(?:data|date|dated|addì|lì|stampa|emess[oa]|rilasciat[oa]|issued|printed|"
                             r"presentat[oa]|sottoscritt[oa]|pubblicat[oa]|firmat[oa]|redatt[oa]|signed|filed|submitted|sent)\b"
                             r"[^:\n]{0,30}:?\s*(?:il\s+|on\s+)?$)")
# «arrives on the 14th»: giorno del mese della lettera
RE_ORDINALE_EN = re.compile(rf"(?<![\w])(?:(?:on|by|until|till|from|before|after|since|for|is|was|due)\s+)?the\s+(?:>[ \t]*)*(?P<g>[0-3]?\d)(?P<ord>{_ORD})(?![\w])"
                            rf"(?!\s+(?:of\s+)?{_MONTH_RE})(?!\s+(?:floor|time|times|place|edition|century|anniversary|grade|year|week|day|"
                            rf"round|row|line|item|step|page|chapter|amendment|percentile|party|person|attempt|quarter|instalment|installment)\b)", re.I)
_PAROLE_QUARTI_EN = ["first", "second", "third", "fourth"]
_PAROLE_QUARTI_IT = ["primo", "secondo", "terzo", "quarto"]
_QUARTI = {w: i + 1 for lista in (_PAROLE_QUARTI_EN, _PAROLE_QUARTI_IT, ["1st", "2nd", "3rd", "4th"]) for i, w in enumerate(lista)}
RE_TRIMESTRE_SOLO = re.compile(r"(?<![\w/-])(?:(?P<q>[Qq][1-4])|(?P<w>(?i:first|second|third|fourth|primo|secondo|terzo|quarto|1st|2nd|3rd|4th))\s+(?i:quarter|trimestre))"
                               r"(?![\w/-])(?!\s*(?:(?:of|del|dell['’]anno)\s+)?(?:19|20)\d\d|\s*['’]\d\d)")
RE_DEL_MESE_IT = re.compile(r"(?<![\w/.,])(?P<g>[0-3]?\d)\s+del\s+(?P<rel>mese\s+(?:scorso|precedente|corrente|in\s+corso|prossimo|successivo))(?![\w])", re.I)
_REL_OFF = {"us": -1, "cm": 0, "corr": 0, "corrente": 0, "pv": 1}
# giorno della settimana e numero senza mese: «giovedì 8», «giovedi' 8», «Thursday the 8th»
RE_SETT_NUMERO = re.compile(
    rf"(?<![\w])(?P<sett>luned[iì]['’]?|marted[iì]['’]?|mercoled[iì]['’]?|gioved[iì]['’]?|venerd[iì]['’]?|sabato|domenica|"
    rf"monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?P<sep0>\s+(?:the\s+)?)(?P<g>[0-3]?\d)(?P<ord>{_ORD})?(?![\w/\-]|\.\d|\s+(?:{_MESE_RE}|{_MONTH_RE})\b)",
    re.I)
# intervalli: «dal 3 al 10 marzo 2025», «3-10 marzo», «3–10 March 2025», «March 3–10, 2025»
RE_INTERVALLO_INIZIO = re.compile(r"(?<![\w/.\-])(?P<g1>[0-3]?\d)(?P<o1>{_ORD})?(?P<mid>\s*(?:-|–|al(?:l['’])?|e|to|and|through|until|till)\s*)(?=[0-3]?\d(?:{_ORD})?\s+(?:{_MESE_RE}|{_MONTH_RE}))".replace("{_ORD}", _ORD).replace("{_MESE_RE}", _MESE_RE).replace("{_MONTH_RE}", _MONTH_RE), re.I)
RE_INTERVALLO_FINE_EN = re.compile(r"(?<=[0-9a-z])(?P<mid>\s*(?:-|–|to|through|until|till)\s*)(?P<g2>[0-3]?\d)(?P<o2>{_ORD})?(?![\w/.\-]|\.\d)".replace("{_ORD}", _ORD), re.I)
# giorno e anno in lettere: «ventidue del mese di luglio», «primo marzo duemilaventicinque»
_UNITA_IT = ["", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci", "undici", "dodici",
             "tredici", "quattordici", "quindici", "sedici", "diciassette", "diciotto", "diciannove"]
_DECINE_IT = ["", "", "venti", "trenta", "quaranta", "cinquanta", "sessanta", "settanta", "ottanta", "novanta"]


def numero_in_lettere(n: int) -> str:
    """0–99 e 1900–2099 in parole italiane («ventidue», «duemilaventicinque»)."""
    if n >= 1000:
        base = "duemila" if n >= 2000 else "millenovecento"
        resto = n - (2000 if n >= 2000 else 1900)
        return base + (numero_in_lettere(resto) if resto else "")
    if n < 20:
        return _UNITA_IT[n]
    d, u = divmod(n, 10)
    p = _DECINE_IT[d]
    if u in (1, 8):
        p = p[:-1]
    return p + (_UNITA_IT[u] if u != 3 else "tré")


_LETTERE_NUMERO = {numero_in_lettere(i): i for i in range(1, 100)}
_LETTERE_NUMERO.update({k.replace("tré", "tre"): v for k, v in list(_LETTERE_NUMERO.items())})
_LETTERE_NUMERO["primo"] = 1
_LETTERE_ANNO = {numero_in_lettere(a): a for a in range(1900, 2100)}
_LETTERE_ANNO.update({k.replace("tré", "tre"): v for k, v in list(_LETTERE_ANNO.items())})
_GIORNI_LETTERE = "|".join(sorted((k for k, v in _LETTERE_NUMERO.items() if v <= 31), key=len, reverse=True))
_ANNI_LETTERE = "|".join(sorted(_LETTERE_ANNO, key=len, reverse=True))
RE_LETTERE = re.compile(
    rf"(?<![\w])(?P<g>{_GIORNI_LETTERE})(?P<sep1>\s+(?:del\s+mese\s+di\s+|di\s+)?)(?P<m>gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
    rf"(?:(?P<sep2>\s+(?:dell['’]anno\s+|del\s+)?)(?P<a>{_ANNI_LETTERE}|(?:19|20)\d\d))?(?![\w])", re.I)
RE_NUMERICA = re.compile(
    r"(?<![\w/.\-])(?:(?P<sett>" + _GIORNO_RE + "|" + _DAY_RE + r")(?P<sep0>,?\s+))?(?P<p1>[0-3]?\d)(?P<s>[/.\-])(?P<p2>[0-3]?\d)(?P=s)(?P<a>(?:19|20)\d\d|\d\d)(?![\w/]|[.\-]\d)",
    re.I)
RE_ISO = re.compile(r"(?<![\w/.\-])(?P<a>(?:19|20)\d\d)(?P<s>[-/])(?P<m>[01]\d)(?P=s)(?P<g>[0-3]\d)(?![\d])")
RE_MESE_ANNO = re.compile(rf"(?<![\w])(?P<m>gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|january|february|march|april|may|june|july|august|september|october|november|december)(?P<sep>,?\s+(?:del\s+|of\s+)?)(?P<a>(?:19|20)\d\d)(?![\w])", re.I)
RE_ANNO_CONTESTO = re.compile(r"(?<![\w])(?P<pre>(?:nel|nell'anno|dal|al|del|anno|anni|entro\s+il|fino\s+al|classe|esercizio|d'imposta|periodo\s+d'imposta|in|since|until|year|tax\s+year|fiscal\s+year|class\s+of|from|to|by|before|after|during|between|circa|c\.|early|late|mid|tra\s+il|fra\s+il|prima\s+del|dopo\s+il|entro|per\s+il|nei\s+primi\s+mesi\s+del|alla\s+fine\s+del|"
                              r"built|purchased|bought|acquired|renewed|through|expires?|expired|issued|completed|graduated|founded|established|"
                              r"registered|licensed|certified|married|divorced|died|est\.|summer|fall|autumn|winter|spring|estate|inverno|"
                              r"primavera|autunno|costruit[oa]|acquistat[oa]|immatricolat[oa]|rilasciat[oa]|conseguit[oa]|diplomat[oa]|"
                              r"laureat[oa]|sposat[oa]|dall['’]anno|a\s+partire\s+dal|sino\s+al|tutto\s+il|fine|inizio|metà|dates\s+to|dating\s+(?:from|to)|risale\s+al)\s+)(?P<a>(?:18|19|20)\d\d)(?![\w/\-])", re.I)
RE_ANNO_RIGA = re.compile(r"(?im)(?:,[ \t]+(?P<a>(?:19|20)\d\d)[ \t]*$|(?<![\w/.\-])(?P<b>(?:19|20)\d\d)(?=[ \t]*[-–][ \t]*(?:present|current|now|oggi|in\s+corso)\b))")
RE_ANNI_INTERVALLO = re.compile(r"(?<![\w/.\-])(?P<a>(?:19|20)\d\d)(?P<s>\s*[-–/]\s*)(?P<b>(?:19|20)\d\d|\d\d)(?![\w/\-]|\.\d)")

# Riferimenti normativi: le loro date sono fatti pubblici e non vanno spostate.
RE_NORMATIVA = re.compile(
    r"(?:\blegge|\bl\.|\bdecreto(?:\s+legislativo|\s+legge|\s+ministeriale|\s+del\s+presidente\s+della\s+repubblica)|"
    r"\bd\.\s?lgs\.?|\bdlgs\.?|\bd\.\s?l\.|\bd\.\s?p\.\s?r\.|\bdpr|\bd\.\s?m\.|\bd\.\s?p\.\s?c\.\s?m\.|\bdpcm|"
    r"\bregolamento(?:\s+\(?ue\)?)?|\bdirettiva(?:\s+\(?ue\)?)?|\bcircolare(?:\s+\w+)?|\bgazzetta\s+ufficiale|\bg\.\s?u\.|"
    r"\bcodice(?:\s+\w+)?|\bcostituzione|\btrattato|\bconvenzione|\br\.\s?d\.|\bregio\s+decreto|"
    r"\b(?:gdpr|regolamento\s*\(?ue\)?[^\n]{0,30})[^\n]{0,15}(?:applicabile|in\s+vigore|efficace)\s+(?:dal|il)|"
    r"\bact(?:\s+of)?|\bstatute|\bregulations?|\bdirective|\bu\.?\s?s\.?\s?c\.?|\bc\.?\s?f\.?\s?r\.?|\bpublic\s+law|\bexecutive\s+order|\bamendment)"
    r"\s*(?:\(\w+\)\s*)?(?:(?:n\.?|nr\.?|no\.?|n°)?\s*[\w/-]*\d[\w/-]*\s*)?(?:,\s*)?(?:del(?:l['’])?\s*|in\s+data\s*|dated\s*|enacted\s*|of\s*|approved\s*|signed\s*)?$",
    re.I)

RE_US = re.compile(r"(?:\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b|\bSSN|\bITIN|\bZIP|\bSocial Security|\bW-2|\bMedicaid|\bMedicare|\$\s?\d|"
                   r"\(\d{3}\)\s?\d{3}-\d{4}|(?<![\d-])\d{3}[-.]\d{3}[-.]\d{4}(?![\d-])|\+1[\s-]\d{3}|"
                   r"\bU\.?S\.?A?\b|\bcolor\b|\bcenter\b|\bpaycheck\b|\bApt\.?\s|\bLLC\b|\bInc\.|\bDr\.\s|\bMr\.\s|\bMrs\.\s|\bMs\.\s)")
RE_UK = re.compile(r"(?:\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b|£\s?\d|\bNHS\b|National Insurance|\+44|\bHMRC\b|\bsolicitor|"
                   r"\bLtd\b|\bCouncil Tax\b|\bsort code\b|\bcolour\b|\bcentre\b|\borganis|\bGP\b|\bpostcode\b|\bMr\s|\bMrs\s)", re.I)


def convenzione_date(testo: str, lingua: str = "it") -> str:
    """«DMY» (Italia, Regno Unito) o «MDY» (Stati Uniti) per le date numeriche del documento.
    Prima le date che lo dicono da sole (un 13 al primo posto vuol dire giorno/mese), poi gli indizi del paese."""
    dmy = mdy = 0
    for m in RE_NUMERICA.finditer(testo):
        p1, p2 = int(m["p1"]), int(m["p2"])
        if p1 > 12 and p2 <= 12:
            dmy += 3
        elif p2 > 12 and p1 <= 12:
            mdy += 3
    if dmy != mdy:
        return "DMY" if dmy > mdy else "MDY"
    if lingua == "it":
        return "DMY"
    us, uk = len(RE_US.findall(testo)), len(RE_UK.findall(testo))
    # date scritte: «March 4, 2025» è uso americano, «4 March 2025» britannico
    us += 2 * sum(1 for m in RE_EN_MDY.finditer(testo) if m.group("a"))
    uk += 2 * sum(1 for m in RE_EN_DMY.finditer(testo) if m.group("a"))
    return "MDY" if us > uk else "DMY"


@dataclass
class DataTrovata:
    inizio: int
    fine: int
    data: dt.date
    granularita: str  # giorno | giorno_senza_anno | mese | anno
    componenti: dict = field(default_factory=dict)  # nome -> (inizio, fine) relativi al testo
    testo: str = ""
    normativa: bool = False
    speciale: dict = field(default_factory=dict)  # date relative, intervalli, trimestri, in lettere


def _anno(s: str, rif: int) -> tuple[int, str]:
    s2 = s.lstrip("'’")
    if len(s2) == 4:
        return int(s2), "4"
    yy = int(s2)
    secolo = 2000 if 2000 + yy <= rif + 15 else 1900
    return secolo + yy, ("'2" if s[0] in "'’" else "2")


def _mese(s: str) -> int:
    t = s.lower().rstrip(".")
    if t in MESI:
        return MESI.index(t) + 1
    if t in MONTHS:
        return MONTHS.index(t) + 1
    if t in ABBR:
        return ABBR[t]
    return MON_ABBR[t]


def _mese_en(s: str) -> int:
    t = s.lower().rstrip(".")
    return MONTHS.index(t) + 1 if t in MONTHS else MON_ABBR[t]


def _comp(m: re.Match, nomi) -> dict:
    return {n: (m.start(n), m.end(n)) for n in nomi if m.group(n) is not None}


def trova_date(testo: str, anno_rif: int | None = None, anni_contesto: bool = True, convenzione: str = "DMY") -> list[DataTrovata]:
    """Tutte le date del testo, senza sovrapposizioni, in ordine."""
    anno_rif = anno_rif or dt.date.today().year
    trovate: list[DataTrovata] = []
    occupato = Intervalli()
    libero = occupato.libero

    def aggiungi(d: DataTrovata):
        if libero(d.inizio, d.fine):
            prima = testo[max(0, d.inizio - 70):d.inizio]
            d.normativa = bool(RE_NORMATIVA.search(prima))
            d.testo = testo[d.inizio:d.fine]
            trovate.append(d)
            occupato.aggiungi(d.inizio, d.fine)

    for m in RE_ISO.finditer(testo):
        try:
            d = dt.date(int(m["a"]), int(m["m"]), int(m["g"]))
        except ValueError:
            continue
        aggiungi(DataTrovata(m.start(), m.end(), d, "giorno", _comp(m, ["a", "m", "g"])))
    for m in RE_NUMERICA.finditer(testo):
        if (m["s"] == "." and len(m["a"]) == 2 and (len(m["p1"]) < 2 or len(m["p2"]) < 2)
                and re.search(r"(?i)(?:\bv|vers(?:ione|ion)?|release|rel\.|build|python|node|app)\s*\.?\s*$", testo[max(0, m.start() - 14):m.start()])):
            continue  # «v1.2.24» è un numero di versione; «3.10.25» in un elenco di pagamenti è una data
        if re.search(r"(?i)(?:ettari|ha|are|mq|m2|km|kg)\s*$", testo[max(0, m.start() - 10):m.start()]):
            continue  # «ettari 3.12.40»: una misura
        anno, _ = _anno(m["a"], anno_rif)
        ordine = ("p1", "p2") if convenzione == "DMY" else ("p2", "p1")  # (giorno, mese)
        for g_n, m_n in (ordine, ordine[::-1]):  # se nell'ordine del documento non è una data, si prova l'altro
            try:
                d = dt.date(anno, int(m[m_n]), int(m[g_n]))
            except ValueError:
                continue
            comp = {"a": (m.start("a"), m.end("a")), "g": (m.start(g_n), m.end(g_n)), "m": (m.start(m_n), m.end(m_n))}
            if m["sett"]:
                comp["sett"] = (m.start("sett"), m.end("sett"))
            aggiungi(DataTrovata(m.start(), m.end(), d, "giorno", comp))
            break
    for m in RE_LETTERE.finditer(testo):  # «ventidue del mese di luglio [duemilaventicinque]»
        g = _LETTERE_NUMERO.get(m["g"].lower())
        a = None
        if m["a"]:
            a = int(m["a"]) if m["a"].isdigit() else _LETTERE_ANNO.get(m["a"].lower())
        try:
            d = dt.date(a or 2000, _mese(m["m"]), g)
        except (ValueError, TypeError):
            continue
        aggiungi(DataTrovata(m.start(), m.end(), d, "giorno" if a else "giorno_senza_anno", _comp(m, ["g", "m", "a"]),
                             speciale={"tipo": "lettere"}))
    for m in RE_TRIMESTRE.finditer(testo):
        a_txt = m["a"] or m["a2"] or m["a3"] or m["a4"] or m["a5"]
        if m["r"]:
            q = {"I": 1, "II": 2, "III": 3, "IV": 4}[m["r"].upper()]
        else:
            q = int((m["q"] or m["q2"] or "Q0")[1]) if (m["q"] or m["q2"]) else int(m["n"]) if m["n"] else _Q_PAROLE[m["w"].lower()]
        anno, _ = _anno(a_txt, anno_rif)
        nomi = [n for n in ("q", "a", "a2", "q2", "n", "a3", "w", "a4", "r", "a5") if m.group(n) is not None]
        comp = {n: (m.start(n), m.end(n)) for n in nomi}
        aggiungi(DataTrovata(m.start(), m.end(), dt.date(anno, 3 * q - 1, 15), "trimestre", comp, speciale={"tipo": "trimestre"}))
    for m in RE_MESE_NUM.finditer(testo):  # «07/2025»: non dopo «n.», «prot.», «art.» (lì è un numero di pratica)
        if RE_ETICHETTA_NUMERO.search(testo[max(0, m.start() - 20):m.start()]):
            continue
        if m["m"]:
            aggiungi(DataTrovata(m.start(), m.end(), dt.date(int(m["a"]), int(m["m"]), 15), "mese", _comp(m, ["m", "a"])))
        else:
            c = {"a": (m.start("a2"), m.end("a2")), "m": (m.start("m2"), m.end("m2"))}
            aggiungi(DataTrovata(m.start(), m.end(), dt.date(int(m["a2"]), int(m["m2"]), 15), "mese", c))
    for m in RE_SCADENZA_MMYY.finditer(testo):
        aggiungi(DataTrovata(m.start("m"), m.end("a"), dt.date(2000 + int(m["a"]), int(m["m"]), 15), "mese",
                             {"m": (m.start("m"), m.end("m")), "a": (m.start("a"), m.end("a"))}))
    for m in RE_NUMERICA_BREVE.finditer(testo):  # «02/03», «28/8», «3/10»: giorno e mese senza anno, nel dubbio una data
        g_n, m_n = ("p1", "p2") if convenzione == "DMY" else ("p2", "p1")
        nucleo = m["p1"] + "/" + m["p2"]
        if nucleo in ("24/7", "7/24", "50/50", "9/11") or RE_ETICHETTA_NUMERO.search(testo[max(0, m.start() - 20):m.start()]):
            continue
        if not m["sett"] and (RE_FRAZIONE_DOPO.match(testo, m.end()) or re.search(r"\d[ \t]$", testo[max(0, m.start() - 2):m.start()])
                              or RE_FRAZIONE_PRIMA.search(testo[max(0, m.start() - 20):m.start()])):
            continue  # «3/4 di litro», «1 1/2», «quota di 1/2», «Flat 1/2», «soffio 2/6»: frazioni
        if (not m["sett"] and int(m["p1"]) < 10 and int(m["p2"]) < 10 and int(m["p1"]) <= int(m["p2"]) <= 4
                and not m["p1"].startswith("0") and not m["p2"].startswith("0")
                and not re.search(r"(?:^|\n)[ \t]*$", testo[max(0, m.start() - 10):m.start()])
                and not RE_CONTESTO_DATA.search(testo[max(0, m.start() - 20):m.start()])):
            continue  # «1/2», «2/3», «3/4» senza un contesto di data: frazioni
        try:
            d = dt.date(2000, int(m[m_n]), int(m[g_n]))
        except ValueError:
            try:  # nel dubbio si sposta: «8/29» in un documento britannico è comunque una data (all'americana)
                g_n, m_n = m_n, g_n
                d = dt.date(2000, int(m[m_n]), int(m[g_n]))
            except ValueError:
                continue
        comp = {"g": (m.start(g_n), m.end(g_n)), "m": (m.start(m_n), m.end(m_n))}
        if m["sett"]:
            comp["sett"] = (m.start("sett"), m.end("sett"))
        aggiungi(DataTrovata(m.start(), m.end(), d, "giorno_senza_anno", comp))
    for rx, mese_fn in ((RE_TESTUALE, _mese), (RE_EN_MDY, _mese_en), (RE_EN_DMY, _mese_en)):
        for m in rx.finditer(testo):
            mese_txt = m["m"]
            t = mese_txt.lower().rstrip(".")
            if (t in ("mar", "may") and not mese_txt.endswith(".") and not m["a"] and rx is not RE_EN_MDY
                    and not (rx is RE_EN_DMY and (m["ord"] or m["sett"] or mese_txt == "May"))):
                continue
            if rx is RE_EN_MDY and t == "may" and not m["a"] and not m["ord"] and not mese_txt[0].isupper():
                continue  # «may 4» senza anno né «th»: troppo spesso il verbo
            try:
                mese = mese_fn(mese_txt)
            except (KeyError, ValueError):
                continue
            gran = "giorno"
            if m["a"]:
                anno, _ = _anno(m["a"], anno_rif)
            else:
                anno, gran = None, "giorno_senza_anno"
            try:
                d = dt.date(anno or 2000, mese, int(m["g"]))
            except ValueError:
                continue
            aggiungi(DataTrovata(m.start(), m.end(), d, gran, _comp(m, ["sett", "g", "ord", "m", "a"])))
    for m in RE_MESE_ANNO.finditer(testo):
        aggiungi(DataTrovata(m.start(), m.end(), dt.date(int(m["a"]), _mese(m["m"]), 15), "mese", _comp(m, ["m", "a"])))
    per_inizio_m = {d.inizio: d for d in trovate}
    for m in RE_MESI_INTERVALLO.finditer(testo):  # il primo mese prende l'anno del secondo
        fine_d = per_inizio_m.get(m.end())
        if fine_d is None or fine_d.granularita != "mese" or not libero(m.start(), m.end("m")):
            continue
        mese = _mese(m["m"])
        anno = fine_d.data.year - (1 if mese > fine_d.data.month else 0)
        aggiungi(DataTrovata(m.start(), m.end("m"), dt.date(anno, mese, 15), "mese", {"m": (m.start("m"), m.end("m"))},
                             speciale={"tipo": "mese_inizio", "fine": fine_d}))
    for m in RE_RELATIVA.finditer(testo):  # il mese si ricava dopo, dalla data della lettera
        if m["rel"][0].isupper() and m["rel"].lower().startswith(("u", "c.", "p")):
            continue  # «26 U.S.C.», «C.M.», «P.V.» in maiuscolo: sigle, non date relative
        chiave = re.sub(r"[\s.]", "", m["rel"].lower())
        try:
            d = dt.date(2000, 1, int(m["g"]))
        except ValueError:
            continue
        aggiungi(DataTrovata(m.start(), m.end(), d, "relativa", _comp(m, ["g", "rel"]),
                             speciale={"tipo": "relativa", "off": _REL_OFF.get(chiave, 0)}))
    for m in RE_DEL_MESE_IT.finditer(testo):  # «il 3 del mese scorso», «il 20 del mese prossimo»
        try:
            d = dt.date(2000, 1, int(m["g"]))
        except ValueError:
            continue
        off = -1 if m["rel"].lower().endswith(("scorso", "precedente")) else 1 if m["rel"].lower().endswith(("prossimo", "successivo")) else 0
        aggiungi(DataTrovata(m.start(), m.end(), d, "relativa", _comp(m, ["g", "rel"]), speciale={"tipo": "relativa", "off": off}))
    for m in RE_ORDINALE_EN.finditer(testo):
        try:
            d = dt.date(2000, 1, int(m["g"]))
        except ValueError:
            continue
        comp, fine, off = _comp(m, ["g", "ord"]), m.end("ord"), 0
        rel = re.match(r"\s+of\s+(last|this|next)\s+month\b", testo[m.end("ord"):], re.I)  # «the 3rd of last month»
        if rel:
            off = {"last": -1, "this": 0, "next": 1}[rel.group(1).lower()]
            comp["rel"] = (m.end("ord") + rel.start(1), m.end("ord") + rel.end(1))
            fine = m.end("ord") + rel.end()
        aggiungi(DataTrovata(m.start("g"), fine, d, "relativa", comp, speciale={"tipo": "ordinale", "off": off}))
    for m in RE_SETT_NUMERO.finditer(testo):
        try:
            d = dt.date(2000, 1, int(m["g"]))
        except ValueError:
            continue
        aggiungi(DataTrovata(m.start(), m.end(), d, "relativa", _comp(m, ["sett", "g", "ord"]), speciale={"tipo": "settimana"}))
    if anni_contesto:
        for m in RE_ANNO_RIGA.finditer(testo):
            g = "a" if m["a"] else "b"
            if not RE_ETICHETTA_NUMERO.search(testo[max(0, m.start() - 20):m.start()]):
                aggiungi(DataTrovata(m.start(g), m.end(g), dt.date(int(m[g]), 7, 1), "anno", {"a": (m.start(g), m.end(g))}))
        for m in RE_ANNI_INTERVALLO.finditer(testo):  # «2019-2021», «2024/25»: due anni
            a, b = int(m["a"]), m["b"]
            b_int = int(b) if len(b) == 4 else (a // 100) * 100 + int(b)
            if not (a < b_int <= a + 30) or RE_ETICHETTA_NUMERO.search(testo[max(0, m.start() - 20):m.start()]):
                continue
            if libero(m.start(), m.end()):
                aggiungi(DataTrovata(m.start("a"), m.end("a"), dt.date(a, 7, 1), "anno", {"a": (m.start("a"), m.end("a"))}))
                aggiungi(DataTrovata(m.start("b"), m.end("b"), dt.date(b_int, 7, 1), "anno", {"a": (m.start("b"), m.end("b"))}))
    if anni_contesto:
        for m in RE_ANNO_CONTESTO.finditer(testo):
            if RE_NON_ANNO_DOPO.match(testo, m.end("a")):
                continue  # «in 2030 dipendenti»: una quantità
            aggiungi(DataTrovata(m.start("a"), m.end("a"), dt.date(int(m["a"]), 7, 1), "anno",
                                 {"a": (m.start("a"), m.end("a"))}))
    # intervalli: il primo giorno prende mese e anno dalla data che segue («dal 3 al 10 marzo 2025»)
    per_inizio = {d.inizio: d for d in trovate}
    for m in RE_INTERVALLO_INIZIO.finditer(testo):
        fine_d = per_inizio.get(m.end())
        if fine_d is None or fine_d.granularita not in ("giorno", "giorno_senza_anno") or not libero(m.start("g1"), m.end("g1")):
            continue
        try:
            d = dt.date(fine_d.data.year, fine_d.data.month, int(m["g1"]))
        except ValueError:
            continue
        if d > fine_d.data:
            continue
        aggiungi(DataTrovata(m.start("g1"), m.end("o1") if m["o1"] else m.end("g1"), d, fine_d.granularita,
                             _comp(m, ["g1", "o1"]), speciale={"tipo": "inizio", "fine": fine_d}))
    # «March 3–10, 2025»: il secondo giorno prende mese e anno dalla data che precede
    per_fine = {d.fine: d for d in trovate}
    for m in RE_INTERVALLO_FINE_EN.finditer(testo):
        ini = per_fine.get(m.start())
        if ini is None or ini.granularita not in ("giorno", "giorno_senza_anno") or not libero(m.start("g2"), m.end("g2")):
            continue
        anno_m = re.match(r",?\s+((?:19|20)\d\d)(?![\w])", testo[m.end():])
        try:
            d = dt.date(int(anno_m.group(1)) if anno_m else ini.data.year, ini.data.month, int(m["g2"]))
        except ValueError:
            continue
        if d < ini.data.replace(year=d.year):
            continue
        if anno_m and ini.granularita == "giorno_senza_anno":
            ini.data = ini.data.replace(year=d.year)
            ini.granularita = "giorno"
            ini.speciale = {**ini.speciale, "anno_da_intervallo": True}
        comp = _comp(m, ["g2", "o2"])
        fine_g = m.end("o2") if m["o2"] else m.end("g2")
        if anno_m:  # l'anno dopo l'intervallo («March 3–10, 2025») si sposta con il secondo giorno
            comp["a"] = (m.end() + anno_m.start(1), m.end() + anno_m.end(1))
            fine_g = m.end() + anno_m.end(1)
        aggiungi(DataTrovata(m.start("g2"), fine_g, d, "giorno" if anno_m else ini.granularita, comp,
                             speciale={"tipo": "fine", "inizio": ini}))
    if anni_contesto:
        for m in RE_ANNO_NUDO.finditer(testo):
            if RE_NON_ANNO_DOPO.match(testo, m.end()) or RE_NON_ANNO_PRIMA.search(testo[max(0, m.start() - 12):m.start()]):
                continue
            if re.search(r"\d[ \t]{1,3}$", testo[max(0, m.start() - 4):m.start()]) or re.match(r"[ \t]{1,3}\d", testo[m.end():m.end() + 4]):
                continue  # numeri in fila (tabelle di importi o quantità)
            aggiungi(DataTrovata(m.start(), m.end(), dt.date(int(m["a"]), 7, 1), "anno", {"a": (m.start(), m.end())}))
        for rx in (RE_MESE_SOLO_IT, RE_MESE_SOLO_EN, RE_MESE_SOLO_EN2, RE_MESE_SOLO_EN_MIN, RE_MESE_SOLO_IT_MAIUSC):
            for m in rx.finditer(testo):
                if not libero(m.start("m"), m.end("m")):
                    continue
                aggiungi(DataTrovata(m.start("m"), m.end("m"), dt.date(anno_rif, _mese(m["m"]), 15), "mese_solo",
                                     {"m": (m.start("m"), m.end("m"))}, speciale={"tipo": "mese_solo"}))
        for m in RE_TRIMESTRE_SOLO.finditer(testo):  # «second quarter», «q1», «terzo trimestre» senza anno
            q = int(m["q"][1]) if m["q"] else _QUARTI[m["w"].lower()]
            if not libero(m.start(), m.end()):
                continue
            aggiungi(DataTrovata(m.start(), m.end(), dt.date(anno_rif, 3 * q - 1, 15), "mese_solo",
                                 {"m": (m.start(), m.end())}, speciale={"tipo": "trimestre_solo"}))
    trovate.sort(key=lambda d: d.inizio)
    # Anno delle date senza anno: quello dell'ultima data completa che le precede, altrimenti l'anno di riferimento.
    ultimo = anno_rif
    for d in trovate:
        if d.granularita in ("giorno", "mese", "anno") and not d.normativa:
            ultimo = d.data.year
        elif d.granularita == "giorno_senza_anno":
            try:
                d.data = d.data.replace(year=ultimo)
            except ValueError:  # 29 febbraio in un anno non bisestile
                d.data = d.data.replace(year=ultimo, day=28)
            if "sett" in d.componenti:  # «giovedì 17 luglio»: l'anno vicino in cui quel giorno è giovedì
                nome = testo[d.componenti["sett"][0]:d.componenti["sett"][1]].lower().rstrip(".'’").replace("ì", "i")
                wd = next((i for i, x in enumerate(GIORNI) if x.replace("ì", "i").startswith(nome[:3])), None)
                if nome[:3] in [x[:3] for x in DAYS]:
                    wd = [x[:3] for x in DAYS].index(nome[:3])
                for k in (0, -1, 1, -2, 2, -3, 3):
                    try:
                        prova = d.data.replace(year=ultimo + k)
                    except ValueError:
                        continue
                    if wd is not None and prova.weekday() == wd:
                        d.data = prova
                        break
    # Date relative: il mese viene dalla data completa più vicina (di solito la data della lettera)
    piene = [d for d in trovate if d.granularita == "giorno" and not d.normativa and not d.speciale.get("tipo")]
    nascita = re.compile(r"(?i)\b(?:nat[oa]|nascita|born|birth|dob|classe)\b[^\n]{0,30}$")
    candidate = [d for d in trovate if not d.normativa and (d.granularita in ("giorno", "giorno_senza_anno"))
                 and d.speciale.get("tipo") in (None, "lettere", "anno_da_intervallo")]
    intestazione = [p for p in candidate if RE_DATA_LETTERA.search(testo[testo.rfind("\n", 0, p.inizio) + 1:p.inizio])]
    if not intestazione:  # la prima data nelle prime righe («Stampa del 15 maggio 2025», «giovedì 17 luglio», «L'anno … il giorno …»)
        intestazione = [p for p in candidate if p.inizio < 900 and testo.count("\n", 0, p.inizio) < 10
                        and not nascita.search(testo[max(0, p.inizio - 40):p.inizio])][:1]
    if intestazione:  # parole relative («ieri», «last Friday»): solo con una data del documento certa
        for m in RE_PAROLA_RELATIVA.finditer(testo):
            if not libero(m.start(), m.end()):
                continue
            if m["p"]:
                k = re.sub(r"[\s'’]", "", m["p"].lower())
                scarto = {"ieri": -1, "domani": 1, "dopodomani": 2, "laltroieri": -2, "altroieri": -2, "yesterday": -1, "tomorrow": 1}[k]
                f = (lambda sc: (lambda r: sc))(scarto)
            elif m["u"] or m["u2"]:
                n = (m["n"] or m["n2"]).lower()
                n = int(n) if n.isdigit() else _NUMERI_PAROLA[n]
                u = (m["u"] or m["u2"]).lower()
                passo = 14 if u.startswith("fortnight") else 7 if u.startswith(("week", "settiman")) else 30 if u.startswith(("month", "mes")) else 1
                f = (lambda sc: (lambda r: sc))(-n * passo)
            else:
                nome = (m["sett"] or m["sett2"]).lower().replace("ì", "i")
                wd = next(i for i, x in enumerate(GIORNI + DAYS) if x.replace("ì", "i").startswith(nome[:3])) % 7
                avanti = (m["dir"] or m["dir2"]).lower().startswith(("pross", "next"))
                f = (lambda wd, av: (lambda r: ((wd - r.weekday()) % 7 or 7) if av else -(((r.weekday() - wd) % 7) or 7)))(wd, avanti)
            nd = DataTrovata(m.start(), m.end(), dt.date(2000, 1, 1), "relativa", {"x": (m.start(), m.end())},
                             speciale={"tipo": "parola", "giorni": f})
            nd.testo = testo[m.start():m.end()]
            nd.normativa = False
            trovate.append(nd)
            occupato.aggiungi(m.start(), m.end())
        trovate.sort(key=lambda d: d.inizio)
    for d in trovate:
        if d.granularita == "mese_solo":  # «a giugno»: l'anno del documento
            rif = intestazione[0].data if intestazione else dt.date(anno_rif, 7, 1)
            d.data = d.data.replace(year=rif.year)
            continue
        if d.granularita != "relativa":
            continue
        if intestazione:  # «Milano, 2 novembre 2025», «Data: …», «Dated …»: la data della lettera
            rif = intestazione[0].data
        elif piene:  # la data completa più vicina prima (non una data di nascita), altrimenti la più vicina
            prima = [p for p in piene if p.inizio < d.inizio
                     and not re.search(r"(?i)\b(?:nat[oa]|nascita|born|birth|dob|classe)\b[^\n]{0,30}$", testo[max(0, p.inizio - 40):p.inizio])]
            rif = (prima[-1] if prima else min(piene, key=lambda p: abs(p.inizio - d.inizio))).data
        else:
            rif = dt.date(anno_rif, dt.date.today().month, 15)
        d.speciale["rif"] = rif
        if d.speciale.get("tipo") == "parola":
            d.data = rif + dt.timedelta(days=d.speciale["giorni"](rif))
            continue
        giorno = d.data.day
        if d.speciale["tipo"] in ("relativa", "ordinale"):
            y, mm = rif.year, rif.month + d.speciale["off"]
            y, mm = y + (mm - 1) // 12, (mm - 1) % 12 + 1
            d.data = dt.date(y, mm, min(giorno, ultimo_giorno(y, mm)))
        else:  # giorno della settimana: il mese vicino in cui quel numero cade in quel giorno
            nome = testo[d.componenti["sett"][0]:d.componenti["sett"][1]].lower().rstrip("'’")
            wd = next((i for i, x in enumerate(GIORNI) if x.replace("ì", "i") == nome.replace("ì", "i")), None)
            if wd is None:
                wd = next((i for i, x in enumerate(DAYS) if x == nome), None)
            scelto = None
            for k in (0, 1, -1, 2, -2):
                y, mm = rif.year, rif.month + k
                y, mm = y + (mm - 1) // 12, (mm - 1) % 12 + 1
                if giorno <= ultimo_giorno(y, mm) and dt.date(y, mm, giorno).weekday() == wd:
                    scelto = dt.date(y, mm, giorno)
                    break
            d.data = scelto or dt.date(rif.year, rif.month, min(giorno, ultimo_giorno(rif.year, rif.month)))
    return trovate


def _stile(campione: str, parola: str) -> str:
    if campione.isupper() and len(campione) > 1:
        return parola.upper()
    if campione[:1].isupper():
        return parola[:1].upper() + parola[1:]
    return parola


def _nome_mese(orig: str, mese: int, inglese: bool = False) -> str:
    t = orig.lower().rstrip(".")
    if t in MESI:
        nuovo = MESI[mese - 1]
    elif t in MONTHS:
        nuovo = MONTHS[mese - 1]
    elif t in MON_ABBR and (t not in ABBR or inglese) or t in ("may", "jun", "jul", "aug", "oct", "dec", "jan", "sep", "sept"):
        nuovo = MON_STD[mese - 1] if t != "sept" else ("sept" if mese == 9 else MON_STD[mese - 1])
    else:
        nuovo = ABBR_STD[mese - 1]
        if t in ("genn", "febb", "sett"):
            nuovo = {1: "genn", 2: "febb", 9: "sett"}.get(mese, nuovo)
    inglese_breve = nuovo in MON_STD and t not in MESI and t not in ABBR_STD or nuovo == "may"
    nuovo = _stile(orig.rstrip("."), nuovo)
    if inglese_breve and nuovo.lower() == "may" and t != "may":
        return nuovo  # «May» non si abbrevia: «Jan. 15» → «May 4»
    return nuovo + ("." if orig.endswith(".") else "")


def _nome_giorno(orig: str, wd: int) -> str:
    t = orig.lower().rstrip(".")
    inglese = t.startswith(("mon", "tue", "wed", "thu", "fri", "sat", "sun")) and t not in ("sab",)
    if inglese:
        nuovo = DAYS[wd] if len(t) > 4 else DAYS_ABBR[wd]
    else:
        nuovo = GIORNI[wd] if len(t) > 3 else GIORNI_ABBR[wd]
        if t.endswith("i") and not t.endswith("ì"):
            nuovo = nuovo.replace("ì", "i")
    return _stile(orig.rstrip("."), nuovo) + ("." if orig.endswith(".") else "")


def _ordinale(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _mesi(d: dt.date) -> int:
    return d.year * 12 + d.month


def _sposta_speciale(d: DataTrovata, testo: str, delta: int, inglese: bool) -> str | None:
    tipo = d.speciale.get("tipo")
    nuova = d.data + dt.timedelta(days=delta)
    c = d.componenti
    if tipo == "trimestre":
        q, anno = (nuova.month - 1) // 3 + 1, nuova.year
        pezzi = []
        for nome, (a, b) in sorted(c.items(), key=lambda kv: kv[1][0]):
            orig = testo[a:b]
            if nome in ("q", "q2"):
                val = orig[0] + str(q)
            elif nome == "r":
                val = ["I", "II", "III", "IV"][q - 1]
            elif nome == "n":
                val = str(q)
            elif nome == "w":
                lista = _Q_EN if orig.lower() in _Q_EN else _Q_IT
                val = _stile(orig, lista[q - 1])
            else:
                val = (orig[0] + f"{anno % 100:02d}") if orig[0] in "'’" else f"{anno % 100:02d}" if len(orig) == 2 else str(anno)
            pezzi.append((a, b, val))
        return _rimonta(d, testo, pezzi)
    if tipo == "lettere":
        pezzi = []
        for nome, (a, b) in sorted(c.items(), key=lambda kv: kv[1][0]):
            orig = testo[a:b]
            if nome == "g":
                val = "primo" if nuova.day == 1 and orig.lower() == "primo" else numero_in_lettere(nuova.day)
                val = _stile(orig, val)
            elif nome == "m":
                val = _nome_mese(orig, nuova.month, inglese)
            else:
                val = str(nuova.year) if orig.isdigit() else _stile(orig, numero_in_lettere(nuova.year))
            pezzi.append((a, b, val))
        return _rimonta(d, testo, pezzi)
    if tipo == "relativa":
        rif = d.speciale["rif"] + dt.timedelta(days=delta)
        off = _mesi(nuova) - _mesi(rif)
        a, b = c["rel"]
        orig = testo[a:b]
        g = str(nuova.day).zfill(2) if testo[c["g"][0]:c["g"][1]].startswith("0") else str(nuova.day)
        if off == d.speciale["off"]:
            rel = orig
        elif off in (-1, 0, 1):
            if orig.lower().startswith("mese"):
                rel = {-1: "mese scorso", 0: "mese corrente", 1: "mese prossimo"}[off]
            else:
                rel = {-1: "u.s.", 0: "corrente" if orig.lower().startswith("corrente") else "corr.", 1: "p.v."}[off]
        else:
            return f"{nuova.day} {MESI[nuova.month - 1]} {nuova.year}"
        return testo[d.inizio:c["g"][0]] + g + testo[c["g"][1]:a] + rel + testo[b:d.fine]
    if tipo == "parola":  # «ieri» → data assoluta spostata, nella lingua del testo
        if inglese:
            return f"{DAYS[nuova.weekday()].capitalize()}, {MONTHS[nuova.month - 1].capitalize()} {nuova.day}, {nuova.year}"
        return f"{GIORNI[nuova.weekday()]} {nuova.day} {MESI[nuova.month - 1]} {nuova.year}"
    if tipo == "trimestre_solo":
        orig = testo[c["m"][0]:c["m"][1]]
        q = (nuova.month - 1) // 3 + 1
        if re.fullmatch(r"[Qq][1-4]", orig):
            return orig[0] + str(q)
        parola, unita = orig.split(None, 1)
        if parola[0].isdigit():
            return ["1st", "2nd", "3rd", "4th"][q - 1] + orig[len(parola):]
        nuovo = (_PAROLE_QUARTI_EN if parola.lower() in _PAROLE_QUARTI_EN else _PAROLE_QUARTI_IT)[q - 1]
        nuovo = nuovo.capitalize() if parola[0].isupper() else nuovo
        return nuovo + orig[len(parola):]
    if tipo == "mese_solo":
        orig = testo[c["m"][0]:c["m"][1]]
        return _nome_mese(orig, nuova.month, inglese or orig.lower() in MONTHS)
    if tipo == "ordinale":
        rif = d.speciale["rif"] + dt.timedelta(days=delta)
        g = str(nuova.day) + _stile(testo[c["ord"][0]:c["ord"][1]], _ordinale(nuova.day))
        off = _mesi(nuova) - _mesi(rif)
        if "rel" in c:
            if off in (-1, 0, 1):
                parola = _stile(testo[c["rel"][0]:c["rel"][1]], {-1: "last", 0: "this", 1: "next"}[off])
                return g + testo[c["ord"][1]:c["rel"][0]] + parola + testo[c["rel"][1]:d.fine]
            return f"{g} of {MONTHS[nuova.month - 1].capitalize()} {nuova.year}"
        return g if off == 0 else f"{g} of {MONTHS[nuova.month - 1].capitalize()}"
    if tipo == "settimana":
        pezzi = []
        for nome, (a, b) in sorted(c.items(), key=lambda kv: kv[1][0]):
            orig = testo[a:b]
            if nome == "sett":
                apos = orig[-1] if orig[-1] in "'’" else ""
                base = orig.rstrip("'’")
                val = _nome_giorno(base, nuova.weekday()) + apos
                if apos and val[-2:-1] == "ì":
                    val = val[:-2] + "i" + apos
            elif nome == "g":
                val = str(nuova.day)
            else:
                val = _stile(orig, _ordinale(nuova.day))
            pezzi.append((a, b, val))
        return _rimonta(d, testo, pezzi)
    if tipo == "mese_inizio":  # «marzo-aprile 2025»: se l'anno finto cambia, il primo mese lo scrive
        fine = d.speciale["fine"].data + dt.timedelta(days=delta)
        nuova = nuova.replace(day=15)
        val = _nome_mese(testo[c["m"][0]:c["m"][1]], nuova.month, inglese)
        return val if nuova.year == fine.year else f"{val} {nuova.year}"
    if tipo == "inizio":  # «dal 3 al 10 marzo»: se i mesi finti sono diversi, il primo giorno prende il suo mese
        fine = d.speciale["fine"].data + dt.timedelta(days=delta)
        a, b = c["g1"]
        g = str(nuova.day)
        if (nuova.year, nuova.month) == (fine.year, fine.month):
            return g + (_stile(testo[c["o1"][0]:c["o1"][1]], _ordinale(nuova.day)) if "o1" in c else "")
        mese = (MONTHS[nuova.month - 1].capitalize() if inglese else MESI[nuova.month - 1])
        anno = f" {nuova.year}" if nuova.year != fine.year else ""
        return f"{g}{_ordinale(nuova.day) if 'o1' in c else ''} {mese}{anno}"
    if tipo == "fine":  # «March 3–10»: se i mesi finti sono diversi, il secondo giorno prende il suo mese
        ini = d.speciale["inizio"].data + dt.timedelta(days=delta)
        g = str(nuova.day) + (_stile(testo[c["o2"][0]:c["o2"][1]], _ordinale(nuova.day)) if "o2" in c else "")
        if (nuova.year, nuova.month) != (ini.year, ini.month):
            g = f"{MONTHS[nuova.month - 1].capitalize() if inglese else MESI[nuova.month - 1]} {g}"
        if "a" in c:
            fine_giorno = c["o2"][1] if "o2" in c else c["g2"][1]
            g += testo[fine_giorno:c["a"][0]] + str(nuova.year)
        return g
    return None


def _rimonta(d: DataTrovata, testo: str, pezzi: list) -> str:
    out, cur = [], d.inizio
    for a, b, v in sorted(pezzi):
        out += [testo[cur:a], v]
        cur = b
    out.append(testo[cur:d.fine])
    return "".join(out)


def sposta(d: DataTrovata, testo: str, delta: int, inglese: bool = False, zeri_come_originale: bool = False) -> str:
    """Restituisce il testo della data spostata di delta giorni, nello stesso formato."""
    if d.speciale.get("tipo") and d.speciale.get("tipo") != "anno_da_intervallo":
        r = _sposta_speciale(d, testo, delta, inglese)
        if r is not None:
            return r
    if d.granularita in ("giorno", "giorno_senza_anno"):
        nuova = d.data + dt.timedelta(days=delta)
    elif d.granularita == "mese":
        nuova = d.data + dt.timedelta(days=delta)
        nuova = nuova.replace(day=15)
    else:
        nuova = (d.data + dt.timedelta(days=delta)).replace(month=7, day=1)
    c = d.componenti
    pezzi = []
    for nome, (a, b) in sorted(c.items(), key=lambda kv: kv[1][0]):
        orig = testo[a:b]
        if nome == "g":
            numerica = "m" in c and testo[c["m"][0]:c["m"][1]].isdigit()
            m_orig = testo[c["m"][0]:c["m"][1]] if "m" in c else ""
            # zeri come nell'originale («2/10/2025» resta senza zeri: non deve diventare uguale a «02/10/2025»);
            # nelle forme corte senza anno («28/8») due cifre servono a riconoscerle al ritorno
            pad = orig.startswith("0") or (not zeri_come_originale and numerica and (len(orig) == 2 or len(m_orig) == 2))
            val = str(nuova.day).zfill(2) if pad else str(nuova.day)
        elif nome == "ord":
            if orig in ("°", "º"):
                val = orig if nuova.day == 1 else ""
            else:
                val = _stile(orig, _ordinale(nuova.day))
        elif nome == "m":
            if orig.isdigit():
                g_orig = testo[c["g"][0]:c["g"][1]] if "g" in c else ""
                pad = orig.startswith("0") or (not zeri_come_originale and (len(orig) == 2 or len(g_orig) == 2))
                val = str(nuova.month).zfill(2) if pad else str(nuova.month)
            else:
                val = _nome_mese(orig, nuova.month, inglese)
        elif nome == "a":
            if orig[0] in "'’":
                val = orig[0] + f"{nuova.year % 100:02d}"
            elif len(orig) == 2:
                val = f"{nuova.year % 100:02d}"
            else:
                val = str(nuova.year)
        elif nome == "sett":
            val = _nome_giorno(orig, nuova.weekday())
        else:
            val = orig
        pezzi.append((a, b, val))
    out, cur = [], d.inizio
    for a, b, v in pezzi:
        out.append(testo[cur:a])
        out.append(v)
        cur = b
    out.append(testo[cur:d.fine])
    return "".join(out)


def scegli_delta(rng, settimane_min: int = 26, settimane_max: int = 156, conserva_settimana: bool = True) -> int:
    """Spostamento all'indietro fra circa 6 mesi e 3 anni."""
    # Mai vicino a un numero intero di anni: giorno e mese senza anno («02/03», «April») resterebbero quasi uguali.
    while True:
        giorni = 7 * rng.randint(settimane_min, settimane_max) if conserva_settimana else rng.randint(settimane_min * 7, settimane_max * 7)
        resto = giorni % 365.25
        if 35 <= resto <= 365.25 - 35:
            return -giorni


def formato_lungo(d: dt.date) -> str:
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"


def ultimo_giorno(anno: int, mese: int) -> int:
    return calendar.monthrange(anno, mese)[1]
